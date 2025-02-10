from datetime import datetime

from fastapi.testclient import TestClient
from oqtopus_cloud.admin.lambda_function import app
from oqtopus_cloud.admin.schemas.users import (
    GetOneUserResponse,
    GetUsersResponse,
    UpdateUserStatusRequest,
    UserStatus,
)
from oqtopus_cloud.common.models.user import User
from pydantic.type_adapter import TypeAdapter

client = TestClient(app)


def _get_model(n: int) -> User:
    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "email": f"email_{n}",
        "username": f"username_{n}",
        "userstatus": UserStatus.approved,
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


def test_get_users_simple(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/users")
    adapter = TypeAdapter(GetUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetUsersResponse(
        offset="0",
        limit="10",
        users=[
            GetOneUserResponse(
                id="1",
                email="email_1",
                name="username_1",
                organization="organization_1",
                status=UserStatus.approved,
                group_id="group_id_1",
                require_mfa_reset=True,
            ),
            GetOneUserResponse(
                id="2",
                email="email_2",
                name="username_2",
                status=UserStatus.approved,
                organization="organization_2",
                group_id="group_id_2",
                require_mfa_reset=True,
            ),
        ],
    )

    assert response.status_code == 200
    assert actual == expect


def test_get_users_query_limit_offset(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.add(_get_model(3))
    test_db.commit()

    response = client.get("/users?limit=2&offset=1")
    adapter = TypeAdapter(GetUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetUsersResponse(
        offset="1",
        limit="2",
        users=[
            GetOneUserResponse(
                id="2",
                email="email_2",
                name="username_2",
                status=UserStatus.approved,
                organization="organization_2",
                group_id="group_id_2",
                require_mfa_reset=True,
            ),
            GetOneUserResponse(
                id="3",
                email="email_3",
                name="username_3",
                status=UserStatus.approved,
                organization="organization_3",
                group_id="group_id_3",
                require_mfa_reset=True,
            ),
        ],
    )

    assert response.status_code == 200
    assert actual == expect


def test_get_user_by_email(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(3))
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/users?email=email_1")
    adapter = TypeAdapter(GetUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetUsersResponse(
        offset="0",
        limit="10",
        users=[
            GetOneUserResponse(
                id="1",
                email="email_1",
                name="username_1",
                organization="organization_1",
                status=UserStatus.approved,
                group_id="group_id_1",
                require_mfa_reset=True,
            )
        ],
    )
    assert response.status_code == 200
    assert actual == expect


def test_get_user_by_name_organization_groupid_status(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(3))
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get(
        "/users?name=username_1&organization=organization_1&group_id=group_id_1&status=approved"
    )
    adapter = TypeAdapter(GetUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetUsersResponse(
        offset="0",
        limit="10",
        users=[
            GetOneUserResponse(
                id="1",
                email="email_1",
                name="username_1",
                organization="organization_1",
                status=UserStatus.approved,
                group_id="group_id_1",
                require_mfa_reset=True,
            )
        ],
    )
    assert response.status_code == 200
    assert actual == expect


def test_patch_job(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    update_data = UpdateUserStatusRequest(status=UserStatus.suspended)
    response = client.patch("/users/1", json=update_data.model_dump())
    adapter = TypeAdapter(GetOneUserResponse)
    actual = adapter.validate_python(response.json())
    expect = GetOneUserResponse(
        id="1",
        email="email_1",
        name="username_1",
        organization="organization_1",
        status=UserStatus.suspended,
        group_id="group_id_1",
        require_mfa_reset=True,
    )
    assert response.status_code == 200
    assert actual == expect


def test_patch_job_404(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    update_data = UpdateUserStatusRequest(status=UserStatus.suspended)
    response = client.patch("/users/2", json=update_data.model_dump())
    assert response.status_code == 404
    assert response.json() == {"message": "User not found"}


def test_post_job_mfa_reset(test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    response = client.patch("/users/1/mfa_reset")
    adapter = TypeAdapter(GetOneUserResponse)
    actual = adapter.validate_python(response.json())
    expect = GetOneUserResponse(
        id="1",
        email="email_1",
        name="username_1",
        organization="organization_1",
        status=UserStatus.approved,
        group_id="group_id_1",
        require_mfa_reset=False,
    )
    assert response.status_code == 200
    assert actual == expect


def test_delete_user(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(3))
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    # confirm the user is in the database
    response = client.get(
        "/users?name=username_1&organization=organization_1&group_id=group_id_1&status=approved"
    )
    adapter = TypeAdapter(GetUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetUsersResponse(
        offset="0",
        limit="10",
        users=[
            GetOneUserResponse(
                id="1",
                email="email_1",
                name="username_1",
                organization="organization_1",
                status=UserStatus.approved,
                group_id="group_id_1",
                require_mfa_reset=True,
            )
        ],
    )
    assert response.status_code == 200
    assert actual == expect

    response = client.delete("/users/1")
    assert response.status_code == 204

    # confirm the user is deleted
    update_data = UpdateUserStatusRequest(status=UserStatus.suspended)
    response = client.patch("/users/1", json=update_data.model_dump())
    assert response.status_code == 404
