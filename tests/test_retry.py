"""Test the 'upload()' function."""

import aiohttp
import yarl

import aiotus


class TestRetry:
    async def test_upload_functional(self, tus_server, memory_file):
        """Test the normal functionality of the 'upload()' function."""

        metadata = {"Content-Type": "image/jpeg".encode(), "key": None}
        additional_headers = {"h1": "v1", "h2": "v2"}

        location = await aiotus.upload(
            tus_server["create_endpoint"],
            memory_file,
            metadata,
            headers=additional_headers,
        )

        assert location is not None
        assert tus_server["metadata"] == "Content-Type aW1hZ2UvanBlZw==, key"
        assert tus_server["data"] is not None
        assert tus_server["data"] == memory_file.getbuffer()
        assert tus_server["post_headers"] is not None
        assert "h1" in tus_server["post_headers"]
        assert tus_server["post_headers"]["h1"] == "v1"
        assert "h2" in tus_server["post_headers"]
        assert tus_server["post_headers"]["h2"] == "v2"

    async def test_upload_client_session(self, tus_server, memory_file):
        """Use a custom client session."""

        headers = {"Authorization": "Basic xyz"}
        md1 = {"key1": "value1".encode(), "key2": "value2".encode()}

        async with aiohttp.ClientSession(headers=headers) as s:
            location = await aiotus.upload(
                tus_server["create_endpoint"], memory_file, md1, client_session=s
            )

            additional_headers = {"h1": "v1", "h2": "v2"}
            md2 = await aiotus.metadata(
                location, client_session=s, headers=additional_headers
            )

            assert not s.closed

        assert tus_server["data"] is not None
        assert tus_server["data"] == memory_file.getbuffer()
        assert tus_server["post_headers"] is not None
        assert "Authorization" in tus_server["post_headers"]
        assert tus_server["post_headers"]["Authorization"] == headers["Authorization"]
        assert tus_server["head_headers"] is not None
        assert "h1" in tus_server["head_headers"]
        assert tus_server["head_headers"]["h1"] == "v1"
        assert "h2" in tus_server["head_headers"]
        assert tus_server["head_headers"]["h2"] == "v2"
        assert md1 == md2

    async def test_upload_wrong_metadata(self, tus_server, memory_file):
        """Test if wrong metadata is rejected."""

        metadata = {"²": "2".encode()}

        location = await aiotus.upload(
            tus_server["create_endpoint"], memory_file, metadata
        )

        assert location is None

    async def test_retry(self, tus_server, memory_file):
        """Test the retry functionality."""

        # Make the server fail a few times to test the retry logic.
        tus_server["retries_head"] = 3
        tus_server["retries_upload"] = 3

        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001)
        md1 = {"key1": "value1".encode(), "key2": "value2".encode()}

        location = await aiotus.upload(
            tus_server["create_endpoint"], memory_file, md1, config=config
        )

        assert location is not None
        assert tus_server["data"] is not None
        assert tus_server["data"] == memory_file.getbuffer()

        tus_server["retries_head"] = 3
        md2 = await aiotus.metadata(location, config=config)

        assert md1 == md2

        tus_server["retries_head"] = 11
        md = await aiotus.metadata(location, config=config)

        assert md is None

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

        md1 = {"key1": "value1".encode(), "key2": "value2".encode()}

        with open(__file__, "rb") as file:
            location = await aiotus.upload(tus_server["create_endpoint"], file, md1)

        assert location is not None
        assert tus_server["data"] is not None
        with open(__file__, "rb") as file:
            data = file.read()
            assert tus_server["data"] == data

        md2 = await aiotus.metadata(str(location))
        assert md1 == md2

    async def test_tusd(self, tusd, memory_file):
        """Test communication with the the tusd server."""

        data = memory_file.getvalue()

        location = await aiotus.upload(tusd.url, memory_file)

        async with aiohttp.ClientSession() as session:
            async with session.get(location) as response:
                body = await response.read()

                assert body == data

        md = await aiotus.metadata(str(location))
        assert not md  # We did not upload any metadata.

        # Upload a file with metadata to tusd, and check if we can read it back.
        md1 = {"key1": "value1".encode(), "key2": "value2".encode()}
        location = await aiotus.upload(tusd.url, memory_file, md1)

        md2 = await aiotus.metadata(location)
        assert md1 == md2
