"""Tests for shiba.network modules."""

import importlib
import unittest


class TestNetworkModules(unittest.TestCase):
    """Test importing network modules."""

    def test_import_client_module(self):
        mod = importlib.import_module("shiba.network.client")
        self.assertIsNotNone(mod)

    def test_import_server_module(self):
        mod = importlib.import_module("shiba.network.server")
        self.assertIsNotNone(mod)


if __name__ == "__main__":
    unittest.main()
