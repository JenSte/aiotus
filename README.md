# Asynchronous tus client library

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
    "Filename": "image.jpeg",
    "Content-Type": "image/jpeg"
}

with open("image.jpeg", "rb") as f:
    location = await aiotus.upload(creation_url, f, metadata)

# 'location' contains the URL where the file was uploaded to.
```

## Requirements

* Python >= 3.7
* [aiohttp](https://pypi.org/project/aiohttp)
* [tenacity](https://pypi.org/project/tenacity)

## License

``aiotus`` is licensed under the Apache 2 license.
