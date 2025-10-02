"""Test the entrypoint module."""

from __future__ import annotations

import os.path
import unittest.mock
from typing import TYPE_CHECKING

import aiotus.entrypoint

if TYPE_CHECKING:  # pragma: no cover
    import pytest

    from . import conftest


class TestAiotusClients:
    def test_no_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        with unittest.mock.patch("sys.argv", [""]):
            assert aiotus.entrypoint.main() == 1

        _, stderr = capsys.readouterr()
        lines = stderr.splitlines(keepends=False)
        assert len(lines) >= 0
        assert lines[0] == "No command specified."

    def test_aiotus_clients(
        self, capsys: pytest.CaptureFixture[str], tusd: conftest.TusServer
    ) -> None:
        conf = aiotus.RetryConfiguration(1, 0.001, ssl=False)
        defaults = (None, None, conf, None, 4 * 1024 * 1024)
        with (
            unittest.mock.patch.object(aiotus.upload, "__defaults__", defaults),
            unittest.mock.patch(
                "sys.argv", ["", "--debug", "upload", str(tusd.url) + "x", __file__]
            ),
        ):
            assert aiotus.entrypoint.main() == 1

        with unittest.mock.patch(
            "sys.argv", ["", "upload", str(tusd.url), __file__ + "x"]
        ):
            assert aiotus.entrypoint.main() == 1

        with unittest.mock.patch("sys.argv", ["", "upload", str(tusd.url), __file__]):
            assert aiotus.entrypoint.main() == 0

        stdout, _ = capsys.readouterr()
        url = stdout.splitlines(keepends=False)[0]

        expected_output = [
            f"filename: {os.path.basename(__file__)}",
            "mime_type: text/x-python",
        ]

        with unittest.mock.patch("sys.argv", ["", "metadata", url]):
            assert aiotus.entrypoint.main() == 0

        stdout, _ = capsys.readouterr()
        lines = stdout.splitlines(keepends=False)
        lines.sort()

        assert lines == expected_output

        with unittest.mock.patch("sys.argv", ["", "--debug", "metadata", url]):
            assert aiotus.entrypoint.main() == 0

        stdout, _ = capsys.readouterr()
        lines = stdout.splitlines(keepends=False)
        lines.sort()
        assert lines == expected_output

    def test_additional_metadata(
        self, capsys: pytest.CaptureFixture[str], tusd: conftest.TusServer
    ) -> None:
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
            assert aiotus.entrypoint.main() == 0

        stdout, _ = capsys.readouterr()
        url = stdout.splitlines(keepends=False)[0]

        with unittest.mock.patch("sys.argv", ["", "metadata", url]):
            assert aiotus.entrypoint.main() == 0

        stdout, _ = capsys.readouterr()
        lines = stdout.splitlines(keepends=False)
        assert "key1: value1" in lines
        assert "key2" in lines
