"""
Implementation of the
`creation extension <https://tus.io/protocols/resumable-upload.html#creation>`_
to the tus protocol.
"""

import asyncio
import base64
import io
from typing import BinaryIO, Mapping, Optional

import aiohttp
import yarl

from . import common
from .log import logger


def _check_metadata_keys(metadata: common.Metadata) -> None:
    """Check if the metadata keys are valid.

    Raises a 'ValueError' exception if a key is invalid.
    """

    for k in metadata:
        if not k.isascii():
            raise ValueError("Metadata keys must only contain ASCII characters.")

        if " " in k:
            raise ValueError("Metadata keys must not contain spaces.")

        if "," in k:
            raise ValueError("Metadata keys must not contain commas.")


async def create(
    session: aiohttp.ClientSession,
    url: yarl.URL,
    file: Optional[BinaryIO],
    metadata: common.Metadata,
    ssl: common.SSLArgument = None,
    headers: Optional[Mapping[str, str]] = None,
) -> yarl.URL:
    """Create an upload.

    :param session: HTTP session to use for connections.
    :param url: The creation endpoint of the server.
    :param file: The file object to upload.
        Used to determine the length of data to be uploaded. If not given, the
        corresponding HTTP header is not included in the request.
    :param metadata: Additional metadata for the upload.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :param headers: Optional headers used in the request.
    :return: The URL to upload the data to.
    """

    tus_headers = dict(headers or {})
    tus_headers["Tus-Resumable"] = common.TUS_PROTOCOL_VERSION

    if file is not None:
        loop = asyncio.get_event_loop()
        total_size = await loop.run_in_executor(None, file.seek, 0, io.SEEK_END)
        tus_headers["Upload-Length"] = str(total_size)

    if metadata:
        _check_metadata_keys(metadata)

        def encode_value(value: Optional[bytes]) -> str:
            if value is None:
                return ""

            encoded_bytes = base64.b64encode(value)
            encoded_string = encoded_bytes.decode()
            return " " + encoded_string

        pairs = [f"{k}{encode_value(v)}" for k, v in metadata.items()]
        tus_headers["Upload-Metadata"] = ",".join(pairs)

    logger.debug("Creating upload...")
    async with await session.post(url, headers=tus_headers, ssl=ssl) as response:
        if response.status != 201:
            raise common.ProtocolError(
                f"Wrong status code {response.status}, expected 201."
            )

        if "Location" not in response.headers:
            raise RuntimeError('Upload created, but no "Location" header in response.')

        return yarl.URL(response.headers["Location"])
