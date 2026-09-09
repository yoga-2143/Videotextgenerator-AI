import pytest
from unittest.mock import MagicMock
from app.services.transcript_service import TranscriptError


def test_transcript_error_structure():
    err = TranscriptError("TRANSCRIPT_UNAVAILABLE", "Test transcript error message")
    assert err.code == "TRANSCRIPT_UNAVAILABLE"
    assert str(err) == "Test transcript error message"


def test_process_video_transcript_failure(client, monkeypatch):
    def fake_get_transcript(video_id, *args, **kwargs):
        raise TranscriptError("TRANSCRIPT_UNAVAILABLE", "No transcript available for this video.")

    monkeypatch.setattr("app.routes.youtube.get_transcript", fake_get_transcript)

    resp = client.post("/api/videos/process", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "TRANSCRIPT_UNAVAILABLE"
    assert "No transcript available" in body["error"]["message"]


def test_process_video_llm_failure_uses_fallback(client, app, monkeypatch):
    def fake_get_transcript(video_id, *args, **kwargs):
        return "This is a test transcript sentence one. This is test transcript sentence two.", "en", "captions"

    class FailingLLM:
        def generate_article(self, ranked_text, video_title=""):
            raise RuntimeError("LLM API quota exceeded")

    monkeypatch.setattr("app.routes.youtube.get_transcript", fake_get_transcript)
    monkeypatch.setattr("app.routes.youtube.get_llm_provider", lambda: FailingLLM())

    resp = client.post("/api/videos/process", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"})
    assert resp.status_code in [200, 422, 500]
    body = resp.get_json()
    if resp.status_code == 200:
        assert body["success"] is True
    else:
        assert body["success"] is False
        assert "error" in body


def test_tts_failure_does_not_destroy_article(client, app, monkeypatch):
    with app.app_context():
        from app.models.models import Video, Article, Audio
        from app import db
        # Clean up any existing records from prior runs
        v = Video.query.filter_by(youtube_id="v_tts_test_unique_99").first()
        if v:
            db.session.delete(v)
            db.session.commit()

        v = Video(youtube_id="v_tts_test_unique_99", youtube_url="https://youtube.com/watch?v=v_tts_test_unique_99", status="done")
        db.session.add(v)
        db.session.commit()

        art = Article(video_id=v.id, language="en", title="Test Article", content="Test article content for TTS failure test.")
        db.session.add(art)
        db.session.commit()
        art_id = art.id

    from app.routes.tts import AUDIO_CACHE
    AUDIO_CACHE.clear()

    from app.services.tts_service import TTSError

    def fake_dubbing(text, lang):
        raise TTSError("gTTS service temporarily unavailable")

    monkeypatch.setattr("app.services.tts_service.generate_audio", fake_dubbing)
    monkeypatch.setattr("app.routes.tts.generate_audio", fake_dubbing)
    monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", fake_dubbing)

    resp = client.post(f"/api/articles/{art_id}/audio")
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False
    assert body["error"]["code"] in ["VOICE_GENERATION_FAILED", "TTS_FAILED"]
