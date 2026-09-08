"""Both drivers must satisfy the same application-visible storage contract."""

from datetime import timedelta

import pytest
import requests  # type: ignore[import-untyped]

from oqtopus_cloud.common.storages import AbstractStorage


@pytest.mark.parametrize(
    "payload",
    [b"", b'{"shots": 1024}', bytes(range(256)) * 16],
    ids=["empty", "json", "binary"],
)
def test_put_get_overwrite_delete(storage: AbstractStorage, payload: bytes) -> None:
    key = "jobs/job-id/result.bin"
    assert storage.get(key) is None
    assert not storage.does_exist(key)
    assert not storage.is_file(key)
    assert not storage.is_directory(key)

    storage.put(key, payload)
    assert storage.get(key) == payload
    assert storage.does_exist(key)
    assert storage.is_file(key)
    assert not storage.is_directory(key)

    storage.put(key, b"replacement")
    assert storage.get(key) == b"replacement"
    storage.delete(key)
    assert storage.get(key) is None
    assert not storage.does_exist(key)
    storage.delete(key)
    assert storage.get(key) is None


def test_prefix_and_traverse(storage: AbstractStorage) -> None:
    objects = {
        "jobs/one/input.json": b"input",
        "jobs/one/nested/result.json": b"result",
        "jobs/two/result.json": b"other job",
    }
    for key, data in objects.items():
        storage.put(key, data)

    assert storage.is_directory("jobs/one")
    assert not storage.is_file("jobs/one")
    expected = {key for key in objects if key.startswith("jobs/one/")}
    assert set(storage.prefix("jobs/one")) == expected
    assert set(storage.prefix("jobs/one/")) == expected
    assert list(storage.prefix("absent")) == []
    assert set(storage.traverse_prefix("jobs/one", lambda key: key)) == expected
    storage.traverse_prefix("jobs/one", storage.delete)
    assert list(storage.prefix("jobs/one")) == []
    assert storage.get("jobs/two/result.json") == b"other job"


@pytest.mark.parametrize(
    "key", ["jobs/job-id/input.bin", "devices/日本語 info+%/data.bin"]
)
@pytest.mark.parametrize(
    "payload", [b"", bytes(range(256)) * 16], ids=["empty", "binary"]
)
def test_presigned_upload_download(
    storage: AbstractStorage, key: str, payload: bytes
) -> None:
    target = storage.get_upload_presigned_url_data(key, timedelta(minutes=5))
    with requests.post(
        target["url"],
        data=target["fields"],
        files={"file": ("payload.bin", payload, "application/octet-stream")},
        timeout=30,
    ) as response:
        assert response.status_code in (200, 201, 204)
    assert storage.get(key) == payload
    url = storage.get_download_presigned_url(key, timedelta(minutes=5))
    with requests.get(url, timeout=30) as response:
        assert response.status_code == 200
        assert response.content == payload
    storage.delete(key)
    with requests.get(url, timeout=30) as response:
        assert response.status_code == 404


def test_presigned_post_rejects_changed_key(storage: AbstractStorage) -> None:
    target = storage.get_upload_presigned_url_data("allowed.bin")
    fields = {**target["fields"], "key": "other.bin"}
    with requests.post(
        target["url"],
        data=fields,
        files={"file": ("payload.bin", b"must not be stored")},
        timeout=30,
    ) as response:
        assert response.status_code == 403
    assert storage.get("allowed.bin") is None
    assert storage.get("other.bin") is None


@pytest.mark.parametrize("payload", [b"", b"program"], ids=["empty", "nonempty"])
def test_traverse_deletes_object_with_trailing_slash(
    storage: AbstractStorage, payload: bytes
) -> None:
    key = "jobs/one/"
    storage.put(key, payload)
    assert storage.get(key) == payload
    assert list(storage.prefix("jobs/one")) == [key]
    storage.traverse_prefix("jobs/one", storage.delete)
    assert storage.get(key) is None
    assert list(storage.prefix("jobs/one")) == []
