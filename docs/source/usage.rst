=====
Usage
=====

Basic Usage
===========

The ``aiotus`` top-level module provides high-level functions that can
be used to upload a file and later query the metadata of an uploaded file.
These functions retry a number of times in case of communication errors
with the server:

.. code-block:: python

   import aiotus

   creation_url = "http://example.com/files"

   metadata = {
       "Filename": "image.jpeg".encode(),
       "Content-Type": "image/jpeg".encode()
   }

   # Upload a file to a tus server.
   with open("image.jpeg", "rb") as f:
       location = await aiotus.upload(creation_url, f, metadata)
       # 'location' is the URL where the file was uploaded to, or 'None'
       # in case of an error.

   if location:
       # Read back the metadata from the server.
       metadata = aiotus.metadata(location)

The retry behaviour can be customized by passing an instance of
:py:class:`aiotus.RetryConfiguration`.

If these functions do not suit your needs,
it is also possible to use the functions from the
:py:mod:`aiotus.core`
and
:py:mod:`aiotus.creation`
modules directly:

.. code-block:: python

    async with aiohttp.ClientSession() as session:
        # Only "create" an upload, but do not upload any actual data.
        location = await aiotus.creation.create(session, creation_url)

Using a Custom aiohttp Session
==============================

To customize the way HTTP requests are made, a custom :py:class:`aiohttp.ClientSession`
can be used:

.. code-block:: python

   auth = aiohttp.BasicAuth("username", "password")
   additional_headers = {"foo": "bar"}
   async with aiohttp.ClientSession(auth=auth, headers=additional_headers) as session:
        await aiotus.metadata(location, client_session=session)

However, if all you want to do is to pass a few additional headers to be used in
the HTTP request, they can also be passed in directly:

.. code-block:: python

   await aiotus.metadata(location, headers={"foo": "bar"})

Controlling SSL Validation
==========================

To customize the way HTTPS checks are done, you can pass in a SSL context
or a boolean that is then passed on to the underlying HTTP library:

.. code-block:: python

   # Low-level function:
   sslcontext = ssl.create_default_context(...)
   async with aiohttp.ClientSession() as session:
        location = await aiotus.creation.create(session, creation_url, ssl=sslcontext)

   # High-level function:
   config = aiotus.RetryConfiguration(ssl=False)
   location = await aiotus.upload(creation_url, data, config=config)

More information on the meaning of the argument can be found in the
`aiohttp documentation <https://docs.aiohttp.org/en/stable/client_advanced.html#ssl-control-for-tcp-sockets>`_.

Logging
=======

All logging is done using the standard :py:mod:`logging` logging module
with a logger called ``"aiotus"``.

Command-Line
============

The ``aiotus`` package installs two command-line tools that can be used to upload
files to a tus server and to show the metadata associated with an upload:

.. code-block::

   $ aiotus-upload --metadata additional=metadata http://example.com/files image.jpeg
   INFO:aiotus:Complete buffer uploaded.
   http://example.com/files/abcd...

   $ aiotus-metadata http://example.com/files/abcd...
   mime_type: image/jpeg
   additional: metadata
   filename: image.jpeg

In addition, these tools can serve as additional examples on how to use ``aiotus``.
Their implementation can be found in the :py:mod:`aiotus.entrypoint` module.
