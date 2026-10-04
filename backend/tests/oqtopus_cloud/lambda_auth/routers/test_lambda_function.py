from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import oqtopus_cloud.lambda_auth.lambda_function as lambda_function
import pytest
from argon2 import PasswordHasher
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.api_jwt import PyJWT
from oqtopus_cloud.common.models.user import MFAStatus, User, UserStatus
from oqtopus_cloud.lambda_auth.lambda_function import (
    AuthError,
    _generate_policy_allow,
    _generate_policy_deny,
    _verify_api_token,
    _verify_access_token,
    lambda_handler,
)


def fake_get_db_client(test_session):
    return test_session


def fake__verify_api_token(api_token=""):
    return "fake_username"


def fake__verify_access_token(access_token=""):
    return "fake_username"


def fake__verify_access_token_none_user_id():
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


def test__verify_access_token(test_session, monkeypatch):
    user = _get_model(1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )

    actual = _verify_access_token("access_token")
    expect = "email1@example.com"
    assert actual == expect


def test__verify_access_token_uses_access_claims(test_session, monkeypatch):
    user = _get_model(1)
    test_session.add(user)
    test_session.commit()
    decode_kwargs = {}

    def fake_decode(*args, **kwargs):
        decode_kwargs.update(kwargs)
        return {
            "username": "email1@example.com",
            "token_use": "access",
            "client_id": "test_client_id",
        }

    monkeypatch.setattr(lambda_function.jwt, "decode", fake_decode)

    assert _verify_access_token("access_token") == "email1@example.com"
    assert "audience" not in decode_kwargs
    assert decode_kwargs["options"]["verify_aud"] is False
    assert set(decode_kwargs["options"]["require"]) == {
        "exp",
        "iss",
        "client_id",
        "token_use",
        "username",
    }


def test__verify_access_token_rejects_wrong_client_id(test_session, monkeypatch):
    user = _get_model(1)
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function.jwt,
        "decode",
        lambda *args, **kwargs: {
            "username": "email1@example.com",
            "token_use": "access",
            "client_id": "other_client",
        },
    )

    with pytest.raises(AuthError, match="Access token is invalid"):
        _verify_access_token("access_token")


def test__verify_access_token_with_real_rsa_signature(test_session, monkeypatch):
    """Exercise the production PyJWT verification with a Cognito-shaped JWT."""
    user = _get_model(1)
    test_session.add(user)
    test_session.commit()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    issuer = "https://cognito-idp.test_region.amazonaws.com/test_user_pool_id"
    access_token = lambda_function.jwt.encode(
        {
            "iss": issuer,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "client_id": "test_client_id",
            "token_use": "access",
            "username": "email1@example.com",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    class StaticJWKClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=public_key)

    monkeypatch.setattr(lambda_function.jwt, "PyJWKClient", StaticJWKClient)
    monkeypatch.setattr(lambda_function.jwt, "decode", PyJWT().decode)

    assert _verify_access_token(access_token) == "email1@example.com"


def test__verify_access_token_rejects_real_signed_id_token(test_session, monkeypatch):
    """A validly signed Cognito ID token must not be accepted as API auth."""
    user = _get_model(1)
    test_session.add(user)
    test_session.commit()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    id_token = lambda_function.jwt.encode(
        {
            "iss": "https://cognito-idp.test_region.amazonaws.com/test_user_pool_id",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "aud": "test_client_id",
            "token_use": "id",
            "cognito:username": "email1@example.com",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    class StaticJWKClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=public_key)

    monkeypatch.setattr(lambda_function.jwt, "PyJWKClient", StaticJWKClient)
    monkeypatch.setattr(lambda_function.jwt, "decode", PyJWT().decode)

    with pytest.raises(AuthError, match="Access token is invalid"):
        _verify_access_token(id_token)


def test__verify_access_token_no_token(test_session, monkeypatch):
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
        _ = _verify_access_token(None)

    assert "Access token is not found" in str(excinfo.value)


def test__verify_access_token_no_env_variable(test_session, monkeypatch):
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
        _ = _verify_access_token("access_token")

    assert "Environment variable is not set 'USER_POOL_WEB_CLIENT_ID" in str(
        excinfo.value
    )


@pytest.mark.usefixtures("override_PyJWKClientFailure")
def test__verify_access_token_jwt_signing_key_failure():
    pytest.raises(AuthError, _verify_access_token, "access_token")


@pytest.mark.usefixtures("override_jwt_decode_failure")
def test__verify_access_token_jwt_decode_failure():
    pytest.raises(AuthError, _verify_access_token, "access_token")


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

    pytest.raises(AuthError, _verify_access_token, "access_token")


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

    pytest.raises(AuthError, _verify_access_token, "access_token")


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

    pytest.raises(AuthError, _verify_access_token, "access_token")


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

    assert "Missing Q-API-Token" in str(excinfo.value)


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


def test__verify_api_token_malformed(test_session, monkeypatch):
    # No dot separator -> rejected by the shared parser before any DB access.
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token("api_token_secret_2")
    assert "Malformed Q-API-Token" in str(excinfo.value)


def test__verify_api_token_mfa_inactive(test_session, monkeypatch):
    # user 2 has MFA disabled; pass a *well-formed* token so verification
    # reaches the MFA check (regression: this previously stopped at the parser).
    user = _get_model(2)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function,
        "_create_session",
        lambda **kwargs: fake_get_db_client(test_session),
    )
    no_rehash = MagicMock()
    monkeypatch.setattr(lambda_function, "rehash_api_token_if_needed", no_rehash)

    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token("api_token_id_2.api_token_secret_2")
    assert "MFA is not enabled for this user" in str(excinfo.value)
    # A rejected request must never rehash.
    no_rehash.assert_not_called()


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
    no_rehash = MagicMock()
    monkeypatch.setattr(lambda_function, "rehash_api_token_if_needed", no_rehash)
    with pytest.raises(AuthError) as excinfo:
        _ = _verify_api_token("api_token_id_1.api_token_secret_1")

    assert "Failed to list users from Cognito Cognito user is not found" in str(
        excinfo.value
    )
    no_rehash.assert_not_called()


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
    no_rehash = MagicMock()
    monkeypatch.setattr(lambda_function, "rehash_api_token_if_needed", no_rehash)
    with pytest.raises(AuthError):
        _ = _verify_api_token("api_token_id_1.api_token_secret_1")
    no_rehash.assert_not_called()


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
    no_rehash = MagicMock()
    monkeypatch.setattr(lambda_function, "rehash_api_token_if_needed", no_rehash)
    with pytest.raises(AuthError):
        _ = _verify_api_token("api_token_id_1.api_token_secret_1")
    no_rehash.assert_not_called()


def test__generate_policy_allow():
    actual = _generate_policy_allow(
        "fake_username1", 'event["methodArn"]1', "fake_username1"
    )
    expect = {
        "principalId": "fake_username1",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": 'event["methodArn"]1',
                }
            ],
        },
        "context": {"user_id": "fake_username1"},
    }

    assert actual == expect


def test__generate_policy_deny():
    actual = _generate_policy_deny(
        "fake_username2", 'event["methodArn"]2', "fake_username2"
    )
    expect = {
        "principalId": "fake_username2",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Deny",
                    "Resource": 'event["methodArn"]2',
                }
            ],
        },
        "context": {"user_id": "fake_username2"},
    }

    assert actual == expect


def test_lambda_handler_api_token(monkeypatch):
    def fake__verify_api_token(id_token=""):
        return "fake_username"

    input = {"headers": {"q-api-token": "api_token_secret"}, "methodArn": "methodArn"}

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


def test_lambda_handler_access_token(monkeypatch):
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
        "oqtopus_cloud.lambda_auth.lambda_function._verify_access_token",
        fake__verify_access_token,
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
        "oqtopus_cloud.lambda_auth.lambda_function._verify_access_token",
        fake__verify_access_token_none_user_id,
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
