from datetime import datetime

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.user import MFAStatus, User, UserStatus
from oqtopus_cloud.user_signup.lambda_function import app
from oqtopus_cloud.user_signup.schemas.mfa_reset import (
    MfaResetConfirmTotpRequest,
    MfaResetStartRequest,
    MfaResetVerifyCodeRequest,
)
from sqlalchemy import select


def _get_model(n: int) -> User:
    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "email": f"email{n}@example.com",
        "username": f"username_{n}",
        "userstatus": UserStatus.approved,
        "api_token_id": f"api_token_id_{n}",
        "api_token_hash": f"api_token_hash_{n}",
        "organization": f"organization_{n}",
        "group_id": f"group_id_{n}",
        "mfa_status": MFAStatus.enabled if n % 2 == 0 else MFAStatus.disabled,
        "api_token_expiration": datetime(2024, 3, 4, 12, 34, 56),
        "created_at": datetime(2024, 3, 4, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58),
    }
    return User(**model_dict)


def test_mfa_reset_start_success(test_db):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetStartRequest(
        email="email1@example.com",
        password="confirmation_code_1",
    )
    response = client.post("/mfa_reset/start", json=body.model_dump())
    assert response.status_code == 200
    assert response.json().get("access_token") == "fake_access_token"


def test_mfa_reset_start_user_mfa_active(test_db):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(2))  # User with MFA disabled
    test_db.commit()
    body = MfaResetStartRequest(
        email="email2@example.com",
        password="confirmation_code_2",
    )
    response = client.post("/mfa_reset/start", json=body.model_dump())
    assert response.status_code == 400
    assert response.json() == {
        "message_code": "MFA_ALREADY_ENABLED",
        "message_params": {"id": "email2@example.com"},
        "message": "MFA is already enabled for user: email2@example.com."
    }

def test_mfa_reset_start_cognito_error(test_db, fake_cognito_client_fixture):
    fake_cognito_client_fixture.admin_initiate_auth = Exception("Invalid token")
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetStartRequest(
        email="email1@example.com",
        password="confirmation_code_1",
    )
    response = client.post("/mfa_reset/start", json=body.model_dump())
    assert response.status_code == 400
    assert response.json() == {
        "message_code": "AUTHENTICATION_FAILED",
        "message_params": {},
        "message": "Failed to authenticate user."
    }


def test_mfa_reset_start_500(test_db, fake_cognito_client_fixture):
    fake_cognito_client_fixture.get_user_attribute_verification_code = Exception()
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetStartRequest(
        email="email1@example.com",
        password="confirmation_code_1",
    )
    response = client.post("/mfa_reset/start", json=body.model_dump())
    assert response.status_code == 500


def test_mfa_reset_verify_code_success(test_db):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetVerifyCodeRequest(
        access_token="fake_access_token",
        code="verification_code_1",
    )
    response = client.post("/mfa_reset/verify_code", json=body.model_dump())
    assert response.status_code == 200
    assert response.json().get("secret") == "secret_code_1"


def test_mfa_reset_verify_code_verification_failure(
    test_db, fake_cognito_client_fixture
):
    fake_cognito_client_fixture.verify_user_attribute = Exception("Invalid token")
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetVerifyCodeRequest(
        access_token="fake_access_token",
        code="verification_code_1",
    )
    response = client.post("/mfa_reset/verify_code", json=body.model_dump())
    assert response.status_code == 400
    assert response.json() == {
        "message_code": "CODE_VERIFICATION_FAILED",
        "message_params": {},
        "message": "Failed to verify the code."
    }


def test_mfa_reset_verify_code_500(fake_cognito_client_fixture):
    fake_cognito_client_fixture.associate_software_token = Exception()
    client = TestClient(app)
    body = MfaResetVerifyCodeRequest(
        access_token="fake_access_token",
        code="verification_code_1",
    )
    response = client.post("/mfa_reset/verify_code", json=body.model_dump())
    assert response.status_code == 500
    assert response.json() == {
        "message_code": "INTERNAL_SERVER_ERROR",
        "message_params": {},
        "message": "Internal Server Error"
    }


def test_mfa_reset_confirm_totp_success(test_db, fake_cognito_client_fixture):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetConfirmTotpRequest(
        access_token="fake_access_token",
        totp_code="verification_code_1",
    )
    response = client.post("/mfa_reset/confirm_totp", json=body.model_dump())
    assert response.status_code == 204
    user = (
        test_db.execute(select(User).where(User.cognito_id == "cognito_id_1"))
        .scalars()
        .first()
    )
    assert user is not None
    assert user.mfa_status == MFAStatus.enabled


def test_mfa_reset_confirm_totp_cognito_error(test_db, fake_cognito_client_fixture):
    fake_cognito_client_fixture.verify_software_token = Exception("Invalid token")
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetConfirmTotpRequest(
        access_token="fake_access_token",
        totp_code="verification_code_1",
    )
    response = client.post("/mfa_reset/confirm_totp", json=body.model_dump())
    assert response.status_code == 400
    assert response.json() == {
        "message_code": "INVALID_TOTP_CODE",
        "message_params": {},
        "message": "Invalid TOTP code."
    }

    user = (
        test_db.execute(select(User).where(User.email == "email1@example.com"))
        .scalars()
        .first()
    )
    assert user is not None
    assert user.mfa_status == MFAStatus.disabled


def test_mfa_reset_confirm_totp_500(test_db, fake_cognito_client_fixture):
    fake_cognito_client_fixture.set_user_mfa_preference = Exception()
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetConfirmTotpRequest(
        access_token="fake_access_token",
        totp_code="verification_code_1",
    )
    response = client.post("/mfa_reset/confirm_totp", json=body.model_dump())
    assert response.status_code == 500
    assert response.json() == {
        "message_code": "INTERNAL_SERVER_ERROR",
        "message_params": {},
        "message": "Internal Server Error"
    }

    user = (
        test_db.execute(select(User).where(User.email == "email1@example.com"))
        .scalars()
        .first()
    )
    assert user is not None
    assert user.mfa_status == MFAStatus.disabled
