from datetime import datetime

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.user import MFAStatus, User
from oqtopus_cloud.user_signup.lambda_function import app
from oqtopus_cloud.user_signup.schemas.mfa_reset_request import (
    MfaResetRequest,
)
from sqlalchemy import select


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


def test_mfa_reset_request_success(test_db):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetRequest(
        email="email1@example.com",
        password="confirmation_code_1",
        client_id="client_id_1",
    )
    response = client.put("/mfa_reset_request", json=body.model_dump())
    assert response.status_code == 200
    # refer to db value
    user = (
        test_db.execute(select(User).where(User.email == "email1@example.com"))
        .scalars()
        .first()
    )
    assert user is not None
    assert user.mfa_status == MFAStatus.disabled


def test_mfa_reset_request_cognito_error(test_db, fake_cognito_client_fixture):
    fake_cognito_client_fixture.admin_initiate_auth = Exception("Invalid token")
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetRequest(
        email="email1@example.com",
        password="confirmation_code_1",
        client_id="client_id_1",
    )
    response = client.put("/mfa_reset_request", json=body.model_dump())
    assert response.status_code == 400


def test_mfa_reset_request_500():
    client = TestClient(app)
    body = MfaResetRequest(
        email="email1@example.com",
        password="confirmation_code_1",
        client_id="client_id_1",
    )
    response = client.put("/mfa_reset_request", json=body.model_dump())
    assert response.status_code == 500


def test_mfa_reset_request_no_user_found(test_db, fake_cognito_client_fixture):
    fake_cognito_client_fixture.admin_initiate_auth = Exception("Invalid token")
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetRequest(
        email="email1@example.com",
        password="confirmation_code_1",
        client_id="client_id_1",
    )
    response = client.put("/mfa_reset_request", json=body.model_dump())
    assert response.status_code == 400


def test__request_no_user_found(test_db):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(2))
    test_db.commit()
    body = MfaResetRequest(
        email="email1@example.com",
        password="confirmation_code_1",
        client_id="client_id_1",
    )
    response = client.put("/mfa_reset_request", json=body.model_dump())
    assert response.status_code == 404
