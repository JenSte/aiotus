import ssl
from typing import Optional, Union

# The version of the tus protocol we implement.
TUS_PROTOCOL_VERSION = "1.0.0"

# The type of the 'ssl' argument passed on to aiohttp.
SSLArgument = Optional[Union[bool, ssl.SSLContext]]


class ProtocolError(Exception):
    """Server response did not follow the Tus protocol."""
