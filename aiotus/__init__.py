"""
Top-level module containing convenience functions.
"""

from __future__ import annotations

from .common import Metadata, ProtocolError, SSLArgument
from .retry import RetryConfiguration, metadata, upload, upload_multiple

__all__ = (
    "Metadata",
    "ProtocolError",
    "RetryConfiguration",
    "SSLArgument",
    "metadata",
    "upload",
    "upload_multiple",
)
