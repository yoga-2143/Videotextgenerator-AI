import pytest
from app import db
from app.services.job_manager import create_video_job, cancel_job, get_job_state
from app.services.llm_service import article_to_plain_text


def test_job_cancellation_flow():
    job_id = create_video_job("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ")
    state_initial = get_job_state(job_id)
    assert state_initial["status"] == "processing"

    cancelled = cancel_job(job_id)
    assert cancelled is True

    state_after = get_job_state(job_id)
    assert state_after["status"] == "failed"
    assert state_after["stage"] == "CANCELLED"
    assert state_after["cancelled"] is True


def test_article_to_plain_text_strips_key_point_labels():
    raw_article = {
        "title": "Web Development Basics",
        "sections": [
            {
                "heading": "IMPORTANT CONTENT",
                "body": "Key Point 1: Web development involves building sites with HTML, CSS, and JS.\nKey Point 2: Figma is used for UI design."
            }
        ]
    }
    result = article_to_plain_text(raw_article)
    assert "Key Point 1:" not in result
    assert "Key Point 2:" not in result
    assert "Web development involves building sites" in result
    assert "Figma is used for UI design." in result


def test_cancel_job_endpoint(client):
    res = client.post("/api/jobs/process", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert res.status_code == 200
    job_id = res.get_json()["data"]["job_id"]

    cancel_res = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.get_json()["success"] is True

    status_res = client.get(f"/api/jobs/{job_id}")
    assert status_res.get_json()["data"]["stage"] == "CANCELLED"
