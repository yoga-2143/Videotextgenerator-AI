import pytest
from app.services.transcript_service import extract_video_id, TranscriptError
from app.models.models import User, Video
from app.utils.auth_utils import issue_token
from app import db


def test_extract_video_id_watch_url():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_short_url():
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_shorts_url():
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_invalid():
    with pytest.raises(TranscriptError):
        extract_video_id("https://example.com/not-a-video")


def test_extract_video_id_empty():
    with pytest.raises(TranscriptError):
        extract_video_id("")


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_languages_endpoint(client):
    resp = client.get("/api/languages")
    assert resp.status_code == 200
    codes = [l["code"] for l in resp.get_json()["data"]]
    assert "ta" in codes and "en" in codes


def test_history_endpoint(client, app):
    # Unauthenticated request returns 200 OK
    resp_unauth = client.get("/api/history")
    assert resp_unauth.status_code == 200

    with app.app_context():
        user = User(email="test_hist@example.com")
        db.session.add(user)
        db.session.commit()
        token = issue_token(user)

    resp = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_get_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_get_me_authenticated(client, app):
    with app.app_context():
        user = User(google_id="test_g_123", email="user@example.com", name="Test User")
        db.session.add(user)
        db.session.commit()
        token = issue_token(user)

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["success"] is True
    assert json_data["data"]["user"]["email"] == "user@example.com"


def test_logout_endpoint(client, app):
    with app.app_context():
        user = User.query.filter_by(google_id="test_g_123").first()
        if not user:
            user = User(google_id="test_g_123", email="user@example.com", name="Test User")
            db.session.add(user)
            db.session.commit()
        token = issue_token(user)

    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_delete_history_item_not_found(client, app):
    with app.app_context():
        user = User(email="del_nf@example.com")
        db.session.add(user)
        db.session.commit()
        token = issue_token(user)

    resp = client.delete("/api/history/9999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_delete_history_item_open(client, app):
    with app.app_context():
        user = User(email="del_open@example.com")
        db.session.add(user)
        db.session.commit()

        video = Video(youtube_id="v_12345", youtube_url="https://youtube.com/watch?v=v_12345", title="Public Video", user_id=user.id)
        db.session.add(video)
        db.session.commit()
        video_id = video.id
        token = issue_token(user)

    resp = client.delete(f"/api/history/{video_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_delete_history_item_success(client, app):
    with app.app_context():
        from app.models.models import Transcript, Article, Audio
        user = User(google_id="owner_delete", email="owner_del@example.com")
        db.session.add(user)
        db.session.commit()

        video = Video(user_id=user.id, youtube_id="v_to_delete", youtube_url="https://youtube.com/watch?v=v_to_delete", title="To Delete")
        db.session.add(video)
        db.session.commit()

        transcript = Transcript(video_id=video.id, raw_text="raw", cleaned_text="cleaned")
        article = Article(video_id=video.id, language="en", title="Title", content="Content")
        db.session.add_all([transcript, article])
        db.session.commit()

        audio = Audio(article_id=article.id, language="en", file_path="")
        db.session.add(audio)
        db.session.commit()

        token = issue_token(user)
        video_id = video.id

    resp = client.delete(f"/api/history/{video_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    with app.app_context():
        from app.models.models import Transcript, Article, Audio
        deleted_v = db.session.get(Video, video_id)
        assert deleted_v is None
        assert Article.query.filter_by(video_id=video_id).first() is None
        assert Transcript.query.filter_by(video_id=video_id).first() is None


def test_process_video_missing_url(client):
    resp = client.post("/api/videos/process", json={"url": ""})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_whisper_fallback_skipped_for_unavailable_video(monkeypatch):
    from app.services import transcript_service

    def fake_fetch_transcript(video_id, *args, **kwargs):
        raise transcript_service.TranscriptError("VIDEO_UNAVAILABLE", "gone")

    monkeypatch.setattr(transcript_service, "fetch_transcript", fake_fetch_transcript)

    with pytest.raises(transcript_service.TranscriptError) as exc_info:
        transcript_service.get_transcript("dQw4w9WgXcQ")
    assert exc_info.value.code == "VIDEO_UNAVAILABLE"


def test_whisper_fallback_triggers_for_no_transcript(monkeypatch):
    from app.services import transcript_service

    def fake_fetch_transcript(video_id, *args, **kwargs):
        raise transcript_service.TranscriptError("NO_TRANSCRIPT", "none")

    def fake_whisper(video_id, *args, **kwargs):
        return "transcribed text", "en"

    monkeypatch.setattr(transcript_service, "fetch_transcript", fake_fetch_transcript)
    monkeypatch.setattr(
        "app.services.whisper_service.transcribe_with_whisper", fake_whisper
    )

    text, lang, source = transcript_service.get_transcript("dQw4w9WgXcQ")
    assert text == "transcribed text"
    assert source == "whisper"
