"""Test uploading to a server behind a TLS proxy."""

from __future__ import annotations

import shutil
import ssl
from typing import TYPE_CHECKING

import aiohttp
import pytest

import aiotus

if TYPE_CHECKING:  # pragma: no cover
    import io

    from . import conftest


@pytest.mark.skipif(shutil.which("nginx") is None, reason="nginx not found")
class TestTLS:
    async def test_upload_fail(
        self, nginx_proxy: conftest.TusServer, memory_file: io.BytesIO
    ) -> None:
        """Test failed upload to a TLS server."""

        # Make sure we actually use encryption, access via plain
        # HTTP shall fail.
        http_url = nginx_proxy.url.with_scheme("http")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiohttp.ClientResponseError) as excinfo:
                await aiotus.creation.create(session, http_url, memory_file, {})
            assert excinfo.value.status == 400

        # As we use a self-signed certificate, the connection will fail.
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiohttp.ClientConnectorCertificateError) as excinfo:
                await aiotus.creation.create(session, nginx_proxy.url, memory_file, {})

            messages = [
                "certificate verify failed: self signed certificate",
                "certificate verify failed: self-signed certificate",
            ]
            assert any(m in str(excinfo.value) for m in messages)

        # The retrying upload function returns 'None', as the upload fails.
        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001)
        location = await aiotus.upload(nginx_proxy.url, memory_file, config=config)
        assert location is None

        # Uploading with TLS verification disabled shall work.
        async with aiohttp.ClientSession() as session:
            await aiotus.creation.create(
                session, nginx_proxy.url, memory_file, {}, ssl=False
            )

        # With TLS verification disabled the creation works.
        config = aiotus.RetryConfiguration(ssl=False)
        location = await aiotus.upload(nginx_proxy.url, memory_file, config=config)
        assert location is not None

        # Fetching the metadata over HTTP fails.
        http_location = location.with_scheme("http")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiohttp.ClientResponseError) as excinfo:
                await aiotus.core.metadata(session, http_location)
            assert "Bad Request" in str(excinfo.value)

    async def test_upload_functional(
        self, nginx_proxy: conftest.TusServer, memory_file: io.BytesIO
    ) -> None:
        """Test creation on a TLS server."""

        ssl_ctx = ssl.create_default_context(cafile=nginx_proxy.certificate)
        async with aiohttp.ClientSession() as session:
            await aiotus.creation.create(
                session, nginx_proxy.url, memory_file, {}, ssl=ssl_ctx
            )

        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001, ssl=ssl_ctx)
        location = await aiotus.upload(nginx_proxy.url, memory_file, config=config)
        assert location is not None
