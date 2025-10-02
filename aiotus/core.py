"""Implementation of the core protocol.

The
`core tus protocol <https://tus.io/protocols/resumable-upload.html#core-protocol>`_
defines how the data upload is handled.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import io
from typing import TYPE_CHECKING

from . import common
from .log import logger

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping
    from typing import BinaryIO

    import aiohttp
    import multidict
    import yarl


@dataclasses.dataclass
class ServerConfiguration:
    """Class to hold the server's configuration."""

    protocol_versions: list[str]
    """
    List of protocol versions supported by the server, sorted by the server's
    preference.
    """

    max_size: int | None
    """
    The maximum allowed file size (in bytes), if reported by the server.
    """

    protocol_extensions: list[str]
    """
    The protocol extensions supported by the server.
    """


def _parse_positive_integer_header(
    headers: multidict.CIMultiDictProxy[str], header_name: str
) -> int:
    """Convert a HTTP header into a positive integer value.

    Raises a ProtocolError if the conversion is not posible.
    """
    if header_name not in headers:
        msg = f'HTTP header "{header_name}" not included in server response.'
        raise common.ProtocolError(msg)

    header_value = headers[header_name]

    try:
        if (result := int(header_value)) < 0:
            raise RuntimeError  # noqa: TRY301
    except Exception as e:
        msg = (
            f'Unable to convert "{header_name}" header '
            f'"{header_value}" to a positive integer.'
        )
        raise common.ProtocolError(msg) from e

    return result


async def offset(
    session: aiohttp.ClientSession,
    location: yarl.URL,
    ssl: common.SSLArgument = True,  # noqa: FBT002
    headers: Mapping[str, str] | None = None,
) -> int:
    """Get the number of uploaded bytes.

    :param session: HTTP session to use for connections.
    :param location: The upload endpoint to query.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :param headers: Optional headers used in the request.
    :return: The number of bytes that are already on the server.
    """
    tus_headers = dict(headers or {})
    tus_headers["Tus-Resumable"] = common.TUS_PROTOCOL_VERSION

    logger.debug(f'Getting offset of "{location}"...')
    async with await session.head(location, headers=tus_headers, ssl=ssl) as response:
        response.raise_for_status()

        return _parse_positive_integer_header(response.headers, "Upload-Offset")


def _parse_metadata(header: str) -> common.Metadata:
    """Split and decode the input into a metadata dictionary."""
    if not (header := header.strip()):
        return {}

    md: dict[str, bytes | None] = {}
    for pair in header.split(","):
        kv = pair.split()
        if len(kv) == 1:
            md[kv[0]] = None
        elif len(kv) == 2:  # noqa: PLR2004
            md[kv[0]] = base64.b64decode(kv[1], validate=True)
        else:
            msg = "Key/Value pair consists of more than two elements."
            raise ValueError(msg)

    return md


async def metadata(
    session: aiohttp.ClientSession,
    location: yarl.URL,
    ssl: common.SSLArgument = True,  # noqa: FBT002
    headers: Mapping[str, str] | None = None,
) -> common.Metadata:
    """Get the metadata associated with an upload.

    See :data:`aiotus.Metadata` for details on how metadata is handled in the
    tus protocol.

    :param session: HTTP session to use for connections.
    :param location: The upload endpoint to query.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :param headers: Optional headers used in the request.
    :return: The metadata of the upload.
    :raises common.ProtocolError: When the server does not comply to the tus protocol.
    """
    tus_headers = dict(headers or {})
    tus_headers["Tus-Resumable"] = common.TUS_PROTOCOL_VERSION

    logger.debug(f'Getting metadata of "{location}"...')
    async with await session.head(location, headers=tus_headers, ssl=ssl) as response:
        response.raise_for_status()

        if "Upload-Metadata" not in response.headers:
            return {}

        try:
            return _parse_metadata(response.headers["Upload-Metadata"])
        except Exception as e:
            msg = f"Unable to parse metadata: {e}"
            raise common.ProtocolError(msg) from e


async def upload_buffer(  # noqa: PLR0913
    session: aiohttp.ClientSession,
    location: yarl.URL,
    buffer: BinaryIO,
    ssl: common.SSLArgument = True,  # noqa: FBT002
    chunksize: int = 4 * 1024 * 1024,
    headers: Mapping[str, str] | None = None,
) -> None:
    """Upload data to the server.

    :param session: HTTP session to use for connections.
    :param location: The endpoint to upload to.
    :param buffer: The data to upload.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :param chunksize: The size of individual chunks to upload at a time.
    :param headers: Optional headers used in the request.
    :raises common.ProtocolError: When the server does not comply to the tus protocol.
    :raises RuntimeError: When reading of the file fails.
    """
    total_size = await asyncio.to_thread(buffer.seek, 0, io.SEEK_END)

    # The position in the file where we currently read from.
    current_read_offset = -1

    # We ask the server for the number of bytes it already has for the upload. This
    # makes it possible to use this function also for resuming aborted uploads.
    current_server_offset = await offset(session, location, ssl=ssl, headers=headers)

    logger.debug(
        f'Resuming upload of "{location}" at offset {current_server_offset}..."'
    )

    while True:
        if current_server_offset == total_size:
            # Done, the whole file is on the server.
            msg = "Complete buffer uploaded."
            logger.info(msg)
            break

        if current_server_offset > total_size:
            # The offset that the server expects next does not exist.
            msg = "Server offset too big."
            raise common.ProtocolError(msg)

        if current_read_offset != current_server_offset:
            # Seek to the offset that the server expects next.
            current_read_offset = current_server_offset
            await asyncio.to_thread(buffer.seek, current_read_offset, io.SEEK_SET)

        if not (chunk := await asyncio.to_thread(buffer.read, chunksize)):
            # If the checks above are correct, we should never get here.
            msg = "Buffer returned unexpected EOF."
            raise RuntimeError(msg)

        current_read_offset += len(chunk)

        tus_headers = dict(headers or {})
        tus_headers.update(
            {
                "Tus-Resumable": common.TUS_PROTOCOL_VERSION,
                "Upload-Offset": str(current_server_offset),
                "Content-Length": str(len(chunk)),
                "Content-Type": "application/offset+octet-stream",
            }
        )

        logger.debug(f'Uploading {len(chunk)} bytes to "{location}"...')
        async with await session.patch(
            location, headers=tus_headers, data=chunk, ssl=ssl
        ) as response:
            response.raise_for_status()

            # Safe the value of the current offset on the server-side, at the beginning
            # of this loop are checks to see if it is valid.
            current_server_offset = _parse_positive_integer_header(
                response.headers, "Upload-Offset"
            )


async def configuration(
    session: aiohttp.ClientSession,
    url: yarl.URL,
    ssl: common.SSLArgument = True,  # noqa: FBT002
    headers: Mapping[str, str] | None = None,
) -> ServerConfiguration:
    """Get the server's configuration.

    :param session: HTTP session to use for connections.
    :param url: The creation endpoint of the server.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :param headers: Optional headers used in the request.
    :return: An object describing the server's configuration.
    :raises common.ProtocolError: When the server does not comply to the tus protocol.
    """
    logger.debug("Querying server configuration...")
    async with await session.options(url, headers=headers, ssl=ssl) as response:
        response.raise_for_status()

        if "Tus-Version" not in response.headers:
            msg = '"Tus-Version" header not present.'
            raise common.ProtocolError(msg)

        versions = response.headers["Tus-Version"].split(",")
        versions = [v.strip() for v in versions]

        max_size = None
        if "Tus-Max-Size" in response.headers:
            max_size = _parse_positive_integer_header(response.headers, "Tus-Max-Size")

        extensions = []
        if "Tus-Extension" in response.headers:
            extensions = response.headers["Tus-Extension"].split(",")
            extensions = [e.strip() for e in extensions]

        return ServerConfiguration(versions, max_size, extensions)
