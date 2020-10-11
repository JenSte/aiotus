import ssl
from typing import Mapping, Optional, Union

import aiohttp

# The version of the tus protocol we implement.
TUS_PROTOCOL_VERSION = "1.0.0"

SSLArgument = Optional[Union[bool, ssl.SSLContext, aiohttp.Fingerprint]]
SSLArgument.__doc__ = "The type of the 'ssl' argument passed on to aiohttp."

Metadata = Mapping[str, Optional[bytes]]
Metadata.__doc__ = """
    The type used to hold metadata of an upload.

    The tus protocol transfers metadata values in binary form (base64 encoded).
    If strings should be saved as metadata, they have to be encoded to binary
    first.

    However, while the protocol itself would allow it to store arbitrary binary
    data as metadata, the handling of metadata may depends on the specific
    server implementation. For example, tusd decodes the metadata values and
    `drops them <https://github.com/tus/tusd/blob/v1.4.0/pkg/handler/unrouted_handler.go#L1135>`_
    if they can not be decoded to strings.
"""  # noqa: E501


class ProtocolError(Exception):
    """Server response did not follow the tus protocol."""
