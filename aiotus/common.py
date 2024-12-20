"""Common constants and classes used in the aiotus package."""

from __future__ import annotations

import ssl
from collections.abc import Mapping
from typing import Final, Optional, Union

import aiohttp

# The version of the tus protocol we implement.
TUS_PROTOCOL_VERSION: Final = "1.0.0"

SSLArgument = Union[bool, ssl.SSLContext, aiohttp.Fingerprint]

Metadata = Mapping[str, Optional[bytes]]


class ProtocolError(Exception):
    """Server response did not follow the tus protocol."""
