from datetime import datetime

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.user_signup.lambda_function import app
from oqtopus_cloud.user_signup.schemas.confirm_signup import (
    ConfirmationSignupRequest,
)

client = TestClient(app)


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
        "api_token_expiration": datetime(2024, 3, 4, 12, 34, 56),
        "created_at": datetime(2024, 3, 4, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58),
    }
    return User(**model_dict)


def test_signup_confirm_success(test_db):
    test_db.flush()
    test_db.add(_get_model(2))
    test_db.commit()
    body = ConfirmationSignupRequest(
        email="email1@gmail.com", confirmation_code="confirmation_code_1"
    )
    response = client.put("/confirm_signup", json=body.model_dump())
    assert response.status_code == 200
    # confirm the user is registered
    user = test_db.query(User).filter(User.email == "email1@gmail.com").first()
    assert user.username == "email1@gmail.com"


def test_signup_confirm_multiple_registration(test_db, fake_cognito_client_fixture):
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
        email="email1@gmail.com", confirmation_code="confirmation_code_1"
    )
    response = client.put("/confirm_signup", json=body.model_dump())
    assert response.status_code == 400
    # confirm the user is NOT registered
    user = test_db.query(User).filter(User.email == "email1@gmail.com").first()
    assert user.username == "username_1"
