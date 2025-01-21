from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import Response
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.admin.lambda_function import app

from oqtopus_cloud.admin.schemas.whitelist_user import (
    GetWhitelistUserResponse,
    WhitelistUserRegisterRequest,
)
from oqtopus_cloud.admin.schemas.whitelist_users import (
    GetWhitelistUsersResponse,
    WhitelistUsersRegisterRequest,
    WhitelistUsersDeleteRequest,
)
from pydantic.type_adapter import TypeAdapter

client = TestClient(app)


def _get_model(n: int, is_completed: bool) -> WhitelistUser:
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


def test_get_whitelist_users_simple(
    test_db,
):
    """_summary_
    Simple GET /whitelist_users tests
    """

    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.commit()

    response = client.get("/whitelist_users")
    adapter = TypeAdapter(GetWhitelistUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetWhitelistUsersResponse(
        users=[
            GetWhitelistUserResponse(
                id=1,
                email="email_1",
                group_id="group_id_1",
                username="username_1",
                organization="organization_1",
                is_signup_completed=True,
            ),
            GetWhitelistUserResponse(
                id=2,
                email="email_2",
                group_id="group_id_2",
                username="username_2",
                organization="organization_2",
                is_signup_completed=False,
            ),
        ],
    )

    assert response.status_code == 200
    assert actual == expect


def test_get_whitelist_users_offset1_limit1(
    test_db,
):
    """_summary_
    Simple GET /whitelist_users tests with offset and limit
    """

    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.add(_get_model(3, False))
    test_db.commit()

    response = client.get("/whitelist_users?offset=1&limit=1")
    adapter = TypeAdapter(GetWhitelistUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetWhitelistUsersResponse(
        users=[
            GetWhitelistUserResponse(
                id=2,
                email="email_2",
                group_id="group_id_2",
                username="username_2",
                organization="organization_2",
                is_signup_completed=False,
            ),
        ],
    )

    assert response.status_code == 200
    assert actual == expect


def test_post_whitelist_users(test_db):
    """_summary_
    Simple POST /whitelist_users tests
    """
    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.commit()
    request_body = WhitelistUsersRegisterRequest(
        users=[
            WhitelistUserRegisterRequest(
                email="email_3",
                group_id="group_id_3",
                username="username_3",
                organization="organization_3",
            ),
            WhitelistUserRegisterRequest(
                email="email_4",
                group_id="group_id_4",
                username="username_4",
                organization="organization_4",
            ),
        ]
    )
    response = client.post(
        "/whitelist_users",
        json=request_body.model_dump(),
    )
    assert response.status_code == 201

    # check the registered users
    response = client.get("/whitelist_users")
    adapter = TypeAdapter(GetWhitelistUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetWhitelistUsersResponse(
        users=[
            GetWhitelistUserResponse(
                id=1,
                email="email_1",
                group_id="group_id_1",
                username="username_1",
                organization="organization_1",
                is_signup_completed=True,
            ),
            GetWhitelistUserResponse(
                id=2,
                email="email_2",
                group_id="group_id_2",
                username="username_2",
                organization="organization_2",
                is_signup_completed=False,
            ),
            GetWhitelistUserResponse(
                id=3,
                email="email_3",
                group_id="group_id_3",
                username="username_3",
                organization="organization_3",
                is_signup_completed=False,
            ),
            GetWhitelistUserResponse(
                id=4,
                email="email_4",
                group_id="group_id_4",
                username="username_4",
                organization="organization_4",
                is_signup_completed=False,
            ),
        ],
    )
    assert response.status_code == 200
    assert actual == expect


def test_delete_whitelist_users(test_db):
    """_summary_
    Simple DELETE /whitelist_users tests
    """
    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.add(_get_model(3, False))
    test_db.add(_get_model(4, False))
    test_db.commit()
    request_body = WhitelistUsersDeleteRequest(user_emails=["email_2", "email_4"])
    response = client.request(
        "DELETE",
        "/whitelist_users",
        json=request_body.model_dump(),
    )

    assert response.status_code == 204

    # check the registered users
    response = client.get("/whitelist_users")
    adapter = TypeAdapter(GetWhitelistUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = GetWhitelistUsersResponse(
        users=[
            GetWhitelistUserResponse(
                id=1,
                email="email_1",
                group_id="group_id_1",
                username="username_1",
                organization="organization_1",
                is_signup_completed=True,
            ),
            GetWhitelistUserResponse(
                id=3,
                email="email_3",
                group_id="group_id_3",
                username="username_3",
                organization="organization_3",
                is_signup_completed=False,
            ),
        ]
    )

    assert response.status_code == 200
    assert actual == expect
