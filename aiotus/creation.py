"""
Implementation of the
`creation extension <https://tus.io/protocols/resumable-upload.html#creation>`_
to the tus protocol.
"""

import asyncio
import base64
import io
from typing import BinaryIO, Optional

import aiohttp
import yarl

from . import common
from .log import logger


async def create(
    session: aiohttp.ClientSession,
    url: yarl.URL,
    file: BinaryIO,
    metadata: common.Metadata,
    ssl: common.SSLArgument = None,
) -> yarl.URL:
    """Create an upload.

    :param session: HTTP session to use for connections.
    :param url: The creation endpoint of the server.
    :param file: The file object to upload.
    :param metadata: Additional metadata for the upload.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :return: The URL to upload the data to.
    """

    loop = asyncio.get_event_loop()
    total_size = await loop.run_in_executor(None, file.seek, 0, io.SEEK_END)

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

        def encode_value(value: Optional[bytes]) -> str:
            if value is None:
                return ""

            encoded_bytes = base64.b64encode(value)
            encoded_string = encoded_bytes.decode()
            return " " + encoded_string

        pairs = [f"{k}{encode_value(v)}" for k, v in metadata.items()]
        headers["Upload-Metadata"] = ", ".join(pairs)

    logger.debug(f"Creating upload...")
    async with await session.post(url, headers=headers, ssl=ssl) as response:
        if response.status != 201:
            raise common.ProtocolError(
                f"Wrong status code {response.status}, expected 201."
            )

        if "Location" not in response.headers:
            raise RuntimeError('Upload created, but no "Location" header in response.')

        return yarl.URL(response.headers["Location"])
