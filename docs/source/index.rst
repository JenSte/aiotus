======
aiotus
======

``aiotus`` is a client side implementation of the
`tus protocol <https://tus.io>`_ for
`asyncio <https://docs.python.org/3/library/asyncio.html>`_ and Python.

Features
========

- Implements the
  `core protocol <https://tus.io/protocols/resumable-upload.html#core-protocol>`_
  (i.e. the actual uploading of data) as well as the
  `creation extension <https://tus.io/protocols/resumable-upload.html#creation>`_
  (i.e. reserving a place on the tus server to upload to).
- High-level functions with built-in retry support in case of communication errors.

Installation
============

Install ``aiotus`` with:

.. code-block:: bash

   $ pip install aiotus

Usage
=====

The ``aiotus`` top-level module provides high-level functions that can
be used to upload a file and later query the metadata of an uploaded file.
These functions retry a number of times in case of communication errors
with the server (the retry behaviour can be customized by passing an
instance of :py:class:`aiotus.RetryConfiguration`):

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
       # 'location' is the URL where the file was uploaded to.

   # Read back the metadata from the server.
   metadata = aiotus.metadata(location)

If these functions don't suit your needs,
it is also possible to use the functions from the
:py:mod:`aiotus.core`
and
:py:mod:`aiotus.creation`
modules directly.

Source Code
===========

The project is hosted on `GitHub <https://github.com/JenSte/aiotus>`_.

License
=======

``aiotus`` is licensed under the Apache 2 license.

API Reference
=============

.. toctree::
   :maxdepth: 2

   aiotus

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Version
=======

This documentation was generated for ``aiotus`` version |release|.
