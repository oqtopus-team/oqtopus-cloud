"""Opt-in contracts against disposable, real S3-compatible backends."""

import os
from collections.abc import Iterator
from uuid import uuid4

import boto3
import pytest

from oqtopus_cloud.common.storages import AbstractStorage, get_storage


@pytest.fixture(params=["seaweedfs", "local:minio"])
def storage(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[AbstractStorage]:
    if os.environ.get("RUN_STORAGE_COMPATIBILITY") != "1":
        pytest.skip("Run make test-storage-compatibility to start both backends")

    driver = request.param
    prefix, port = (
        ("STORAGE_SEAWEEDFS", 18333)
        if driver == "seaweedfs"
        else ("STORAGE_LOCAL_MINIO", 19000)
    )
    # Deliberately independent of deployment settings: only disposable local
    # services from compose.yaml in this directory can receive test writes.
    endpoint = f"http://127.0.0.1:{port}"
    bucket = f"compatibility-{uuid4().hex}"
    monkeypatch.setenv("STORAGE_DRIVER", driver)
    for name, value in {
        "BUCKET_NAME": bucket,
        "USERNAME": "compatibility",
        "PASSWORD": "compatibility-secret",
        "ENDPOINT_URL": endpoint,
    }.items():
        monkeypatch.setenv(f"{prefix}_{name}", value)

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id="compatibility",
        aws_secret_access_key="compatibility-secret",
        region_name="us-east-1",
    )
    client.create_bucket(Bucket=bucket)
    try:
        yield get_storage()
    finally:
        # Use the SDK for fixture cleanup so a failing storage method does not
        # prevent cleanup. Each test owns its entire bucket.
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            for item in page.get("Contents", []):
                client.delete_object(Bucket=bucket, Key=item["Key"])
        client.delete_bucket(Bucket=bucket)
        client.close()
