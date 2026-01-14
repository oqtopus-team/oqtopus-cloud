import json
from datetime import datetime
import pytz
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from starlette.requests import Request
from typing import Any, Dict
from sqlalchemy import select

from fastapi.testclient import TestClient
from oqtopus_cloud.user.lambda_function import app
from oqtopus_cloud.user.schemas.users import (
    LoginEvent,
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
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.user.routers.users import get_user, update_user, delete_user, localize
from oqtopus_cloud.user.common.validation_utils import LEN_VARCHAR

client = TestClient(app)

def _get_model(n: int) -> User:
    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "email": f"email_{n}",
        "username": f"username_{n}",
        "userstatus": "approved",
        "api_token_id": f"api_token_id{n}",
        "api_token_hash": f"api_token_hash{n}",
        "api_token_expiration": datetime(2026, 3, 4, 12, 34, 56),
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


def _get_job_model(n: int, email: str, job_type: str = "sampling") -> Job:
    model_dict = {
        "id": f"testjob{n}id",
        "owner": email,
        "name": f"testjob{n}",
        "description": f"test job {n}",
        "device_id": "Kawasaki",
        "job_type": job_type,
        "job_info": json.dumps({"program": ["code"]}),
        "transpiler_info": json.dumps({"this_is": "transpiler_info"}),
        "simulator_info": json.dumps({"this_is": "simulator_info"}),
        "mitigation_info": json.dumps(
            {"field1": "value1", "field2": "value2", "field3": "value3"}
        ),
        "status": "submitted",
        "shots": 1000,
        "submitted_at": pytz.utc.localize(datetime(2024, 3, 3 + n, 12, 34, 56)),
        "created_at": pytz.utc.localize(datetime(2024, 3, 3 + n, 12, 34, 56)),
    }
    return Job(**model_dict)


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

    request = Request(scope=scope)
    request.state.user_pool_id = "dummy_user_pool_id"

    return request


def _create_cloud_trail_event(
    cognito_id: str,
    event_name: str = "RespondToAuthChallenge",
    user_agent: str = "test_user_agent",
    token: str | None = "some_token"
):
    return {
        "CloudTrailEvent": json.dumps({
            "eventName": event_name,
            "additionalEventData": {
                "sub": cognito_id
            },
            "responseElements": {
                "authenticationResult": {
                    "accessToken": token,
                }
            },
            "eventTime": pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)).isoformat(),
            "userAgent": user_agent,
            "sourceIPAddress": "127.0.0.1"
        })
    }

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
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57)),
        login_events=[]
    )

    assert actual == expected


def test_get_user_with_login_events(test_db, fake_cloud_trails_client_fixture):
    n = 1
    user_cognito_id = "test_cognito_id"
    test_db.flush()
    user = _get_model(n)
    user.cognito_id = user_cognito_id
    test_db.add(user)
    test_db.commit()

    fake_cloud_trails_client_fixture.events = [{
        "Events": [
            _create_cloud_trail_event(user_cognito_id),
        ]}, {
        "Events": [
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_2"),
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_3")
        ]
    }]

    request = _create_request()
    request.state.owner = f"email_{n}"
    actual = get_user(request, test_db)

    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="username_1",
        organization="organization_1",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57)),
        login_events=[
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="test_user_agent",
                ip="127.0.0.1"
            ),
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_2",
                ip="127.0.0.1"
            ),
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_3",
                ip="127.0.0.1"
            ),
        ]
    )

    assert actual == expected


def test_get_user_should_include_login_events_only_from_given_user(test_db, fake_cloud_trails_client_fixture):
    n = 1
    user_cognito_id = "test_cognito_id"
    test_db.flush()
    user = _get_model(n)
    user.cognito_id = user_cognito_id
    test_db.add(user)
    test_db.commit()

    fake_cloud_trails_client_fixture.events = [{
        "Events": [
            _create_cloud_trail_event(user_cognito_id),
        ]}, {
        "Events": [
            _create_cloud_trail_event("different_user_cognito_id", user_agent="different_user_agent"),
            _create_cloud_trail_event(user_cognito_id)
        ]
    }]

    request = _create_request()
    request.state.owner = f"email_{n}"
    actual = get_user(request, test_db)

    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="username_1",
        organization="organization_1",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57)),
        login_events=[
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="test_user_agent",
                ip="127.0.0.1"
            ),
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="test_user_agent",
                ip="127.0.0.1"
            ),
        ]
    )

    assert actual == expected


def test_get_user_should_include_only_auth_events(test_db, fake_cloud_trails_client_fixture):
    n = 1
    user_cognito_id = "test_cognito_id"
    test_db.flush()
    user = _get_model(n)
    user.cognito_id = user_cognito_id
    test_db.add(user)
    test_db.commit()

    fake_cloud_trails_client_fixture.events = [{
        "Events": [
            _create_cloud_trail_event(user_cognito_id, event_name="different_event"),
        ]}, {
        "Events": [
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_1"),
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_2")
        ]
    }]

    request = _create_request()
    request.state.owner = f"email_{n}"
    actual = get_user(request, test_db)

    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="username_1",
        organization="organization_1",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57)),
        login_events=[
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_1",
                ip="127.0.0.1"
            ),
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_2",
                ip="127.0.0.1"
            ),
        ]
    )

    assert actual == expected


def test_get_user_should_skip_events_without_event_data(test_db, fake_cloud_trails_client_fixture):
    n = 1
    user_cognito_id = "test_cognito_id"
    test_db.flush()
    user = _get_model(n)
    user.cognito_id = user_cognito_id
    test_db.add(user)
    test_db.commit()

    event_without_event_data = {
        "CloudTrailEvent": json.dumps({
            "eventName": "InitiateAuth",
            "requestParameters": {
                "authFlow": "USER_SRP_AUTH"
            },
            "eventTime": pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)).isoformat(),
            "userAgent": "user_agent",
            "sourceIPAddress": "127.0.0.1"
        })
    }

    fake_cloud_trails_client_fixture.events = [{
        "Events": [
            event_without_event_data,
        ]}, {
        "Events": [
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_1"),
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_2")
        ]
    }]

    request = _create_request()
    request.state.owner = f"email_{n}"
    actual = get_user(request, test_db)

    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="username_1",
        organization="organization_1",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57)),
        login_events=[
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_1",
                ip="127.0.0.1"
            ),
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_2",
                ip="127.0.0.1"
            ),
        ]
    )

    assert actual == expected


def test_get_user_should_skip_events_without_response_auth_results(test_db, fake_cloud_trails_client_fixture):
    n = 1
    user_cognito_id = "test_cognito_id"
    test_db.flush()
    user = _get_model(n)
    user.cognito_id = user_cognito_id
    test_db.add(user)
    test_db.commit()

    event_without_response_elements = {
        "CloudTrailEvent": json.dumps({
            "eventName": "InitiateAuth",
            "additionalEventData": {
                "sub": user_cognito_id
            },
            "eventTime": pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)).isoformat(),
            "userAgent": "user_agent",
            "sourceIPAddress": "127.0.0.1"
        })
    }
    event_without_auth_results = {
        "CloudTrailEvent": json.dumps({
            "eventName": "InitiateAuth",
            "additionalEventData": {
                "sub": user_cognito_id
            },
            "responseElements": {},
            "eventTime": pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)).isoformat(),
            "userAgent": "user_agent",
            "sourceIPAddress": "127.0.0.1"
        })
    }

    fake_cloud_trails_client_fixture.events = [{
        "Events": [
            event_without_response_elements,
            event_without_auth_results,
        ]}, {
        "Events": [
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_1"),
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_2")
        ]
    }]

    request = _create_request()
    request.state.owner = f"email_{n}"
    actual = get_user(request, test_db)

    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="username_1",
        organization="organization_1",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57)),
        login_events=[
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_1",
                ip="127.0.0.1"
            ),
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_2",
                ip="127.0.0.1"
            ),
        ]
    )

    assert actual == expected


def test_get_user_should_include_events_with_token(test_db, fake_cloud_trails_client_fixture):
    n = 1
    user_cognito_id = "test_cognito_id"
    test_db.flush()
    user = _get_model(n)
    user.cognito_id = user_cognito_id
    test_db.add(user)
    test_db.commit()

    fake_cloud_trails_client_fixture.events = [{
        "Events": [
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_test", token=None),
        ]}, {
        "Events": [
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_1"),
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_2")
        ]
    }]

    request = _create_request()
    request.state.owner = f"email_{n}"
    actual = get_user(request, test_db)

    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="username_1",
        organization="organization_1",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57)),
        login_events=[
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_1",
                ip="127.0.0.1"
            ),
            LoginEvent(
                event_date=pytz.utc.localize(datetime(2025, 2, 3, 12, 34, 56)),
                user_agent="user_agent_2",
                ip="127.0.0.1"
            ),
        ]
    )

    assert actual == expected


def test_get_user_should_skip_login_events_when_disabled(test_db, monkeypatch, fake_cloud_trails_client_fixture):
    monkeypatch.setenv("LOGIN_HISTORY_ENABLED", "false")
    n = 1
    user_cognito_id = "test_cognito_id"
    test_db.flush()
    user = _get_model(n)
    user.cognito_id = user_cognito_id
    test_db.add(user)
    test_db.commit()

    fake_cloud_trails_client_fixture.events = [{
        "Events": [
            _create_cloud_trail_event(user_cognito_id),
        ]}, {
        "Events": [
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_2"),
            _create_cloud_trail_event(user_cognito_id, user_agent="user_agent_3")
        ]
    }]

    request = _create_request()
    request.state.owner = f"email_{n}"
    actual = get_user(request, test_db)

    expected = GetOneUserResponse(
        id=1,
        email="email_1",
        name="username_1",
        organization="organization_1",
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57)),
        login_events=None
    )

    assert actual == expected


def test_get_user_should_return_only_visible_fields(test_db, monkeypatch):
    monkeypatch.setenv("VISIBLE_FIELDS", '["email", "organization"]')
    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    actual = get_user(request, test_db)

    expected = GetOneUserResponse(
        id=None,
        email="email_1",
        name=None,
        organization="organization_1",
        created_at=None,
        login_events=[]
    )

    assert actual == expected

    monkeypatch.setenv("VISIBLE_FIELDS", '["id", "name", "created_at"]')
    actual2 = get_user(request, test_db)
    expected2 = GetOneUserResponse(
        id=1,
        email=None,
        name="username_1",
        organization=None,
        created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 57)),
        login_events=[]
    )

    assert actual2 == expected2

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


def test_update_user_name_update_disabled(test_db, monkeypatch):
    monkeypatch.setenv("EDITABLE_FIELDS", '["organization"]')

    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"

    request_body = UpdateUserRequest(name="new_name", organization="new_organization")
    response = update_user(request, request_body, test_db)

    assert type(response) is UnauthorizedResponse
    assert response.status_code == 401
    assert json.loads(response.body) == {"message": "name field is disabled for updates"}


def test_update_user_organization_update_disabled(test_db, monkeypatch):
    monkeypatch.setenv("EDITABLE_FIELDS", '["name"]')

    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"

    request_body = UpdateUserRequest(name="new_name", organization="new_organization")
    response = update_user(request, request_body, test_db)

    assert type(response) is UnauthorizedResponse
    assert response.status_code == 401
    assert json.loads(response.body) == {"message": "organization field is disabled for updates"}


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

    # confirm thr whitelist_user got removed
    whitelist_user = test_db.query(WhitelistUser).filter(WhitelistUser.id == n).first()
    assert whitelist_user is None


def test_delete_user_should_remove_user_jobs(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model_whitelist(n, is_completed=True))
    test_db.add(_get_model(n))
    test_db.add(_get_job_model(1, f"email_{n}"))
    test_db.add(_get_job_model(2, f"email_{n}"))
    test_db.add(_get_job_model(3, f"email_{n}"))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    delete_user(request, test_db)

    user_jobs = test_db.scalars(select(Job).where(Job.owner == f"email_{n}")).all()
    assert user_jobs == []


def test_delete_user_should_not_delete_other_users_jobs(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model_whitelist(n, is_completed=True))
    test_db.add(_get_model(n))
    test_db.add(_get_job_model(1, f"email_{n}"))
    test_db.add(_get_job_model(2, f"email_{n}"))
    test_db.add(_get_job_model(3, f"email_{n}"))
    test_db.add(_get_job_model(4, "email_2"))
    test_db.add(_get_job_model(5, "email_3"))
    test_db.add(_get_job_model(6, "email_3"))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    delete_user(request, test_db)

    user2_jobs = test_db.scalars(select(Job).where(Job.owner == "email_2")).all()
    user3_jobs = test_db.scalars(select(Job).where(Job.owner == "email_3")).all()

    assert isinstance(user2_jobs, list)
    assert len(user2_jobs) == 1
    assert isinstance(user3_jobs, list)
    assert len(user3_jobs) == 2


def test_delete_user_should_remove_sse_jobs_from_s3(test_db, test_storage):
    test_db.flush()
    test_db.add(_get_model_whitelist(1, is_completed=True))
    test_db.add(_get_model(1))
    test_db.add(_get_job_model(1, "email_1", job_type="sse"))
    test_db.add(_get_job_model(2, "email_1"))
    test_db.add(_get_job_model(3, "email_1"))
    test_db.commit()

    test_storage.put(key="testjob1id/oqtopus_test_program.py", data=b"program1")
    test_storage.put(key="testjob1id/oqtopus_test_log.log", data=b"log1")
    test_storage.put(key="testjob2id/oqtopus_test_program.py", data=b"program2")
    test_storage.put(key="testjob2id/oqtopus_test_log.log", data=b"log2")

    request = _create_request()
    request.state.owner = "email_1"
    response = delete_user(request, test_db, test_storage)

    assert response is None

    object_keys = [key for key in test_storage.prefix(prefix="testjob1id")]
    assert object_keys == []

    # should not delete other sse jobs from s3
    other_object_keys = [key for key in test_storage.prefix(prefix="testjob2id")]
    assert len(other_object_keys) == 2
    assert "testjob2id/oqtopus_test_program.py" in other_object_keys
    assert "testjob2id/oqtopus_test_log.log" in other_object_keys


def test_delete_user_with_no_whitelist_user(test_db):
    n = 1
    test_db.flush()
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    response = delete_user(request, test_db)

    assert response is None

    get_response = get_user(request, test_db)

    assert type(get_response) is NotFoundErrorResponse
    assert get_response.status_code == 404


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


def test_delete_user_user_deletion_disabled(test_db, monkeypatch):
    monkeypatch.setenv("ALLOW_DELETION", "false")

    n = 1
    test_db.flush()
    test_db.add(_get_model_whitelist(n, is_completed=True))
    test_db.add(_get_model(n))
    test_db.commit()

    request = _create_request()
    request.state.owner = f"email_{n}"
    response = delete_user(request, test_db)

    assert type(response) is UnauthorizedResponse
    assert response.status_code == 401
    assert json.loads(response.body) == {
        "message": "user deletion is disabled"
    }


def test_localize():
    date = datetime(2024, 3, 4, 12, 34, 57)
    actual = localize(date)
    assert pytz.utc.localize(date) == actual


def test_localize_none():
    assert localize(None) is None
