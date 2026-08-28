"""Tests for shiba.ssh module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import shiba.ssh as ssh
from shiba.ssh.remote import (
    client as ssh_client_sync,
    connect,
    deploy_server,
    forward,
    handler,
    install_server,
    secure_copy,
    start_server,
)


class TestSSHModuleExports(unittest.TestCase):
    """Test that shiba.ssh exports all required functions."""

    def test_exports(self):
        self.assertTrue(callable(ssh.client))
        self.assertTrue(callable(ssh.connect))
        self.assertTrue(callable(ssh.deploy_server))
        self.assertTrue(callable(ssh.forward))
        self.assertTrue(callable(ssh.install_server))
        self.assertTrue(callable(ssh.secure_copy))


class TestSSHConnect(unittest.TestCase):
    """Test connect function in shiba.ssh.remote."""

    @patch("shiba.ssh.remote.paramiko.SSHClient")
    def test_connect_with_explicit_credentials(self, mock_ssh_client_cls):
        mock_client = MagicMock()
        mock_ssh_client_cls.return_value = mock_client

        res = connect(
            hostname="test.example.com",
            username="testuser",
            password="testpassword",
        )

        mock_ssh_client_cls.assert_called_once()
        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once_with(
            hostname="test.example.com",
            username="testuser",
            password="testpassword",
        )
        self.assertEqual(res, mock_client)

    @patch("shiba.ssh.remote.logger.error")
    def test_connect_hostname_none(self, mock_logger_error):
        # We can test the underlying function when hostname is None by bypassing decorator or passing None through
        from shiba.ssh.remote import connect as decorated_connect
        # Unwrapped function
        unwrapped_connect = decorated_connect.__wrapped__

        with self.assertRaises(Exception):
            unwrapped_connect(hostname=None, username="user", password="pwd")

        mock_logger_error.assert_called_once_with("The hostname is None ...")

    @patch("shiba.utilities.getpass.getpass", return_value="mock_pwd")
    @patch("shiba.utilities.load_config")
    @patch("shiba.ssh.remote.paramiko.SSHClient")
    def test_connect_with_credentials_decorator_from_config(
        self, mock_ssh_client_cls, mock_load_config, mock_getpass
    ):
        mock_client = MagicMock()
        mock_ssh_client_cls.return_value = mock_client
        mock_load_config.return_value = {
            "connect": {
                "hostname": "config.example.com",
                "username": "config_user",
            }
        }

        res = connect()

        mock_client.connect.assert_called_once_with(
            hostname="config.example.com",
            username="config_user",
            password="mock_pwd",
        )
        self.assertEqual(res, mock_client)


class TestSSHForward(unittest.TestCase):
    """Test forward function in shiba.ssh.remote."""

    @patch("sshtunnel.SSHTunnelForwarder")
    def test_forward_with_explicit_args(self, mock_forwarder_cls):
        mock_server = MagicMock()
        mock_server.local_bind_port = 8888
        mock_server.local_bind_address = ("127.0.0.1", 8888)
        mock_forwarder_cls.return_value = mock_server

        port = forward(
            hostname="tunnel.example.com",
            username="tunneluser",
            password="tunnelpassword",
            port=9000,
        )

        mock_forwarder_cls.assert_called_once_with(
            "tunnel.example.com",
            ssh_username="tunneluser",
            ssh_password="tunnelpassword",
            remote_bind_address=("127.0.0.1", 9000),
        )
        mock_server.start.assert_called_once()
        self.assertEqual(port, 8888)

    @patch("sshtunnel.SSHTunnelForwarder")
    def test_forward_default_port(self, mock_forwarder_cls):
        mock_server = MagicMock()
        mock_server.local_bind_port = 8000
        mock_server.local_bind_address = ("127.0.0.1", 8000)
        mock_forwarder_cls.return_value = mock_server

        port = forward(
            hostname="tunnel.example.com",
            username="tunneluser",
            password="tunnelpassword",
        )

        mock_forwarder_cls.assert_called_once_with(
            "tunnel.example.com",
            ssh_username="tunneluser",
            ssh_password="tunnelpassword",
            remote_bind_address=("127.0.0.1", 8000),
        )
        mock_server.start.assert_called_once()
        self.assertEqual(port, 8000)


class TestSSHSecureCopyAndInstallServer(unittest.TestCase):
    """Test secure_copy and install_server in shiba.ssh.remote."""

    @patch("shiba.ssh.remote.scp.SCPClient")
    @patch("shiba.ssh.remote.connect")
    def test_secure_copy(self, mock_connect, mock_scp_cls):
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_client.__enter__.return_value = mock_client
        mock_connect.return_value = mock_client

        mock_scp = MagicMock()
        mock_scp.__enter__.return_value = mock_scp
        mock_scp_cls.return_value = mock_scp

        secure_copy(
            file="/path/to/local/file.txt",
            hostname="scp.example.com",
            username="scpuser",
            password="scppassword",
        )

        mock_connect.assert_called_once_with(
            "scp.example.com", "scpuser", "scppassword"
        )
        mock_scp_cls.assert_called_once_with(mock_transport)
        mock_scp.put.assert_called_once_with("/path/to/local/file.txt")

    @patch("shiba.ssh.remote.secure_copy")
    def test_install_server(self, mock_secure_copy):
        install_server(
            hostname="install.example.com",
            username="installuser",
            password="installpwd",
        )

        mock_secure_copy.assert_called_once()
        call_kwargs = mock_secure_copy.call_args.kwargs
        self.assertEqual(call_kwargs["hostname"], "install.example.com")
        self.assertEqual(call_kwargs["username"], "installuser")
        self.assertEqual(call_kwargs["password"], "installpwd")
        self.assertTrue(call_kwargs["file"].endswith("network/server.py") or "server.py" in call_kwargs["file"])


class TestSSHWebsocket(unittest.TestCase):
    """Test websocket communication in shiba.ssh.remote."""

    def test_handler(self):
        async def run_test():
            mock_ws = AsyncMock()
            mock_ws.recv.return_value = "World"

            await handler(mock_ws)

            mock_ws.recv.assert_awaited_once()
            mock_ws.send.assert_awaited_once_with("Hello World!")

        asyncio.run(run_test())

    @patch("websockets.asyncio.server.serve")
    def test_start_server(self, mock_serve):
        async def run_test():
            mock_server = MagicMock()
            mock_server.serve_forever = AsyncMock()
            mock_server_cm = AsyncMock()
            mock_server_cm.__aenter__.return_value = mock_server
            mock_serve.return_value = mock_server_cm

            await start_server()

            mock_serve.assert_called_once_with(handler, "localhost", 8765)
            mock_server.serve_forever.assert_awaited_once()

        asyncio.run(run_test())

    @patch("shiba.ssh.remote.start_server", new_callable=MagicMock)
    @patch("asyncio.run")
    def test_deploy_server(self, mock_asyncio_run, mock_start_server):
        dummy_coro = MagicMock()
        mock_start_server.return_value = dummy_coro

        deploy_server()

        mock_start_server.assert_called_once()
        mock_asyncio_run.assert_called_once_with(dummy_coro)

    @patch("builtins.input", return_value="Alice")
    @patch("websockets.sync.client.connect")
    def test_client(self, mock_connect, mock_input):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = "Hello Alice!"
        mock_ws_cm = MagicMock()
        mock_ws_cm.__enter__.return_value = mock_ws
        mock_connect.return_value = mock_ws_cm

        ssh_client_sync()

        mock_connect.assert_called_once_with("ws://localhost:8765")
        mock_input.assert_called_once_with("What's your name? ")
        mock_ws.send.assert_called_once_with("Alice")
        mock_ws.recv.assert_called_once()


if __name__ == "__main__":
    unittest.main()
