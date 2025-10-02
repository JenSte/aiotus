"""Common constants and classes used in the aiotus package."""

from __future__ import annotations

import ssl
from collections.abc import Mapping
from typing import Final

import aiohttp

# The version of the tus protocol we implement.
TUS_PROTOCOL_VERSION: Final = "1.0.0"

SSLArgument = bool | ssl.SSLContext | aiohttp.Fingerprint

Metadata = Mapping[str, bytes | None]


class ProtocolError(Exception):
    """Server response did not follow the tus protocol."""
