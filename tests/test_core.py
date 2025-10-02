"""Test the implementation of the core protocol."""

from __future__ import annotations

import binascii
from typing import TYPE_CHECKING

import aiohttp
import pytest

import aiotus

if TYPE_CHECKING:  # pragma: no cover
    import io

    import pytest_aiohttp

    from . import conftest


class TestOffset:
    async def test_offset_exceptions(
        self, aiohttp_server: pytest_aiohttp.AiohttpServer
    ) -> None:
        """Check for the different exceptions that can be thrown."""

        async def handler_not_found(_: aiohttp.web.Request) -> aiohttp.web.Response:
            raise aiohttp.web.HTTPNotFound

        async def handler_no_offset(_: aiohttp.web.Request) -> aiohttp.web.Response:
            raise aiohttp.web.HTTPOk

        async def handler_wrong_offset(_: aiohttp.web.Request) -> aiohttp.web.Response:
            headers = {"Upload-Offset": "xyz"}
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_negative_offset(
            _: aiohttp.web.Request,
        ) -> aiohttp.web.Response:
            headers = {"Upload-Offset": "-1"}
            raise aiohttp.web.HTTPOk(headers=headers)

        app = aiohttp.web.Application()
        app.router.add_route("HEAD", "/not_found", handler_not_found)
        app.router.add_route("HEAD", "/no_offset", handler_no_offset)
        app.router.add_route("HEAD", "/wrong_offset", handler_wrong_offset)
        app.router.add_route("HEAD", "/negative_offset", handler_negative_offset)
        server = await aiohttp_server(app)

        # Check if status code is checked correctly.
        location = server.make_url("/not_found")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiohttp.ClientResponseError):
                await aiotus.core.offset(session, location)

        # Check if the check for the "Upload-Offset" header is working.
        location = server.make_url("/no_offset")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(
                aiotus.ProtocolError,
                match=r'HTTP header "Upload-Offset" not included in server response.',
            ):
                await aiotus.core.offset(session, location)

        # Check if the offset value is checked properly.
        location = server.make_url("/wrong_offset")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(
                aiotus.ProtocolError,
                match='Unable to convert "Upload-Offset" header',
            ):
                await aiotus.core.offset(session, location)

        location = server.make_url("/negative_offset")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(
                aiotus.ProtocolError,
                match='Unable to convert "Upload-Offset" header',
            ):
                await aiotus.core.offset(session, location)

    async def test_offset_functional(
        self, aiohttp_server: pytest_aiohttp.AiohttpServer
    ) -> None:
        """Test the normal functionality of the '_offset' function."""

        async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
            assert "Tus-Resumable" in request.headers
            assert (
                request.headers["Tus-Resumable"] == aiotus.common.TUS_PROTOCOL_VERSION
            )

            headers = {"Upload-Offset": "123"}
            raise aiohttp.web.HTTPOk(headers=headers)

        app = aiohttp.web.Application()
        app.router.add_route("HEAD", "/files/12345678", handler)
        server = await aiohttp_server(app)

        location = server.make_url("/files/12345678")

        async with aiohttp.ClientSession() as session:
            offset = await aiotus.core.offset(session, location)

        assert offset == 123


class TestMetadata:
    def test_parse_metadata(self) -> None:
        """Check if metadata is parsed correctly."""

        md = aiotus.core._parse_metadata("")
        assert md == {}

        md = aiotus.core._parse_metadata("key")
        assert md == {"key": None}

        md = aiotus.core._parse_metadata("key ")
        assert md == {"key": None}

        md = aiotus.core._parse_metadata("key dmFsdWU=")
        assert md == {"key": b"value"}

        md = aiotus.core._parse_metadata("k1, k2 dmFsdWU=")
        assert md == {"k1": None, "k2": b"value"}

        md = aiotus.core._parse_metadata("k1 djE=, k2 djI=  ")
        assert md == {"k1": b"v1", "k2": b"v2"}

        with pytest.raises(binascii.Error, match="padding") as excinfo:
            aiotus.core._parse_metadata("k1 djE")

        with pytest.raises(binascii.Error) as excinfo:
            aiotus.core._parse_metadata("k1 dj&=")
        assert any(s in str(excinfo.value) for s in ("Non-base64", "Only base64"))

        with pytest.raises(ValueError, match="more than two elements"):
            aiotus.core._parse_metadata("k v v")

    async def test_metadata(self, aiohttp_server: pytest_aiohttp.AiohttpServer) -> None:
        """Check the 'core.metadata()' function."""

        async def handler_no_metadata(_: aiohttp.web.Request) -> aiohttp.web.Response:
            headers = {"Tus-Resumable": aiotus.common.TUS_PROTOCOL_VERSION}
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_invalid(_: aiohttp.web.Request) -> aiohttp.web.Response:
            headers = {
                "Tus-Resumable": aiotus.common.TUS_PROTOCOL_VERSION,
                "Upload-Metadata": "k1 djE",
            }
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_valid(_: aiohttp.web.Request) -> aiohttp.web.Response:
            headers = {
                "Tus-Resumable": aiotus.common.TUS_PROTOCOL_VERSION,
                "Upload-Metadata": "k1, k2 dmFsdWU=",
            }
            raise aiohttp.web.HTTPOk(headers=headers)

        app = aiohttp.web.Application()
        app.router.add_route("HEAD", "/no_metadata", handler_no_metadata)
        app.router.add_route("HEAD", "/invalid", handler_invalid)
        app.router.add_route("HEAD", "/valid", handler_valid)
        server = await aiohttp_server(app)

        async with aiohttp.ClientSession() as session:
            md = await aiotus.core.metadata(session, server.make_url("/no_metadata"))
            assert md == {}

            with pytest.raises(aiotus.ProtocolError, match="Unable to parse metadata"):
                await aiotus.core.metadata(session, server.make_url("/invalid"))

            md = await aiotus.core.metadata(session, server.make_url("/valid"))
            assert md == {"k1": None, "k2": b"value"}


class TestUploadBuffer:
    async def test_upload_buffer(
        self,
        tus_server: conftest.MockTusServer,
        memory_file: io.BytesIO,
    ) -> None:
        """Test the upload function without simulating errors."""

        # We don't want to test the creation functionality here, so just create the
        # byte array so that 'tus_server' can accept data.
        tus_server.data = bytearray()

        async with aiohttp.ClientSession() as s:
            # Pass a small chunksize so that we have multiple uploads even with
            # the small test file.
            await aiotus.core.upload_buffer(
                s, tus_server.upload_endpoint, memory_file, ssl=False, chunksize=3
            )

        assert tus_server.data is not None
        assert tus_server.data == memory_file.getbuffer()

    async def test_server_offset(
        self,
        tus_server: conftest.MockTusServer,
        memory_file: io.BytesIO,
    ) -> None:
        """Test if the upload routine honors the offset value at the server-side."""

        tus_server.data = bytearray()

        # Make the server drop half of the uploaded data for each request.
        tus_server.drop_upload = True

        async with aiohttp.ClientSession() as s:
            await aiotus.core.upload_buffer(
                s, tus_server.upload_endpoint, memory_file, ssl=False, chunksize=3
            )

        assert tus_server.data is not None
        assert tus_server.data == memory_file.getbuffer()

    async def test_server_error(
        self,
        tus_server: conftest.MockTusServer,
        memory_file: io.BytesIO,
    ) -> None:
        """Simulate a server error."""

        tus_server.data = bytearray()
        tus_server.retries_upload = 2

        with pytest.raises(aiohttp.ClientResponseError) as excinfo:
            async with aiohttp.ClientSession() as s:
                await aiotus.core.upload_buffer(
                    s, tus_server.upload_endpoint, memory_file
                )

        assert "Internal Server Error" in str(excinfo.value)

    async def test_server_wrong_size(
        self,
        tus_server: conftest.MockTusServer,
        memory_file: io.BytesIO,
    ) -> None:
        """Simulate the case where the server has a bitter file than locally."""

        tus_server.data = bytearray(20 * b"x")

        with pytest.raises(aiotus.common.ProtocolError) as excinfo:
            async with aiohttp.ClientSession() as s:
                await aiotus.core.upload_buffer(
                    s, tus_server.upload_endpoint, memory_file
                )

        assert "Server offset too big" in str(excinfo.value)

    async def test_eof(
        self,
        tus_server: conftest.MockTusServer,
        eof_memory_file: io.BytesIO,
    ) -> None:
        """Simulate the case where the local file shrinks during an upload."""

        tus_server.data = bytearray()

        with pytest.raises(RuntimeError) as excinfo:
            async with aiohttp.ClientSession() as s:
                await aiotus.core.upload_buffer(
                    s, tus_server.upload_endpoint, eof_memory_file
                )

        assert "Buffer returned unexpected EOF" in str(excinfo.value)


class TestConfiguration:
    async def test_configuration_exceptions(
        self, aiohttp_server: pytest_aiohttp.AiohttpServer
    ) -> None:
        """Check for the different exceptions that can be thrown."""

        async def handler_not_found(_: aiohttp.web.Request) -> aiohttp.web.Response:
            raise aiohttp.web.HTTPNotFound

        async def handler_no_version(_: aiohttp.web.Request) -> aiohttp.web.Response:
            raise aiohttp.web.HTTPOk

        async def handler_max_size_invalid(
            _: aiohttp.web.Request,
        ) -> aiohttp.web.Response:
            headers = {"Tus-Version": "1.0.0", "Tus-Max-Size": "xyz"}
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_max_size_negative(
            _: aiohttp.web.Request,
        ) -> aiohttp.web.Response:
            headers = {"Tus-Version": "1.0.0", "Tus-Max-Size": "-1"}
            raise aiohttp.web.HTTPOk(headers=headers)

        app = aiohttp.web.Application()
        app.router.add_route("OPTIONS", "/not_found", handler_not_found)
        app.router.add_route("OPTIONS", "/no_version", handler_no_version)
        app.router.add_route("OPTIONS", "/max_size_invalid", handler_max_size_invalid)
        app.router.add_route("OPTIONS", "/max_size_negative", handler_max_size_negative)
        server = await aiohttp_server(app)

        url = server.make_url("/not_found")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiohttp.ClientResponseError):
                await aiotus.core.configuration(session, url)

        url = server.make_url("/no_version")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiotus.ProtocolError):
                await aiotus.core.configuration(session, url)

        url = server.make_url("/max_size_invalid")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiotus.ProtocolError):
                await aiotus.core.configuration(session, url)

        url = server.make_url("/max_size_negative")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiotus.ProtocolError):
                await aiotus.core.configuration(session, url)

    async def test_configuration_function(
        self, aiohttp_server: pytest_aiohttp.AiohttpServer
    ) -> None:
        """Test the normal functionality of the 'configuration()' function."""

        async def handler_only_version(_: aiohttp.web.Request) -> aiohttp.web.Response:
            headers = {"Tus-Version": "1.0.0"}
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_all(_: aiohttp.web.Request) -> aiohttp.web.Response:
            headers = {
                "Tus-Version": "1.0.0,0.9.9",
                "Tus-Max-Size": "1024",
                "Tus-Extension": "creation,checksum",
            }
            raise aiohttp.web.HTTPOk(headers=headers)

        app = aiohttp.web.Application()
        app.router.add_route("OPTIONS", "/only_version", handler_only_version)
        app.router.add_route("OPTIONS", "/all", handler_all)
        server = await aiohttp_server(app)

        # The server only returns the protocol version.
        url = server.make_url("/only_version")
        async with aiohttp.ClientSession() as session:
            config = await aiotus.core.configuration(session, url)

        assert len(config.protocol_versions) == 1
        assert config.protocol_versions[0] == "1.0.0"
        assert config.max_size is None
        assert len(config.protocol_extensions) == 0

        # The server also returns max size and protocol extensions.
        url = server.make_url("/all")
        async with aiohttp.ClientSession() as session:
            config = await aiotus.core.configuration(session, url)

        assert len(config.protocol_versions) == 2
        assert config.protocol_versions[0] == "1.0.0"
        assert config.protocol_versions[1] == "0.9.9"
        assert config.max_size == 1024
        assert len(config.protocol_extensions) == 2
        assert config.protocol_extensions[0] == "creation"
        assert config.protocol_extensions[1] == "checksum"

    async def test_configuration_function_tusd(self, tusd: conftest.TusServer) -> None:
        """Test the normal functionality of the 'configuration()' function with tusd."""

        async with aiohttp.ClientSession() as session:
            config = await aiotus.core.configuration(session, tusd.url)

        assert config.protocol_versions == ["1.0.0"]
        assert config.max_size is None
        assert "creation" in config.protocol_extensions
