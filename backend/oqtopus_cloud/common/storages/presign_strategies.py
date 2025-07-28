import os

from abc import ABC, abstractmethod
from datetime import timedelta
from fsspec.asyn import sync  # type: ignore[import-untyped]
from s3fs import S3FileSystem  # type: ignore[import-untyped]
from typing import Any


class AbstractPresignStrategy(ABC):
    """
    Interface for presigned URL generation strategies.
    """

    @abstractmethod
    def get_upload_presigned_url_data(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> dict[str, Any]: ...

    @abstractmethod
    def get_download_presigned_url(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> str: ...


class GeneralPresignStrategy(AbstractPresignStrategy):
    """
    General presigned URL strategy valid for all storage types (including storage types that genuinely do not support presigned URLs).
    It will always raise NotImplementedError.
    """

    def get_upload_presigned_url_data(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "This storage protocol does not support presigned upload URLs."
        )

    def get_download_presigned_url(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> str:
        raise NotImplementedError(
            "This storage protocol does not support presigned download URLs."
        )


class S3PresignStrategy(GeneralPresignStrategy):
    """
    Presigned URL strategy for AWS S3 compatible storages (S3, minIO) using boto3.
    """

    def __init__(self, s3_fs: S3FileSystem, bucket_name: str):
        if not isinstance(s3_fs, S3FileSystem):
            raise TypeError("S3PresignStrategy requires an s3fs.S3FileSystem instance.")
        self._fs = s3_fs
        self._bucket_name = bucket_name

    def get_upload_presigned_url_data(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> dict[str, Any]:
        # underlying S3FileSystem's client is async
        presigned_url_data = sync(
            self._fs.loop,  # event-loop owned by s3fs
            self._fs.s3.generate_presigned_post,  # coroutine function
            Bucket=self._bucket_name,
            Key=key,
            ExpiresIn=int(
                expires.total_seconds(),
            ),
        )
        return presigned_url_data

    def get_download_presigned_url(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> str:
        # underlying S3FileSystem's client is async
        presigned_url = sync(
            self._fs.loop,  # event-loop owned by s3fs
            self._fs.s3.generate_presigned_url,  # coroutine function
            ClientMethod="get_object",
            Params={"Bucket": self._bucket_name, "Key": key},
            ExpiresIn=expires.total_seconds(),
        )
        return presigned_url


class LocalFilePresignStrategy(GeneralPresignStrategy):
    """
    "Simulates" presigned URLs for local filesystem by returning direct file:// paths.
    """

    def __init__(self, storage_path: str):
        self._storage_path = storage_path.rstrip("/")

    def get_upload_presigned_url_data(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> dict[str, Any]:
        full_path = os.path.join(self._storage_path, key)
        return {"url": f"file://{full_path}", "fields": {}}

    def get_download_presigned_url(
        self, key: str, expires: timedelta = timedelta(hours=1)
    ) -> str:
        full_path = os.path.join(self._storage_path, key)
        return f"file://{full_path}"
