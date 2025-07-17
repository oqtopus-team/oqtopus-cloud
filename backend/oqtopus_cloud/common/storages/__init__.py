__all__ = ["AbstractStorage", "FSSpecStorage"]
from os import environ

from oqtopus_cloud.common.storages.abstract_storage import AbstractStorage
from oqtopus_cloud.common.storages.fsspec_storage import FSSpecStorage


def get_storage() -> AbstractStorage:
    storage_driver = environ.get("STORAGE_DRIVER", "s3")

    match storage_driver:
        case "s3":
            s3_bucket_name = environ.get("STORAGE_S3_BUCKET_NAME")
            s3_region = environ.get("STORAGE_S3_REGION")
            return FSSpecStorage(
                fs_url=f"s3://{s3_bucket_name}",
                client_kwargs={"region_name": s3_region},
            )

        case "local:minio":
            minio_bucket_name = environ.get("STORAGE_LOCAL_MINIO_BUCKET_NAME")
            minio_username = environ.get("STORAGE_LOCAL_MINIO_USERNAME")
            minio_password = environ.get("STORAGE_LOCAL_MINIO_PASSWORD")
            minio_endpoint_url = environ.get("STORAGE_LOCAL_MINIO_ENDPOINT_URL")
            return FSSpecStorage(
                fs_url=f"s3://{minio_bucket_name}",
                key=minio_username,
                secret=minio_password,
                client_kwargs={"endpoint_url": minio_endpoint_url},
            )

        case "local":
            local_base_path = environ.get("STORAGE_LOCAL_BASE_PATH", "/tmp/storage")
            return FSSpecStorage(fs_url=f"file://{local_base_path}")

        case _:
            raise ValueError(f"Unknown storage driver: {storage_driver}")
