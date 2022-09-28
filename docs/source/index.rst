======
aiotus
======

``aiotus`` is a client-side implementation of the
`tus protocol <https://tus.io>`_ for
`asyncio <https://docs.python.org/3/library/asyncio.html>`_ and Python.

Features
========

- Implements the following parts of the tus protocol:

  - `Core protocol <https://tus.io/protocols/resumable-upload.html#core-protocol>`_
    - The actual uploading of data.
  - `Creation extension <https://tus.io/protocols/resumable-upload.html#creation>`_
    - Reserving a place on the tus server to upload to.
  - `Concatenation extension <https://tus.io/protocols/resumable-upload.html#concatenation>`_
    - Upload multiple parts separately and combine them on the server-side.

- High-level functions with built-in retry support in case of communication errors.

Installation
============

Install ``aiotus`` with:

.. code-block:: bash

   $ pip install aiotus

Source Code
===========

The project is hosted on `GitHub <https://github.com/JenSte/aiotus>`_.

License
=======

``aiotus`` is licensed under the Apache 2 license.

Version
=======

This documentation was generated for ``aiotus`` version |release|.

.. toctree::
   :hidden:
   :maxdepth: 3

   Introduction<self>
   usage
   aiotus
