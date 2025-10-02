"""Test the implementation of the creation extension."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import pytest

import aiotus

if TYPE_CHECKING:  # pragma: no cover
    import io

    import pytest_aiohttp

    from . import conftest


class TestCreate:
    async def test_create_wrong_metadata(self, memory_file: io.BytesIO) -> None:
        """Check the different checks performed on metadata keys."""

        metadata = {"k1": b"v1", "k²": b"v2", "k3": b"v3"}
        with pytest.raises(ValueError, match="ASCII characters"):
            await aiotus.creation.create(
                None,  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
                memory_file,
                metadata,
            )

        metadata = {"k1": b"v1", "k 2": b"v2", "k3": b"v3"}
        with pytest.raises(ValueError, match="spaces"):
            await aiotus.creation.create(
                None,  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
                memory_file,
                metadata,
            )

        metadata = {"k1": b"v1", "k2,": b"v2", "k3": b"v3"}
        with pytest.raises(ValueError, match="commas"):
            await aiotus.creation.create(
                None,  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
                memory_file,
                metadata,
            )

    async def test_create_wrong_status(
        self, aiohttp_server: pytest_aiohttp.AiohttpServer, memory_file: io.BytesIO
    ) -> None:
        """Check if status code is checked correctly."""

        async def handler_status_200(
            _: aiohttp.web.Request,
        ) -> aiohttp.web.Response:
            return aiohttp.web.Response(status=200)

        async def handler_status_400(
            _: aiohttp.web.Request,
        ) -> aiohttp.web.Response:
            return aiohttp.web.Response(status=400)

        app = aiohttp.web.Application()
        app.router.add_route("POST", "/status_200", handler_status_200)
        app.router.add_route("POST", "/status_400", handler_status_400)
        server = await aiohttp_server(app)

        endpoint = server.make_url("/status_200")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiotus.ProtocolError, match="Wrong status code"):
                await aiotus.creation.create(session, endpoint, memory_file, {})

        endpoint = server.make_url("/status_400")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiohttp.ClientResponseError) as excinfo:
                await aiotus.creation.create(session, endpoint, memory_file, {})
        assert excinfo.value.status == 400

    async def test_create_no_location(
        self, aiohttp_server: pytest_aiohttp.AiohttpServer, memory_file: io.BytesIO
    ) -> None:
        """Check if the check for the "Location" header is working."""

        async def handler_no_location(
            _: aiohttp.web.Request,
        ) -> aiohttp.web.Response:
            raise aiohttp.web.HTTPCreated

        app = aiohttp.web.Application()
        app.router.add_route("POST", "/no_location", handler_no_location)
        server = await aiohttp_server(app)

        endpoint = server.make_url("/no_location")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiotus.ProtocolError) as excinfo:
                await aiotus.creation.create(session, endpoint, memory_file, {})

        assert 'no "Location" header' in str(excinfo.value)

    async def test_create_functional(
        self, tus_server: conftest.MockTusServer, memory_file: io.BytesIO
    ) -> None:
        """Test the normal functionality of the upload creation."""

        metadata = {"k1": b"1", "k2": "2²".encode(), "k-3": b"three"}

        endpoint = tus_server.server.make_url("/files")

        async with aiohttp.ClientSession() as session:
            location = await aiotus.creation.create(
                session, endpoint, memory_file, metadata
            )

        assert tus_server.upload_endpoint == location
