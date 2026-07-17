from datetime import datetime, timedelta, timezone

import oqtopus_cloud.lambda_auth.lambda_function as lambda_function
import pytest
from argon2 import PasswordHasher
from oqtopus_cloud.common.models.user import MFAStatus, User, UserStatus
from oqtopus_cloud.lambda_auth.lambda_function import (
    AuthError,
    _generate_policy_allow,
    _generate_policy_deny,
    _generate_stage_resource_arn,
    _validate_headers_for_api_token,
    _verify_api_token,
    _verify_id_token,
    lambda_handler,
)


def fake_get_db_client(test_session):
    return test_session


def fake__verify_api_token(api_token=""):
    return "fake_username"


def fake__verify_id_token(id_token=""):
    return "fake_username"


def fake__verify_id_token_none_user_id():
    return ""


def fake__generate_policy_allow(principal_id="", resource="", user_id=""):
    const = {
        "principalId": "fake_username",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": 'event["methodArn"]',
                }
            ],
        },
        "context": {"user_id": "fake_username"},
    }

    return const


def fake__generate_policy_deny(principal_id="", resource="", user_id=""):
    const = {
        "principalId": "fake_username",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Deny",
                    "Resource": 'event["methodArn"]',
                }
            ],
        },
        "context": {"user_id": "fake_username"},
    }


def fake__generate_policy_none(principal_id="", resource="", user_id=""):
    const = {
        "principalId": "",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Deny",
                    "Resource": 'event["methodArn"]',
                }
            ],
        },
        "context": {"user_id": ""},
    }

    return const


def _get_model(n: int, expiration_day=90, status=UserStatus.approved) -> User:
    model_dict = {
        "id": f"email{n}@example.com",
        "cognito_id": f"cognito_id_{n}",
        "email": f"email{n}@example.com",
        "display_name": f"test_user_{n}",
        "userstatus": status,
        "organization": f"organization_{n}",
        "group_id": f"group_id_{n}",
        "available_devices": '["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"]',
        "mfa_status": MFAStatus.disabled if n % 2 == 0 else MFAStatus.enabled,
        "api_token_id": f"api_token_id_{n}",
        "api_token_hash": PasswordHasher().hash(f"api_token_secret_{n}"),
        "api_token_expiration": datetime.now(timezone.utc).replace(
            second=0, microsecond=0
        )
        + timedelta(days=expiration_day),
    }
    return User(**model_dict)


def test__validate_headers_for_api_token_success():
    headers = {
        "q-api-token": "token-value",
        "authorization": "token-value",
    }

    _validate_headers_for_api_token(headers)


def test__validate_headers_for_api_token_missing_header():
    headers = {
        "q-api-token": "token-value",
        "authorization": None,
    }

    with pytest.raises(AuthError) as excinfo:
        _validate_headers_for_api_token(headers)

    assert "Authentication header is missing" in str(excinfo.value)


def test__validate_headers_for_api_token_mismatch():
    headers = {
        "q-api-token": "token-value",
        "authorization": "another-value",
    }

    with pytest.raises(AuthError) as excinfo:
        _validate_headers_for_api_token(headers)

    assert "Authorization and q-api-token do not match" in str(excinfo.value)


def test__verify_id_token(test_session, monkeypatch):
    user = _get_model(1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )

    actual = _verify_id_token("id_token")
    expect = "email1@example.com"
    assert actual == expect


def test__verify_id_token_no_token(test_session, monkeypatch):
    user = _get_model(1, -1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_id_token(None)

    assert "ID token is not found" in str(excinfo.value)


def test__verify_id_token_no_env_variable(test_session, monkeypatch):
    user = _get_model(1, -1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    monkeypatch.delenv("USER_POOL_WEB_CLIENT_ID", raising=False)
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_id_token("id_token")

    assert "Environment variable is not set 'USER_POOL_WEB_CLIENT_ID" in str(
        excinfo.value
    )


@pytest.mark.usefixtures("override_PyJWKClientFailure")
def test__verify_id_token_jwt_signing_key_failure():
    pytest.raises(AuthError, _verify_id_token, "id_token")


@pytest.mark.usefixtures("override_jwt_decode_failure")
def test__verify_id_token_jwt_decode_failure():
    pytest.raises(AuthError, _verify_id_token, "id_token")


def test__verify_suspended(test_session, monkeypatch):
    user = _get_model(1, status=UserStatus.suspended)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )

    pytest.raises(AuthError, _verify_id_token, "id_token")


def test__verify_unapproved(test_session, monkeypatch):
    user = _get_model(1, status=UserStatus.unapproved)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )

    pytest.raises(AuthError, _verify_id_token, "id_token")


def test__verify_mfa_inactive(test_session, monkeypatch):
    user = _get_model(2)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )

    pytest.raises(AuthError, _verify_id_token, "id_token")


def test__verify_api_token(test_session, monkeypatch):
    user = _get_model(1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    ret = _verify_api_token("api_token_id_1.api_token_secret_1")

    assert ret == "fake_username"


def test__verify_api_token_expired(test_session, monkeypatch):
    user = _get_model(1, -1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )

    try:
        _ = _verify_api_token("api_token_id_1.api_token_secret_1")
    except AuthError as e:
        assert str(e) == "Database error API token is expired"
    else:
        assert False


def test__verify_api_token_api_no_token(test_session, monkeypatch):
    user = _get_model(1, -1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token(None)

    assert "API token is None" in str(excinfo.value)


def test__verify_api_token_no_env_variable(test_session, monkeypatch):
    user = _get_model(1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    monkeypatch.delenv("AUTH_USER_POOL_ID", raising=False)
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token("api_token_id_1.api_token_secret_1")

    assert "Environment variable is not set 'AUTH_USER_POOL_ID'" in str(excinfo.value)


def test__verify_api_token_mfa_inactive(test_session, monkeypatch):
    user = _get_model(2)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )

    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token("api_token_secret_2")
    assert "API token is malformed" in str(excinfo.value)


@pytest.mark.usefixtures("override_boto3_client_zero_user")
def test__verify_api_token_no_cognito_user(test_session, monkeypatch):
    user = _get_model(1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token("api_token_id_1.api_token_secret_1")

    assert "Failed to list users from Cognito Cognito user is not found" in str(
        excinfo.value
    )


@pytest.mark.usefixtures("override_boto3_client_multiple_users")
def test__verify_api_token_multiple_cognito_user(test_session, monkeypatch):
    user = _get_model(1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token("api_token_id_1.api_token_secret_1")

    assert "Failed to list users from Cognito Cognito user is duplicated" in str(
        excinfo.value
    )


def test__verify_api_token_suspended(test_session, monkeypatch):
    user = _get_model(1, status=UserStatus.suspended)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token("api_token_id_1.api_token_secret_1")


def test__verify_api_token_unapproved(test_session, monkeypatch):
    user = _get_model(1, status=UserStatus.unapproved)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token("api_token_id_1.api_token_secret_1")


def test__generate_stage_resource_arn():
    method_arn = "arn:aws:execute-api:ap-northeast-1:123456789012:api-id/dev/GET/foo"

    actual = _generate_stage_resource_arn(method_arn)

    assert (
        actual
        == "arn:aws:execute-api:ap-northeast-1:123456789012:api-id/dev/*/*"
    )


def test__generate_stage_resource_arn_invalid_arn_format():
    with pytest.raises(AuthError) as excinfo:
        _generate_stage_resource_arn("invalid-method-arn")

    assert "Invalid methodArn" in str(excinfo.value)


def test__generate_stage_resource_arn_invalid_api_gateway_part():
    with pytest.raises(AuthError) as excinfo:
        _generate_stage_resource_arn(
            "arn:aws:execute-api:ap-northeast-1:123456789012:api-id"
        )

    assert "Invalid methodArn" in str(excinfo.value)


def test__generate_policy_allow():
    method_arn = "arn:aws:execute-api:ap-northeast-1:123456789012:api-id/dev/GET/devices"
    actual = _generate_policy_allow("fake_username1", method_arn, "fake_username1")
    expect = {
        "principalId": "fake_username1",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": "arn:aws:execute-api:ap-northeast-1:123456789012:api-id/dev/*/*",
                }
            ],
        },
        "context": {"user_id": "fake_username1"},
    }

    assert actual == expect


def test__generate_policy_deny():
    method_arn = "arn:aws:execute-api:ap-northeast-1:123456789012:api-id/prod/POST/jobs"
    actual = _generate_policy_deny("fake_username2", method_arn, "fake_username2")
    expect = {
        "principalId": "fake_username2",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Deny",
                    "Resource": "arn:aws:execute-api:ap-northeast-1:123456789012:api-id/prod/*/*",
                }
            ],
        },
        "context": {"user_id": "fake_username2"},
    }

    assert actual == expect


def test_lambda_handler_api_token(monkeypatch):
    def fake__verify_api_token(id_token=""):
        return "fake_username"

    input = {
        "headers": {
            "q-api-token": "api_token_secret",
            "authorization": "api_token_secret",
        },
        "methodArn": "methodArn",
    }

    const = {
        "principalId": "fake_username",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": 'event["methodArn"]',
                }
            ],
        },
        "context": {"user_id": "fake_username"},
    }
    monkeypatch.setattr(lambda_function, "_verify_api_token", fake__verify_api_token)
    monkeypatch.setattr(
        lambda_function, "_generate_policy_allow", fake__generate_policy_allow
    )

    actual = lambda_handler(input, None)
    event = const

    assert actual == event


def test_lambda_handler_no_api_token(monkeypatch):
    def fake__verify_api_token_deny(principal_id=None, resource=None, user_id=None):
        return "fake_username"

    input = {"headers": {"q-api-token": None}, "methodArn": "methodArn"}
    monkeypatch.setattr(
        lambda_function, "_generate_policy_deny", fake__verify_api_token_deny
    )
    actual = lambda_handler(input, None)
    assert actual == "fake_username"


def test_lambda_handler_id_token(monkeypatch):
    input = {"headers": {"authorization": "api_token_secret"}, "methodArn": "methodArn"}

    const = {
        "principalId": "fake_username",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": 'event["methodArn"]',
                }
            ],
        },
        "context": {"user_id": "fake_username"},
    }
    monkeypatch.setattr(
        "oqtopus_cloud.lambda_auth.lambda_function._verify_id_token",
        fake__verify_id_token,
    )
    monkeypatch.setattr(
        "oqtopus_cloud.lambda_auth.lambda_function._generate_policy_allow",
        fake__generate_policy_allow,
    )

    actual = lambda_handler(input, None)
    event = const

    assert actual == event


def test_lambda_handler_none_user_id(monkeypatch):
    input = {"headers": {"authorization": "api_token_secret"}, "methodArn": "methodArn"}

    ans = {
        "principalId": "",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Deny",
                    "Resource": 'event["methodArn"]',
                }
            ],
        },
        "context": {"user_id": ""},
    }
    monkeypatch.setattr(
        "oqtopus_cloud.lambda_auth.lambda_function._verify_id_token",
        fake__verify_id_token_none_user_id,
    )
    monkeypatch.setattr(
        "oqtopus_cloud.lambda_auth.lambda_function._generate_policy_deny",
        fake__generate_policy_none,
    )

    actual = lambda_handler(input, None)
    event = ans

    assert actual == event


def test_lambda_handler_unexpected_header(monkeypatch):
    def fake__verify_api_token_deny(principal_id=None, resource=None, user_id=None):
        return "fake_username"

    input = {"headers": {"q-api-token-unexpected": None}, "methodArn": "methodArn"}
    monkeypatch.setattr(
        lambda_function, "_generate_policy_deny", fake__verify_api_token_deny
    )
    actual = lambda_handler(input, None)
    assert actual == "fake_username"
