import ssl
from typing import Optional, Union

# The type of the 'ssl' argument passed on to aiohttp.
SSLArgument = Optional[Union[bool, ssl.SSLContext]]
