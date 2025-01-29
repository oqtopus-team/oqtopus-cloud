from datetime import datetime

import oqtopus_cloud.lambda_auth.lambda_function as lambda_function
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.lambda_auth.lambda_function import (
    _verify_id_token,
    _verify_api_token,
    _generate_policy_allow,
    _generate_policy_deny,
    lambda_handler
)


def fake_get_db_client(test_session):
    yield test_session


def fake__verify_api_token(api_token=""):
    return "fake_username"


def fake__verify_id_token(id_token=""):
    return "fake_username"


def fake__verify_id_token_none_owner():
    return ""


def fake__generate_policy_allow(principal_id="", resource="", owner=""):
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
        "context":{
            "owner": "fake_username"
        }
    }

    return const


def fake__generate_policy_deny(principal_id="", resource="", owner=""):
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
        "context":{
            "owner": "fake_username"
        }
    }


def fake__generate_policy_none(principal_id="", resource="", owner=""):
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
        "context":{
            "owner": ""
        }
    }

    return const


def _get_model(n: int) -> User:
    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "email": f"email{n}@gmail.com",
        "username": f"username_{n}",
        "userstatus": 1,
        "api_token_secret": f"api_token_secret_{n}",
        "organization": f"organization_{n}",
        "purpose": f"purpose_{n}",
        "group_id": f"group_id_{n}",
        "require_mfa_reset": False,
    }
    return User(**model_dict)


def test__verify_id_token(

):
    actual = _verify_id_token("id_token")
    expect = "fake_username"
    assert actual == expect


def test__verify_api_token(test_session, monkeypatch):
    user = _get_model(1)
    test_session.flush()
    test_session.add(user)
    test_session.commit()
    monkeypatch.setattr(
        lambda_function, "get_db", lambda: fake_get_db_client(test_session)
    )
    ret = _verify_api_token("api_token_secret_1")

    assert ret == "fake_username"


def test__generate_policy_allow(
):
    actual = _generate_policy_allow("fake_username1", 'event["methodArn"]1', 'fake_username1')
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
        "context":{
            "owner": "fake_username1"
        }
    }

    assert actual == expect


def test__generate_policy_deny(
):
    actual = _generate_policy_deny("fake_username2", 'event["methodArn"]2', 'fake_username2')
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
        "context":{
            "owner": "fake_username2"
        }
    }

    assert actual == expect


def test_lambda_handler_api_token(monkeypatch):

    def fake__verify_api_token(id_token=""):
        return "fake_username"

    input = {
        "headers": {
            "q-api-token": "api_token_secret"
        },
        "methodArn": "methodArn"
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
        "context":{
            "owner": "fake_username"
        }
    }
    monkeypatch.setattr(lambda_function, "_verify_api_token", fake__verify_api_token)
    monkeypatch.setattr(lambda_function, '_generate_policy_allow', fake__generate_policy_allow)

    actual = lambda_handler(input, None)
    event = const

    assert actual == event


def test_lambda_handler_id_token(monkeypatch):
    input = {
        "headers": {
            "authorization": "api_token_secret"
        },
        "methodArn": "methodArn"
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
        "context":{
            "owner": "fake_username"
        }
    }
    monkeypatch.setattr('oqtopus_cloud.lambda_auth.lambda_function._verify_id_token', fake__verify_id_token)
    monkeypatch.setattr('oqtopus_cloud.lambda_auth.lambda_function._generate_policy_allow', fake__generate_policy_allow)

    actual = lambda_handler(input, None)
    event = const

    assert actual == event


def test_lambda_handler_none_owner(monkeypatch):
    input = {
        "headers": {
            "authorization": "api_token_secret"
        },
        "methodArn": "methodArn"
    }

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
        "context":{
            "owner": ""
        }
    }
    monkeypatch.setattr('oqtopus_cloud.lambda_auth.lambda_function._verify_id_token', fake__verify_id_token_none_owner)
    monkeypatch.setattr('oqtopus_cloud.lambda_auth.lambda_function._generate_policy_deny', fake__generate_policy_none)

    actual = lambda_handler(input, None)
    event = ans

    assert actual == event
