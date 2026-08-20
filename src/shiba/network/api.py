"""API utilities for gathering and uploading dataset files to Cloudflare R2 storage."""

from __future__ import annotations

import os
import pathlib
import zipfile
import boto3
import toolviper

from collections.abc import Sequence
from typing import Any
from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

DEFAULT_BUCKET_NAME = os.getenv("CLOUDFLARE_BUCKET_NAME", "public-data")
SPINNER = "dots"
console = Console()


class CloudflareClient:
    """Client wrapper for interacting with Cloudflare R2 storage via S3 API."""

    def __init__(
        self,
        account_id: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region_name: str = "auto",
    ) -> None:
        """Initialize the Cloudflare R2 S3 client.

        Args:
            account_id: Cloudflare account ID (defaults to CLOUDFLARE_ACCOUNT_ID env var).
            access_key_id: R2 access key ID (defaults to CLOUDFLARE_ACCESS_KEY_ID env var).
            secret_access_key: R2 secret access key (defaults to CLOUDFLARE_SECRET_ACCESS_KEY env var).
            region_name: S3 region name (default: "auto").

        Raises:
            ValueError: If required credentials are missing.
            ClientError: If client initialization fails.
        """
        self.account_id = account_id or os.getenv("CLOUDFLARE_ACCOUNT_ID")
        self.access_key_id = access_key_id or os.getenv("CLOUDFLARE_ACCESS_KEY_ID")
        self.secret_access_key = secret_access_key or os.getenv("CLOUDFLARE_SECRET_ACCESS_KEY")

        missing_vars = [
            var_name
            for var_name, val in [
                ("CLOUDFLARE_ACCOUNT_ID", self.account_id),
                ("CLOUDFLARE_ACCESS_KEY_ID", self.access_key_id),
                ("CLOUDFLARE_SECRET_ACCESS_KEY", self.secret_access_key),
            ]
            if not val
        ]

        if missing_vars:
            raise ValueError(
                f"Missing required Cloudflare credentials: {', '.join(missing_vars)}. "
                "Please set environment variables or pass credentials explicitly."
            )

        try:
            self.s3_client = boto3.client(
                service_name="s3",
                endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=region_name,
            )
        except (ClientError, BotoCoreError) as e:
            console.log(f"[red]Error initializing Cloudflare client: {e}[/red]")
            raise

    def upload_file(
        self,
        file_path: str | pathlib.Path,
        bucket_name: str = DEFAULT_BUCKET_NAME,
        key: str | None = None,
    ) -> None:
        """Upload a local file to the Cloudflare R2 bucket.

        Args:
            file_path: Path to the local file to upload.
            bucket_name: Target R2 bucket name.
            key: Destination object key in bucket (defaults to file name).
        """
        path = pathlib.Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        object_key = key or path.name
        self.s3_client.upload_file(
            Filename=str(path),
            Bucket=bucket_name,
            Key=object_key,
        )


def file_gather(
    directory: str | pathlib.Path,
    recursive: bool = False,
) -> list[pathlib.Path]:
    """Gather all valid zip archive files from a directory.

    Args:
        directory: Directory path to scan.
        recursive: Whether to scan subdirectories recursively.

    Returns:
        List of Path objects representing valid zip files.
    """
    dir_path = pathlib.Path(directory).resolve()
    if not dir_path.is_dir():
        console.log(f"[red]Provided path is not a directory: {dir_path}[/red]")
        raise NotADirectoryError(f"Directory not found or is not a directory: {dir_path}")

    files: list[pathlib.Path] = []
    iterator = dir_path.rglob("*") if recursive else dir_path.iterdir()

    with console.status(status="[bold green]Gathering files...", spinner=SPINNER):
        for path in iterator:
            if path.is_file() and zipfile.is_zipfile(path):
                files.append(path)

    return files


def load_manifest(manifest: str | pathlib.Path | None = None) -> tuple[pathlib.Path, dict[str, Any]]:
    """Resolve and load the download manifest JSON file.

    Args:
        manifest: Optional explicit path to manifest file.

    Returns:
        Tuple of (manifest_path, manifest_data_dict).
    """
    if manifest:
        manifest_path = pathlib.Path(manifest).resolve()

    else:
        current_path = pathlib.Path.cwd()
        toolviper.utils.data.update(path=str(current_path))
        manifest_path = current_path / "file.download.json"

    if not manifest_path.is_file():
        console.log(f"[red]Manifest not found at {manifest_path}...[/red]")
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    manifest_data = toolviper.utils.tools.open_json(file=str(manifest_path))
    return manifest_path, manifest_data


def upload(
    files: str | pathlib.Path | Sequence[str | pathlib.Path] | None = None,
    manifest: str | pathlib.Path | None = None,
    directory: str | pathlib.Path | None = None,
    bucket_name: str = DEFAULT_BUCKET_NAME,
) -> None:
    """Upload zip files to Cloudflare R2 bucket according to metadata paths in manifest.

    Args:
        files: Single file path or sequence of file paths to upload.
        manifest: Path to the download manifest JSON (defaults to current dir 'file.download.json').
        directory: Directory to gather zip files from if `files` is not explicitly provided.
        bucket_name: Destination bucket name.


    Raises:
        ValueError: If neither `files` nor `directory` is provided.
        FileNotFoundError: If manifest file does not exist.
    """
    target_files: list[pathlib.Path] = []

    if directory:
        target_files.extend(file_gather(directory))

    elif files:
        if isinstance(files, (str, pathlib.Path)):
            target_files.append(pathlib.Path(files).resolve())

        else:
            target_files.extend(pathlib.Path(f).resolve() for f in files)
    else:
        raise ValueError("Either 'files' or 'directory' must be provided to upload.")

    if not target_files:
        console.log("[yellow]No files found to upload.[/yellow]")
        return

    _, manifest_data = load_manifest(manifest)
    metadata = manifest_data.get("metadata", {})

    client = CloudflareClient()

    with Progress(
        SpinnerColumn(spinner_name=SPINNER),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[bold green]Uploading files...", total=len(target_files))

        for file_path in target_files:
            if not file_path.is_file():
                console.log(f"[red]File not found:[/red] {file_path}")
                progress.advance(task)
                continue

            filename = file_path.name
            file_meta = metadata.get(filename)

            if not file_meta or "path" not in file_meta:
                console.log(
                    f"[yellow]File {filename} not found in manifest metadata.[/yellow]\n"
                    "If it is a new file, add it to the manifest and try again."
                )
                progress.advance(task)
                continue

            key = file_meta["path"]
            try:
                client.upload_file(file_path=file_path, bucket_name=bucket_name, key=key)
                console.log(f"[green]Uploaded[/green] {filename} -> {key}")

            except (ClientError, BotoCoreError) as e:
                console.log(f"[red]Failed to upload {filename} to {key}: {e}[/red]")
                console.log(f"[red]Failed to upload {filename}: {e}[/red]")

            progress.advance(task)
