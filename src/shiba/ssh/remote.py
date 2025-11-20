from typing import Union

import paramiko
import toolviper.utils.logger as logger

from shiba.utilities import credentials


@credentials
def connect(
    hostname: Union[str, None] = None,
    username: Union[str, None] = None,
    password: Union[str, None] = None,
) -> Union[paramiko.SSHClient, None]:
    """
    Connects to a remote host using SSH.

    Args:
        host (str): The hostname or IP address of the remote host.
        username (str): The username to use for authentication.
        password (str): The password to use for authentication.

    Returns:
        paramiko.SSHClient: An SSH client object connected to the remote host.
    """

    if hostname is not None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=hostname, username=username, password=password)

        return client

    else:
        logger.error("The hostname is None ...")
        return None


@credentials
def forward(
    hostname: Union[str, None] = None,
    username: Union[str, None] = None,
    password: Union[str, None] = None,
    port: Union[int, None] = 8000,
) -> int:
    import sshtunnel

    server = sshtunnel.SSHTunnelForwarder(
        hostname,
        ssh_username=username,
        ssh_password=password,
        remote_bind_address=("127.0.0.1", port),
    )

    server.start()

    logger.info(f"Binding to (local address, port): {server.local_bind_address} ...")

    return server.local_bind_port
