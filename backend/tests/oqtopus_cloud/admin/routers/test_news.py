from datetime import datetime, timezone

from fastapi.testclient import TestClient
from oqtopus_cloud.admin.lambda_function import app
from oqtopus_cloud.admin.schemas.news import (
    GetNewsListResponse,
    GetNewsResponse
)
from oqtopus_cloud.common.models.news import News
from pydantic.type_adapter import TypeAdapter

client = TestClient(app)


def _get_model(n: int) -> News:
    model_dict = {
        "id": n,
        "title": f"title_{n}",
        "content": f"content_{n}",
        "start_time": datetime(2024, 3, 4, 14, 0, 0),
        "end_time": datetime(2024, 3, 5, 14, 0, 0),
        "publishable": True,
        "created_at": datetime(2024, 3, 4, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58),
    }
    return News(**model_dict)


def test_get_all_news(
    test_db,
):
    """_summary_
    GET /news tests
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/news")

    adapter = TypeAdapter(GetNewsListResponse)
    actual = adapter.validate_python(response.json())
    expect = GetNewsListResponse(
        news=[
            GetNewsResponse(
                id=1,
                title="title_1",
                content="content_1",
                start_time=datetime(2024, 3, 4, 14, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 3, 5, 14, 0, 0, tzinfo=timezone.utc),
                publishable=True
            ),
            GetNewsResponse(
                id=2,
                title="title_2",
                content="content_2",
                start_time=datetime(2024, 3, 4, 14, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 3, 5, 14, 0, 0, tzinfo=timezone.utc),
                publishable=True
            ),
        ],
    )

    assert response.status_code == 200
    assert actual == expect


def test_get_all_news_offset1_limit1(
    test_db,
):
    """_summary_
    GET /news tests with offset and limit
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.add(_get_model(3))
    test_db.commit()

    response = client.get("/news?offset=1&limit=1")

    adapter = TypeAdapter(GetNewsListResponse)
    actual = adapter.validate_python(response.json())
    expect = GetNewsListResponse(
        news=[
            GetNewsResponse(
                id=2,
                title="title_2",
                content="content_2",
                start_time=datetime(2024, 3, 4, 14, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 3, 5, 14, 0, 0, tzinfo=timezone.utc),
                publishable=True
            ),
        ],
    )

    assert response.status_code == 200
    assert actual == expect


def test_get_all_news_500():
    """_summary_
    GET /news tests 500 error
    """

    response = client.get("/news")
    assert response.status_code == 500


def test_get_news(
    test_db,
):
    """_summary_
    GET /news/{news_id} tests
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/news/1")

    adapter = TypeAdapter(GetNewsResponse)
    actual = adapter.validate_python(response.json())
    expect = GetNewsResponse(
        id=1,
        title="title_1",
        content="content_1",
        start_time=datetime(2024, 3, 4, 14, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 3, 5, 14, 0, 0, tzinfo=timezone.utc),
        publishable=True
    )

    assert response.status_code == 200
    assert actual == expect


def test_get_news_404(
    test_db,
):
    """_summary_
    GET /news/{news_id} tests with news not found
    """
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.get("/news/2")
    assert response.status_code == 404


def test_get_device_500():
    """_summary_
    GET /news/{news_id} tests 500 error
    """
    response = client.get("/news/1")
    assert response.status_code == 500


def test_delete_news(test_db):
    """_summary_
    DELETE /news tests
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.delete("/news/1")
    assert response.status_code == 204

    response = client.get("/news")

    adapter = TypeAdapter(GetNewsListResponse)
    actual = adapter.validate_python(response.json())
    expect = GetNewsListResponse(
        news=[]
    )

    assert response.status_code == 200
    assert actual == expect


def test_delete_news_404(
    test_db,
):
    """_summary_
    DELETE /news/{news_id} tests with news not found
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.delete("/news/2")
    assert response.status_code == 404


def test_get_device_500():
    """_summary_
    DELETE /news/{news_id} tests 500 error
    """
    response = client.delete("/news/1")
    assert response.status_code == 500
