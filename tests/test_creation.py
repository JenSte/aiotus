"""Test the implementation of the creation extension."""

from __future__ import annotations

import io

import aiohttp
import pytest
import pytest_aiohttp

import aiotus

from . import conftest


class TestCreate:
    async def test_create_wrong_metadata(self, memory_file: io.BytesIO) -> None:
        """Check the different checks performed on metadata keys."""

        with pytest.raises(ValueError) as excinfo:
            metadata = {"k1": "v1".encode(), "k²": "v2".encode(), "k3": "v3".encode()}
            await aiotus.creation.create(
                None,  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
                memory_file,
                metadata,
            )

        assert "ASCII characters" in str(excinfo.value)

        with pytest.raises(ValueError) as excinfo:
            metadata = {"k1": "v1".encode(), "k 2": "v2".encode(), "k3": "v3".encode()}
            await aiotus.creation.create(
                None,  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
                memory_file,
                metadata,
            )

        assert "spaces" in str(excinfo.value)

        with pytest.raises(ValueError) as excinfo:
            metadata = {"k1": "v1".encode(), "k2,": "v2".encode(), "k3": "v3".encode()}
            await aiotus.creation.create(
                None,  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
                memory_file,
                metadata,
            )

        assert "commas" in str(excinfo.value)

    async def test_create_wrong_status(
        self, aiohttp_server: pytest_aiohttp.AiohttpServer, memory_file: io.BytesIO
    ) -> None:
        """Check if status code is checked correctly."""

        async def handler_status_200(
            request: aiohttp.web.Request,
        ) -> aiohttp.web.Response:
            return aiohttp.web.Response(status=200)

        async def handler_status_400(
            request: aiohttp.web.Request,
        ) -> aiohttp.web.Response:
            return aiohttp.web.Response(status=400)

        app = aiohttp.web.Application()
        app.router.add_route("POST", "/status_200", handler_status_200)
        app.router.add_route("POST", "/status_400", handler_status_400)
        server = await aiohttp_server(app)

        with pytest.raises(aiotus.ProtocolError, match="Wrong status code"):
            endpoint = server.make_url("/status_200")
            async with aiohttp.ClientSession() as session:
                await aiotus.creation.create(session, endpoint, memory_file, {})

        with pytest.raises(aiohttp.ClientResponseError) as excinfo:
            endpoint = server.make_url("/status_400")
            async with aiohttp.ClientSession() as session:
                await aiotus.creation.create(session, endpoint, memory_file, {})
        assert excinfo.value.status == 400

    async def test_create_no_location(
        self, aiohttp_server: pytest_aiohttp.AiohttpServer, memory_file: io.BytesIO
    ) -> None:
        """Check if the check for the "Location" header is working."""

        async def handler_no_location(
            request: aiohttp.web.Request,
        ) -> aiohttp.web.Response:
            raise aiohttp.web.HTTPCreated()

        app = aiohttp.web.Application()
        app.router.add_route("POST", "/no_location", handler_no_location)
        server = await aiohttp_server(app)

        with pytest.raises(aiotus.ProtocolError) as excinfo:
            endpoint = server.make_url("/no_location")

            async with aiohttp.ClientSession() as session:
                await aiotus.creation.create(session, endpoint, memory_file, {})

        assert 'no "Location" header' in str(excinfo.value)

    async def test_create_functional(
        self, tus_server: conftest.MockTusServer, memory_file: io.BytesIO
    ) -> None:
        """Test the normal functionality of the upload creation."""

        metadata = {"k1": "1".encode(), "k2": "2²".encode(), "k-3": "three".encode()}

        endpoint = tus_server.server.make_url("/files")

        async with aiohttp.ClientSession() as session:
            location = await aiotus.creation.create(
                session, endpoint, memory_file, metadata
            )

        assert tus_server.upload_endpoint == location
