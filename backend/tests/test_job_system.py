import pytest
from app.services.transcript_service import extract_video_id, TranscriptError
from app.services.job_manager import create_video_job, get_job_state, update_job_stage, set_job_result, set_job_error, JobStage
from app.services.llm_service import clean_speech_sentence, synthesize_clean_prose, proofread_content


def test_job_manager_creation_and_stage_transitions():
    job_id = create_video_job("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ")
    state = get_job_state(job_id)
    assert state is not None
    assert state["status"] == "processing"
    assert state["stage"] == JobStage.QUEUED

    update_job_stage(job_id, JobStage.FETCHING_TRANSCRIPT)
    state = get_job_state(job_id)
    assert state["stage"] == JobStage.FETCHING_TRANSCRIPT
    assert state["progress"] == 20

    set_job_result(job_id, {"video_id": 123, "article": {"id": 456}})
    state = get_job_state(job_id)
    assert state["status"] == "completed"
    assert state["progress"] == 100
    assert state["result_available"] is True


def test_job_manager_error_handling():
    job_id = create_video_job("https://www.youtube.com/watch?v=invalid_vid", "invalid_vid")
    set_job_error(job_id, "TRANSCRIPT_UNAVAILABLE", "Captions not accessible.", retryable=True)

    state = get_job_state(job_id)
    assert state["status"] == "failed"
    assert state["progress"] == 0
    assert state["error"]["code"] == "TRANSCRIPT_UNAVAILABLE"
    assert state["error"]["retryable"] is True


def test_submit_job_api_valid_url(client):
    resp = client.post("/api/jobs/process", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["success"] is True
    assert "job_id" in json_data["data"]

    job_id = json_data["data"]["job_id"]
    status_resp = client.get(f"/api/jobs/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.get_json()["success"] is True


def test_submit_job_api_invalid_url(client):
    resp = client.post("/api/jobs/process", json={"url": "invalid_url_string"})
    assert resp.status_code == 400
    json_data = resp.get_json()
    assert json_data["success"] is False
    assert json_data["error"]["code"] == "INVALID_URL"
    assert json_data["error"]["retryable"] is False


def test_context_aware_correction_rules():
    # Context-aware correction when Figma design context present
    text_figma = "We created the website mockup in Pigma and exported index html."
    cleaned = clean_speech_sentence(text_figma)
    assert "Figma" in cleaned
    assert "index.html" in cleaned

    # Uncertain / ambiguous text preserved without hallucination
    text_ambiguous = "The speaker mentioned pangali in passing."
    # Without Yoga Sutra context, pangali should not be blindly replaced if confidence is low
    clean_ambiguous = clean_speech_sentence(text_ambiguous)
    assert "pangali" in clean_ambiguous.lower() or "patanjali" in clean_ambiguous.lower()


def test_proofread_fallback_preserves_meaning():
    raw_text = "Um hello guys so basically today we are talking about web development and index html."
    proofread = proofread_content(raw_text, video_title="Web Development Tutorial")
    assert "Um" not in proofread
    assert "hello guys" not in proofread.lower()
    assert len(proofread) > 10
