from datetime import datetime

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.user_signup.lambda_function import app
from oqtopus_cloud.user_signup.routers.confirm_signup import cleanup_user
from oqtopus_cloud.user_signup.schemas.confirm_signup import (
    ConfirmationSignupRequest,
)

client = TestClient(app)


def _get_model_whitelist_users(n: int, is_completed: bool) -> WhitelistUser:
    model_dict = {
        "id": n,
        "email": f"email{n}@example.com",
        "group_id": f"group_id_{n}",
        "is_signup_completed": is_completed,
        "username": f"username_{n}",
        "organization": f"organization_{n}",
        "available_devices": '["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"]',
        "created_at": datetime(2024, 3, 4, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58),
    }
    return WhitelistUser(**model_dict)


def _get_model(n: int) -> User:
    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "email": f"email{n}@example.com",
        "username": f"username_{n}",
        "userstatus": 1,
        "api_token_secret": f"api_token_secret_{n}",
        "organization": f"organization_{n}",
        "group_id": f"group_id_{n}",
        "available_devices": '["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"]',
        "api_token_expiration": datetime(2024, 3, 4, 12, 34, 56),
        "created_at": datetime(2024, 3, 4, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58),
    }
    return User(**model_dict)


def test_confirm_confirm(test_db):
    test_db.flush()
    test_db.add(_get_model(2))
    test_db.commit()
    body = ConfirmationSignupRequest(
        email="email1@example.com", confirmation_code="confirmation_code_1"
    )
    response = client.put("/confirm_signup", json=body.model_dump())
    assert response.status_code == 200


def test_confirm_signup_cognito_failure(test_db, fake_cognito_client_fixture):
    error_response = {
        "Error": {
            "Code": "InvalidParameterException",
            "Message": "Invalid confirmation code.",
        }
    }
    fake_cognito_client_fixture.confirm_sign_up_exception = ClientError(
        error_response, "ConfirmSignUp"
    )

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = ConfirmationSignupRequest(
        email="email1@example.com", confirmation_code="confirmation_code_1"
    )
    response = client.put("/confirm_signup", json=body.model_dump())
    assert response.status_code == 400
    # confirm the user is NOT registered
    user = test_db.query(User).filter(User.email == "email1@example.com").first()
    assert user.username == "username_1"


def test_confirm_signup_exception(test_db, fake_cognito_client_fixture):
    error_response = {
        "Error": {
            "Code": "InvalidParameterException",
            "Message": "Invalid confirmation code.",
        }
    }
    fake_cognito_client_fixture.confirm_sign_up_exception = Exception(
        error_response, "ConfirmSignUp"
    )

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = ConfirmationSignupRequest(
        email="email1@example.com", confirmation_code="confirmation_code_1"
    )
    response = client.put("/confirm_signup", json=body.model_dump())
    assert response.status_code == 500


def test_cleanup_user(test_db, fake_cognito_client_fixture):
    fake_cognito_client_fixture.admin_delete_user = lambda UserPoolId, Username: None
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model_whitelist_users(1, True))
    test_db.commit()
    cleanup_user(test_db, fake_cognito_client_fixture, "email1@example.com", "pool_id")
    user = test_db.query(User).filter(User.email == "email1@example.com").first()
    whitelist_user = (
        test_db.query(WhitelistUser)
        .filter(WhitelistUser.email == "email1@example.com")
        .first()
    )
    assert user is None
    assert whitelist_user.is_signup_completed is False
