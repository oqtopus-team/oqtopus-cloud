from unittest.mock import MagicMock, call, patch

with patch("boto3.client", return_value=MagicMock()):
    from oqtopus_cloud.maintenance.lambda_version_cleaner import lambda_function


def test_lambda_handler_cleans_requested_function(monkeypatch):
    cleanup = MagicMock()
    monkeypatch.setattr(
        lambda_function,
        "CLEANUP_FUNCTION_PREFIX",
        "oqtopus-oqtopus-dev-",
    )
    monkeypatch.setattr(lambda_function, "cleanup_lambda_versions", cleanup)

    response = lambda_function.lambda_handler(
        {"functionName": "oqtopus-oqtopus-dev-user-api"},
        None,
    )

    assert response == {"statusCode": 200}
    cleanup.assert_called_once_with("oqtopus-oqtopus-dev-user-api")


def test_lambda_handler_rejects_unscoped_function(monkeypatch):
    cleanup = MagicMock()
    monkeypatch.setattr(
        lambda_function,
        "CLEANUP_FUNCTION_PREFIX",
        "oqtopus-oqtopus-dev-",
    )
    monkeypatch.setattr(lambda_function, "cleanup_lambda_versions", cleanup)

    response = lambda_function.lambda_handler(
        {"functionName": "unrelated-function"},
        None,
    )

    assert response == {"statusCode": 400}
    cleanup.assert_not_called()


def test_lambda_handler_cleans_all_scoped_functions(monkeypatch):
    cleanup = MagicMock()
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {
            "Functions": [
                {"FunctionName": "oqtopus-oqtopus-dev-user-api"},
                {"FunctionName": "unrelated-function"},
                {"FunctionName": "oqtopus-oqtopus-dev-provider-api"},
            ]
        }
    ]
    lambda_client = MagicMock()
    lambda_client.get_paginator.return_value = paginator

    monkeypatch.setattr(
        lambda_function,
        "CLEANUP_FUNCTION_PREFIX",
        "oqtopus-oqtopus-dev-",
    )
    monkeypatch.setattr(lambda_function, "lambda_client", lambda_client)
    monkeypatch.setattr(lambda_function, "cleanup_lambda_versions", cleanup)

    response = lambda_function.lambda_handler({"functionName": "*"}, None)

    assert response == {"statusCode": 200}
    assert cleanup.call_args_list == [
        call("oqtopus-oqtopus-dev-user-api"),
        call("oqtopus-oqtopus-dev-provider-api"),
    ]
