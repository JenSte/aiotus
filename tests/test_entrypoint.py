"""Test the entrypoint module."""

import unittest.mock

import aiotus.entrypoint


class TestAiotusClient:
    def test_aiotus_client(self, tusd):
        with unittest.mock.patch(
            "sys.argv", ["aiotus-client", str(tusd.url) + "x", __file__]
        ):
            assert 1 == aiotus.entrypoint.aiotus_client()

        with unittest.mock.patch(
            "sys.argv", ["aiotus-client", str(tusd.url), __file__]
        ):
            assert 0 == aiotus.entrypoint.aiotus_client()
