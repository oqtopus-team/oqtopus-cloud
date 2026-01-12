import boto3

lambda_client = boto3.client("lambda")


def get_all_versions(function_name: str) -> list[str]:
    paginator = lambda_client.get_paginator("list_versions_by_function")

    return [
        v["Version"]
        for page in paginator.paginate(FunctionName=function_name)
        for v in page["Versions"]
        if v["Version"] != "$LATEST"
    ]


def get_protected_aliased_versions(function_name: str) -> list[str]:
    paginator = lambda_client.get_paginator("list_aliases")

    aliased_versions = [
        alias["FunctionVersion"]
        for page in paginator.paginate(FunctionName=function_name)
        for alias in page["Aliases"]
        if alias["FunctionVersion"] != "$LATEST"
    ]

    rollback_versions = [
        str(int(v) - 1) for v in aliased_versions if v.isdigit() and int(v) > 1
    ]

    return aliased_versions + rollback_versions


def lambda_handler(event, context):
    paginator = lambda_client.get_paginator("list_functions")

    for page in paginator.paginate():
        for function in page["Functions"]:
            function_name = function["FunctionName"]

            print(f"Check lambda: {function_name}")

            try:
                all_versions = get_all_versions(function_name)
                if not all_versions:
                    print("to_delete: []")
                    continue

                protected_aliased = get_protected_aliased_versions(function_name)
                protected_recent = all_versions[-2:]

                to_delete = [
                    v
                    for v in all_versions
                    if v not in protected_aliased and v not in protected_recent
                ]

                print(f"all: {all_versions}")
                print(f"protected_recent: {protected_recent}")
                print(f"protected_aliased: {protected_aliased}")
                print(f"to_delete: {to_delete}")

            except Exception as e:
                print(f"Failed to cleanup lambda {function_name}: {e}")

    return {"statusCode": 200}
