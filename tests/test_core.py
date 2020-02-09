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
        with pytest.raises(RuntimeError) as excinfo:
            location = server.make_url("/wrong_offset")

            async with aiohttp.ClientSession() as session:
                await aiotus.core.offset(session, location)

        assert 'Unable to convert "Upload-Offset" header' in str(excinfo.value)

        with pytest.raises(RuntimeError) as excinfo:
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
            md = aiotus.core._parse_metadata("k1 djE")
        assert "padding" in str(excinfo.value)

        with pytest.raises(binascii.Error) as excinfo:
            md = aiotus.core._parse_metadata("k1 dj&=")
        assert "Non-base64" in str(excinfo.value)

        with pytest.raises(ValueError) as excinfo:
            md = aiotus.core._parse_metadata("k v v")
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
                md = await aiotus.core.metadata(session, server.make_url("/invalid"))
                assert "Unable to parse metadata" in str(excinfo.value)

            md = await aiotus.core.metadata(session, server.make_url("/valid"))
            assert md == {"k1": None, "k2": b"value"}
