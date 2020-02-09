import ssl
from typing import Dict, Optional, Union

# The version of the tus protocol we implement.
TUS_PROTOCOL_VERSION = "1.0.0"

#: The type of the 'ssl' argument passed on to aiohttp.
SSLArgument = Optional[Union[bool, ssl.SSLContext]]

#: The type used to hold metadata of an upload.
Metadata = Dict[str, Optional[bytes]]


class ProtocolError(Exception):
    """Server response did not follow the tus protocol."""
