# Asynchronous tus client library

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Code Style: black](https://img.shields.io/badge/Code%20Style-black-000000.svg)](https://black.readthedocs.io)
[![Actions Status](https://github.com/JenSte/aiotus/workflows/Continuous%20Integration/badge.svg?branch=master)](https://github.com/JenSte/aiotus/actions)
[![codecov](https://codecov.io/gh/JenSte/aiotus/branch/master/graph/badge.svg)](https://codecov.io/gh/JenSte/aiotus)
[![Documentation Status](https://readthedocs.org/projects/aiotus/badge/?version=latest)](https://aiotus.readthedocs.io/en/latest/)
[![PyPI version](https://badge.fury.io/py/aiotus.svg)](https://pypi.org/project/aiotus)

``aiotus`` implements the client side of the [tus](https://tus.io) protocol.

## Features

* Implements the [core protocol](https://tus.io/protocols/resumable-upload.html#core-protocol) as
  well as the [creation extension](https://tus.io/protocols/resumable-upload.html#creation).
* Built-in retry support in case of communication errors.

## Usage

```python
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
```

## Requirements

* Python >= 3.7
* [aiohttp](https://pypi.org/project/aiohttp)
* [tenacity](https://pypi.org/project/tenacity)

## Installation

Install ``aiotus`` from [PyPi](https://pypi.org/project/aiotus):

```
pip install aiotus
```

Development versions can be installed from [TestPyPi](https://test.pypi.org/project/aiotus):

```
pip install --index-url https://test.pypi.org/simple --extra-index-url https://pypi.org/simple aiotus
```

## License

``aiotus`` is licensed under the Apache 2 license.
