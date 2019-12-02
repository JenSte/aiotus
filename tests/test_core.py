"""Test the implementation of the core protocol."""

import io

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


class TestUploadRemaining:
    async def test_upload_remaining_functional(self, aiohttp_server, memory_file):
        """Test the normal functionality of the 'upload_remaining' function."""

        data = memory_file.getbuffer()

        async def handler(request):
            assert "Tus-Resumable" in request.headers
            assert "Upload-Offset" in request.headers
            assert "Content-Length" in request.headers
            assert "Content-Type" in request.headers

            assert (
                request.headers["Tus-Resumable"] == aiotus.common.TUS_PROTOCOL_VERSION
            )
            assert request.headers["Content-Type"] == "application/offset+octet-stream"

            offset = int(request.headers["Upload-Offset"])
            length = int(request.headers["Content-Length"])

            body = await request.read()

            assert offset + length <= len(data)
            assert length == len(body)
            assert body == data[offset : offset + length]

            raise aiohttp.web.HTTPNoContent()

        app = aiohttp.web.Application()
        app.router.add_route("PATCH", "/files/12345678", handler)
        server = await aiohttp_server(app)

        location = server.make_url("/files/12345678")

        async with aiohttp.ClientSession() as session:
            await aiotus.core.upload_remaining(session, location, io.BytesIO(data), 0)
            await aiotus.core.upload_remaining(session, location, io.BytesIO(data), 1)
            await aiotus.core.upload_remaining(session, location, io.BytesIO(data), 3)
