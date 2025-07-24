from datetime import datetime

from fastapi.testclient import TestClient
from oqtopus_cloud.admin.common.validation_utils import LEN_VARCHAR
from oqtopus_cloud.admin.lambda_function import app
from oqtopus_cloud.admin.schemas.users import (
    GetOneUserResponse,
    GetUsersResponse,
    UpdateUserRequest,
    UserStatus,
)
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from pydantic.type_adapter import TypeAdapter

client = TestClient(app)


def _get_model(n: int, status: UserStatus = UserStatus.approved) -> User:
    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "email": f"email_{n}",
        "username": f"username_{n}",
        "userstatus": status,
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


def test_get_users_simple(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2, UserStatus.unapproved))
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
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
            GetOneUserResponse(
                id="2",
                email="email_2",
                name="username_2",
                status=UserStatus.unapproved,
                organization="organization_2",
                group_id="group_id_2",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
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
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
            GetOneUserResponse(
                id="3",
                email="email_3",
                name="username_3",
                status=UserStatus.approved,
                organization="organization_3",
                group_id="group_id_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
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
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
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
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            )
        ],
    )
    assert response.status_code == 200
    assert actual == expect


def test_get_users_order_ascending(test_db):
    test_db.flush()
    test_db.add(_get_model(3))
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/users?sort=name,asc")
    adapter = TypeAdapter(GetUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetUsersResponse(
        offset="0",
        limit="10",
        users=[
            GetOneUserResponse(
                id=1,
                email="email_1",
                name="username_1",
                organization="organization_1",
                status=UserStatus.approved,
                group_id="group_id_1",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
            GetOneUserResponse(
                id=2,
                email="email_2",
                name="username_2",
                organization="organization_2",
                status=UserStatus.approved,
                group_id="group_id_2",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
            GetOneUserResponse(
                id=3,
                email="email_3",
                name="username_3",
                organization="organization_3",
                status=UserStatus.approved,
                group_id="group_id_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            )
        ],
    )
    assert response.status_code == 200
    assert actual == expect


def test_get_users_order_descending(test_db):
    test_db.flush()
    test_db.add(_get_model(3))
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/users?sort=email,desc")
    adapter = TypeAdapter(GetUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetUsersResponse(
        offset="0",
        limit="10",
        users=[
            GetOneUserResponse(
                id=3,
                email="email_3",
                name="username_3",
                organization="organization_3",
                status=UserStatus.approved,
                group_id="group_id_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
            GetOneUserResponse(
                id=2,
                email="email_2",
                name="username_2",
                organization="organization_2",
                status=UserStatus.approved,
                group_id="group_id_2",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
            GetOneUserResponse(
                id=1,
                email="email_1",
                name="username_1",
                organization="organization_1",
                status=UserStatus.approved,
                group_id="group_id_1",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            )
        ],
    )
    assert response.status_code == 200
    assert actual == expect


def test_get_users_invalid_sort_query_parameter():
    response = client.get("/users?sort=name")
    assert response.status_code == 400
    assert response.json() == {"message": "Invalid sort parameter: name"}

    response = client.get("/users?sort=name,desc,something_else")
    assert response.status_code == 400
    assert response.json() == {"message": "Invalid sort parameter: name,desc,something_else"}


def test_get_users_invalid_column_name():
    response = client.get("/users?sort=no_such_column,desc")
    assert response.status_code == 400
    assert response.json() == {"message": "Invalid column name to sort: no_such_column"}


def test_get_users_invalid_order():
    response = client.get("/users?sort=name,invalid_order")
    assert response.status_code == 400
    assert response.json() == {"message": "Invalid order to sort: invalid_order"}


def test_get_user_500():
    response = client.get(
        "/users?name=username_1&organization=organization_1&group_id=group_id_1&status=approved"
    )
    assert response.status_code == 500


def test_patch_job_status_to_suspended(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    update_data = UpdateUserRequest(status=UserStatus.suspended)
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
        available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
    )
    assert response.status_code == 200
    assert actual == expect


def test_patch_job_status_to_unapproved(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    update_data = UpdateUserRequest(status=UserStatus.unapproved)
    response = client.patch("/users/1", json=update_data.model_dump())
    adapter = TypeAdapter(GetOneUserResponse)
    actual = adapter.validate_python(response.json())
    expect = GetOneUserResponse(
        id="1",
        email="email_1",
        name="username_1",
        organization="organization_1",
        status=UserStatus.unapproved,
        group_id="group_id_1",
        available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
    )
    assert response.status_code == 200
    assert actual == expect


def test_patch_user(test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    update_data = UpdateUserRequest(
        name="user_name_1",
        organization="new_organization",
    )
    response = client.patch("/users/1", json=update_data.model_dump())
    adapter = TypeAdapter(GetOneUserResponse)
    actual = adapter.validate_python(response.json())
    expect = GetOneUserResponse(
        id=1,
        email="email_1",
        name="user_name_1",
        organization="new_organization",
        status=UserStatus.approved,
        group_id="group_id_1",
        available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
    )
    assert response.status_code == 200
    assert actual == expect


def test_patch_user_all_fields(test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    update_data = UpdateUserRequest(
        email="email@email.com",
        name="user_name_1",
        organization="new_organization",
        status=UserStatus.unapproved,
        group_id="new_group_id",
        available_devices=["SVSim", "Kawasaki"],
    )
    response = client.patch("/users/1", json=update_data.model_dump())
    adapter = TypeAdapter(GetOneUserResponse)
    actual = adapter.validate_python(response.json())
    expect = GetOneUserResponse(
        id=1,
        email="email@email.com",
        name="user_name_1",
        organization="new_organization",
        status=UserStatus.unapproved,
        group_id="new_group_id",
        available_devices=["SVSim", "Kawasaki"],
    )
    assert response.status_code == 200
    assert actual == expect


def test_patch_job_404(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    update_data = UpdateUserRequest(status=UserStatus.suspended)
    response = client.patch("/users/2", json=update_data.model_dump())
    assert response.status_code == 404
    assert response.json() == {"message": "User not found: 2"}


def test_patch_job_400_email_too_long(test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    too_long_email = "a" * (LEN_VARCHAR + 1)
    update_data = UpdateUserRequest(
        email=too_long_email,
    )
    response = client.patch("/users/1", json=update_data.model_dump())

    assert response.status_code == 400
    assert response.json() == {"message": f"The length of {too_long_email} exceeds the limit. Please enter within {LEN_VARCHAR} characters"}


def test_patch_job_400_email_already_exist(test_db):
    user_1_mail = "email@email.com"
    user_1 = _get_model(1)
    user_1.email = user_1_mail

    test_db.flush()
    test_db.add(user_1)
    test_db.add(_get_model(2))
    test_db.commit()
    update_data = UpdateUserRequest(
        email=user_1_mail,
    )
    response = client.patch("/users/2", json=update_data.model_dump())

    assert response.status_code == 400
    assert response.json() == {"message": f"{user_1_mail} is already registered."}


def test_patch_job_400_name_too_long(test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    too_long_name = "a" * (LEN_VARCHAR + 1)
    update_data = UpdateUserRequest(
        name=too_long_name,
    )
    response = client.patch("/users/1", json=update_data.model_dump())

    assert response.status_code == 400
    assert response.json() == {"message": f"The length of {too_long_name} exceeds the limit. Please enter within {LEN_VARCHAR} characters"}


def test_patch_job_400_organization_too_long(test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    too_long_organization = "a" * (LEN_VARCHAR + 1)
    update_data = UpdateUserRequest(
        organization=too_long_organization,
    )
    response = client.patch("/users/1", json=update_data.model_dump())

    assert response.status_code == 400
    assert response.json() == {"message": f"The length of {too_long_organization} exceeds the limit. Please enter within {LEN_VARCHAR} characters"}


def test_patch_job_400_group_id_too_long(test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()
    too_long_group_id = "a" * (LEN_VARCHAR + 1)
    update_data = UpdateUserRequest(
        group_id=too_long_group_id,
    )
    response = client.patch("/users/1", json=update_data.model_dump())

    assert response.status_code == 400
    assert response.json() == {"message": f"The length of {too_long_group_id} exceeds the limit. Please enter within {LEN_VARCHAR} characters"}


def test_patch_job_500():
    update_data = UpdateUserRequest(status=UserStatus.suspended)
    response = client.patch("/users/2", json=update_data.model_dump())
    assert response.status_code == 500


def test_delete_user(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(3))
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.add(_get_model_whitelist(3, is_completed=True))
    test_db.add(_get_model_whitelist(1, is_completed=True))
    test_db.add(_get_model_whitelist(2, is_completed=True))
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
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            )
        ],
    )
    assert response.status_code == 200
    assert actual == expect

    response = client.delete("/users/1")
    assert response.status_code == 204

    # confirm the user is deleted
    update_data = UpdateUserRequest(status=UserStatus.suspended)
    response = client.patch("/users/1", json=update_data.model_dump())
    assert response.status_code == 404

    # confirm the is_signup_completed is set to False in whitelist_users
    whitelist_user = test_db.query(WhitelistUser).filter(WhitelistUser.id == 1).first()
    assert whitelist_user.is_signup_completed is False


def test_delete_user_404(
    test_db,
):
    test_db.flush()
    test_db.add(_get_model(3))
    test_db.add(_get_model(2))
    test_db.commit()
    # confirm the user is in the database
    response = client.delete("/users/1")
    assert response.status_code == 404


def test_delete_user_500():
    # confirm the user is in the database
    response = client.delete("/users/1")
    assert response.status_code == 500
