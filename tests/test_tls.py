"""Test uploading to a server behind a TLS proxy."""

import ssl

import aiohttp
import pytest  # type: ignore

import aiotus


class TestTLS:
    async def test_upload_fail(self, nginx_proxy, memory_file):
        """Test failed upload to a TLS server."""

        # Make sure we actually use encryption, access via plain
        # HTTP shall fail.
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiotus.ProtocolError) as excinfo:
                url = nginx_proxy.url.with_scheme("http")
                await aiotus.creation.create(session, url, memory_file, {})
        assert "Wrong status code" in str(excinfo.value)

        # As we use a self-signed certificate, the connection will fail.
        async with aiohttp.ClientSession() as session:
            with pytest.raises(aiohttp.ClientConnectorCertificateError) as excinfo:
                await aiotus.creation.create(session, nginx_proxy.url, memory_file, {})
        assert "certificate verify failed: self signed certificate" in str(
            excinfo.value
        )

        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001)
        location = await aiotus.upload(nginx_proxy.url, memory_file, config=config)
        assert location is None

    async def test_upload_verification_disabled(self, nginx_proxy, memory_file):
        """Test upload with TLS verification disabled."""

        async with aiohttp.ClientSession() as session:
            await aiotus.creation.create(
                session, nginx_proxy.url, memory_file, {}, ssl=False
            )

        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001, ssl=False)
        location = await aiotus.upload(nginx_proxy.url, memory_file, config=config)
        assert location is not None

    async def test_upload_functional(self, nginx_proxy, memory_file):
        """Test creation on a TLS server."""

        ssl_ctx = ssl.create_default_context(cafile=nginx_proxy.certificate)
        async with aiohttp.ClientSession() as session:
            await aiotus.creation.create(
                session, nginx_proxy.url, memory_file, {}, ssl=ssl_ctx
            )

        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001, ssl=ssl_ctx)
        location = await aiotus.upload(nginx_proxy.url, memory_file, config=config)
        assert location is not None
