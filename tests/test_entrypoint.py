"""Test the entrypoint module."""

import io
import os.path
import sys
import unittest.mock

import aiotus.entrypoint


class TestAiotusClients:
    def test_no_command(self):
        with unittest.mock.patch("sys.argv", [""]):
            with unittest.mock.patch("sys.stderr", new_callable=io.StringIO):
                assert 1 == aiotus.entrypoint.main()

                lines = sys.stderr.getvalue().splitlines(False)
                assert len(lines) >= 0
                assert lines[0] == "No command specified."

    def test_aiotus_clients(self, tusd):
        conf = aiotus.RetryConfiguration(1, 0.001, None)
        defaults = (None, None, conf, None, 4 * 1024 * 1024)
        with unittest.mock.patch.object(aiotus.upload, "__defaults__", defaults):
            with unittest.mock.patch(
                "sys.argv", ["", "--debug", "upload", str(tusd.url) + "x", __file__]
            ):
                assert 1 == aiotus.entrypoint.main()

        with unittest.mock.patch(
            "sys.argv", ["", "upload", str(tusd.url), __file__ + "x"]
        ):
            assert 1 == aiotus.entrypoint.main()

        with unittest.mock.patch("sys.argv", ["", "upload", str(tusd.url), __file__]):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.main()
                url = sys.stdout.getvalue().strip()

        expected_output = [
            f"filename: {os.path.basename(__file__)}",
            "mime_type: text/x-python",
        ]

        with unittest.mock.patch("sys.argv", ["", "metadata", url]):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.main()

                lines = sys.stdout.getvalue().splitlines(False)
                lines.sort()

                assert lines == expected_output

        with unittest.mock.patch("sys.argv", ["", "--debug", "metadata", url]):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.main()

                lines = sys.stdout.getvalue().splitlines(False)
                lines.sort()

                assert lines == expected_output

    def test_additional_metadata(self, tusd):
        with unittest.mock.patch(
            "sys.argv",
            [
                "",
                "upload",
                "--metadata",
                "key1=value1",
                "--metadata",
                "key2",
                str(tusd.url),
                __file__,
            ],
        ):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.main()
                url = sys.stdout.getvalue().strip()

        with unittest.mock.patch("sys.argv", ["", "metadata", url]):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO):
                assert 0 == aiotus.entrypoint.main()

                lines = sys.stdout.getvalue().splitlines(False)
                assert "key1: value1" in lines
                assert "key2" in lines
