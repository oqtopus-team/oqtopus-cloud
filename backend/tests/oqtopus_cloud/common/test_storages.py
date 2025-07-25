import boto3
import fsspec
import pytest
import requests

# from datetime import timedelta
from moto import mock_aws
from urllib.parse import urlparse, parse_qs

from oqtopus_cloud.common.storages.fsspec_storage import S3PresignStrategy


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


@mock_aws
def test_s3_presign_strategy_upload_url_moto(s3_setup_moto):
    """
    Tests S3PresignStrategy for upload
    Mock AWS S3 service with moto
    """

    bucket_name = s3_setup_moto["bucket_name"]
    s3_client_moto = s3_setup_moto["s3_client_moto"]

    key = "data/test_file.txt"
    file_content = "test_content"

    s3_fs_instance = fsspec.filesystem("s3",
                                       **{"client_kwargs": {"region_name": "us-east-1"}})

    strategy = S3PresignStrategy(s3_fs=s3_fs_instance,
                                 bucket_name=bucket_name)

    presigned_url_data = strategy.get_upload_presigned_url_data(key)

    # basic verification of presinged URL
    assert presigned_url_data["url"] == "https://test-bucket.s3.amazonaws.com/"
    assert presigned_url_data["fields"]["key"] == "data/test_file.txt"
    assert "AWSAccessKeyId" in presigned_url_data["fields"]
    assert "policy" in presigned_url_data["fields"]
    assert "signature" in presigned_url_data["fields"]

    # use the presigned URL for upload
    files = {"file": (key, file_content)}
    response = requests.post(presigned_url_data["url"], data=presigned_url_data["fields"], files=files)
    assert response.status_code == 204

    # verify the object was actually created in the mock S3
    s3_object = s3_client_moto.get_object(Bucket=bucket_name,
                                          Key=key)
    assert s3_object["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert s3_object["Body"].read().decode() == file_content


@mock_aws
def test_s3_presign_strategy_download_url_moto(s3_setup_moto):
    """
    Tests S3PresignStrategy for download
    Mock AWS S3 service with moto
    """

    key = "data/test_file.txt"
    file_content = "test_content"

    bucket_name = s3_setup_moto["bucket_name"]
    s3_client_moto = s3_setup_moto["s3_client_moto"]
    s3_client_moto.put_object(Bucket=bucket_name, Key=key, Body=file_content)

    s3_fs_instance = fsspec.filesystem("s3",
                                       **{"client_kwargs": {"region_name": "us-east-1"}})

    strategy = S3PresignStrategy(s3_fs=s3_fs_instance,
                                 bucket_name=bucket_name)

    presigned_url = strategy.get_download_presigned_url(key)
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
