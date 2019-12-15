import base64
import io
import os
from typing import BinaryIO

import aiohttp
import yarl

from . import common
from .log import logger


async def offset(
    session: aiohttp.ClientSession, location: yarl.URL, ssl: common.SSLArgument = None
) -> int:
    """Get the number of uploaded bytes.

    :param session: HTTP session to use for connections.
    :param location: The upload endpoint to query.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :return: The number of bytes that are already on the server.
    """

    headers = {"Tus-Resumable": common.TUS_PROTOCOL_VERSION}

    logger.debug(f'Getting offset of "{location}"...')
    async with await session.head(location, headers=headers, ssl=ssl) as response:
        response.raise_for_status()

        if "Upload-Offset" not in response.headers:
            raise RuntimeError(
                f"HEAD request succeeded for {location}, "
                'but no "Upload-Offset" header in response.'
            )

        try:
            offset_header = response.headers["Upload-Offset"]
            current_offset = int(offset_header)
            if current_offset < 0:
                raise RuntimeError()

            return current_offset
        except Exception:
            raise RuntimeError(
                f'Unable to convert "Upload-Offset" header '
                f'"{offset_header}" to a positive integer.'
            )


def parse_metadata(header: str) -> common.Metadata:
    """Split and decode the input into a metadata dictionary."""

    header = header.strip()
    if not header:
        return {}

    md: common.Metadata = {}
    for pair in header.split(","):
        kv = pair.split()
        if len(kv) == 1:
            md[kv[0]] = None
        elif len(kv) == 2:
            md[kv[0]] = base64.b64decode(kv[1], validate=True)
        else:
            raise ValueError("Key/Value pair consists of more than two elements.")

    return md


async def metadata(
    session: aiohttp.ClientSession, location: yarl.URL, ssl: common.SSLArgument = None
) -> common.Metadata:
    """Get the metadata associated with an upload.

    :param session: HTTP session to use for connections.
    :param location: The upload endpoint to query.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :return: The metadata of the upload.
    """

    headers = {"Tus-Resumable": common.TUS_PROTOCOL_VERSION}

    logger.debug(f'Getting metadata of "{location}"...')
    async with await session.head(location, headers=headers, ssl=ssl) as response:
        response.raise_for_status()

        if "Upload-Metadata" not in response.headers:
            return {}

        try:
            return parse_metadata(response.headers["Upload-Metadata"])
        except Exception as e:
            raise common.ProtocolError(f"Unable to parse metadata: {e}")


async def upload_remaining(
    session: aiohttp.ClientSession,
    location: yarl.URL,
    file: BinaryIO,
    current_offset: int,
    ssl: common.SSLArgument = None,
) -> None:
    """Upload remaining data to the server.

    :param session: HTTP session to use for connections.
    :param location: The endpoint to upload to.
    :param file: The file object to upload.
    :param current_offset: The number of bytes already uploaded.
    :param ssl: SSL validation mode, passed on to aiohttp.
    """

    total_size = file.seek(0, io.SEEK_END)
    outstanding = total_size - current_offset

    file.seek(current_offset, io.SEEK_SET)

    headers = {
        "Tus-Resumable": common.TUS_PROTOCOL_VERSION,
        "Upload-Offset": str(current_offset),
        "Content-Length": str(outstanding),
        "Content-Type": "application/offset+octet-stream",
    }

    logger.debug(f'Uploading {outstanding} bytes to "{location}"...')
    async with await session.patch(
        location, headers=headers, data=file, ssl=ssl
    ) as response:
        response.raise_for_status()


async def upload_buffer(
    session: aiohttp.ClientSession,
    location: yarl.URL,
    file: BinaryIO,
    ssl: common.SSLArgument = None,
) -> None:
    """Upload data to the server.

    :param session: HTTP session to use for connections.
    :param location: The endpoint to upload to.
    :param file: The file object to upload.
    :param ssl: SSL validation mode, passed on to aiohttp.
    """

    current_offset = await offset(session, location, ssl=ssl)

    logger.debug(f'Resuming upload of "{location}" at offset {current_offset}..."')

    # We reopen the file, as the streaming upload in 'upload_remaining()'
    # closes the file, and we may have to reuse the origin file if we resume
    # the upload later.

    if hasattr(file, "getbuffer"):
        file = io.BytesIO(file.getbuffer())  # type: ignore
        await upload_remaining(session, location, file, current_offset, ssl=ssl)
    else:
        fd = os.dup(file.fileno())
        with os.fdopen(fd, "rb") as file:
            await upload_remaining(session, location, file, current_offset, ssl=ssl)
