"""Tests for shiba.network.api module."""

import os
import pathlib
import tempfile
import unittest
import zipfile
from unittest.mock import MagicMock, patch

from botocore.exceptions import BotoCoreError, ClientError

import shiba.network.api as api
from shiba.network.api import CloudflareClient, file_gather, load_manifest, upload


def create_dummy_zip(path: pathlib.Path) -> None:
    """Helper to create a valid zip archive file."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("test.txt", "hello world")


class TestCloudflareClient(unittest.TestCase):
    """Test CloudflareClient in shiba.network.api."""

    @patch("shiba.network.api.boto3.client")
    def test_init_with_explicit_credentials(self, mock_boto3_client):
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3

        client = CloudflareClient(
            account_id="acc123",
            access_key_id="key123",
            secret_access_key="sec123",
            region_name="auto",
        )

        mock_boto3_client.assert_called_once_with(
            service_name="s3",
            endpoint_url="https://acc123.r2.cloudflarestorage.com",
            aws_access_key_id="key123",
            aws_secret_access_key="sec123",
            region_name="auto",
        )
        self.assertEqual(client.s3_client, mock_s3)

    @patch("shiba.network.api.boto3.client")
    def test_init_with_env_vars(self, mock_boto3_client):
        env_vars = {
            "CLOUDFLARE_ACCOUNT_ID": "env_acc",
            "CLOUDFLARE_ACCESS_KEY_ID": "env_key",
            "CLOUDFLARE_SECRET_ACCESS_KEY": "env_sec",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            client = CloudflareClient()
            mock_boto3_client.assert_called_once_with(
                service_name="s3",
                endpoint_url="https://env_acc.r2.cloudflarestorage.com",
                aws_access_key_id="env_key",
                aws_secret_access_key="env_sec",
                region_name="auto",
            )
            self.assertEqual(client.account_id, "env_acc")
            self.assertEqual(client.access_key_id, "env_key")
            self.assertEqual(client.secret_access_key, "env_sec")

    def test_init_missing_credentials_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(KeyError):
                CloudflareClient()

        # If empty strings are in os.environ
        with patch.dict(
            os.environ,
            {
                "CLOUDFLARE_ACCOUNT_ID": "",
                "CLOUDFLARE_ACCESS_KEY_ID": "",
                "CLOUDFLARE_SECRET_ACCESS_KEY": "",
            },
            clear=True,
        ):
            with self.assertRaises(ValueError) as ctx:
                CloudflareClient()
            self.assertIn("Missing required Cloudflare credentials", str(ctx.exception))

        with patch.dict(
            os.environ,
            {
                "CLOUDFLARE_ACCOUNT_ID": "acc",
                "CLOUDFLARE_ACCESS_KEY_ID": "key",
                "CLOUDFLARE_SECRET_ACCESS_KEY": "",
            },
            clear=True,
        ):
            with self.assertRaises(ValueError) as ctx:
                CloudflareClient()
            self.assertIn("CLOUDFLARE_SECRET_ACCESS_KEY", str(ctx.exception))

    @patch("shiba.network.api.boto3.client")
    def test_init_boto_error_raises(self, mock_boto3_client):
        mock_boto3_client.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "CreateClient"
        )
        with self.assertRaises(ClientError):
            CloudflareClient(
                account_id="acc",
                access_key_id="key",
                secret_access_key="sec",
            )

    @patch("shiba.network.api.boto3.client")
    def test_upload_file_success(self, mock_boto3_client):
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        client = CloudflareClient(
            account_id="acc", access_key_id="key", secret_access_key="sec"
        )

        with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
            tmp_path = pathlib.Path(tmp.name)
            client.upload_file(
                file_path=tmp_path,
                bucket_name="my-bucket",
                key="destination/folder",
            )

            expected_key = str(pathlib.Path("destination/folder").joinpath(tmp_path.name))
            mock_s3.upload_file.assert_called_once_with(
                Filename=str(tmp_path.resolve()),
                Bucket="my-bucket",
                Key=expected_key,
            )

    @patch("shiba.network.api.boto3.client")
    def test_upload_file_nonexistent_raises(self, mock_boto3_client):
        client = CloudflareClient(
            account_id="acc", access_key_id="key", secret_access_key="sec"
        )
        with self.assertRaises(FileNotFoundError):
            client.upload_file(file_path="/non/existent/file.zip")


class TestFileGather(unittest.TestCase):
    """Test file_gather function in shiba.network.api."""

    def test_file_gather_not_a_directory(self):
        with self.assertRaises(NotADirectoryError):
            file_gather("/non/existent/directory/path")

    def test_file_gather_non_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = pathlib.Path(tmpdir)
            zip1 = tmpdir_path / "archive1.zip"
            create_dummy_zip(zip1)

            txt1 = tmpdir_path / "notes.txt"
            txt1.write_text("just text")

            subdir = tmpdir_path / "subdir"
            subdir.mkdir()
            zip2 = subdir / "archive2.zip"
            create_dummy_zip(zip2)

            gathered = file_gather(tmpdir_path, recursive=False)
            self.assertEqual(len(gathered), 1)
            self.assertEqual(gathered[0], zip1.resolve())

    def test_file_gather_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = pathlib.Path(tmpdir)
            zip1 = tmpdir_path / "archive1.zip"
            create_dummy_zip(zip1)

            subdir = tmpdir_path / "sub"
            subdir.mkdir()
            zip2 = subdir / "archive2.zip"
            create_dummy_zip(zip2)

            txt2 = subdir / "subnotes.txt"
            txt2.write_text("sub text")

            gathered = file_gather(tmpdir_path, recursive=True)
            self.assertEqual(len(gathered), 2)
            gathered_names = {f.name for f in gathered}
            self.assertEqual(gathered_names, {"archive1.zip", "archive2.zip"})


class TestLoadManifest(unittest.TestCase):
    """Test load_manifest function in shiba.network.api."""

    @patch("toolviper.utils.tools.open_json")
    def test_load_manifest_explicit_existing(self, mock_open_json):
        mock_open_json.return_value = {"metadata": {"file1.zip": {"path": "dest"}}}

        with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
            tmp_path = pathlib.Path(tmp.name)
            manifest_path, manifest_data = load_manifest(tmp_path)

            self.assertEqual(manifest_path, tmp_path.resolve())
            self.assertEqual(manifest_data, {"metadata": {"file1.zip": {"path": "dest"}}})
            mock_open_json.assert_called_once_with(file=str(tmp_path.resolve()))

    def test_load_manifest_explicit_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_manifest("/non/existent/manifest.json")

    @patch("toolviper.utils.data.update")
    @patch("toolviper.utils.tools.open_json")
    def test_load_manifest_default(self, mock_open_json, mock_data_update):
        mock_open_json.return_value = {"metadata": {}}
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = pathlib.Path(tmpdir)
            default_manifest = tmpdir_path / "file.download.json"
            default_manifest.write_text("{}")

            with patch("pathlib.Path.cwd", return_value=tmpdir_path):
                manifest_path, data = load_manifest()
                self.assertEqual(manifest_path, default_manifest)
                mock_data_update.assert_called_once_with(path=str(tmpdir_path))
                mock_open_json.assert_called_once_with(file=str(default_manifest))


class TestUpload(unittest.TestCase):
    """Test upload function in shiba.network.api."""

    def test_upload_no_files_no_directory_raises(self):
        with self.assertRaises(ValueError) as ctx:
            upload()
        self.assertIn("Either 'files' or 'directory' must be provided", str(ctx.exception))

    @patch("shiba.network.api.file_gather", return_value=[])
    def test_upload_empty_directory(self, mock_file_gather):
        # Should return gracefully without raising error
        upload(directory="/dummy/empty/dir")
        mock_file_gather.assert_called_once_with("/dummy/empty/dir")

    @patch("shiba.network.api.CloudflareClient")
    @patch("shiba.network.api.load_manifest")
    def test_upload_success_with_files(self, mock_load_manifest, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = pathlib.Path(tmpdir)
            file1 = tmpdir_path / "sample.ms.zarr.zip"
            create_dummy_zip(file1)

            manifest_path = tmpdir_path / "manifest.json"
            manifest_data = {
                "metadata": {
                    "sample.ms.zarr": {"path": "remote/astrohack"}
                }
            }
            mock_load_manifest.return_value = (manifest_path, manifest_data)

            upload(
                files=[str(file1)],
                manifest=manifest_path,
                bucket_name="custom-bucket",
            )

            mock_client.upload_file.assert_called_once_with(
                file_path=file1.resolve(),
                bucket_name="custom-bucket",
                key="remote/astrohack",
            )

    @patch("shiba.network.api.CloudflareClient")
    @patch("shiba.network.api.load_manifest")
    def test_upload_exact_filename_in_metadata(self, mock_load_manifest, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = pathlib.Path(tmpdir)
            file1 = tmpdir_path / "datafile.txt"
            file1.write_text("dummy data")

            manifest_path = tmpdir_path / "manifest.json"
            manifest_data = {
                "metadata": {
                    "datafile.txt": {"path": "exact/path"}
                }
            }
            mock_load_manifest.return_value = (manifest_path, manifest_data)

            upload(
                files=file1,
                manifest=manifest_path,
            )

            mock_client.upload_file.assert_called_once_with(
                file_path=file1.resolve(),
                bucket_name=api.DEFAULT_BUCKET_NAME,
                key="exact/path",
            )

    @patch("shiba.network.api.CloudflareClient")
    @patch("shiba.network.api.load_manifest")
    def test_upload_file_not_in_manifest(self, mock_load_manifest, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = pathlib.Path(tmpdir)
            file1 = tmpdir_path / "unknown.zip"
            create_dummy_zip(file1)

            manifest_path = tmpdir_path / "manifest.json"
            manifest_data = {"metadata": {}}
            mock_load_manifest.return_value = (manifest_path, manifest_data)

            upload(files=[file1], manifest=manifest_path)
            mock_client.upload_file.assert_not_called()

    @patch("shiba.network.api.CloudflareClient")
    @patch("shiba.network.api.load_manifest")
    def test_upload_missing_local_file(self, mock_load_manifest, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        manifest_data = {"metadata": {"missing.zip": {"path": "dest"}}}
        mock_load_manifest.return_value = (pathlib.Path("/manifest.json"), manifest_data)

        # Non-existent file passed directly
        upload(files=["/non/existent/missing.zip"], manifest="/manifest.json")
        mock_client.upload_file.assert_not_called()

    @patch("shiba.network.api.CloudflareClient")
    @patch("shiba.network.api.load_manifest")
    @patch("shiba.network.api.file_gather")
    def test_upload_with_directory_and_boto_error_handling(
        self, mock_file_gather, mock_load_manifest, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client.upload_file.side_effect = BotoCoreError()
        mock_client_cls.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = pathlib.Path(tmpdir)
            file1 = tmpdir_path / "data.zip"
            create_dummy_zip(file1)

            mock_file_gather.return_value = [file1]
            manifest_data = {"metadata": {"data": {"path": "target/data"}}}
            mock_load_manifest.return_value = (tmpdir_path / "m.json", manifest_data)

            # Should not raise BotoCoreError, but handle it gracefully
            upload(directory=tmpdir_path, manifest=tmpdir_path / "m.json")
            mock_client.upload_file.assert_called_once()


if __name__ == "__main__":
    unittest.main()
