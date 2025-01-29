from datetime import datetime

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.user_signup.lambda_function import app
from oqtopus_cloud.user_signup.schemas.signup import (
    SignupRequest,
)


def _get_model(n: int) -> WhitelistUser:
    model_dict = {
        "id": n,
        "email": f"email_{n}",
        "group_id": f"group_id_{n}",
        "is_signup_completed": False,
        "username": f"username_{n}",
        "organization": f"organization_{n}",
        "created_at": datetime(2024, 3, 4, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58),
    }
    return WhitelistUser(**model_dict)


def test_signup_success(test_db):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = SignupRequest(email="email_1", password="password_1")
    response = client.post("/signup", json=body.model_dump())
    assert response.status_code == 201


def test_signup_not_in_whitelist(test_db):
    client = TestClient(app)
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    body = SignupRequest(email="email_2", password="password_1")
    response = client.post("/signup", json=body.model_dump())
    assert response.status_code == 400
    assert response.json() == {"message": "Not in whitelist_users"}
