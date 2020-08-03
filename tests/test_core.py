"""Test the implementation of the core protocol."""

import binascii

import aiohttp
import pytest  # type: ignore

import aiotus


class TestOffset:
    async def test_offset_exceptions(self, aiohttp_server, memory_file):
        """Check for the different exceptions that can be thrown."""

        async def handler_not_found(request):
            raise aiohttp.web.HTTPNotFound()

        async def handler_no_offset(request):
            raise aiohttp.web.HTTPOk()

        async def handler_wrong_offset(request):
            headers = {"Upload-Offset": "xyz"}
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_negative_offset(request):
            headers = {"Upload-Offset": "-1"}
            raise aiohttp.web.HTTPOk(headers=headers)

        app = aiohttp.web.Application()
        app.router.add_route("HEAD", "/not_found", handler_not_found)
        app.router.add_route("HEAD", "/no_offset", handler_no_offset)
        app.router.add_route("HEAD", "/wrong_offset", handler_wrong_offset)
        app.router.add_route("HEAD", "/negative_offset", handler_negative_offset)
        server = await aiohttp_server(app)

        # Check if status code is checked correctly.
        with pytest.raises(aiohttp.ClientResponseError):
            location = server.make_url("/not_found")

            async with aiohttp.ClientSession() as session:
                await aiotus.core.offset(session, location)

        # Check if the check for the "Upload-Offset" header is working.
        with pytest.raises(RuntimeError) as excinfo:
            location = server.make_url("/no_offset")

            async with aiohttp.ClientSession() as session:
                await aiotus.core.offset(session, location)

        assert 'no "Upload-Offset" header' in str(excinfo.value)

        # Check if the offset value is checked properly.
        with pytest.raises(aiotus.ProtocolError) as excinfo:
            location = server.make_url("/wrong_offset")

            async with aiohttp.ClientSession() as session:
                await aiotus.core.offset(session, location)

        assert 'Unable to convert "Upload-Offset" header' in str(excinfo.value)

        with pytest.raises(aiotus.ProtocolError) as excinfo:
            location = server.make_url("/negative_offset")

            async with aiohttp.ClientSession() as session:
                await aiotus.core.offset(session, location)

        assert 'Unable to convert "Upload-Offset" header' in str(excinfo.value)

    async def test_offset_functional(self, aiohttp_server):
        """Test the normal functionality of the '_offset' function."""

        async def handler(request):

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
    def test_parse_metadata(self):
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

        with pytest.raises(binascii.Error) as excinfo:
            aiotus.core._parse_metadata("k1 djE")
        assert "padding" in str(excinfo.value)

        with pytest.raises(binascii.Error) as excinfo:
            aiotus.core._parse_metadata("k1 dj&=")
        assert "Non-base64" in str(excinfo.value)

        with pytest.raises(ValueError) as excinfo:
            aiotus.core._parse_metadata("k v v")
        assert "more than two elements" in str(excinfo.value)

    async def test_metadata(self, aiohttp_server):
        """Check the 'core.metadata()' function."""

        async def handler_no_metadata(request):
            headers = {"Tus-Resumable": aiotus.common.TUS_PROTOCOL_VERSION}
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_invalid(request):
            headers = {
                "Tus-Resumable": aiotus.common.TUS_PROTOCOL_VERSION,
                "Upload-Metadata": "k1 djE",
            }
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_valid(request):
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

            with pytest.raises(aiotus.ProtocolError) as excinfo:
                await aiotus.core.metadata(session, server.make_url("/invalid"))
                assert "Unable to parse metadata" in str(excinfo.value)

            md = await aiotus.core.metadata(session, server.make_url("/valid"))
            assert md == {"k1": None, "k2": b"value"}


class TestConfiguration:
    async def test_configuration_exceptions(self, aiohttp_server):
        """Check for the different exceptions that can be thrown."""

        async def handler_not_found(request):
            raise aiohttp.web.HTTPNotFound()

        async def handler_no_version(request):
            raise aiohttp.web.HTTPOk()

        async def handler_max_size_invalid(request):
            headers = {"Tus-Version": "1.0.0", "Tus-Max-Size": "xyz"}
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_max_size_negative(request):
            headers = {"Tus-Version": "1.0.0", "Tus-Max-Size": "-1"}
            raise aiohttp.web.HTTPOk(headers=headers)

        app = aiohttp.web.Application()
        app.router.add_route("OPTIONS", "/not_found", handler_not_found)
        app.router.add_route("OPTIONS", "/no_version", handler_no_version)
        app.router.add_route("OPTIONS", "/max_size_invalid", handler_max_size_invalid)
        app.router.add_route("OPTIONS", "/max_size_negative", handler_max_size_negative)
        server = await aiohttp_server(app)

        with pytest.raises(aiohttp.ClientResponseError):
            url = server.make_url("/not_found")

            async with aiohttp.ClientSession() as session:
                await aiotus.core.configuration(session, url)

        with pytest.raises(aiotus.ProtocolError):
            url = server.make_url("/no_version")

            async with aiohttp.ClientSession() as session:
                await aiotus.core.configuration(session, url)

        with pytest.raises(aiotus.ProtocolError):
            url = server.make_url("/max_size_invalid")

            async with aiohttp.ClientSession() as session:
                await aiotus.core.configuration(session, url)

        with pytest.raises(aiotus.ProtocolError):
            url = server.make_url("/max_size_negative")

            async with aiohttp.ClientSession() as session:
                await aiotus.core.configuration(session, url)

    async def test_configuration_function(self, aiohttp_server):
        """Test the normal functionality of the 'configuration()' function."""

        async def handler_only_version(request):
            headers = {"Tus-Version": "1.0.0"}
            raise aiohttp.web.HTTPOk(headers=headers)

        async def handler_all(request):
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

    async def test_configuration_function_tusd(self, tusd):
        """Test the normal functionality of the 'configuration()' function with tusd."""

        async with aiohttp.ClientSession() as session:
            config = await aiotus.core.configuration(session, tusd.url)

        assert config.protocol_versions == ["1.0.0"]
        assert config.max_size is None
        assert "creation" in config.protocol_extensions
