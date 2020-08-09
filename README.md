<h1 align="center">aiotus - Asynchronous tus client library</h1>

<div align="center">
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img alt="License: Apache 2.0" src="https://img.shields.io/badge/license-Apache%202.0-blue.svg?style=flat-square">
  </a>
  <a href="https://www.python.org">
    <img alt="Python Versions" src="https://img.shields.io/pypi/pyversions/aiotus?style=flat-square">
  </a>
  <a href="http://mypy-lang.org">
    <img alt="Mypy Checked" src="https://img.shields.io/badge/mypy-checked-blue.svg?style=flat-square">
  </a>
  <a href="https://black.readthedocs.io">
    <img alt="Code Style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square">
  </a>
</div>
<div align="center">
  <a href="https://github.com/JenSte/aiotus/actions">
    <img alt="CI Status" src="https://img.shields.io/github/workflow/status/JenSte/aiotus/Continuous Integration?style=flat-square">
  </a>
  <a href="https://codecov.io/gh/JenSte/aiotus">
    <img alt="Code Coverage" src="https://img.shields.io/codecov/c/github/JenSte/aiotus?style=flat-square">
  </a>
  <a href="https://sonarcloud.io/dashboard?id=JenSte_aiotus">
    <img alt="Quality Gate" src="https://img.shields.io/sonar/quality_gate/JenSte_aiotus?server=https%3A%2F%2Fsonarcloud.io&style=flat-square">
  </a>
  <a href="https://aiotus.readthedocs.io/en/latest">
    <img alt="Documentation Status" src="https://img.shields.io/readthedocs/aiotus?style=flat-square">
  </a>
  <a href="https://pypi.org/project/aiotus">
    <img alt="PyPI Package Version" src="https://img.shields.io/pypi/v/aiotus?style=flat-square">
  </a>
</div>

``aiotus`` implements the client side of the [tus](https://tus.io) protocol.

## Features

* Implements the [core protocol](https://tus.io/protocols/resumable-upload.html#core-protocol) as
  well as the [creation](https://tus.io/protocols/resumable-upload.html#creation)
  and [concatenation](https://tus.io/protocols/resumable-upload.html#concatenation) extensions.
* Built-in retry support in case of communication errors.
* Extensive test bench, including tests against the reference [tusd](https://github.com/tus/tusd) server.

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

* [Python](https://www.python.org) ≥ 3.7
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

``aiotus`` is licensed under the Apache 2.0 license.
