import boto3
import fsspec
import pytest
import requests

from moto import mock_aws
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse, parse_qs

from oqtopus_cloud.common.storages.fsspec_storage import FSSpecStorage
from oqtopus_cloud.common.storages.presign_strategies import (
    GeneralPresignStrategy,
    LocalFilePresignStrategy,
    S3PresignStrategy,
)


@pytest.fixture
def s3_setup_moto():
    """
    Pytest fixture to set up a mock S3 environment for testing.
    Mock AWS S3 service with moto
    """

    bucket_name = "test-bucket"
    region = "us-east-1"

    with mock_aws():
        s3_client_moto = boto3.client("s3", region_name=region)
        s3_client_moto.create_bucket(Bucket=bucket_name)

        yield {
            "bucket_name": bucket_name,
            "s3_client_moto": s3_client_moto,
        }


def test_fsspec_storage_s3_upload_url_moto(s3_setup_moto):
    """
    Tests FSSpecStorage with S3 for upload
    Mock AWS S3 service with moto
    """

    bucket_name = s3_setup_moto["bucket_name"]
    s3_client_moto = s3_setup_moto["s3_client_moto"]

    key = "data/test_file.txt"
    file_content = "test_content"

    # create storage
    fs_url = f"s3://{bucket_name}"
    storage_options = {"client_kwargs": {"region_name": "us-east-1"}}
    storage = FSSpecStorage(fs_url=fs_url, **storage_options)

    # verify strategy
    assert isinstance(storage._presigned_url_strategy, S3PresignStrategy)

    # get & check presigned URL
    presigned_url_data = storage.get_upload_presigned_url_data(key)

    assert presigned_url_data["url"] == "https://test-bucket.s3.amazonaws.com/"
    assert presigned_url_data["fields"]["key"] == "data/test_file.txt"
    assert "AWSAccessKeyId" in presigned_url_data["fields"]
    assert "policy" in presigned_url_data["fields"]
    assert "signature" in presigned_url_data["fields"]

    # use the presigned URL for upload
    files = {"file": (key, file_content)}
    response = requests.post(
        presigned_url_data["url"], data=presigned_url_data["fields"], files=files
    )
    assert response.status_code == 204

    # verify the object was actually created in the mock S3
    s3_object = s3_client_moto.get_object(Bucket=bucket_name, Key=key)
    assert s3_object["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert s3_object["Body"].read().decode() == file_content


def test_fsspec_storage_s3_download_url_moto(s3_setup_moto):
    """
    Tests FSSpecStorage with S3 for download
    Mock AWS S3 service with moto
    """

    key = "data/test_file.txt"
    file_content = "test_content"

    # upload test file
    bucket_name = s3_setup_moto["bucket_name"]
    s3_client_moto = s3_setup_moto["s3_client_moto"]
    s3_client_moto.put_object(Bucket=bucket_name, Key=key, Body=file_content)

    # create storage
    fs_url = f"s3://{bucket_name}"
    storage_options = {"client_kwargs": {"region_name": "us-east-1"}}
    storage = FSSpecStorage(fs_url=fs_url, **storage_options)

    # verify strategy
    assert isinstance(storage._presigned_url_strategy, S3PresignStrategy)

    # get & check presigned URL
    presigned_url = storage.get_download_presigned_url(key)
    parsed_presigned_url = urlparse(presigned_url)
    query_params = parse_qs(parsed_presigned_url.query).keys()

    assert parsed_presigned_url.scheme == "https"
    assert parsed_presigned_url.netloc == f"{bucket_name}.s3.amazonaws.com"
    assert parsed_presigned_url.path == f"/{key}"
    assert "AWSAccessKeyId" in query_params
    assert "Signature" in query_params
    assert "Expires" in query_params

    # use the presigned URL for download
    response = requests.get(presigned_url)

    # verify downloaded file
    assert response.status_code == 200
    assert response.text == file_content


def test_fsspec_storage_local_file_upload_url(tmp_path):
    """
    Tests FSSpecStorage with local filesystem for upload
    """

    storage_base = tmp_path
    key = "data/test_file.txt"

    # create storage
    fs_url = f"file://{storage_base}"
    storage = FSSpecStorage(fs_url=fs_url)

    # verify strategy
    assert isinstance(storage._presigned_url_strategy, LocalFilePresignStrategy)

    # get & check presigned URL
    presigned_url_data = storage.get_upload_presigned_url_data(key)

    assert presigned_url_data["url"] == f"file://{storage_base}/{key}"
    assert presigned_url_data["fields"] == {
        "key": f"file://{storage_base}/{key}"
    }


def test_fsspec_storage_local_file_download_url(tmp_path):
    """
    Tests FSSpecStorage with local filesystem for download
    """

    storage_base = tmp_path
    key = "data/test_file.txt"

    # create storage
    fs_url = f"file://{storage_base}"
    storage = FSSpecStorage(fs_url=fs_url)

    # verify strategy
    assert isinstance(storage._presigned_url_strategy, LocalFilePresignStrategy)

    # get & check presigned URL
    presigned_url = storage.get_download_presigned_url(key)
    assert presigned_url == f"file://{storage_base}/{key}"


@patch("fsspec.filesystem")
def test_fsspec_storage_unsupported_protocol(mock_filesystem):
    """
    Tests FSSpecStorage with protocol without presigned URL support (ftp)
    Mock fsspec.filesystem to prevent actual FTP connection attempt
    """

    mock_generic_fs = MagicMock(spec=fsspec.AbstractFileSystem)
    mock_filesystem.return_value = mock_generic_fs

    fs_url = "ftp://test_user:test_pass@ftp-server:21/data/test_file.txt"
    storage = FSSpecStorage(fs_url=fs_url)

    assert isinstance(storage._presigned_url_strategy, GeneralPresignStrategy)

    with pytest.raises(
        NotImplementedError,
        match="This storage protocol does not support presigned upload URLs.",
    ):
        storage.get_upload_presigned_url_data("key")
    with pytest.raises(
        NotImplementedError,
        match="This storage protocol does not support presigned download URLs.",
    ):
        storage.get_download_presigned_url("key")
