import pathlib
from threading import ExceptHookArgs
from typing import Union

import paramiko
import scp
import toolviper.utils.logger as logger

from shiba.utilities import credentials


@credentials
def connect(
    hostname: Union[str, None] = None,
    username: Union[str, None] = None,
    password: Union[str, None] = None,
) -> paramiko.SSHClient:
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
        raise Exception()


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


@credentials
def secure_copy(
    file: str,
    hostname: Union[str, None] = None,
    username: Union[str, None] = None,
    password: Union[str, None] = None,
):
    # Find sever file.
    # file = pathlib.Path(__file__).parent.parent.joinpath("network") / "server.py"

    with connect(hostname, username, password) as client:
        with scp.SCPClient(client.get_transport()) as scp_:
            scp_.put(file)


@credentials
def install_server(
    hostname: Union[str, None] = None,
    username: Union[str, None] = None,
    password: Union[str, None] = None,
):
    file = str(pathlib.Path(__file__).parent.parent.joinpath("network") / "server.py")
    secure_copy(file=file, hostname=hostname, username=username, password=password)


### Network communication


async def handler(websocket):
    name = await websocket.recv()
    print(f"<<< {name}")

    greeting = f"Hello {name}!"

    await websocket.send(greeting)
    print(f">>> {greeting}")


async def start_server():
    from websockets.asyncio.server import serve

    async with serve(handler, "localhost", 8765) as server:
        await server.serve_forever()


def deploy_server():
    import asyncio

    asyncio.run(start_server())


def client():
    from websockets.sync.client import connect

    uri = "ws://localhost:8765"
    with connect(uri) as websocket:
        name = input("What's your name? ")

        websocket.send(name)
        print(f">>> {name}")

        greeting = websocket.recv()
        print(f"<<< {greeting}")
