from typing import Generator
from unittest import mock

import boto3
import jwt
import pytest
from oqtopus_cloud.common.models.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class FakeCognitoClient:
    def __init__(self):
        self.confirm_sign_up_exception = None

    def list_users(self, UserPoolId=None, Filter="sub = 1"):
        return {
            "Users": [
                {
                    "Username": "fake_username",
                    "Attributes": [
                        {"Name": "sub", "Value": "1"},
                    ],
                }
            ]
        }


class FakeCognitoClientZeroUser:
    def __init__(self):
        self.confirm_sign_up_exception = None

    def list_users(self, UserPoolId, Filter):
        return {"Users": []}


class FakeCognitoClientMultipleUsers:
    def __init__(self):
        self.confirm_sign_up_exception = None

    def list_users(self, UserPoolId, Filter):
        return {
            "Users": [
                {
                    "Username": "fake_username1",
                    "Attributes": [
                        {"Name": "sub", "Value": "1"},
                    ],
                },
                {
                    "Username": "fake_username2",
                    "Attributes": [
                        {"Name": "sub", "Value": "2"},
                    ],
                },
            ]
        }


class FakePyJWKClient:
    # Mirror jwt.PyJWKClient(uri, timeout=...) so the production call,
    # which now passes an explicit timeout, can be monkeypatched.
    def __init__(self, uri, timeout=None, **kwargs):
        self.uri = uri
        self.timeout = timeout

    def get_signing_key_from_jwt(self, token):
        return mock.MagicMock()


class FakePyJWKClientFailure:
    def __init__(self, uri, timeout=None, **kwargs):
        self.uri = uri

    def get_signing_key_from_jwt(self, token):
        raise ValueError("Invalid token")


@pytest.fixture(autouse=True)
def fake_os_env(monkeypatch):
    monkeypatch.setenv("REGION", "test_region")
    monkeypatch.setenv("AUTH_USER_POOL_ID", "test_user_pool_id")
    monkeypatch.setenv("USER_POOL_WEB_CLIENT_ID", "test_client_id")


@pytest.fixture(scope="function")
def test_session() -> Generator:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestSessionLocal()
    yield session
    session.rollback()
    session.close()
    engine.dispose()


@pytest.fixture(autouse=True, scope="function")
def override_get_db_session(test_session, monkeypatch):
    def _get_test_db_session(read_timeout=None):
        yield test_session

    monkeypatch.setenv("DB_HOST", "sqlite:///:memory:")
    monkeypatch.setattr("oqtopus_cloud.common.session.get_db", _get_test_db_session)


@pytest.fixture()
def fake_cognito_client_fixture():
    return FakeCognitoClient()


@pytest.fixture()
def fake_cognito_client_fixture_zero_user():
    return FakeCognitoClientZeroUser()


@pytest.fixture()
def fake_cognito_client_fixture_multiple_users():
    return FakeCognitoClientMultipleUsers()


@pytest.fixture(autouse=True)
def override_boto3_client(monkeypatch, fake_cognito_client_fixture):
    def _fake_boto3_client(service, region_name=None, **kwargs):
        if service == "cognito-idp":
            return fake_cognito_client_fixture
        raise ValueError(f"Unsupported service: {service}")

    monkeypatch.setattr(boto3, "client", _fake_boto3_client)


@pytest.fixture()
def override_boto3_client_zero_user(monkeypatch, fake_cognito_client_fixture_zero_user):
    def _fake_boto3_client(service, region_name=None, **kwargs):
        if service == "cognito-idp":
            return fake_cognito_client_fixture_zero_user
        raise ValueError(f"Unsupported service: {service}")

    monkeypatch.setattr(boto3, "client", _fake_boto3_client)


@pytest.fixture()
def override_boto3_client_multiple_users(
    monkeypatch, fake_cognito_client_fixture_multiple_users
):
    def _fake_boto3_client(service, region_name=None, **kwargs):
        if service == "cognito-idp":
            return fake_cognito_client_fixture_multiple_users
        raise ValueError(f"Unsupported service: {service}")

    monkeypatch.setattr(boto3, "client", _fake_boto3_client)


@pytest.fixture(autouse=True)
def override_PyJWKClient(monkeypatch):
    monkeypatch.setattr(jwt, "PyJWKClient", FakePyJWKClient)


@pytest.fixture()
def override_PyJWKClientFailure(monkeypatch):
    monkeypatch.setattr(jwt, "PyJWKClient", FakePyJWKClientFailure)


def fake_jwt_decode(*args, **kwargs):
    return {"cognito:username": "email1@example.com", "token_use": "id"}


def fake_jwt_decode_failure(*args, **kwargs):
    return {"cognito:username": "fake_username", "token_use": "not id"}


@pytest.fixture(autouse=True)
def override_jwt_decode(monkeypatch):
    monkeypatch.setattr(jwt, "decode", fake_jwt_decode)

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


@pytest.fixture()
def override_jwt_decode_failure(monkeypatch):
    monkeypatch.setattr(jwt, "decode", fake_jwt_decode_failure)

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
