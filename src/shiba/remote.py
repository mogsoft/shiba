import paramiko

from shiba.utilities import credentials


@credentials
def connect(host: str, username: str, password: str) -> None:  # aramiko.SSHClient:
    """
    Connects to a remote host using SSH.

    Args:
        host (str): The hostname or IP address of the remote host.
        username (str): The username to use for authentication.
        password (str): The password to use for authentication.

    Returns:
        paramiko.SSHClient: An SSH client object connected to the remote host.
    """

    print(f"host: {host}, username: {username}, password: {password}")
    # client = paramiko.SSHClient()
    # client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # client.connect(host, username=username, password=password)

    # return client
