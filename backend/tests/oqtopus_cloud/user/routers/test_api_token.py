from datetime import datetime
from typing import Any, Dict

from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.user.lambda_function import app
from oqtopus_cloud.user.routers.api_token import (
    create_api_token,
    delete_api_token,
    get_api_token,
)
from oqtopus_cloud.user.schemas.api_token import ApiToken
from starlette.requests import Request


def _get_model(n: int) -> User:
    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "email": f"email_{n}",
        "username": f"username_{n}",
        "userstatus": 1,
        "api_token_secret": f"api_token_secret_{n}",
        "organization": f"organization_{n}",
        "purpose": f"purpose_{n}",
        "group_id": f"group_id_{n}",
        "require_mfa_reset": True,
        "api_token_expiration": datetime(2024, 3, 4, 12, 34, 56),
        "created_at": datetime(2024, 3, 4, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58),
    }
    return User(**model_dict)


def test_get_api_token(
    test_db,
):
    # Create a dummy-request object
    scope: Dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
    }

    async def receive() -> Dict[str, Any]:
        return {"type": "http.request", "body": b""}

    request = Request(scope=scope, receive=receive)
    request.state.owner = "username_1"

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = get_api_token(
        request,
        test_db,
    )
    assert response == ApiToken(
        api_token_secret="api_token_secret_1",
        api_token_expiration=datetime(2024, 3, 4, 12, 34, 56),
    )


def test_post_api_token(
    test_db,
):
    # Create a dummy-request object
    scope: Dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
    }

    async def receive() -> Dict[str, Any]:
        return {"type": "http.request", "body": b""}

    request = Request(scope=scope, receive=receive)
    request.state.owner = "username_1"

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    # check if user has api token
    old_api_token = (
        test_db.query(User)
        .filter(User.username == "username_1")
        .first()
        .api_token_secret
    )
    assert old_api_token == "api_token_secret_1"

    response = create_api_token(
        request,
        test_db,
    )

    # check if api token is created
    assert response.api_token_secret != "api_token_secret_1"
    assert len(response.api_token_secret) != 0


def test_delete_api_token(
    test_db,
):
    # Create a dummy-request object
    scope: Dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
    }

    async def receive() -> Dict[str, Any]:
        return {"type": "http.request", "body": b""}

    request = Request(scope=scope, receive=receive)
    request.state.owner = "username_1"

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    # check if user has api token
    assert (
        test_db.query(User)
        .filter(User.username == "username_1")
        .first()
        .api_token_secret
        == "api_token_secret_1"
    )

    response = delete_api_token(
        request,
        test_db,
    )
    assert response.status_code == 200
    # check if api token is deleted
    assert (
        test_db.query(User)
        .filter(User.username == "username_1")
        .first()
        .api_token_secret
        is None
    )
