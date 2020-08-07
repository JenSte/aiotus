import asyncio
import contextlib
import dataclasses
from typing import (
    AsyncContextManager,
    AsyncIterator,
    BinaryIO,
    Callable,
    Mapping,
    Optional,
    Union,
)

import aiohttp
import tenacity  # type: ignore
import yarl

from . import common, core, creation
from .log import logger


@contextlib.asynccontextmanager
async def asyncnullcontext(
    enter_result: aiohttp.ClientSession,
) -> AsyncIterator[aiohttp.ClientSession]:
    """Asynchronous version of 'contextlib.nullcontext()'.

    (Typed to 'aiohttp.ClientSession', as I could not get 'AsyncIterator[]' work with
    generic 'TypeVar's.)
    """
    yield enter_result


@dataclasses.dataclass
class RetryConfiguration:
    """Class to hold settings for the functions of this module."""

    retry_attempts: int = 10
    """
    Number of retry attempts to do when the communication fails.
    """

    max_retry_period_seconds: float = 60.0
    """
    Maximum time between retries, in seconds.

    Exponential backoff is used in case of communication errors,
    but the time between retries is caped by this value.
    """

    ssl: common.SSLArgument = None
    """
    'ssl' argument passed on to the aiohttp calls.

    This can be None, False, or an instance of ssl.SSLContext, see
    the `aiohttp documentation
    <https://docs.aiohttp.org/en/stable/client_advanced.html#ssl-control-for-tcp-sockets>`_
    for the different meanings.
    """  # noqa: E501


def _make_log_before_function(s: str) -> Callable[[tenacity.RetryCallState], None]:
    """Create a function used to log before a retry attempt."""

    def log(retry_state: tenacity.RetryCallState) -> None:

        if retry_state.attempt_number > 1:
            logger.info(
                f"Trying {s} again, attempt number {retry_state.attempt_number}..."
            )

    return log


def _make_log_before_sleep_function(
    s: str,
) -> Callable[[tenacity.RetryCallState], None]:
    """Create a function used when a call made through tenacity fails."""

    def log(retry_state: tenacity.RetryCallState) -> None:
        if (retry_state.next_action is not None) and (retry_state.outcome is not None):
            duration = retry_state.next_action.sleep
            if retry_state.outcome.failed:
                value = retry_state.outcome.exception()
            else:
                value = retry_state.outcome.result()
            logger.warning(
                f"{s.capitalize()} failed, "
                f"retrying in {duration:.0f} second(s): {value}"
            )

    return log


def _make_retrying(s: str, config: RetryConfiguration) -> tenacity.AsyncRetrying:
    """Create a tenacity retry object."""

    return tenacity.AsyncRetrying(
        retry=tenacity.retry_if_exception_type(aiohttp.ClientError),
        stop=tenacity.stop_after_attempt(config.retry_attempts),
        wait=tenacity.wait_exponential(max=config.max_retry_period_seconds),
        before=_make_log_before_function(s),
        before_sleep=_make_log_before_sleep_function(s),
    )


async def upload(
    endpoint: Union[str, yarl.URL],
    file: BinaryIO,
    metadata: Optional[common.Metadata] = None,
    client_session: Optional[aiohttp.ClientSession] = None,
    config: RetryConfiguration = RetryConfiguration(),
    headers: Optional[Mapping[str, str]] = None,
) -> Optional[yarl.URL]:
    """Upload a file to a tus server.

    In case of a communication error, this function retries the upload.

    :param endpoint: The creation endpoint of the server.
    :param file: The file to upload.
    :param metadata: Additional metadata for the upload.
    :param client_session: An aiohttp ClientSession to use.
    :param config: Settings to customize the retry behaviour.
    :param headers: Optional headers used in the request.
    :return: The location where the file was uploaded to (if the upload succeeded).
    """

    url = yarl.URL(endpoint)

    if metadata is None:
        metadata = {}

    retrying_create = _make_retrying("upload creation", config)
    retrying_upload_file = _make_retrying("upload", config)

    try:
        ctx: Union[aiohttp.ClientSession, AsyncContextManager[aiohttp.ClientSession]]
        if client_session is None:
            ctx = aiohttp.ClientSession()
        else:
            ctx = asyncnullcontext(client_session)

        async with ctx as session:
            location: yarl.URL
            location = await retrying_create.call(
                creation.create,
                session,
                url,
                file,
                metadata,
                ssl=config.ssl,
                headers=headers,
            )
            if not location.is_absolute():
                location = url / location.path

            await retrying_upload_file.call(
                core.upload_buffer,
                session,
                location,
                file,
                ssl=config.ssl,
                headers=headers,
            )

            return location
    except asyncio.CancelledError:  # pragma: no cover
        raise
    except tenacity.RetryError as e:
        logger.error(
            f"Unable to upload file, even after retrying: {e.last_attempt.exception()}"
        )
    except Exception as e:
        logger.error(f"Unable to upload file: {e}")

    return None


async def metadata(
    endpoint: Union[str, yarl.URL],
    client_session: Optional[aiohttp.ClientSession] = None,
    config: RetryConfiguration = RetryConfiguration(),
    headers: Optional[Mapping[str, str]] = None,
) -> Optional[common.Metadata]:
    """Retrieve the metadata of an upload.

    In case of a communication error, this function retries.

    :param endpoint: The location of the upload.
    :param client_session: An aiohttp ClientSession to use.
    :param config: Settings to customize the retry behaviour.
    :param headers: Optional headers used in the request.
    :return: The metadata associated with the upload.
    """

    if isinstance(endpoint, str):
        url = yarl.URL(endpoint)
    else:
        url = endpoint

    retrying_metadata = _make_retrying("query metadata", config)

    try:
        ctx: Union[aiohttp.ClientSession, AsyncContextManager[aiohttp.ClientSession]]
        if client_session is None:
            ctx = aiohttp.ClientSession()
        else:
            ctx = asyncnullcontext(client_session)

        async with ctx as session:
            md: common.Metadata
            md = await retrying_metadata.call(
                core.metadata, session, url, ssl=config.ssl, headers=headers
            )

            return md
    except asyncio.CancelledError:  # pragma: no cover
        raise
    except tenacity.RetryError as e:
        logger.error(
            f"Unable to get metadata, even after retrying: {e.last_attempt.exception()}"
        )

    return None
