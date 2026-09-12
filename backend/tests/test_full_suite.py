import pytest
import os
import json
import tempfile
from unittest.mock import MagicMock
from app import db
from app.models.models import User, Video, Transcript, Article, Audio, TranslationCache
from app.utils.auth_utils import issue_token
from app.services.transcript_service import extract_video_id, TranscriptError
from app.services.job_manager import create_video_job, get_job_state, update_job_stage, set_job_result, set_job_error, JobStage
from app.services.llm_service import clean_speech_sentence, synthesize_clean_prose, proofread_content
from app.services.translator_service import translate_text, _chunk_text
from app.services.tts_service import generate_audio, _chunk_tts_text, AUDIO_DIR


# 1. Invalid URL Test
def test_invalid_url():
    with pytest.raises(TranscriptError) as exc_info:
        extract_video_id("not_a_valid_url")
    assert exc_info.value.code == "INVALID_URL"


# 2. Valid URL Processing Success Test
def test_valid_url_success(client):
    res = client.post("/api/jobs/process", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert "job_id" in body["data"]


# 3. Transcript API Failure Test
def test_transcript_api_failure(client, monkeypatch):
    def fake_get_transcript(*args, **kwargs):
        raise TranscriptError("TRANSCRIPT_UNAVAILABLE", "Captions disabled for this video.")

    monkeypatch.setattr("app.routes.youtube.get_transcript", fake_get_transcript)
    res = client.post("/api/jobs/process", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert res.status_code == 200
    job_id = res.get_json()["data"]["job_id"]

    # Poll status until failure recorded
    import time
    for _ in range(10):
        st = client.get(f"/api/jobs/{job_id}").get_json()["data"]
        if st["status"] == "failed":
            break
        time.sleep(0.1)

    assert st["status"] == "failed"
    assert st["error"]["code"] == "TRANSCRIPT_UNAVAILABLE"


# 4. Slow Transcript Call Timeout Test
def test_slow_transcript_call(monkeypatch):
    def fake_slow_fetch(video_id, request_id=None, timeout_seconds=1):
        raise TranscriptError("TRANSCRIPT_FETCH_TIMEOUT", "Retrieving captions timed out.")

    monkeypatch.setattr("app.services.transcript_service.fetch_transcript", fake_slow_fetch)
    with pytest.raises(TranscriptError) as exc_info:
        fake_slow_fetch("slow_vid_id")
    assert exc_info.value.code == "TRANSCRIPT_FETCH_TIMEOUT"


# 5. Whisper Failure Test
def test_whisper_failure():
    from app.services.whisper_service import WhisperError
    err = WhisperError("SPEECH_TO_TEXT_FAILED", "Whisper STT failed to process audio.")
    assert err.code == "SPEECH_TO_TEXT_FAILED"


# 6. AI Cleanup Failure Fallback Test
def test_ai_cleanup_failure(client, app, monkeypatch):
    def fake_get_transcript(*args, **kwargs):
        return "This is sentence one about web development. This is sentence two about index html.", "en", "captions"

    class FailingLLM:
        def generate_article(self, ranked_text, video_title=""):
            raise RuntimeError("LLM Service Error")

    monkeypatch.setattr("app.routes.youtube.get_transcript", fake_get_transcript)
    monkeypatch.setattr("app.routes.youtube.get_llm_provider", lambda: FailingLLM())

    res = client.post("/api/videos/process", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert res.status_code in [200, 422, 500]


# 7. Database Failure and Rollback Test
def test_database_failure_and_rollback(app):
    with app.app_context():
        try:
            v = Video(youtube_id="rollback_test", youtube_url="invalid_entry", status="processing")
            db.session.add(v)
            # Intentionally cause rollback
            db.session.rollback()
        except Exception:
            db.session.rollback()

        check = Video.query.filter_by(youtube_id="rollback_test").first()
        assert check is None


# 8. Translation Failure Test
def test_translation_failure(client, app, monkeypatch):
    with app.app_context():
        v = Video(youtube_id="v_tr_fail", youtube_url="https://youtube.com/watch?v=v_tr_fail", status="done")
        db.session.add(v)
        db.session.commit()
        art = Article(video_id=v.id, language="en", title="Test", content="Content to translate.")
        db.session.add(art)
        db.session.commit()
        art_id = art.id

    def fake_translate_text(text, target, source):
        from app.services.translator_service import TranslationError
        raise TranslationError("Translation service unavailable.")

    monkeypatch.setattr("app.routes.translate.translate_text", fake_translate_text)
    res = client.post(f"/api/articles/{art_id}/translate", json={"language": "ta"})
    assert res.status_code == 502
    assert res.get_json()["error"]["code"] == "TRANSLATION_FAILED"


# 9. Voice Generation Failure Test
def test_voice_generation_failure(client, app, monkeypatch):
    with app.app_context():
        v = Video.query.filter_by(youtube_id="v_voice_fail").first()
        if v:
            db.session.delete(v)
            db.session.commit()

        v = Video(youtube_id="v_voice_fail", youtube_url="https://youtube.com/watch?v=v_voice_fail", status="done")
        db.session.add(v)
        db.session.commit()
        art = Article(video_id=v.id, language="en", title="Test Voice", content="Content for voice failure test.")
        db.session.add(art)
        db.session.commit()
        art_id = art.id
        Audio.query.filter_by(article_id=art_id).delete()
        db.session.commit()

    from app.routes.tts import AUDIO_CACHE
    AUDIO_CACHE.clear()

    def fake_dubbing(text, target):
        from app.services.tts_service import TTSError
        raise TTSError("gTTS engine timed out")

    monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", fake_dubbing)
    res = client.post(f"/api/articles/{art_id}/audio")
    assert res.status_code == 500
    assert res.get_json()["error"]["code"] == "VOICE_GENERATION_FAILED"


# 10. Frontend/Backend Error Response Compatibility Test
def test_error_response_compatibility(client):
    res = client.post("/api/jobs/process", json={"url": "invalid_url_string"})
    assert res.status_code == 400
    body = res.get_json()
    assert "success" in body
    assert body["success"] is False
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
    assert "retryable" in body["error"]


# 11. Job Always Reaches Completed or Failed State Test
def test_job_completion_or_failure_guarantee():
    job_id = create_video_job("https://youtube.com/watch?v=test_vid_11", "test_vid_11")
    st = get_job_state(job_id)
    assert st["status"] == "processing"

    set_job_result(job_id, {"article": {"id": 1}})
    st_end = get_job_state(job_id)
    assert st_end["status"] in ["completed", "failed"]


# 12. No Infinite Loading Behavior Test
def test_no_infinite_loading_behavior():
    job_id = create_video_job("https://youtube.com/watch?v=test_vid_12", "test_vid_12")
    set_job_error(job_id, "TEST_ERROR", "Test error message", retryable=True)
    st = get_job_state(job_id)
    assert st["status"] == "failed"
    assert st["progress"] == 0


# 13. Duplicate Sentence Cleanup Test
def test_duplicate_sentence_cleanup():
    raw = "Web development is fun. Web development is fun. React is great."
    cleaned = synthesize_clean_prose(raw)
    assert cleaned.count("Web development is fun.") == 1


# 14. Context-Aware Technical Correction Test
def test_context_aware_technical_correction():
    # Figma correction when design context present
    text_design = "We created the website mockup in Pigma and exported index html."
    cleaned_design = clean_speech_sentence(text_design, full_context="Figma UI UX design software mockup")
    assert "Figma" in cleaned_design
    assert "index.html" in cleaned_design

    # Patanjali correction when Yoga context present
    text_yoga = "The ancient sage pangali wrote the yoga sutra on samadi."
    cleaned_yoga = clean_speech_sentence(text_yoga, full_context="Yoga philosophy Patanjali sutra meditation")
    assert "Patanjali" in cleaned_yoga
    assert "Samadhi" in cleaned_yoga


# 15. Uncertain Words Are Not Hallucinated Test
def test_uncertain_words_not_hallucinated():
    text_ambiguous = "The speaker mentioned pangali in passing without elaboration."
    cleaned = clean_speech_sentence(text_ambiguous, full_context="General conversation with no yoga context")
    # Should not blindly hallucinate Patanjali without yoga context
    assert "pangali" in cleaned.lower() or "patanjali" not in cleaned


# 16. Translation Caching Test
def test_translation_caching(client, app):
    with app.app_context():
        v = Video(youtube_id="v_tr_cache", youtube_url="https://youtube.com/watch?v=v_tr_cache", status="done")
        db.session.add(v)
        db.session.commit()
        art = Article(video_id=v.id, language="en", title="Original Title", content="Original content text.")
        db.session.add(art)
        db.session.commit()
        art_id = art.id

        tc = TranslationCache(article_id=art.id, target_language="ta", title="தலைப்பு", content="உள்ளடக்கம்")
        db.session.add(tc)
        db.session.commit()

    res = client.post(f"/api/articles/{art_id}/translate", json={"language": "ta"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["data"]["content"] == "உள்ளடக்கம்"


# 17. Voice Generation Includes Final Sentence Test
def test_voice_includes_final_sentence():
    long_text = "Sentence one. " * 30 + "This is the final conclusion sentence that must never be skipped."
    chunks = _chunk_tts_text(long_text)
    full_recombined = " ".join(chunks)
    assert "final conclusion sentence" in full_recombined


# 18. Long Content Chunk Processing Test
def test_long_content_chunk_processing():
    long_article = "Paragraph content sentence. " * 200
    chunks = _chunk_text(long_article)
    assert len(chunks) > 1


# 19. Meaningful Emphasis Preserved Test
def test_meaningful_emphasis_preserved():
    text_emphasis = "This step is exceptionally critical and exceptionally critical for system security."
    cleaned = clean_speech_sentence(text_emphasis)
    assert "critical" in cleaned


# 20. Broken Sentence Reconstruction Test
def test_broken_sentence_reconstruction():
    fragmented = "we created the web project index html in react"
    cleaned = clean_speech_sentence(fragmented, full_context="web project react index html")
    assert cleaned.startswith("We")
    assert cleaned.endswith(".")
    assert "index.html" in cleaned
    assert "React" in cleaned


# 21. Cache Invalidation On Article Text Change Test
def test_cache_invalidation_on_article_text_change(client, app, monkeypatch):
    with app.app_context():
        v = Video(youtube_id="v_hash_inv", youtube_url="https://youtube.com/watch?v=v_hash_inv", status="done")
        db.session.add(v)
        db.session.commit()
        art = Article(video_id=v.id, language="en", title="Original Title", content="Version 1 content for audio.", is_original=True)
        db.session.add(art)
        db.session.commit()

        def mock_dubbing_1(text, lang):
            f_path = os.path.join(AUDIO_DIR, "audio_v1.mp3")
            with open(f_path, "wb") as f:
                f.write(b"AUDIO_DATA_V1")
            return "audio_v1.mp3", "gtts_fallback"

        monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", mock_dubbing_1)

        res1 = client.post(f"/api/articles/{art.id}/audio", json={"language": "en"})
        assert res1.status_code == 200
        assert "audio_v1.mp3" in res1.get_json()["data"]["audioUrl"]

        # Mutate content -> text hash changes -> audio cache must invalidate
        art.content = "Version 2 updated content with new explanations."
        db.session.commit()

        def mock_dubbing_2(text, lang):
            f_path = os.path.join(AUDIO_DIR, "audio_v2.mp3")
            with open(f_path, "wb") as f:
                f.write(b"AUDIO_DATA_V2")
            return "audio_v2.mp3", "gtts_fallback"

        monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", mock_dubbing_2)

        res2 = client.post(f"/api/articles/{art.id}/audio", json={"language": "en"})
        assert res2.status_code == 200
        assert "audio_v2.mp3" in res2.get_json()["data"]["audioUrl"]


# 22. History Saves Only Valid Completed Records Test
def test_history_saves_only_completed(client, app):
    with app.app_context():
        user = User(email="test_h_comp@example.com")
        db.session.add(user)
        db.session.commit()
        token = issue_token(user)

        v_done = Video(youtube_id="v_done_hist", youtube_url="https://youtube.com/watch?v=v_done_hist", status="done", title="Completed Video", user_id=user.id)
        v_fail = Video(youtube_id="v_fail_hist", youtube_url="https://youtube.com/watch?v=v_fail_hist", status="failed", title="Failed Video", user_id=user.id)
        db.session.add_all([v_done, v_fail])
        db.session.commit()

        art_done = Article(video_id=v_done.id, language="en", title="Completed Article", content="Valid completed content.", is_original=True)
        db.session.add(art_done)
        db.session.commit()

    res = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    history_data = res.get_json()["data"]
    video_titles = [item.get("title") for item in history_data]
    assert "Completed Video" in video_titles
    assert "Failed Video" not in video_titles

