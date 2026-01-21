import pytz

from argon2 import PasswordHasher
from datetime import datetime
from pydantic.type_adapter import TypeAdapter
from typing import Any, Dict

from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.user.routers.api_token import (
    create_api_token,
    delete_api_token,
    get_api_token_status
)
from oqtopus_cloud.user.schemas.api_token import ApiToken, ApiTokenStatus
from starlette.requests import Request
from zoneinfo import ZoneInfo

utc = ZoneInfo("UTC")


def _get_model(n: int) -> User:
    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "user_identifier": f"email_{n}",
        "email": f"email_{n}",
        "display_name": f"test_user_{n}",
        "userstatus": UserStatus.approved,
        "organization": f"organization_{n}",
        "group_id": f"group_id_{n}",
        "available_devices": '["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"]',
        "api_token_id": None,
        "api_token_hash": None,
        "api_token_expiration": None,
        "created_at": datetime(2024, 3, 4, 12, 34, 57, tzinfo=utc),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58, tzinfo=utc),
    }
    return User(**model_dict)


def _get_model_with_token(n: int) -> User:
    user = _get_model(n)
    user.api_token_id = f"api_token_id_{n}"
    user.api_token_hash = f"api_token_hash_{n}"
    user.api_token_expiration = datetime(2024, 12, 31, 23, 59, 59, tzinfo=utc)
    return user


def test_create_api_token(
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
    request.state.user_identifier = "email_1"

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = create_api_token(
        request,
        test_db,
    )

    adapter = TypeAdapter(ApiToken)
    actual = adapter.validate_python(response)

    assert actual.api_token_id is not None
    assert actual.api_token_secret is not None
    assert actual.api_token_expiration is not None

    user = test_db.query(User).filter(User.user_identifier == "email_1").first()
    assert user.api_token_id == actual.api_token_id
    assert PasswordHasher().verify(user.api_token_hash, actual.api_token_secret)
    assert pytz.utc.localize(user.api_token_expiration) == actual.api_token_expiration


def test_create_api_token_no_user_found(
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
    request.state.user_identifier = "email_2"

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = create_api_token(
        request,
        test_db,
    )

    assert response.status_code == 404


def test_create_api_token_user_status_suspended(
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
    request.state.user_identifier = "email_1"

    test_db.flush()
    new_user = _get_model(1)
    new_user.userstatus = UserStatus.suspended
    test_db.add(new_user)
    test_db.commit()

    response = create_api_token(
        request,
        test_db,
    )

    assert response.status_code == 403


def test_create_api_token_500(
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
    request.state.user_identifier = "email_1"

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = create_api_token(
        request,
        None,
    )

    assert response.status_code == 500


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
    request.state.user_identifier = "email_1"

    test_db.flush()
    test_db.add(_get_model_with_token(1))
    test_db.commit()

    # check if user has api token
    assert (
        test_db.query(User).filter(User.user_identifier == "email_1").first().api_token_id
        == "api_token_id_1"
    )

    response = delete_api_token(
        request,
        test_db,
    )
    assert response.status_code == 200

    # check if api token is deleted
    user = test_db.query(User).filter(User.user_identifier == "email_1").first()
    assert user.api_token_id is None
    assert user.api_token_hash is None
    assert user.api_token_expiration is None


def test_delete_api_token_500():
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
    request.state.user_identifier = "email_1"

    response = delete_api_token(
        request,
        None,
    )
    assert response.status_code == 500


def test_delete_api_token_no_user_found(
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
    request.state.user_identifier = "email_2"

    test_db.flush()
    test_db.add(_get_model_with_token(1))
    test_db.commit()

    # check if user has api token
    assert (
        test_db.query(User).filter(User.user_identifier == "email_1").first().api_token_id
        == "api_token_id_1"
    )

    response = delete_api_token(
        request,
        test_db,
    )

    assert response.status_code == 404

    # check if api token is NOT deleted
    assert (
        test_db.query(User).filter(User.user_identifier == "email_1").first().api_token_id
        == "api_token_id_1"
    )


def test_delete_api_token_user_status_suspended(
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
    request.state.user_identifier = "email_1"

    test_db.flush()
    new_user = _get_model_with_token(1)
    new_user.userstatus = UserStatus.suspended
    test_db.add(new_user)
    test_db.commit()

    # check if user has api token
    assert (
        test_db.query(User).filter(User.user_identifier == "email_1").first().api_token_id
        == "api_token_id_1"
    )

    response = delete_api_token(
        request,
        test_db,
    )
    assert response.status_code == 403
    # check if api token is NOT deleted
    assert (
        test_db.query(User).filter(User.user_identifier == "email_1").first().api_token_id
        == "api_token_id_1"
    )

def test_get_api_token_status(
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
    request.state.user_identifier = "email_1"

    test_db.flush()
    test_db.add(_get_model_with_token(1))
    test_db.commit()

    response = get_api_token_status(
        request,
        test_db,
    )
    assert response == ApiTokenStatus(
        api_token_expiration=datetime(2024, 12, 31, 23, 59, 59, tzinfo=utc),
    )


def test_get_api_token_no_user_found(
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
    request.state.user_identifier = "email_2"

    test_db.flush()
    test_db.add(_get_model_with_token(1))
    test_db.commit()

    response = get_api_token_status(
        request,
        test_db,
    )
    assert response.status_code == 404


def test_get_api_token_no_user_status_suspended(
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
    request.state.user_identifier = "email_1"

    test_db.flush()
    new_user = _get_model_with_token(1)
    new_user.userstatus = UserStatus.suspended
    test_db.add(new_user)
    test_db.commit()

    response = get_api_token_status(
        request,
        test_db,
    )
    assert response.status_code == 403


def test_get_api_token_500(
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
    request.state.user_identifier = "email_1"

    test_db.flush()
    test_db.add(_get_model_with_token(1))
    test_db.commit()

    response = get_api_token_status(
        request,
        None,
    )
    assert response.status_code == 500
