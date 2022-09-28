=========
Reference
=========

aiotus module
=============

.. automodule:: aiotus
   :members:

.. data:: SSLArgument
   :value: Union[bool, ssl.SSLContext, aiohttp.Fingerprint]

   Alias for the type of the 'ssl' argument passed to aiohttp calls.

.. data:: Metadata
   :value: Mapping[str, Optional[bytes]]

   Alias for the type used to hold metadata of an upload.

   The tus protocol transfers metadata values in binary form (Base64 encoded).
   If strings should be saved as metadata, they have to be encoded to binary
   first.

   However, while the protocol itself would allow it to store arbitrary binary
   data as metadata, the handling of metadata may depends on the specific
   server implementation. For example, tusd decodes the metadata values and
   `drops them <https://github.com/tus/tusd/blob/v1.4.0/pkg/handler/unrouted_handler.go#L1135>`_
   if they can not be decoded to strings.

aiotus.core module
==================

.. automodule:: aiotus.core
   :members:

aiotus.creation module
======================

.. automodule:: aiotus.creation
   :members:
