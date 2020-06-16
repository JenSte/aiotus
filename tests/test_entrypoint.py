"""Test the entrypoint module."""

import io
import os.path
import sys
import unittest.mock

import aiotus.entrypoint


class TestAiotusClients:
    def test_aiotus_clients(self, tusd):
        with unittest.mock.patch(
            "sys.argv", ["aiotus-upload", "--debug", str(tusd.url) + "x", __file__]
        ):
            assert 1 == aiotus.entrypoint.aiotus_upload()

        with unittest.mock.patch(
            "sys.argv", ["aiotus-upload", str(tusd.url), __file__ + "x"]
        ):
            assert 1 == aiotus.entrypoint.aiotus_upload()

        with unittest.mock.patch(
            "sys.argv", ["aiotus-upload", str(tusd.url), __file__]
        ):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.aiotus_upload()
                url = sys.stdout.getvalue().strip()

        expected_output = [
            f"filename: {os.path.basename(__file__)}",
            "mime_type: text/x-python",
        ]

        with unittest.mock.patch("sys.argv", ["aiotus-metadata", url]):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.aiotus_metadata()

                lines = sys.stdout.getvalue().splitlines(False)
                lines.sort()

                assert lines == expected_output

        with unittest.mock.patch("sys.argv", ["aiotus-metadata", "--debug", url]):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.aiotus_metadata()

                lines = sys.stdout.getvalue().splitlines(False)
                lines.sort()

                assert lines == expected_output

    def test_additional_metadata(self, tusd):
        with unittest.mock.patch(
            "sys.argv",
            [
                "aiotus-upload",
                "--metadata",
                "key1=value1",
                "--metadata",
                "key2",
                str(tusd.url),
                __file__,
            ],
        ):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.aiotus_upload()
                url = sys.stdout.getvalue().strip()

        with unittest.mock.patch("sys.argv", ["aiotus-metadata", url]):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.aiotus_metadata()

                lines = sys.stdout.getvalue().splitlines(False)
                assert "key1: value1" in lines
                assert "key2" in lines
