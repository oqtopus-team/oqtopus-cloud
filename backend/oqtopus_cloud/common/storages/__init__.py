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

        case "local":
            local_base_path = environ.get("STORAGE_LOCAL_BASE_PATH", "/tmp/storage")
            return FSSpecStorage(fs_url=f"file://{local_base_path}")

        case "seaweedfs":
            # Bucket and endpoint are required: without them s3fs would silently
            # fall back to AWS S3. Credentials stay optional, since a SeaweedFS
            # gateway with no configured identity accepts anonymous access.
            bucket_name = environ["STORAGE_SEAWEEDFS_BUCKET_NAME"]
            access_key = environ.get("STORAGE_SEAWEEDFS_USERNAME")
            secret_key = environ.get("STORAGE_SEAWEEDFS_PASSWORD")
            endpoint_url = environ["STORAGE_SEAWEEDFS_ENDPOINT_URL"]
            return FSSpecStorage(
                fs_url=f"s3://{bucket_name}",
                key=access_key,
                secret=secret_key,
                client_kwargs={"endpoint_url": endpoint_url},
            )

        case _:
            raise ValueError(f"Unknown storage driver: {storage_driver}")
