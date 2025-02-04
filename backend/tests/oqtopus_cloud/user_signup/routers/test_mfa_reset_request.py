import logging
from datetime import datetime

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.user_signup.lambda_function import app
from oqtopus_cloud.user_signup.schemas.mfa_reset_request import (
    MfaResetRequest,
)

logger = logging.getLogger(__name__)


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


def test_mfa_reset_request_success(test_db):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = MfaResetRequest(
        email="email1@gmail.com",
        password="confirmation_code_1",
        client_id="client_id_1",
    )
    response = client.put("/mfa_reset_request", json=body.model_dump())
    logger.info(response)
    assert response.status_code == 200
    # confirm that the user's require_mfa_reset is set to True
    user = test_db.query(User).filter(User.email == "email1@gmail.com").first()
    assert user.require_mfa_reset is True


def test_mfa_reset_request_no_user_found(test_db):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(2))
    test_db.commit()
    body = MfaResetRequest(
        email="email1@gmail.com",
        password="confirmation_code_1",
        client_id="client_id_1",
    )
    response = client.put("/mfa_reset_request", json=body.model_dump())
    logger.info(response)
    assert response.status_code == 404
    # confirm that the user's require_mfa_reset is not changed
    user = test_db.query(User).filter(User.email == "email2@gmail.com").first()
    assert user.require_mfa_reset is False
