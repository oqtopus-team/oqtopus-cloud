import os
from typing import (
    Generator,
)

import boto3
import pytest
from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user_signup.lambda_function import app
from sqlalchemy import (
    create_engine,
)
from sqlalchemy.exc import (
    SQLAlchemyError,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.orm.session import (
    close_all_sessions,
)


class TestingSession(Session):
    """_summary_

    Args:
            Session (_type_): _description_
    """

    def commit(
        self,
    ) -> None:
        self.flush()
        self.expire_all()


@pytest.fixture(scope="function")
def test_db() -> (
    Generator[
        Session,
        None,
        None,
    ]
):
    """_summary_

    Yields:
            Generator[Session, None, None]: _description_
    """
    print("SetUp")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        echo=True,
    )
    # Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(
        class_=TestingSession,
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    db = TestSessionLocal()

    # https://fastapi.tiangolo.com/advanced/testing-dependencies/
    def get_db_for_testing() -> (
        Generator[
            Session,
            None,
            None,
        ]
    ):
        try:
            yield db
            db.commit()
        except SQLAlchemyError as e:
            assert e is not None
            db.rollback()

    app.dependency_overrides[get_db] = get_db_for_testing

    yield db

    os.remove("./test.db")
    db.rollback()
    close_all_sessions()
    engine.dispose()


class FakeCognitoClient:
    def __init__(self):
        self.confirm_sign_up_exception = None

    def sign_up(
        self,
        ClientId=None,
        Username=None,
        Password=None,
        UserAttributes=[
            {"Name": "email", "Value": None},
        ],
        ValidationData=[],
    ):
        return {"Response": "Ok"}

    def confirm_sign_up(
        self,
        ClientId=None,
        Username=None,
        ConfirmationCode=None,
        ForceAliasCreation=False,
    ):
        if self.confirm_sign_up_exception:
            raise self.confirm_sign_up_exception
        return {"Response": "Ok"}

    def admin_get_user(
        self,
        UserPoolId=None,
        Username=None,
    ):
        return {
            "Username": "user@example.com",
            "UserAttributes": [
                {"Name": "sub", "Value": "cognito-id-1234-5678-9012"},
                {"Name": "email", "Value": "user@example.com"},
                {"Name": "email_verified", "Value": "true"},
            ],
            "Enabled": True,
            "UserStatus": "CONFIRMED",
        }

    def admin_initiate_auth(
        self,
        UserPoolId=None,
        ClientId=None,
        AuthFlow=None,
        AuthParameters=None,
    ):
        return {"Response": "Ok"}


def fake_boto3_client(service, region_name=None, **kwargs):
    if service == "cognito-idp":
        return fake_cognito_client
    raise ValueError(f"Unsupported service: {service}")


@pytest.fixture
def fake_cognito_client_fixture():
    return FakeCognitoClient()


@pytest.fixture(autouse=True)
def override_boto3_client(monkeypatch, fake_cognito_client_fixture):
    global fake_cognito_client
    fake_cognito_client = fake_cognito_client_fixture
    monkeypatch.setattr(boto3, "client", fake_boto3_client)
