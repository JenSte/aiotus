"""High-level functions that do retrying in case of communication errors."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
from typing import TYPE_CHECKING

import aiohttp
import tenacity
import yarl

from . import common, core, creation
from .log import logger

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Iterable, Mapping
    from contextlib import AbstractAsyncContextManager
    from typing import BinaryIO


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

    ssl: common.SSLArgument = True
    """
    'ssl' argument passed on to the aiohttp calls.

    This can be a boolean, or an instance of ssl.SSLContext, see
    the `aiohttp documentation
    <https://docs.aiohttp.org/en/stable/client_advanced.html#ssl-control-for-tcp-sockets>`_
    for the different meanings.
    """


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


def _sanitize_metadata(metadata: common.Metadata | None) -> common.Metadata:
    """Make sure the given optional metadata object is valid."""
    if metadata is None:
        metadata = {}

    # Try to encode the metadata once here, as this function is called outside
    # of any code that does retries, so that invalid arguments are caught early
    # and the exception is not swallowed.
    creation.encode_metadata(metadata)

    return metadata


async def upload(  # noqa: PLR0913
    endpoint: str | yarl.URL,
    file: BinaryIO,
    metadata: common.Metadata | None = None,
    client_session: aiohttp.ClientSession | None = None,
    config: RetryConfiguration | None = None,
    headers: Mapping[str, str] | None = None,
    chunksize: int = 4 * 1024 * 1024,
) -> yarl.URL | None:
    """Upload a file to a tus server.

    This function creates an upload on the server and then uploads
    the data to that location.

    In case of a communication error, this function retries the upload.

    :param endpoint: The creation endpoint of the server.
    :param file: The file to upload.
    :param metadata: Additional metadata for the upload.
    :param client_session: An aiohttp ClientSession to use.
    :param config: Settings to customize the retry behaviour.
    :param headers: Optional headers used in the request.
    :param chunksize: The size of individual chunks to upload at a time.
    :return: The location where the file was uploaded to (if the upload succeeded).
    """
    if config is None:
        config = RetryConfiguration()

    url = yarl.URL(endpoint)
    metadata = _sanitize_metadata(metadata)

    retrying_create = _make_retrying("upload creation", config)
    retrying_upload_file = _make_retrying("upload", config)

    try:
        ctx: aiohttp.ClientSession | AbstractAsyncContextManager[aiohttp.ClientSession]
        if client_session is None:
            ctx = aiohttp.ClientSession()
        else:
            ctx = contextlib.nullcontext(client_session)

        async with ctx as session:
            async for attempt in retrying_create:
                with attempt:
                    location = await creation.create(
                        session,
                        url,
                        file,
                        metadata,
                        ssl=config.ssl,
                        headers=headers,
                    )

            logger.debug(f"Upload created, upload URL is '{location}'.")
            if not location.is_absolute():
                location = url / location.path
                logger.debug(f"Upload URL was relative, changed to '{location}'.")

            async for attempt in retrying_upload_file:
                with attempt:
                    await core.upload_buffer(
                        session,
                        location,
                        file,
                        ssl=config.ssl,
                        chunksize=chunksize,
                        headers=headers,
                    )

            return location
    except tenacity.RetryError as e:
        logger.error(
            f"Unable to upload file, even after retrying: {e.last_attempt.exception()}"
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Unable to upload file: {e}")

    return None


async def metadata(
    endpoint: str | yarl.URL,
    client_session: aiohttp.ClientSession | None = None,
    config: RetryConfiguration | None = None,
    headers: Mapping[str, str] | None = None,
) -> common.Metadata | None:
    """Read back the metadata of an upload.

    See :data:`aiotus.Metadata` for details on how metadata is handled in the
    tus protocol.

    In case of a communication error, this function retries.

    :param endpoint: The location of the upload.
    :param client_session: An aiohttp ClientSession to use.
    :param config: Settings to customize the retry behaviour.
    :param headers: Optional headers used in the request.
    :return: The metadata associated with the upload.
    """
    if config is None:
        config = RetryConfiguration()

    url = yarl.URL(endpoint)

    retrying_metadata = _make_retrying("query metadata", config)

    try:
        ctx: aiohttp.ClientSession | AbstractAsyncContextManager[aiohttp.ClientSession]
        if client_session is None:
            ctx = aiohttp.ClientSession()
        else:
            ctx = contextlib.nullcontext(client_session)

        async with ctx as session:
            async for attempt in retrying_metadata:
                with attempt:
                    return await core.metadata(
                        session, url, ssl=config.ssl, headers=headers
                    )
    except tenacity.RetryError as e:
        logger.error(
            f"Unable to get metadata, even after retrying: {e.last_attempt.exception()}"
        )

    return None


async def _upload_partial(  # noqa: PLR0913
    semaphore: asyncio.Semaphore,
    endpoint: str | yarl.URL,
    file: BinaryIO,
    client_session: aiohttp.ClientSession | None,
    config: RetryConfiguration,
    headers: Mapping[str, str] | None,
    chunksize: int,
) -> str:
    """Upload a single part of an upload with the "concatenation" extension.

    Helper function for 'upload_multiple()'.
    """
    tus_headers = dict(headers or {})
    tus_headers["Upload-Concat"] = "partial"

    async with semaphore:
        url = await upload(
            endpoint, file, None, client_session, config, tus_headers, chunksize
        )

    if url is None:
        msg = "Unable to upload part."
        raise RuntimeError(msg)

    return url.path


async def upload_multiple(  # noqa: C901 PLR0913
    endpoint: str | yarl.URL,
    files: Iterable[BinaryIO],
    metadata: common.Metadata | None = None,
    client_session: aiohttp.ClientSession | None = None,
    config: RetryConfiguration | None = None,
    headers: Mapping[str, str] | None = None,
    chunksize: int = 4 * 1024 * 1024,
    parallel_uploads: int = 3,
) -> yarl.URL | None:
    """Upload multiple files using the "concatenation" extension.

    Upload multiple files and then use the "concatenation" protocol extension
    to combine the parts on the server-side.

    :param endpoint: The creation endpoint of the server.
    :param files: The files to upload.
    :param metadata: Additional metadata for the final upload.
    :param client_session: An aiohttp ClientSession to use.
    :param config: Settings to customize the retry behaviour.
    :param headers: Optional headers used in the request.
    :param chunksize: The size of individual chunks to upload at a time.
    :param parallel_uploads: The number of parallel uploads to do concurrently.
    :return: The location of the final (concatenated) file on the server.
    :raises RuntimeError: If the server does not support the "concatenation" extension.
    """
    if config is None:
        config = RetryConfiguration()

    url = yarl.URL(endpoint)
    metadata = _sanitize_metadata(metadata)

    retrying_config = _make_retrying("query configuration", config)
    retrying_create = _make_retrying("upload creation", config)

    try:
        ctx: aiohttp.ClientSession | AbstractAsyncContextManager[aiohttp.ClientSession]
        if client_session is None:
            ctx = aiohttp.ClientSession()
        else:
            ctx = contextlib.nullcontext(client_session)

        async with ctx as session:
            #
            # Check if the server supports the "concatenation" extension.
            #
            async for attempt in retrying_config:
                with attempt:
                    server_config = await core.configuration(
                        session, url, ssl=config.ssl, headers=headers
                    )

            if "concatenation" not in server_config.protocol_extensions:
                msg = 'Server does not support the "concatenation" extension.'
                raise RuntimeError(msg)  # noqa: TRY301

            #
            # Upload the individual parts.
            #

            # Used to limit the number of coroutines that perform uploads in parallel.
            semaphore = asyncio.Semaphore(parallel_uploads)

            coros = [
                _upload_partial(
                    semaphore, endpoint, f, session, config, headers, chunksize
                )
                for f in files
            ]
            tasks = [asyncio.create_task(c) for c in coros]

            try:
                paths = await asyncio.gather(*tasks)
            except Exception as e:
                logger.info("Cancelling other uploads...")
                for t in tasks:
                    if not t.done():
                        t.cancel()

                msg = f"Upload of a part failed: {e}"
                raise RuntimeError(msg) from e

            concat_header = "final;" + " ".join(paths)

            #
            # Do the final concatenation.
            #
            final_headers = dict(headers or {})
            final_headers.update({"Upload-Concat": concat_header})

            async for attempt in retrying_create:  # pragma: no branch
                with attempt:
                    return await creation.create(
                        session,
                        url,
                        None,
                        metadata,
                        ssl=config.ssl,
                        headers=final_headers,
                    )
    except tenacity.RetryError as e:
        logger.error(
            f"Unable to upload files, even after retrying: {e.last_attempt.exception()}"
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Unable to upload files: {e}")

    return None
