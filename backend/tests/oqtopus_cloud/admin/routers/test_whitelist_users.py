import json
from datetime import datetime

from fastapi.testclient import TestClient
from oqtopus_cloud.admin.lambda_function import app
from oqtopus_cloud.admin.schemas.whitelist_users import (
    ListWhitelistUserResponse,
    ListWhitelistUsersResponse,
    RegisterWhitelistUserRequest,
    RegisterWhitelistUsersRequest,
    WhitelistUsersDeleteRequest,
)
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from pydantic.type_adapter import TypeAdapter
from sqlalchemy import select

client = TestClient(app)


def _get_model(n: int, is_completed: bool) -> WhitelistUser:
    model_dict = {
        "id": n,
        "email": f"email_{n}",
        "group_id": f"group_id_{n}",
        "is_signup_completed": is_completed,
        "username": f"username_{n}",
        "organization": f"organization_{n}",
        "available_devices": '["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"]',
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
    adapter = TypeAdapter(ListWhitelistUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = ListWhitelistUsersResponse(
        users=[
            ListWhitelistUserResponse(
                id=1,
                email="email_1",
                group_id="group_id_1",
                username="username_1",
                organization="organization_1",
                is_signup_completed=True,
            ),
            ListWhitelistUserResponse(
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
    adapter = TypeAdapter(ListWhitelistUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = ListWhitelistUsersResponse(
        users=[
            ListWhitelistUserResponse(
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


def test_get_whitelist_users_filtering(
    test_db,
):
    """_summary_
    Simple GET /whitelist_users tests with filtering
    """

    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.add(_get_model(3, False))
    test_db.commit()

    response = client.get(
        "/whitelist_users?email=email_&group_id=group_id_2&organization=organization_2&username=username"
    )
    adapter = TypeAdapter(ListWhitelistUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = ListWhitelistUsersResponse(
        users=[
            ListWhitelistUserResponse(
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


def test_get_whitelist_users_500():
    """_summary_
    Simple GET /whitelist_users tests 500 error
    """

    response = client.get("/whitelist_users")
    assert response.status_code == 500


def test_post_whitelist_users(test_db):
    """_summary_
    Simple POST /whitelist_users tests
    """
    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.commit()
    request_body = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email="email_3",
                group_id="group_id_3",
                username="username_3",
                organization="organization_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
            RegisterWhitelistUserRequest(
                email="email_4",
                group_id="group_id_4",
                username="username_4",
                organization="organization_4",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
        ]
    )
    response = client.post(
        "/whitelist_users",
        json=request_body.model_dump(),
    )
    assert response.status_code == 200

    # check the registered users
    response = client.get("/whitelist_users")
    adapter = TypeAdapter(ListWhitelistUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = ListWhitelistUsersResponse(
        users=[
            ListWhitelistUserResponse(
                id=1,
                email="email_1",
                group_id="group_id_1",
                username="username_1",
                organization="organization_1",
                is_signup_completed=True,
            ),
            ListWhitelistUserResponse(
                id=2,
                email="email_2",
                group_id="group_id_2",
                username="username_2",
                organization="organization_2",
                is_signup_completed=False,
            ),
            ListWhitelistUserResponse(
                id=3,
                email="email_3",
                group_id="group_id_3",
                username="username_3",
                organization="organization_3",
                is_signup_completed=False,
            ),
            ListWhitelistUserResponse(
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


def test_post_whitelist_users_with_all_available_devices(test_db):
    """_summary_
    Simple POST /whitelist_users tests with all available devices 
    using * for one user and actual list of devices for other
    """
    test_db.flush()
    request_body = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email="email_1",
                group_id="group_id_1",
                username="username_1",
                organization="organization_1",
                available_devices="*",
            ),
            RegisterWhitelistUserRequest(
                email="email_2",
                group_id="group_id_2",
                username="username_2",
                organization="organization_2",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
        ]
    )
    response = client.post(
        "/whitelist_users",
        json=request_body.model_dump(),
    )
    assert response.status_code == 200

    whitelist_user_1 = test_db.scalars(select(WhitelistUser).where(WhitelistUser.username == "username_1")).first()
    whitelist_user_2 = test_db.scalars(select(WhitelistUser).where(WhitelistUser.username == "username_2")).first()

    assert whitelist_user_1.available_devices == '*'
    assert whitelist_user_2.available_devices == json.dumps(["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"])


def test_post_whitelist_users_invalid_request_contents(test_db):
    """_summary_
    Simple POST /whitelist_users tests
    """
    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.commit()
    request_body_no_email = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email=None,
                group_id="group_id_3",
                username="username_3",
                organization="organization_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
        ]
    )
    request_body_no_group_id = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email="email_3",
                group_id=None,
                username="username_3",
                organization="organization_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
        ]
    )
    request_body_email_too_long = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email="a" * 256,
                group_id="group_id_3",
                username="username_3",
                organization="organization_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
        ]
    )
    request_body_group_id_too_long = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email="email_3",
                group_id="a" * 256,
                username="username_3",
                organization="organization_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
        ]
    )
    request_body_username_too_long = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email="email_3",
                group_id="group_id_3",
                username="a" * 256,
                organization="organization_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
        ]
    )
    request_body_organization_too_long = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email="email_3",
                group_id="group_id_3",
                username="username_3",
                organization="a" * 256,
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
        ]
    )
    request_body_overlap_username = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email="email_1",
                group_id="group_id_3",
                username="username_3",
                organization="organization_3",
                available_devices=["SC", "SVSim", "Kawasaki", "01927422-86d4-7597-b724-b08a5e7781fc"],
            ),
        ]
    )
    response_no_email = client.post(
        "/whitelist_users",
        json=request_body_no_email.model_dump(),
    )
    assert response_no_email.status_code == 400
    request_body_no_group_id = client.post(
        "/whitelist_users",
        json=request_body_no_group_id.model_dump(),
    )
    assert request_body_no_group_id.status_code == 400
    request_body_email_too_long = client.post(
        "/whitelist_users",
        json=request_body_email_too_long.model_dump(),
    )
    assert request_body_email_too_long.status_code == 400
    request_body_group_id_too_long = client.post(
        "/whitelist_users",
        json=request_body_group_id_too_long.model_dump(),
    )
    assert request_body_group_id_too_long.status_code == 400
    request_body_username_too_long = client.post(
        "/whitelist_users",
        json=request_body_username_too_long.model_dump(),
    )
    assert request_body_username_too_long.status_code == 400
    request_body_organization_too_long = client.post(
        "/whitelist_users",
        json=request_body_organization_too_long.model_dump(),
    )
    assert request_body_organization_too_long.status_code == 400
    request_body_overlap_username = client.post(
        "/whitelist_users",
        json=request_body_overlap_username.model_dump(),
    )
    assert request_body_overlap_username.status_code == 400


def test_post_whitelist_users_no_userlist_in_request(test_db):
    """_summary_
    Simple POST /whitelist_users tests 400 error
    """
    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.commit()
    request_body = RegisterWhitelistUsersRequest(users=[])
    response = client.post(
        "/whitelist_users",
        json=request_body.model_dump(),
    )
    assert response.status_code == 400


def test_post_whitelist_users_no_valid_user(test_db):
    """_summary_
    Simple POST /whitelist_users tests 400 error
    """
    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.commit()
    request_body = RegisterWhitelistUsersRequest(users=None)
    response = client.post(
        "/whitelist_users",
        json=request_body.model_dump(),
    )
    assert response.status_code == 400


def test_post_whitelist_users_no_available_devices(test_db):
    """_summary_
    POST /whitelist_users tests 400 error when available_devices were not provided
    """
    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(2, False))
    test_db.commit()
    request_body = RegisterWhitelistUsersRequest(
        users=[
            RegisterWhitelistUserRequest(
                email="email_3",
                group_id="group_id_3",
                username="username_3",
                organization="a" * 256,
            ),
        ]
    )
    response = client.post(
        "/whitelist_users",
        json=request_body.model_dump(),
    )
    assert response.status_code == 400
    assert response.json() == {"message": "available_devices is required."}


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
    adapter = TypeAdapter(ListWhitelistUsersResponse)
    actual = adapter.validate_python(response.json())
    expect = ListWhitelistUsersResponse(
        users=[
            ListWhitelistUserResponse(
                id=1,
                email="email_1",
                group_id="group_id_1",
                username="username_1",
                organization="organization_1",
                is_signup_completed=True,
            ),
            ListWhitelistUserResponse(
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


def test_delete_whitelist_500():
    """_summary_
    Simple DELETE /whitelist_users tests no deletion
    """
    request_body = WhitelistUsersDeleteRequest(user_emails=["email_5"])
    response = client.request(
        "DELETE",
        "/whitelist_users",
        json=request_body.model_dump(),
    )

    assert response.status_code == 500


def test_delete_whitelist_email_none(test_db):
    """_summary_
    Simple DELETE /whitelist_users tests no deletion
    """
    test_db.flush()
    test_db.add(_get_model(1, True))
    test_db.add(_get_model(3, False))
    test_db.commit()
    request_body = WhitelistUsersDeleteRequest(user_emails=None)
    response = client.request(
        "DELETE",
        "/whitelist_users",
        json=request_body.model_dump(),
    )

    assert response.status_code == 204
