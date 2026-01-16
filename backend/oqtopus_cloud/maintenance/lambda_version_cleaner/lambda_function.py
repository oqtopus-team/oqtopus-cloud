import boto3
import os

from oqtopus_cloud.maintenance.lambda_version_cleaner.conf import logger

VERSIONS_TO_KEEP = 1
CLEANUP_FUNCTION_PREFIX = os.getenv("CLEANUP_FUNCTION_PREFIX")

lambda_client = boto3.client("lambda")


def get_all_versions(function_name: str) -> list[str]:
    paginator = lambda_client.get_paginator("list_versions_by_function")

    return [
        v["Version"]
        for page in paginator.paginate(FunctionName=function_name)
        for v in page["Versions"]
        if v["Version"] != "$LATEST"
    ]


def get_aliased_versions(function_name: str) -> list[str]:
    paginator = lambda_client.get_paginator("list_aliases")

    return [
        alias["FunctionVersion"]
        for page in paginator.paginate(FunctionName=function_name)
        for alias in page["Aliases"]
        if alias["FunctionVersion"] != "$LATEST"
    ]


def cleanup_lambda_versions(function_name: str):
    logger.info(f"Cleanup check for: {function_name}")
    try:
        all_versions = get_all_versions(function_name)
        logger.debug(f"all_versions: {all_versions}")

        if not all_versions:
            logger.info(f"No versions for: {function_name}")
            return

        protected_recent = all_versions[-VERSIONS_TO_KEEP:]
        logger.debug(f"protected_recent: {protected_recent}")

        protected_aliased = get_aliased_versions(function_name)
        logger.debug(f"protected_aliased: {protected_aliased}")

        to_delete = [
            v
            for v in all_versions
            if v not in protected_aliased and v not in protected_recent
        ]
        logger.debug(f"to_delete: {to_delete}")

        if not to_delete:
            logger.info(f"No versions to delete for: {function_name}")
            return

        logger.info(f"Deleting versions: {to_delete}")
        for version in to_delete:
            lambda_client.delete_function(FunctionName=function_name, Qualifier=version)
            logger.debug(f"Deleted version: {version}")

    except Exception as e:
        logger.error(f"Failed to cleanup lambda {function_name}: {e}")


def lambda_handler(event, context):
    function_name = (
        event.get("detail", {}).get("requestParameters", {}).get("functionName")
    )

    if not function_name:
        logger.error("No function name provided")
        return {"statusCode": 400}

    if function_name != "*":
        # triggered by CloudWatch event for a specific function
        if not function_name.startswith(CLEANUP_FUNCTION_PREFIX):
            logger.error(f"Received event trigger for invalid function: {function_name}")
            return {"statusCode": 400}
        cleanup_lambda_versions(function_name)
    else:
        # manual trigger for all functions
        paginator = lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for function in page["Functions"]:
                if function["FunctionName"].startswith(CLEANUP_FUNCTION_PREFIX):
                    cleanup_lambda_versions(function["FunctionName"])

    return {"statusCode": 200}
