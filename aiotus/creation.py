"""Implementation of the creation extension.

The
`creation extension <https://tus.io/protocols/resumable-upload.html#creation>`_
defines how to reserve space on the server for uploading data to.
"""

from __future__ import annotations

import asyncio
import base64
import io
from typing import TYPE_CHECKING, BinaryIO

import yarl

from . import common
from .log import logger

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

    import aiohttp


def _check_metadata_keys(metadata: common.Metadata) -> None:
    """Check if the metadata keys are valid.

    Raises a 'ValueError' exception if a key is invalid.
    """
    for k in metadata:
        if not k.isascii():
            msg = "Metadata keys must only contain ASCII characters."
            raise ValueError(msg)

        if " " in k:
            msg = "Metadata keys must not contain spaces."
            raise ValueError(msg)

        if "," in k:
            msg = "Metadata keys must not contain commas."
            raise ValueError(msg)


def encode_metadata(metadata: common.Metadata) -> str:
    """Encode the metadata to the value of the metadata header.

    :param metadata: The metadata to encode.
    :return: The value for the "Upload-Metadata" header.
    """
    _check_metadata_keys(metadata)

    def encode_value(value: bytes | None) -> str:
        if value is None:
            return ""

        encoded_bytes = base64.b64encode(value)
        encoded_string = encoded_bytes.decode()
        return " " + encoded_string

    pairs = [f"{k}{encode_value(v)}" for k, v in metadata.items()]
    return ",".join(pairs)


async def create(  # noqa: PLR0913
    session: aiohttp.ClientSession,
    url: yarl.URL,
    file: BinaryIO | None,
    metadata: common.Metadata,
    ssl: common.SSLArgument = True,  # noqa: FBT002
    headers: Mapping[str, str] | None = None,
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
    :raises common.ProtocolError: When the server does not comply to the tus protocol.
    """
    tus_headers = dict(headers or {})
    tus_headers["Tus-Resumable"] = common.TUS_PROTOCOL_VERSION

    if file is not None:
        total_size = await asyncio.to_thread(file.seek, 0, io.SEEK_END)
        tus_headers["Upload-Length"] = str(total_size)

    if metadata_header := encode_metadata(metadata):
        tus_headers["Upload-Metadata"] = metadata_header

    logger.debug("Creating upload...")
    async with await session.post(url, headers=tus_headers, ssl=ssl) as response:
        response.raise_for_status()
        if response.status != 201:  # noqa: PLR2004
            msg = f"Wrong status code {response.status}, expected 201."
            raise common.ProtocolError(msg)

        if "Location" not in response.headers:
            msg = 'Upload created, but no "Location" header in response.'
            raise common.ProtocolError(msg)

        return yarl.URL(response.headers["Location"])
