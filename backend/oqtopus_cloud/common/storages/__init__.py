__all__ = ["AbstractStorage", "FSSpecStorage"]
import logging
from os import environ

from oqtopus_cloud.common.storages.abstract_storage import AbstractStorage
from oqtopus_cloud.common.storages.fsspec_storage import FSSpecStorage

logger = logging.getLogger(__name__)


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
            # All four are required. Omitting any of them makes s3fs fall back
            # to AWS defaults instead: the real S3 endpoint, or the ambient AWS
            # credential chain. Credentials are not optional either -- a gateway
            # with no identity configured rejects every signed request, so it
            # cannot serve presigned URLs at all.
            bucket_name = environ["STORAGE_SEAWEEDFS_BUCKET_NAME"]
            access_key = environ["STORAGE_SEAWEEDFS_USERNAME"]
            secret_key = environ["STORAGE_SEAWEEDFS_PASSWORD"]
            endpoint_url = environ["STORAGE_SEAWEEDFS_ENDPOINT_URL"]
            return FSSpecStorage(
                fs_url=f"s3://{bucket_name}",
                key=access_key,
                secret=secret_key,
                client_kwargs={"endpoint_url": endpoint_url},
            )

        case "local:minio":
            # Deprecated alias kept so that an existing self-hosted deployment
            # survives the upgrade. The settings are read exactly as they were
            # before the seaweedfs driver was introduced, lax fallbacks
            # included, so nothing that works today changes behaviour.
            # Logged rather than raised as a DeprecationWarning, which Python
            # suppresses by default and an operator would never see.
            logger.warning(
                "STORAGE_DRIVER='local:minio' is deprecated and will be removed "
                "in a future release. Switch to STORAGE_DRIVER='seaweedfs' and "
                "the STORAGE_SEAWEEDFS_* settings."
            )
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

        case _:
            raise ValueError(f"Unknown storage driver: {storage_driver}")
