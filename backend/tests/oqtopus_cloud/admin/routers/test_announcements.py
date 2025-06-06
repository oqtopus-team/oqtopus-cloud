import pytest

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from oqtopus_cloud.admin.lambda_function import app
from oqtopus_cloud.admin.schemas.announcements import (
    GetAnnouncementsListResponse,
    GetAnnouncementResponse
)
from oqtopus_cloud.common.models.announcements import Announcement
from pydantic.type_adapter import TypeAdapter

client = TestClient(app)


def _get_model(n: int) -> Announcement:
    model_dict = {
        "id": n,
        "title": f"title_{n}",
        "content": f"content_{n}",
        "start_time": datetime(2024, 3, 4 + n, 14, 0, 0),
        "end_time": datetime(2024, 3, 5 + n, 14, 0, 0),
        "publishable": True,
        "created_at": datetime(2024, 3, 4 + n, 12, 34, 57),
        "updated_at": datetime(2024, 3, 4 + n, 12, 34, 58),
    }
    return Announcement(**model_dict)


def test_get_all_announcements(
    test_db,
):
    """_summary_
    GET /announcements tests
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/announcements")

    adapter = TypeAdapter(GetAnnouncementsListResponse)
    actual = adapter.validate_python(response.json())
    expect = GetAnnouncementsListResponse(
        announcements=[
            GetAnnouncementResponse(
                id=1,
                title="title_1",
                content="content_1",
                start_time=datetime(2024, 3, 5, 14, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 3, 6, 14, 0, 0, tzinfo=timezone.utc),
                publishable=True,
                updated_at=datetime(2024, 3, 5, 12, 34, 58, tzinfo=timezone.utc)
            ),
            GetAnnouncementResponse(
                id=2,
                title="title_2",
                content="content_2",
                start_time=datetime(2024, 3, 6, 14, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 3, 7, 14, 0, 0, tzinfo=timezone.utc),
                publishable=True,
                updated_at=datetime(2024, 3, 6, 12, 34, 58, tzinfo=timezone.utc)
            ),
        ],
    )

    assert response.status_code == 200
    assert actual == expect


def test_get_all_announcements_offset1_limit2_desc(
    test_db,
):
    """_summary_
    GET /announcements tests with offset and limit
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.add(_get_model(3))
    test_db.add(_get_model(4))
    test_db.commit()

    response = client.get("/announcements?offset=1&limit=2&order=DESC")

    adapter = TypeAdapter(GetAnnouncementsListResponse)
    actual = adapter.validate_python(response.json())
    expect = GetAnnouncementsListResponse(
        announcements=[
            GetAnnouncementResponse(
                id=3,
                title="title_3",
                content="content_3",
                start_time=datetime(2024, 3, 7, 14, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 3, 8, 14, 0, 0, tzinfo=timezone.utc),
                publishable=True,
                updated_at=datetime(2024, 3, 7, 12, 34, 58, tzinfo=timezone.utc)
            ),
            GetAnnouncementResponse(
                id=2,
                title="title_2",
                content="content_2",
                start_time=datetime(2024, 3, 6, 14, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 3, 7, 14, 0, 0, tzinfo=timezone.utc),
                publishable=True,
                updated_at=datetime(2024, 3, 6, 12, 34, 58, tzinfo=timezone.utc)
            ),
        ],
    )

    assert response.status_code == 200
    assert actual == expect


def test_get_announcements_list_with_current_time(test_db):
    test_db.flush()
    test_db.add(Announcement(
        id=1, 
        title="title1", 
        content="content1", 
        start_time=datetime(2025, 1, 5, 12, 34, 56, tzinfo=timezone.utc), 
        end_time=datetime(2025, 1, 6, 12, 34, 56, tzinfo=timezone.utc), 
        updated_at=datetime(2025, 1, 5, 12, 34, 56, tzinfo=timezone.utc)
    ))
    test_db.add(Announcement(
        id=2, 
        title="title2", 
        content="content2", 
        start_time=datetime(2025, 1, 4, 12, 34, 56, tzinfo=timezone.utc), 
        end_time=datetime(2025, 1, 6, 12, 34, 56, tzinfo=timezone.utc), 
        updated_at=datetime(2025, 1, 4, 12, 34, 56, tzinfo=timezone.utc)
    ))
    test_db.add(Announcement(
        id=3, 
        title="title3", 
        content="content3", 
        start_time=datetime(2025, 1, 4, 12, 34, 56, tzinfo=timezone.utc), 
        end_time=datetime(2025, 1, 5, 11, 34, 56, tzinfo=timezone.utc), 
        updated_at=datetime(2025, 1, 4, 12, 34, 56, tzinfo=timezone.utc)
    ))
    test_db.commit()

    response = client.get("/announcements?current_time=2025-01-05T18:20:26Z")
    adapter = TypeAdapter(GetAnnouncementsListResponse)
    actual = adapter.validate_python(response.json())

    expected = GetAnnouncementsListResponse(announcements=[
        GetAnnouncementResponse(
            id=2,
            title="title2",
            content="content2",
            publishable=False,
            start_time=datetime(2025, 1, 4, 12, 34, 56, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 6, 12, 34, 56, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 4, 12, 34, 56, tzinfo=timezone.utc),
        ),
        GetAnnouncementResponse(
            id=1,
            title="title1",
            content="content1",
            publishable=False,
            start_time=datetime(2025, 1, 5, 12, 34, 56, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 6, 12, 34, 56, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 5, 12, 34, 56, tzinfo=timezone.utc),
        ),
    ])

    assert response.status_code == 200
    assert actual == expected


def test_get_all_announcements_500():
    """_summary_
    GET /announcements tests 500 error
    """
    response = client.get("/announcements")
    assert response.status_code == 500


def test_get_announcement(
    test_db,
):
    """_summary_
    GET /announcements/{announcement_id} tests
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/announcements/1")

    adapter = TypeAdapter(GetAnnouncementResponse)
    actual = adapter.validate_python(response.json())
    expect = GetAnnouncementResponse(
        id=1,
        title="title_1",
        content="content_1",
        start_time=datetime(2024, 3, 5, 14, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 3, 6, 14, 0, 0, tzinfo=timezone.utc),
        publishable=True,
        updated_at=datetime(2024, 3, 5, 12, 34, 58, tzinfo=timezone.utc)
    )

    assert response.status_code == 200
    assert actual == expect


def test_get_announcement_404(
    test_db,
):
    """_summary_
    GET /announcements/{announcement_id} tests with announcement not found
    """
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.get("/announcements/2")
    assert response.status_code == 404
    assert response.json() == {"message": "announcement_id=2 is not found."}


def test_get_announcement_500():
    """_summary_
    GET /announcements/{announcement_id} tests 500 error
    """
    response = client.get("/announcements/1")
    assert response.status_code == 500


@pytest.fixture
def announcement_body():
    return {
        "title": "Test title",
        "content": "Test content",
        "start_time": "2025-04-08 13:05:47+00:00",
        "end_time": "2025-04-09 13:05:47+00:00",
        "publishable": True
    }


def test_register_announcement(
    test_db,
    announcement_body
):
    """_summary_
    POST /announcements tests
    """

    response = client.post(
        "/announcements",
        json=announcement_body,
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Announcement registered successfully"}

    announcement = test_db.query(Announcement).filter(Announcement.id == "1").first()

    assert announcement.title == "Test title"
    assert announcement.content == "Test content"
    assert announcement.start_time == datetime(2025, 4, 8, 13, 5, 47)
    assert announcement.end_time == datetime(2025, 4, 9, 13, 5, 47)
    assert announcement.publishable == True


def test_register_announcement_missing_parameters(
    announcement_body,
):
    """_summary_
    POST /announcements tests with missing mandatory parameter
    """

    for param in announcement_body.keys():
        malformed_body = announcement_body.copy()
        del malformed_body[param]

        response = client.post(
            "/announcements",
            json=malformed_body,
        )
        assert response.status_code == 422


def test_register_announcement_no_utc(
    announcement_body,
):
    """_summary_
    POST /announcements tests with invalid timezones for start_time and end_time
    """

    for param in ["start_time", "end_time"]:
        malformed_body = announcement_body.copy()
        malformed_body[param] = "2025-04-08 13:05:47+06:00"

        response = client.post(
            "/announcements",
            json=malformed_body,
        )
        assert response.status_code == 400
        assert response.json() == {"message": "Datetime is not in UTC."}


def test_register_announcements_500(
    announcement_body
):
    """_summary_
    POST /announcements tests 500 error
    """
    response = client.post(
        "/announcements",
        json=announcement_body,
    )
    assert response.status_code == 500


def test_update_announcement_full_update(
    test_db,
    announcement_body
):
    """_summary_
    PATCH /announcements tests update all parameters
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.patch(
        "/announcements/1",
        json=announcement_body,
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Announcement updated successfully"}

    announcement = test_db.query(Announcement).filter(Announcement.id == "1").first()

    assert announcement.title == "Test title"
    assert announcement.content == "Test content"
    assert announcement.start_time == datetime(2025, 4, 8, 13, 5, 47)
    assert announcement.end_time == datetime(2025, 4, 9, 13, 5, 47)
    assert announcement.publishable == True


def test_update_announcement_partial_update(
    test_db,
):
    """_summary_
    PATCH /announcements tests update selected parameters
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.patch(
        "/announcements/1",
        json={
            "title": "Test title",
            "content": "Test content",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Announcement updated successfully"}

    announcement = test_db.query(Announcement).filter(Announcement.id == "1").first()

    assert announcement.title == "Test title"
    assert announcement.content == "Test content"
    assert announcement.start_time == datetime(2024, 3, 5, 14, 0, 0)
    assert announcement.end_time == datetime(2024, 3, 6, 14, 0, 0)
    assert announcement.publishable == True


def test_update_announcement_no_utc(
    test_db,
):
    """_summary_
    PATCH /announcements tests update with invalid timezones for start_time and end_time
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.patch(
        "/announcements/1",
        json={
            "start_time": "2025-04-08 13:05:47+06:00"
        },
    )
    assert response.status_code == 400
    assert response.json() == {"message": "Datetime is not in UTC."}


def test_update_announcement_404(
    test_db,
    announcement_body
):
    """_summary_
    PATCH /announcements tests with announcement not found
    """
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.patch(
        "/announcements/2",
        json=announcement_body,
    )
    assert response.status_code == 404
    assert response.json() == {"message": "announcement_id=2 is not found."}


def test_update_announcement_500(
    announcement_body
):
    """_summary_
    PATCH /announcements tests 500 error
    """
    response = client.patch(
        "/announcements/1",
        json=announcement_body,
    )
    assert response.status_code == 500


def test_delete_announcement(
    test_db,
):
    """_summary_
    DELETE /announcements tests
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.delete("/announcements/1")
    assert response.status_code == 204

    announcement = test_db.query(Announcement).filter(Announcement.id == 1).first()
    assert announcement is None


def test_delete_announcement_404(
    test_db,
):
    """_summary_
    DELETE /announcements/{announcement_id} tests with announcement not found
    """
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.delete("/announcements/2")
    assert response.status_code == 404
    assert response.json() == {"message": "announcement_id=2 is not found."}


def test_delete_announcement_500():
    """_summary_
    DELETE /announcements/{announcement_id} tests 500 error
    """
    response = client.delete("/announcements/1")
    assert response.status_code == 500
