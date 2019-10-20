import asyncio
import dataclasses
import typing

import aiohttp
import tenacity  # type: ignore
import yarl

from . import lowlevel
from .log import logger


@dataclasses.dataclass
class UploadConfiguration:
    """Class to hold the configuration for the 'upload()' function."""

    # Number of retry attempts to do when the communication fails.
    retry_attempts: int = 10

    # Maximum time between retries, in seconds.
    #
    # Exponential backoff is used in case of communication errors,
    # but the time between retries is caped by this value.
    max_retry_period_seconds: float = 60.0


def _make_log_before_function(s: str) -> typing.Callable[[str], None]:
    def log(retry_state: tenacity.RetryCallState) -> None:

        if retry_state.attempt_number > 1:
            logger.info(
                f"Trying {s} again, attempt number {retry_state.attempt_number}..."
            )

    return log


def _make_log_before_sleep_function(s: str) -> typing.Callable[[str], None]:
    def log(retry_state: tenacity.RetryCallState) -> None:
        duration = retry_state.next_action.sleep
        if retry_state.outcome.failed:
            value = retry_state.outcome.exception()
        else:
            value = retry_state.outcome.result()
        logger.warning(
            f"{s.capitalize()} failed, retrying in {duration:.0f} second(s): {value}"
        )

    return log


async def upload(
    endpoint: str,
    file: typing.BinaryIO,
    metadata: typing.Optional[typing.Dict[str, str]] = None,
    client_session: typing.Optional[aiohttp.ClientSession] = None,
    config: UploadConfiguration = UploadConfiguration(),
) -> typing.Optional[yarl.URL]:
    """Upload a file to a tus server.

    In case of a communication error, this function retries the upload.

    :param endpoint: The creation endpoint of the server.
    :param file: The file to upload.
    :param metadata: Additional metadata for the upload.
    :param config: Settings to customize the upload.
    :return: The location where the file was uploaded to (if the upload succeeded).
    """

    url = yarl.URL(endpoint)

    if metadata is None:
        metadata = {}

    retrying_create = tenacity.AsyncRetrying(
        retry=tenacity.retry_if_exception_type(aiohttp.ClientError),
        stop=tenacity.stop_after_attempt(config.retry_attempts),
        wait=tenacity.wait_exponential(max=config.max_retry_period_seconds),
        before=_make_log_before_function("upload creation"),
        before_sleep=_make_log_before_sleep_function("upload creation"),
    )

    retrying_upload_file = tenacity.AsyncRetrying(
        retry=tenacity.retry_if_exception_type(aiohttp.ClientError),
        stop=tenacity.stop_after_attempt(config.retry_attempts),
        wait=tenacity.wait_exponential(max=config.max_retry_period_seconds),
        before=_make_log_before_function("upload"),
        before_sleep=_make_log_before_sleep_function("upload"),
    )

    try:
        if client_session is None:
            client_session = aiohttp.ClientSession()

        async with client_session:
            location: yarl.URL
            location = await retrying_create.call(
                lowlevel.create, client_session, url, file, metadata
            )
            if not location.is_absolute():
                location = url / location.path

            await retrying_upload_file.call(
                lowlevel.upload_buffer, client_session, location, file
            )

            return location
    except asyncio.CancelledError:  # pragma: no cover
        # Up until python 3.7, CancelledError is not derived from BaseException.
        raise
    except tenacity.RetryError as e:
        logger.error(
            f"Unable to upload file, even after retrying: {e.last_attempt.exception()}"
        )
    except Exception as e:
        logger.error(f"Unable to upload file: {e}")

    return None
