import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

cognito = boto3.client("cognito-idp")
s3 = boto3.client("s3")


def _serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _list_users(user_pool_id):
    users = []
    paginator = cognito.get_paginator("list_users")
    for page in paginator.paginate(UserPoolId=user_pool_id):
        users.extend(page["Users"])
    return users


def _list_groups_with_members(user_pool_id):
    groups = []
    group_paginator = cognito.get_paginator("list_groups")
    member_paginator = cognito.get_paginator("list_users_in_group")
    for page in group_paginator.paginate(UserPoolId=user_pool_id):
        for group in page["Groups"]:
            members = []
            for member_page in member_paginator.paginate(
                UserPoolId=user_pool_id, GroupName=group["GroupName"]
            ):
                members.extend(user["Username"] for user in member_page["Users"])
            group["Members"] = members
            groups.append(group)
    return groups


def lambda_handler(event, context):
    bucket = os.environ["BACKUP_BUCKET"]
    pool_ids = [p for p in os.environ["USER_POOL_IDS"].split(",") if p]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    # The invocation id keeps the key unique even if two runs land in the same
    # second (e.g. a manual re-run alongside the schedule), so a backup is never
    # silently overwritten (the bucket is intentionally not versioned).
    run_id = getattr(context, "aws_request_id", "manual")

    results = {}
    failures = {}
    # Back up each pool independently so one pool's failure does not skip the
    # others; still fail the invocation at the end so the failure is alarmable.
    for pool_id in pool_ids:
        try:
            backup = {
                "user_pool_id": pool_id,
                "backed_up_at": timestamp,
                "users": _list_users(pool_id),
                "groups": _list_groups_with_members(pool_id),
            }
            key = f"{pool_id}/{timestamp}-{run_id}.json"
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(backup, default=_serialize, ensure_ascii=False),
                ContentType="application/json",
            )
            results[pool_id] = {
                "users": len(backup["users"]),
                "groups": len(backup["groups"]),
                "key": key,
            }
            logger.info(
                "backed up %s: %d users, %d groups -> s3://%s/%s",
                pool_id,
                len(backup["users"]),
                len(backup["groups"]),
                bucket,
                key,
            )
        except Exception as e:
            logger.exception("failed to back up user pool %s", pool_id)
            failures[pool_id] = str(e)

    if failures:
        raise RuntimeError(f"cognito backup failed for pools: {sorted(failures)}")
    return results
