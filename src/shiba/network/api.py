import toolviper
import pathlib
import zipfile

from rich.console import Console

logger = toolviper.utils.logger

BUCKET_NAME = "public-data"
SPINNER = "dots"

def file_gather(directory: str):

    files = []
    console = Console()

    with console.status(status="[bold green]Gathering files...", spinner=SPINNER) as status:
        for path in pathlib.Path(directory).iterdir():
            if zipfile.is_zipfile(path):
                files.append(str(path))

    return files

def upload(files: str | list[str], manifest: str, directory: str):

        if directory:
            files = file_gather(directory)

        if not isinstance(files, list):
            files = [files]

        current_path = pathlib.Path.cwd()
        if not manifest:
            toolviper.utils.data.update(path=str(current_path))
            manifest_path = current_path / "file.download.json"

        else:
            manifest_path = pathlib.Path(manifest)

        if not manifest_path.exists():
            logger.error(f"Manifest not found in {manifest_path.parent}...")
            raise FileNotFoundError()

        manifest = toolviper.utils.tools.open_json(file=str(manifest_path))

        client = CloudflareClient()

        console = Console()
        with console.status(status="[bold green]Uploading files...", spinner=SPINNER) as status:

            for file in files:
                try:
                    file_path = pathlib.Path(file).absolute()

                    if not file_path.exists():
                        raise FileNotFoundError()

                    filename = file_path.name

                    key = manifest["metadata"][filename]["path"]
                    client.bucket.upload(Filename=filename, Bucket=BUCKET_NAME, Key=key)
                    console.log(f"Uploaded {file} to {key}...")

                except FileNotFoundError:
                    console.log(f"File {file} not found in {file_path}...\n")
                    continue

                except KeyError:
                    console.log(f"File {file} not found in manifest...\n")
                    console.log("If it is a new file, add it to the manifest and try again.")
                    continue


class CloudflareClient:
    def __init__(self):
        import boto3
        import os
        from botocore.exceptions import ClientError

        ACCOUNT_ID = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        ACCESS_KEY_ID = os.environ["CLOUDFLARE_ACCESS_KEY_ID"]
        SECRET_ACCESS_KEY = os.environ["CLOUDFLARE_SECRET_ACCESS_KEY"]

        try:
            self.bucket = boto3.client(
                service_name="s3",
                endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
                aws_access_key_id=ACCESS_KEY_ID,
                aws_secret_access_key=SECRET_ACCESS_KEY,
                region_name="auto",
            )

        except ClientError as e:
            logger.error(f"Error initializing Cloudflare client: {e}")
            raise ClientError