from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.announcements import Announcement
from oqtopus_cloud.user.lambda_function import app
from oqtopus_cloud.user.schemas.announcements import (
    GetAnnouncementResponse,
    GetAnnouncementsListResponse,
)
from pydantic.type_adapter import TypeAdapter
from zoneinfo import ZoneInfo

utc = ZoneInfo("UTC")


def _get_model(
    id=1, title="announcement title", content="announcement content", publishable=False
):
    mode_dict = {
        "id": id,
        "title": title,
        "content": content,
        "start_time": datetime(2023, 1, 2 + id, 12, 34, 56, tzinfo=utc),
        "end_time": datetime(2024, 3, 4 + id, 12, 34, 56, tzinfo=utc),
        "publishable": publishable,
        "created_at": datetime(2023, 1, 1 + id, 10, 30, 40, tzinfo=utc),
        "updated_at": datetime(2023, 1, 4 + id, 11, 11, 20, tzinfo=utc),
    }
    return Announcement(**mode_dict)


def test_get_announcements_list(test_client, test_db):
    test_db.flush()
    test_db.add(_get_model(id=1, title="title1", content="content1", publishable=True))
    test_db.add(_get_model(id=2, title="title2", content="content2", publishable=True))
    test_db.add(_get_model(id=3, title="title3", content="content3", publishable=False))
    test_db.commit()

    response = test_client.get("/announcements")
    adapter = TypeAdapter(GetAnnouncementsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetAnnouncementsListResponse(
        announcements=[
            GetAnnouncementResponse(
                id=1,
                title="title1",
                content="content1",
                publishable=True,
                start_time=datetime(2023, 1, 3, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 5, 12, 34, 56, tzinfo=utc),
            ),
            GetAnnouncementResponse(
                id=2,
                title="title2",
                content="content2",
                publishable=True,
                start_time=datetime(2023, 1, 4, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 6, 12, 34, 56, tzinfo=utc),
            ),
            GetAnnouncementResponse(
                id=3,
                title="title3",
                content="content3",
                publishable=False,
                start_time=datetime(2023, 1, 5, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 7, 12, 34, 56, tzinfo=utc),
            ),
        ]
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_announcements_list_with_offset(test_client, test_db):
    test_db.flush()
    test_db.add(_get_model(id=1, title="title1", content="content1", publishable=True))
    test_db.add(_get_model(id=2, title="title2", content="content2", publishable=True))
    test_db.add(_get_model(id=3, title="title3", content="content3", publishable=False))
    test_db.commit()

    response = test_client.get("/announcements?offset=2")
    adapter = TypeAdapter(GetAnnouncementsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetAnnouncementsListResponse(
        announcements=[
            GetAnnouncementResponse(
                id=3,
                title="title3",
                content="content3",
                publishable=False,
                start_time=datetime(2023, 1, 5, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 7, 12, 34, 56, tzinfo=utc),
            ),
        ]
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_announcements_list_with_limit(test_client, test_db):
    test_db.flush()
    test_db.add(_get_model(id=1, title="title1", content="content1", publishable=True))
    test_db.add(_get_model(id=2, title="title2", content="content2", publishable=True))
    test_db.add(_get_model(id=3, title="title3", content="content3", publishable=False))
    test_db.commit()

    response = test_client.get("/announcements?limit=2")
    adapter = TypeAdapter(GetAnnouncementsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetAnnouncementsListResponse(
        announcements=[
            GetAnnouncementResponse(
                id=1,
                title="title1",
                content="content1",
                publishable=True,
                start_time=datetime(2023, 1, 3, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 5, 12, 34, 56, tzinfo=utc),
            ),
            GetAnnouncementResponse(
                id=2,
                title="title2",
                content="content2",
                publishable=True,
                start_time=datetime(2023, 1, 4, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 6, 12, 34, 56, tzinfo=utc),
            ),
        ]
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_announcements_list_with_order(test_client, test_db):
    test_db.flush()
    test_db.add(_get_model(id=1, title="title1", content="content1", publishable=True))
    test_db.add(_get_model(id=2, title="title2", content="content2", publishable=True))
    test_db.add(_get_model(id=3, title="title3", content="content3", publishable=False))
    test_db.commit()

    response = test_client.get("/announcements?order=DESC")
    adapter = TypeAdapter(GetAnnouncementsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetAnnouncementsListResponse(
        announcements=[
            GetAnnouncementResponse(
                id=3,
                title="title3",
                content="content3",
                publishable=False,
                start_time=datetime(2023, 1, 5, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 7, 12, 34, 56, tzinfo=utc),
            ),
            GetAnnouncementResponse(
                id=2,
                title="title2",
                content="content2",
                publishable=True,
                start_time=datetime(2023, 1, 4, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 6, 12, 34, 56, tzinfo=utc),
            ),
            GetAnnouncementResponse(
                id=1,
                title="title1",
                content="content1",
                publishable=True,
                start_time=datetime(2023, 1, 3, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 5, 12, 34, 56, tzinfo=utc),
            ),
        ]
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_announcements_list_with_current_time(test_client, test_db):
    test_db.flush()
    test_db.add(
        Announcement(
            id=1,
            title="title1",
            content="content1",
            start_time=datetime(2025, 1, 5, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2025, 1, 6, 12, 34, 56, tzinfo=utc),
        )
    )
    test_db.add(
        Announcement(
            id=2,
            title="title2",
            content="content2",
            start_time=datetime(2025, 1, 4, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2025, 1, 6, 12, 34, 56, tzinfo=utc),
        )
    )
    test_db.add(
        Announcement(
            id=3,
            title="title3",
            content="content3",
            start_time=datetime(2025, 1, 4, 12, 34, 56, tzinfo=utc),
            end_time=datetime(2025, 1, 5, 11, 34, 56, tzinfo=utc),
        )
    )
    test_db.commit()

    response = test_client.get("/announcements?current_time=2025-01-05T18:20:26Z")
    adapter = TypeAdapter(GetAnnouncementsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetAnnouncementsListResponse(
        announcements=[
            GetAnnouncementResponse(
                id=2,
                title="title2",
                content="content2",
                publishable=False,
                start_time=datetime(2025, 1, 4, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2025, 1, 6, 12, 34, 56, tzinfo=utc),
            ),
            GetAnnouncementResponse(
                id=1,
                title="title1",
                content="content1",
                publishable=False,
                start_time=datetime(2025, 1, 5, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2025, 1, 6, 12, 34, 56, tzinfo=utc),
            ),
        ]
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_announcements_list_all_params(test_client, test_db):
    test_db.flush()
    test_db.add(_get_model(id=1, title="title1", content="content1", publishable=True))
    test_db.add(_get_model(id=2, title="title2", content="content2", publishable=True))
    test_db.add(_get_model(id=3, title="title3", content="content3", publishable=False))
    test_db.add(_get_model(id=4, title="title4", content="content4", publishable=False))
    test_db.commit()

    response = test_client.get("/announcements?limit=2&offset=1&order=DESC")
    adapter = TypeAdapter(GetAnnouncementsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetAnnouncementsListResponse(
        announcements=[
            GetAnnouncementResponse(
                id=3,
                title="title3",
                content="content3",
                publishable=False,
                start_time=datetime(2023, 1, 5, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 7, 12, 34, 56, tzinfo=utc),
            ),
            GetAnnouncementResponse(
                id=2,
                title="title2",
                content="content2",
                publishable=True,
                start_time=datetime(2023, 1, 4, 12, 34, 56, tzinfo=utc),
                end_time=datetime(2024, 3, 6, 12, 34, 56, tzinfo=utc),
            ),
        ]
    )

    assert response.status_code == 200
    assert actual == expected


@pytest.mark.parametrize("test_client", ["without_db"], indirect=True)
def test_get_announcements_list_500(test_client):
    response = test_client.get("/announcements")
    assert response.status_code == 500


def test_get_announcement(test_client, test_db):
    test_db.flush()
    test_db.add(_get_model(id=1, publishable=True))
    test_db.commit()

    response = test_client.get("/announcements/1")
    adapter = TypeAdapter(GetAnnouncementResponse)
    actual = adapter.validate_python(response.json())

    expected = GetAnnouncementResponse(
        id=1,
        title="announcement title",
        content="announcement content",
        start_time=datetime(2023, 1, 3, 12, 34, 56, tzinfo=utc),
        end_time=datetime(2024, 3, 5, 12, 34, 56, tzinfo=utc),
        publishable=True,
    )

    assert response.status_code == 200
    assert actual == expected


@pytest.mark.parametrize("test_client", ["without_db"], indirect=True)
def test_get_announcement_500(test_client):
    response = test_client.get("/announcements/1")
    assert response.status_code == 500


def test_get_announcement_404(test_client, test_db):
    test_db.flush()
    test_db.add(_get_model(id=1, publishable=True))
    test_db.commit()

    response = test_client.get("/announcements/202")

    assert response.status_code == 404
