"""Test the 'upload()' function."""

import aiohttp
import yarl

import aiotus


class TestUploadFile:
    async def test_upload_functional(self, tus_server, memory_file):
        """Test the normal functionality of the 'upload()' function."""

        metadata = {"Content-Type": "image/jpeg".encode(), "key": None}

        location = await aiotus.upload(
            tus_server["create_endpoint"], memory_file, metadata
        )

        assert location is not None
        assert tus_server["metadata"] == "Content-Type aW1hZ2UvanBlZw==, key"
        assert tus_server["data"] is not None
        assert tus_server["data"] == memory_file.getbuffer()

    async def test_upload_client_session(self, tus_server, memory_file):
        """Use a custom client session."""

        headers = {"Authorization": "Basic xyz"}

        async with aiohttp.ClientSession(headers=headers) as s:
            await aiotus.upload(
                tus_server["create_endpoint"], memory_file, client_session=s
            )

        assert tus_server["data"] is not None
        assert tus_server["data"] == memory_file.getbuffer()
        assert tus_server["headers"] is not None
        assert "Authorization" in tus_server["headers"]
        assert tus_server["headers"]["Authorization"] == headers["Authorization"]

    async def test_upload_wrong_metadata(self, tus_server, memory_file):
        """Test if wrong metadata is rejected."""

        metadata = {"²": "2".encode()}

        location = await aiotus.upload(
            tus_server["create_endpoint"], memory_file, metadata
        )

        assert location is None

    async def test_upload_retry(self, tus_server, memory_file):
        """Test the retry functionality."""

        # Make the server fail a few times to test the retry logic.
        tus_server["retries_offset"] = 3
        tus_server["retries_upload"] = 3

        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001)

        location = await aiotus.upload(
            tus_server["create_endpoint"], memory_file, config=config
        )

        assert location is not None
        assert tus_server["data"] is not None
        assert tus_server["data"] == memory_file.getbuffer()

    async def test_upload_create_retries_exceeded(self, tus_server, memory_file):
        """Not enough retries to create the upload."""

        tus_server["retries_create"] = 11

        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001)

        location = await aiotus.upload(
            tus_server["create_endpoint"], memory_file, config=config
        )

        assert location is None
        assert tus_server["data"] is None  # Upload could not be created.

    async def test_upload_upload_retries_exceeded(self, tus_server, memory_file):
        """Not enough retries to do the upload."""

        tus_server["retries_upload"] = 11

        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001)

        location = await aiotus.upload(
            tus_server["create_endpoint"], memory_file, config=config
        )

        assert location is None
        assert tus_server["data"] is not None  # Upload could be created.

    async def test_upload_relative_create(self, tus_server, memory_file):
        """Test what happens if the server returns a relative URL on creation."""

        # Make the create-handler return only the last part of the URL.
        path = tus_server["upload_endpoint"].path
        tus_server["upload_endpoint"] = yarl.URL(path.split("/")[-1])

        location = await aiotus.upload(tus_server["create_endpoint"], memory_file)

        assert location is not None
        assert tus_server["data"] is not None
        assert tus_server["data"] == memory_file.getbuffer()

    async def test_upload_file(self, tus_server):
        """Test upload of an actual file, not an 'io.BytesIO'."""

        with open(__file__, "rb") as file:
            location = await aiotus.upload(tus_server["create_endpoint"], file)

        assert location is not None
        assert tus_server["data"] is not None
        with open(__file__, "rb") as file:
            data = file.read()
            assert tus_server["data"] == data

    async def test_upload_tusd(self, tusd, memory_file):
        """Test upload to the tusd server."""

        data = memory_file.getvalue()

        location = await aiotus.upload(tusd.url, memory_file)

        async with aiohttp.ClientSession() as session:
            async with session.get(location) as response:
                body = await response.read()

                assert body == data
