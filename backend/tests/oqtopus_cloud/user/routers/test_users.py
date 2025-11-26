import json
from datetime import datetime
import pytz
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from starlette.requests import Request
from typing import Any, Dict

from fastapi.testclient import TestClient
from oqtopus_cloud.user.lambda_function import app
from oqtopus_cloud.user.schemas.users import (
    GetOneUserResponse,
    UpdateUserRequest,
)
from oqtopus_cloud.user.schemas.errors import (
    InternalServerErrorResponse,
    NotFoundErrorResponse,
    BadRequestResponse,
    UnauthorizedResponse,
)
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.user.routers.users import get_user, update_user, delete_user
from oqtopus_cloud.user.common.validation_utils import LEN_VARCHAR

client = TestClient(app)

def _get_model(n: int) -> User:
    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "email": f"email_{n}",
        "username": f"username_{n}",
        "userstatus": "approved",
        "api_token_secret": f"api_token_secret_{n}",
        "organization": f"organization_{n}",
        "group_id": f"group_id_{n}",
        "available_devices": '["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"]',
        "api_token_expiration": datetime(2024, 3, 4, 12, 34, 56),
        "created_at": datetime(2024, 3, 4, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58),
    }
    return User(**model_dict)


def _get_model_whitelist(n: int, is_completed: bool) -> WhitelistUser:
    model_dict = {
        "id": n,
        "email": f"email_{n}",
        "group_id": f"group_id_{n}",
        "is_signup_completed": is_completed,
        "username": f"username_{n}",
        "organization": f"organization_{n}",
        "created_at": datetime(2024, 3, 4, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58),
    }
    return WhitelistUser(**model_dict)


def _create_request(
        method="GET", 
        headers=[("Authorization".lower().encode(), "Bearer some_access_token".encode())]
) -> Request:
    scope: Dict[str, Any] = {
        "type": "http",
        "method": method,
        "path": "/test",
        "headers": headers,
        "state": { "region": "test_region" }
    }

    return Request(scope=scope)


def test_get_user(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    actual = get_user(request, test_db)
    
    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="username_1",
        organization="organization_1",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57))
    )
    
    assert actual == expected


def test_get_user_not_found(test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_2"
    response = get_user(request, test_db)

    assert type(response) is NotFoundErrorResponse
    assert response.status_code == 404
    assert json.loads(response.body) == {
        "message": "user is not found"
    }


def test_get_one_user_500_on_unexpected_error(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    response = get_user(request)

    assert type(response) is InternalServerErrorResponse
    assert response.status_code == 500
    assert json.loads(response.body) == {
        "message": "Internal Server Error"
    }


def test_update_user(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"

    request_body = UpdateUserRequest(name="new_name", organization="new_organization")
    actual = update_user(request, request_body, test_db)

    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="new_name",
        organization="new_organization",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57))
    )

    assert actual == expected


def test_update_user_update_only_fields_present_in_request(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"

    request_body = UpdateUserRequest(name="new_name")
    actual = update_user(request, request_body, test_db)

    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="new_name",
        organization="organization_1",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57))
    )

    assert actual == expected


def test_update_user_not_found(test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_2"

    request_body = UpdateUserRequest(name="new_name", organization="new_organization")
    response = update_user(request, request_body, test_db)

    assert type(response) is NotFoundErrorResponse
    assert response.status_code == 404
    assert json.loads(response.body) == {
        "message": "user not found"
    }


def test_update_user_name_too_long(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"

    too_long_name = "a" * (LEN_VARCHAR + 1)
    request_body = UpdateUserRequest(name=too_long_name, organization="new_organization")
    response = update_user(request, request_body, test_db)
    
    assert type(response) is BadRequestResponse
    assert response.status_code == 400
    assert json.loads(response.body) == {"message": f"The length of {too_long_name} exceeds the limit. Please enter within {LEN_VARCHAR} characters"}


def test_update_user_organization_too_long(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"

    too_long_organization = "a" * (LEN_VARCHAR + 1)
    request_body = UpdateUserRequest(name="new_name", organization=too_long_organization)
    response = update_user(request, request_body, test_db)
    
    assert type(response) is BadRequestResponse
    assert response.status_code == 400
    assert json.loads(response.body) == {"message": f"The length of {too_long_organization} exceeds the limit. Please enter within {LEN_VARCHAR} characters"}


def test_update_user_500_on_unexpected_error(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    request_body = UpdateUserRequest(name="new_name", organization="new_organization")
    response = update_user(request, request_body)

    assert type(response) is InternalServerErrorResponse
    assert response.status_code == 500
    assert json.loads(response.body) == {
        "message": "Internal Server Error"
    }


def test_delete_user(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model_whitelist(n, is_completed=True))
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    response = delete_user(request, test_db)

    assert response is None

    get_response = get_user(request, test_db)

    assert type(get_response) is NotFoundErrorResponse
    assert get_response.status_code == 404

    # confirm the is_signup_completed is set to False in whitelist_users
    whitelist_user = test_db.query(WhitelistUser).filter(WhitelistUser.id == n).first()
    assert whitelist_user.is_signup_completed is False


def test_delete_user_no_auth_header(test_db):
    request = _create_request(headers=[])
    request.state.owner = f"email_{1}"
    response = delete_user(request, test_db)

    assert type(response) is UnauthorizedResponse
    assert response.status_code == 401
    assert json.loads(response.body) == {
        "message": "authorization header not found"
    }


def test_delete_user_no_bearer_in_auth_header(test_db):
    request = _create_request(headers=[("Authorization".lower().encode(), "some_access_token".encode())])
    request.state.owner = f"email_{1}"
    response = delete_user(request, test_db)

    assert type(response) is UnauthorizedResponse
    assert response.status_code == 401
    assert json.loads(response.body) == {
        "message": "authorization header provided with invalid format"
    }


def test_delete_user_invalid_auth_header(test_db):
    request = _create_request(headers=[("Authorization".lower().encode(), "not_a_bearer some_access_token".encode())])
    request.state.owner = f"email_{1}"
    response = delete_user(request, test_db)

    assert type(response) is UnauthorizedResponse
    assert response.status_code == 401
    assert json.loads(response.body) == {
        "message": "authorization header provided with invalid format"
    }


def test_delete_user_no_user(test_db):
    test_db.flush()

    request = _create_request()
    request.state.owner = f"email_{2}"
    response = delete_user(request, test_db)

    assert type(response) is NotFoundErrorResponse
    assert response.status_code == 404
    assert json.loads(response.body) == {
        "message": "User not found"
    }


def test_delete_user_500(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model_whitelist(n, is_completed=True))
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    response = delete_user(request)

    assert type(response) is InternalServerErrorResponse
    assert response.status_code == 500
    assert json.loads(response.body) == {
        "message": "Internal Server Error"
    }