"""
Implementation of the
`core tus protocol <https://tus.io/protocols/resumable-upload.html#core-protocol>`_.
"""

import asyncio
import base64
import dataclasses
import io
from typing import BinaryIO, Dict, List, Mapping, Optional

import aiohttp
import multidict
import yarl

from . import common
from .log import logger


@dataclasses.dataclass
class ServerConfiguration:
    """Class to hold the server's configuration."""

    protocol_versions: List[str]
    """
    List of protocol versions supported by the server, sorted by the server's
    preference.
    """

    max_size: Optional[int]
    """
    The maximum allowed file size (in bytes), if reported by the server.
    """

    protocol_extensions: List[str]
    """
    The protocol extensions supported by the server.
    """


def _parse_positive_integer_header(
    headers: multidict.CIMultiDictProxy[str], header_name: str
) -> int:
    """Convert a HTTP header into a positive integer value.

    Raises a ProtocolError if the conversion is not posible.
    """

    try:
        header_value = headers[header_name]
        result = int(header_value)
        if result < 0:
            raise RuntimeError()

        return result
    except asyncio.CancelledError:  # pragma: no cover
        raise
    except Exception:
        raise common.ProtocolError(
            f'Unable to convert "{header_name}" header '
            f'"{header_value}" to a positive integer.'
        )


async def offset(
    session: aiohttp.ClientSession,
    location: yarl.URL,
    ssl: common.SSLArgument = None,
    headers: Optional[Mapping[str, str]] = None,
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

        if "Upload-Offset" not in response.headers:
            raise RuntimeError(
                f"HEAD request succeeded for {location}, "
                'but no "Upload-Offset" header in response.'
            )

        return _parse_positive_integer_header(response.headers, "Upload-Offset")


def _parse_metadata(header: str) -> common.Metadata:
    """Split and decode the input into a metadata dictionary."""

    header = header.strip()
    if not header:
        return {}

    md: Dict[str, Optional[bytes]] = {}
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
    session: aiohttp.ClientSession,
    location: yarl.URL,
    ssl: common.SSLArgument = None,
    headers: Optional[Mapping[str, str]] = None,
) -> common.Metadata:
    """Get the metadata associated with an upload.

    :param session: HTTP session to use for connections.
    :param location: The upload endpoint to query.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :param headers: Optional headers used in the request.
    :return: The metadata of the upload.
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
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception as e:
            raise common.ProtocolError(f"Unable to parse metadata: {e}")


async def upload_buffer(
    session: aiohttp.ClientSession,
    location: yarl.URL,
    buffer: BinaryIO,
    ssl: common.SSLArgument = None,
    chunksize: int = 4 * 1024 * 1024,
    headers: Optional[Mapping[str, str]] = None,
) -> None:
    """Upload data to the server.

    :param session: HTTP session to use for connections.
    :param location: The endpoint to upload to.
    :param buffer: The data to upload.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :param chunksize: The size of individual chunks to upload at a time.
    :param headers: Optional headers used in the request.
    """

    loop = asyncio.get_event_loop()

    total_size = await loop.run_in_executor(None, buffer.seek, 0, io.SEEK_END)

    # The position in the file where we currently read from.
    current_read_offset = -1

    # We ask the server for the number of bytes it already has for the upload. This
    # makes it possible to use this function also for resuming aborted uploads.
    current_server_offset = await offset(session, location, ssl=ssl)

    logger.debug(
        f'Resuming upload of "{location}" at offset {current_server_offset}..."'
    )

    while True:
        if current_server_offset == total_size:
            # Done, the whole file is on the server.
            logger.info("Complete buffer uploaded.")
            break

        if current_server_offset > total_size:
            # The offset that the server expects next does not exist.
            raise common.ProtocolError("Server offset too big.")

        if current_read_offset != current_server_offset:
            # Seek to the offset that the server expects next.
            current_read_offset = current_server_offset
            await loop.run_in_executor(
                None, buffer.seek, current_read_offset, io.SEEK_SET
            )

        chunk = await loop.run_in_executor(None, buffer.read, chunksize)
        if not chunk:
            # If the checks above are correct, we should never get here.
            raise RuntimeError("Buffer returned unexpected EOF.")

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
    ssl: common.SSLArgument = None,
    headers: Optional[Mapping[str, str]] = None,
) -> ServerConfiguration:
    """Get the server's configuration.

    :param session: HTTP session to use for connections.
    :param url: The creation endpoint of the server.
    :param ssl: SSL validation mode, passed on to aiohttp.
    :param headers: Optional headers used in the request.
    :return: An object describing the server's configuration.
    """

    logger.debug("Querying server configuration...")
    async with await session.options(url, headers=headers, ssl=ssl) as response:
        response.raise_for_status()

        if "Tus-Version" not in response.headers:
            raise common.ProtocolError('"Tus-Version" header not present.')

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
