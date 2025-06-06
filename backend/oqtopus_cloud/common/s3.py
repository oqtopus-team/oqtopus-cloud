import os

import boto3
import botocore

from oqtopus_cloud.user.conf import logger

JOB_INFO_INPUT_PARAM = "input"
JOB_INFO_COMBINED_PROGRAM_PARAM = "combined_program"
JOB_INFO_RESULT_PARAM = "result"
JOB_INFO_TRANSPILE_RESULT_PARAM = "transpile_result"
JOB_INFO_SSE_LOG_PARAM = "sse_log"

DEFAULT_PRESIGNED_ULR_EXP_S = 60 * 60  # 1h
DEFAULT_MAX_UPLOAD_CONTENT_LENGTH_B = 50 * 1024 * 1024  # 50Mb


def get_download_presigned_url(bucket: str, key: str) -> str:
    return boto3.client("s3").generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": key,
        },
        ExpiresIn=int(
            os.environ.get("PRESIGNED_ULR_EXP_S", DEFAULT_PRESIGNED_ULR_EXP_S)
        ),
    )


def get_upload_presigned_url_data(bucket: str, key: str) -> dict:
    presigned_data = boto3.client("s3").generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Conditions=[
            [
                "content-length-range",
                0,
                int(
                    os.environ.get(
                        "MAX_UPLOAD_CONTENT_LENGTH",
                        DEFAULT_MAX_UPLOAD_CONTENT_LENGTH_B,
                    )
                ),
            ]
        ],
        ExpiresIn=int(
            os.environ.get("PRESIGNED_ULR_EXP_S", DEFAULT_PRESIGNED_ULR_EXP_S)
        ),
    )
    return presigned_data


def validate_upload(bucket: str, key: str) -> bool:
    try:
        boto3.client("s3").head_object(
            Bucket=bucket,
            Key=key,
        )
        return True

    except botocore.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            logger.info(f"job information input file: {key} not found")
            return False
        else:
            logger.error(f"job information input file: {key} not accessible")
            raise exc
