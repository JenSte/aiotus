import base64
import io
from typing import BinaryIO, Dict

import aiohttp
import yarl

from . import common
from .log import logger


async def create(
    session: aiohttp.ClientSession,
    url: yarl.URL,
    file: BinaryIO,
    metadata: Dict[str, str],
    ssl: common.SSLArgument = None,
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

    headers = {
        "Tus-Resumable": common.TUS_PROTOCOL_VERSION,
        "Upload-Length": str(total_size),
    }

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
