import fsspec
import os

from datetime import timedelta
from s3fs import S3FileSystem  # type: ignore[import-untyped]
from typing import Any, Iterator, cast
from urllib.parse import urlparse

from oqtopus_cloud.common.storages.abstract_storage import AbstractStorage
from oqtopus_cloud.common.storages.presign_strategies import (
    GeneralPresignStrategy,
    S3PresignStrategy,
    LocalFilePresignStrategy,
)


class FSSpecStorage(AbstractStorage):
    """_summary_

    Args:
        AbstractStorage (_type_): _description_
    """

    fs: fsspec.AbstractFileSystem

    def __init__(self, fs_url: str, **storage_options):
        """
        :param fs_url: Storage URL scheme (e.g. "s3://my-bucket" or "file:///tmp")
        :param storage_options: options for specific storage driver (AWS credentials for s3 driver, etc)
        """
        self.fs_url = fs_url.rstrip("/")
        self._parsed_fs_url = urlparse(self.fs_url)
        self.fs = fsspec.filesystem(self._parsed_fs_url.scheme, **storage_options)
        self._presigned_url_strategy: GeneralPresignStrategy = (
            self._init_presign_strategy()
        )

    def _init_presign_strategy(self) -> GeneralPresignStrategy:
        if self._parsed_fs_url.scheme == "s3":
            return S3PresignStrategy(
                s3_fs=cast(S3FileSystem, self.fs),
                bucket_name=self._parsed_fs_url.netloc,
            )
        elif self._parsed_fs_url.scheme == "file":
            return LocalFilePresignStrategy(storage_path=self._parsed_fs_url.path)
        else:
            return GeneralPresignStrategy()

    def put(self, key: str, data: bytes, recursive: bool = True) -> None:
        full_path = f"{self.fs_url}/{key}"
        if recursive:
            local_path = cast(str, self.fs._strip_protocol(full_path))
            parent_dir = os.path.dirname(local_path)
            self.fs.makedirs(parent_dir, exist_ok=True)
        with self.fs.open(full_path, "wb") as f:
            f.write(data)

    def get(self, key: str) -> bytes | None:
        full_path = f"{self.fs_url}/{key}"
        if self.fs.exists(full_path):
            with self.fs.open(full_path, mode="rb") as f:
                return cast(bytes, f.read())
        else:
            return None

    def delete(self, key: str) -> None:
        full_path = f"{self.fs_url}/{key}"
        self.fs.rm(full_path)

    def does_exist(self, key: str) -> bool:
        return cast(bool, self.fs.exists(f"{self.fs_url}/{key}"))

    def is_file(self, key: str) -> bool:
        path = f"{self.fs_url}/{key}"
        return self.fs.exists(path) and not self.fs.isdir(path)

    def is_directory(self, key: str) -> bool:
        path = f"{self.fs_url}/{key}"
        return self.fs.exists(path) and cast(bool, self.fs.isdir(path))

    def prefix(self, prefix: str) -> Iterator[str]:
        full_prefix = f"{self.fs_url}/{prefix}".rstrip("/")
        storage_base = cast(str, self.fs._strip_protocol(self.fs_url))

        for dirpath, _, filenames in self.fs.walk(full_prefix):
            for filename in filenames:
                full_path = f"{dirpath}/{filename}"
                if full_path.startswith(storage_base):
                    relative_path = full_path[len(storage_base) :].lstrip("/")
                    yield relative_path

    def get_upload_presigned_url_data(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> dict[str, Any]:
        return self._presigned_url_strategy.get_upload_presigned_url_data(key, expires)

    def get_download_presigned_url(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> str:
        return self._presigned_url_strategy.get_download_presigned_url(key, expires)
