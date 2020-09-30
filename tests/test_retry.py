"""Test the 'upload()' function."""

import io
import logging

import aiohttp
import pytest  # type: ignore
import tenacity  # type: ignore
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
        assert tus_server["metadata"] == "Content-Type aW1hZ2UvanBlZw==,key"
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


class TestUploadMultiple:
    """Test the 'aiotus.upload_multiple()' function."""

    async def test_upload_functional(self, tusd, memory_file):
        """Upload files, read back as a single file."""

        file_a = io.BytesIO(b"\x00\x01")
        file_b = io.BytesIO(b"\x02\x03")
        file_c = io.BytesIO(b"\x04\x05")
        file_d = io.BytesIO(b"\x06\x07")

        md1 = {"key": "value".encode()}

        location = await aiotus.upload_multiple(
            tusd.url, [file_a, file_b, file_c, file_d], md1
        )

        md2 = await aiotus.metadata(location)
        assert md1 == md2

        async with aiohttp.ClientSession() as session:
            async with session.get(location) as response:
                body = await response.read()

                assert body == b"\x00\x01\x02\x03\x04\x05\x06\x07"

    async def test_upload_functional_session(self, tusd, memory_file):
        """Upload files, read back as a single file, passing in a HTTP session."""

        file_a = io.BytesIO(b"\x00\x01")
        file_b = io.BytesIO(b"\x02\x03")
        file_c = io.BytesIO(b"\x04\x05")
        file_d = io.BytesIO(b"\x06\x07")

        async with aiohttp.ClientSession() as session:
            location = await aiotus.upload_multiple(
                tusd.url, [file_a, file_b, file_c, file_d], None, session
            )

            md = await aiotus.metadata(location)
            assert not md

            async with session.get(location) as response:
                body = await response.read()

                assert body == b"\x00\x01\x02\x03\x04\x05\x06\x07"

    async def test_not_supported(self, tus_server, memory_file):
        """Try uploading to a server that does not support concatenation."""

        location = await aiotus.upload_multiple(
            tus_server["create_endpoint"], [memory_file]
        )
        assert location is None

    async def test_part_failure(self, tusd):
        """Check the handling of a failure to upload a part."""

        file_a = io.BytesIO(b"\x00\x01")
        file_b = open("/proc/self/mem", "rb")

        location = await aiotus.upload_multiple(tusd.url, [file_a, file_b])
        assert location is None

    async def test_timeout(self, tus_server, memory_file):
        """Test handling of the retry exception."""

        tus_server["retries_options"] = 20

        config = aiotus.RetryConfiguration(max_retry_period_seconds=0.001)
        location = await aiotus.upload_multiple(
            tus_server["create_endpoint"], [memory_file], config=config
        )

        assert location is None


class TestTenacity:
    """Test the log functions for tenacity."""

    async def test_exception_logging(self, caplog):
        rt = tenacity.AsyncRetrying(
            retry=tenacity.retry_if_exception_type(RuntimeError),
            stop=tenacity.stop_after_attempt(3),
            before=aiotus.retry._make_log_before_function("test"),
            before_sleep=aiotus.retry._make_log_before_sleep_function("test"),
        )

        with caplog.at_level(logging.INFO, logger="aiotus"):
            with pytest.raises(tenacity.RetryError):
                await rt.call(TestTenacity.raise_runtime_error)

            lg = caplog.record_tuples
            assert len(lg) == 4
            assert lg[0][2] == "Test failed, retrying in 0 second(s): test error"
            assert lg[1][2] == "Trying test again, attempt number 2..."
            assert lg[2][2] == "Test failed, retrying in 0 second(s): test error"
            assert lg[3][2] == "Trying test again, attempt number 3..."

    async def test_result_logging(self, caplog):
        rt = tenacity.AsyncRetrying(
            retry=tenacity.retry_if_result(lambda r: r is None),
            stop=tenacity.stop_after_attempt(2),
            before=aiotus.retry._make_log_before_function("test"),
            before_sleep=aiotus.retry._make_log_before_sleep_function("test"),
        )

        with caplog.at_level(logging.INFO, logger="aiotus"):
            with pytest.raises(tenacity.RetryError):
                await rt.call(TestTenacity.return_none)

            lg = caplog.record_tuples
            assert len(lg) == 2
            assert lg[0][2] == "Test failed, retrying in 0 second(s): None"
            assert lg[1][2] == "Trying test again, attempt number 2..."

    @staticmethod
    async def raise_runtime_error():
        raise RuntimeError("test error")

    @staticmethod
    async def return_none():
        return None
