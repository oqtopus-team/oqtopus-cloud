import os
from typing import (
    Generator,
)

import boto3
import pytest
from fastapi import Request as Event
from oqtopus_cloud.admin.lambda_function import app
from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.session import (
    get_db,
)
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
    def admin_set_user_mfa_preference(
        self,
        SMSMfaSettings=None,
        SoftwareTokenMfaSettings=None,
        Username=None,
        UserPoolId=None,
        **kwargs,
    ):
        return {"Response": "Ok"}

    def admin_delete_user(
        self,
        SMSMfaSettings=None,
        SoftwareTokenMfaSettings=None,
        Username=None,
        UserPoolId=None,
        **kwargs,
    ):
        return {"Response": "Ok"}


def fake_boto3_client(service, region_name=None, **kwargs):
    if service == "cognito-idp":
        return FakeCognitoClient()
    raise ValueError(f"Unsupported service: {service}")


@pytest.fixture(autouse=True)
def override_boto3_client(monkeypatch):
    monkeypatch.setattr(boto3, "client", fake_boto3_client)


@pytest.fixture
def apigw_event_dummy():
    response = Event({"type": "http"})
    response.user_pool_id = "dummy_user_pool_id"
    response.region = "dummy_region"
    response.state.user_id = "username_1"
    return response
