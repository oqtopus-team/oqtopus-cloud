import pytest

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
    assert response.json() == {"message": "news_id=2 is not found."}


def test_get_news_500():
    """_summary_
    GET /news/{news_id} tests 500 error
    """
    response = client.get("/news/1")
    assert response.status_code == 500

@pytest.fixture
def news_body():
    return {
        "title": "Test title",
        "content": "Test content",
        "start_time": "2025-04-08 13:05:47+00:00",
        "end_time": "2025-04-09 13:05:47+00:00",
        "publishable": True
    }

def test_register_news(
    test_db,
    news_body
):
    """_summary_
    POST /news tests
    """

    response = client.post(
        "/news",
        json=news_body,
    )
    assert response.status_code == 200
    assert response.json() == {"message": "News registered successfully"}

    news = test_db.query(News).filter(News.id == "1").first()

    assert news.title == "Test title"
    assert news.content == "Test content"
    assert news.start_time == datetime(2025, 4, 8, 13, 5, 47)
    assert news.end_time == datetime(2025, 4, 9, 13, 5, 47)
    assert news.publishable == True


def test_register_news_missing_parameters(
    news_body,
):
    """_summary_
    POST /news tests with missing mandatory parameter
    """

    for param in news_body.keys():
        malformed_body = news_body.copy()
        del malformed_body[param]

        response = client.post(
            "/news",
            json=malformed_body,
        )
        assert response.status_code == 422


def test_register_news_no_utc(
    news_body,
):
    """_summary_
    POST /news tests with invalid timezones for start_time and end_time
    """

    for param in ["start_time", "end_time"]:
        malformed_body = news_body.copy()
        malformed_body[param] = "2025-04-08 13:05:47+06:00"

        response = client.post(
            "/news",
            json=malformed_body,
        )
        assert response.status_code == 400
        assert response.json() == {"message": "Datetime is not in UTC."}


def test_register_news_500(
    news_body
):
    """_summary_
    POST /news tests 500 error
    """
    response = client.post(
        "/news",
        json=news_body,
    )
    assert response.status_code == 500


def test_update_news_full_update(
    test_db,
    news_body
):
    """_summary_
    PATCH /news tests update all parameters
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.patch(
        "/news/1",
        json=news_body,
    )
    assert response.status_code == 200
    assert response.json() == {"message": "News updated successfully"}

    news = test_db.query(News).filter(News.id == "1").first()

    assert news.title == "Test title"
    assert news.content == "Test content"
    assert news.start_time == datetime(2025, 4, 8, 13, 5, 47)
    assert news.end_time == datetime(2025, 4, 9, 13, 5, 47)
    assert news.publishable == True


def test_update_news_partial_update(
    test_db,
):
    """_summary_
    PATCH /news tests update selected parameters
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.patch(
        "/news/1",
        json={
            "title": "Test title",
            "content": "Test content",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"message": "News updated successfully"}

    news = test_db.query(News).filter(News.id == "1").first()

    assert news.title == "Test title"
    assert news.content == "Test content"
    assert news.start_time == datetime(2024, 3, 4, 14, 0, 0)
    assert news.end_time == datetime(2024, 3, 5, 14, 0, 0)
    assert news.publishable == True


def test_update_news_no_utc(
    test_db,
):
    """_summary_
    PATCH /news tests update with invalid timezones for start_time and end_time
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.patch(
        "/news/1",
        json={
            "start_time": "2025-04-08 13:05:47+06:00"
        },
    )
    assert response.status_code == 400
    assert response.json() == {"message": "Datetime is not in UTC."}


def test_update_news_404(
    test_db,
    news_body
):
    """_summary_
    PATCH /news tests with news not found
    """
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.patch(
        "/news/2",
        json=news_body,
    )
    assert response.status_code == 404
    assert response.json() == {"message": "news_id=2 is not found."}


def test_update_news_500(
    news_body
):
    """_summary_
    PATCH /news tests 500 error
    """
    response = client.patch(
        "/news/1",
        json=news_body,
    )
    assert response.status_code == 500


def test_delete_news(
    test_db,
):
    """_summary_
    DELETE /news tests
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.delete("/news/1")
    assert response.status_code == 204

    news = test_db.query(News).filter(News.id == 1).first()
    assert news is None


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
    assert response.json() == {"message": "news_id=2 is not found."}


def test_delete_news_500():
    """_summary_
    DELETE /news/{news_id} tests 500 error
    """
    response = client.delete("/news/1")
    assert response.status_code == 500
