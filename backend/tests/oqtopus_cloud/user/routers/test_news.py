from datetime import datetime
from oqtopus_cloud.common.models.news import News
from oqtopus_cloud.user.schemas.news import GetNewsListResponse, GetNewsResponse
from oqtopus_cloud.user.lambda_function import app

from fastapi.testclient import TestClient
from zoneinfo import ZoneInfo
from pydantic.type_adapter import TypeAdapter

client = TestClient(app)

utc = ZoneInfo("UTC")

def _get_model(id=1, title="news title", content="news content", publishable=False):
    mode_dict = {
        "id": id,
        "title": title,
        "content": content,
        "start_time": datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
        "end_time": datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        "publishable": publishable,
        "created_at": datetime(2023, 1, 1, 10, 30, 40, tzinfo=utc),
        "updated_at": datetime(2023, 1, 4, 11, 11, 20, tzinfo=utc),
    }
    return News(**mode_dict)


def test_get_news_list(test_db):
    test_db.flush()
    test_db.add(_get_model(id=101, title="title101", content="content101", publishable=True))
    test_db.add(_get_model(id=512, title="title512", content="content512", publishable=True))
    test_db.add(_get_model(id=4124, title="title4124", content="content4124", publishable=False))
    test_db.commit()

    response = client.get("/news")
    adapter = TypeAdapter(GetNewsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetNewsListResponse(news=[
        GetNewsResponse(
            id=101,
            title="title101", 
            content="content101", 
            publishable=True,
            start_time=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        ),
        GetNewsResponse(
            id=512,
            title="title512", 
            content="content512", 
            publishable=True,
            start_time=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        ),
        GetNewsResponse(
            id=4124,
            title="title4124", 
            content="content4124", 
            publishable=False,
            start_time=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        ),
    ])

    assert response.status_code == 200
    assert actual == expected

def test_get_news_list_with_offset(test_db):
    test_db.flush()
    test_db.add(_get_model(id=101, title="title101", content="content101", publishable=True))
    test_db.add(_get_model(id=512, title="title512", content="content512", publishable=True))
    test_db.add(_get_model(id=4124, title="title4124", content="content4124", publishable=False))
    test_db.commit()

    response = client.get("/news?offset=2")
    adapter = TypeAdapter(GetNewsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetNewsListResponse(news=[
        GetNewsResponse(
            id=4124,
            title="title4124", 
            content="content4124", 
            publishable=False,
            start_time=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        ),
    ])

    assert response.status_code == 200
    assert actual == expected


def test_get_news_list_with_limit(test_db):
    test_db.flush()
    test_db.add(_get_model(id=101, title="title101", content="content101", publishable=True))
    test_db.add(_get_model(id=512, title="title512", content="content512", publishable=True))
    test_db.add(_get_model(id=4124, title="title4124", content="content4124", publishable=False))
    test_db.commit()

    response = client.get("/news?limit=2")
    adapter = TypeAdapter(GetNewsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetNewsListResponse(news=[
        GetNewsResponse(
            id=101,
            title="title101", 
            content="content101", 
            publishable=True,
            start_time=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        ),
        GetNewsResponse(
            id=512,
            title="title512", 
            content="content512", 
            publishable=True,
            start_time=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        ),
    ])

    assert response.status_code == 200
    assert actual == expected


def test_get_news_list_with_limit_and_offset(test_db):
    test_db.flush()
    test_db.add(_get_model(id=101, title="title101", content="content101", publishable=True))
    test_db.add(_get_model(id=512, title="title512", content="content512", publishable=True))
    test_db.add(_get_model(id=4124, title="title4124", content="content4124", publishable=False))
    test_db.commit()

    response = client.get("/news?limit=2&offset=1")
    adapter = TypeAdapter(GetNewsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetNewsListResponse(news=[
        GetNewsResponse(
            id=512,
            title="title512", 
            content="content512", 
            publishable=True,
            start_time=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        ),
        GetNewsResponse(
            id=4124,
            title="title4124", 
            content="content4124", 
            publishable=False,
            start_time=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        ),
    ])

    assert response.status_code == 200
    assert actual == expected


def test_get_news_list_500():
    response = client.get("/news")
    assert response.status_code == 500


def test_get_news(test_db):
    test_db.flush()
    test_db.add(_get_model(id=101, publishable=True))
    test_db.commit()

    response = client.get("/news/101")
    adapter = TypeAdapter(GetNewsResponse)
    actual = adapter.validate_python(response.json())

    expected = GetNewsResponse(
        id=101,
        title="news title",
        content="news content",
        start_time=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
        end_time=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        publishable= True
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_news_500():
    response = client.get("/news/101")
    assert response.status_code == 500
    

def test_get_news_404(test_db):
    test_db.flush()
    test_db.add(_get_model(id=101, publishable=True))
    test_db.commit()

    response = client.get("/news/202")

    assert response.status_code == 404
