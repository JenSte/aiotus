import base64
import io
import os
from typing import BinaryIO, Dict

import aiohttp
import yarl

from . import types
from .log import logger

# The version of the tus protocol we implement.
TUS_PROTOCOL_VERSION = "1.0.0"


async def create(
    session: aiohttp.ClientSession,
    url: yarl.URL,
    file: BinaryIO,
    metadata: Dict[str, str],
    ssl: types.SSLArgument = None,
) -> yarl.URL:
    """Create an upload.

    :param session: HTTP session to use for connections.
    :param location: The creation endpoint of the server.
    :param file: The file object to upload.
    :param metadata: Additional metadata for the upload.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :return: The URL to upload the data to.
    """

    total_size = file.seek(0, io.SEEK_END)

    headers = {"Tus-Resumable": TUS_PROTOCOL_VERSION, "Upload-Length": str(total_size)}

    if metadata:
        # Check metadata keys before we proceed.
        for k in metadata:
            if not k.isascii():
                raise ValueError("Metadata keys must only contain ASCII characters.")

            if " " in k:
                raise ValueError("Metadata keys must not contain spaces.")

            if "," in k:
                raise ValueError("Metadata keys must not contain commas.")

        def encode_value(value: str) -> str:
            encoded_bytes = base64.b64encode(value.encode())
            encoded_string = encoded_bytes.decode()
            return encoded_string

        pairs = [f"{k} {encode_value(v)}" for k, v in metadata.items()]
        headers["Upload-Metadata"] = ", ".join(pairs)

    logger.debug(f"Creating upload...")
    async with await session.post(url, headers=headers, ssl=ssl) as response:
        if response.status != 201:
            raise aiohttp.ClientResponseError(
                response.request_info,
                response.history,
                status=response.status,
                message="Wrong status code, expected 201.",
                headers=response.headers,
            )

        if "Location" not in response.headers:
            raise RuntimeError('Upload created, but no "Location" header in response.')

        return yarl.URL(response.headers["Location"])


async def offset(
    session: aiohttp.ClientSession, location: yarl.URL, ssl: types.SSLArgument = None
) -> int:
    """Get the number of uploaded bytes.

    :param session: HTTP session to use for connections.
    :param location: The upload endpoint to query.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :return: The number of bytes that are already on the server.
    """

    headers = {"Tus-Resumable": TUS_PROTOCOL_VERSION}

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


async def upload_remaining(
    session: aiohttp.ClientSession,
    location: yarl.URL,
    file: BinaryIO,
    current_offset: int,
    ssl: types.SSLArgument = None,
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
        "Tus-Resumable": TUS_PROTOCOL_VERSION,
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
    ssl: types.SSLArgument = None,
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
