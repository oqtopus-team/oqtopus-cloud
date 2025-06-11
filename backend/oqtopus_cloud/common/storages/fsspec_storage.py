from typing import Iterator, cast

import fsspec

from oqtopus_cloud.common.storages.abstract_storage import AbstractStorage


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
        self.fs = fsspec.filesystem(self._get_protocol(fs_url), **storage_options)

    def _get_protocol(self, url: str) -> str:
        return url.split("://")[0]

    def put(self, key: str, data: bytes) -> None:
        full_path = f"{self.fs_url}/{key}"
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
        if self.fs.exists(full_path):
            self.fs.rm(full_path)

    def prefix(self, prefix: str) -> Iterator[str]:
        full_prefix = f"{self.fs_url}/{prefix}".rstrip("/")
        for dirpath, _, filenames in self.fs.walk(full_prefix):
            for filename in filenames:
                yield f"{dirpath}/{filename}"
