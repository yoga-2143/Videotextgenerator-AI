import os
import pytest
import json
from app import create_app, db
from app.models.models import Video, Article, Audio
from app.services.language_config import CANONICAL_58_LANGUAGES, get_language_config
from app.services.translator_service import translate_hard_words


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_audit_all_58_languages_registry():
    """Validates that all 58 languages in CANONICAL_58_LANGUAGES have valid language IDs, NLLB codes, and Edge TTS voice codes."""
    assert len(CANONICAL_58_LANGUAGES) == 58
    for lang_item in CANONICAL_58_LANGUAGES:
        code = lang_item["code"]
        config = get_language_config(code)
        assert config is not None, f"Language config missing for {code}"
        assert config.get("nllb_code") is not None, f"NLLB code missing for {code}"
        assert isinstance(config["nllb_code"], str) and len(config["nllb_code"]) > 0
        assert config.get("voice_code") is not None, f"Voice code missing for {code}"
        assert isinstance(config["voice_code"], str) and len(config["voice_code"]) > 0


def test_audit_all_58_languages_hard_words_translation():
    """Validates that hard word explanations translate into target language structures for all 58 languages."""
    sample_hard_words = [
        {
            "word": "Algorithm",
            "simple_meaning": "A step-by-step procedure for calculations.",
            "explanation": "A set of clear rules to solve a problem.",
            "example": "Sorting numbers using a defined algorithm."
        }
    ]

    for lang_item in CANONICAL_58_LANGUAGES:
        code = lang_item["code"]
        translated_hw = translate_hard_words(sample_hard_words, code)
        assert isinstance(translated_hw, list)
        assert len(translated_hw) == 1
        assert translated_hw[0]["word"] == "Algorithm"  # Original word token preserved
        assert "simple_meaning" in translated_hw[0]
        assert "explanation" in translated_hw[0]
        assert len(translated_hw[0]["simple_meaning"]) > 0


def test_audit_all_58_languages_audio_pipeline(client, app):
    """Automated test validating all 58 target languages for translation config, Edge Neural TTS, audio file size, MIME type, HTTP 200, and non-empty audio output."""
    with app.app_context():
        # Setup base test video and original article
        video = Video(
            youtube_id="audit58_vid",
            youtube_url="https://www.youtube.com/watch?v=audit58_vid",
            title="58 Language Audit Video",
            status="done",
            original_language="en",
            user_id=None
        )
        db.session.add(video)
        db.session.commit()

        orig_article = Article(
            video_id=video.id,
            language="en",
            title="Overview of AI Technology",
            content="IMPORTANT CONTENT\n\n- Artificial intelligence transforms language processing.\n- Modern web application support global communication.",
            hard_words_json=json.dumps([{"word": "Algorithm", "simple_meaning": "A step-by-step procedure"}]),
            is_original=True
        )
        db.session.add(orig_article)
        db.session.commit()
        orig_article_id = orig_article.id

        # Pre-create translated articles for all 58 languages to ensure fast, deterministic testing
        for lang_item in CANONICAL_58_LANGUAGES:
            lang_id = lang_item["code"]
            if lang_id != "en":
                sub_article = Article(
                    video_id=video.id,
                    language=lang_id,
                    title=f"Article Title for {lang_id}",
                    content=f"IMPORTANT CONTENT in {lang_id}\n\n- Fact 1 for {lang_id}.\n- Fact 2 for {lang_id}.",
                    hard_words_json=json.dumps([{"word": "Algorithm", "simple_meaning": f"Meaning in {lang_id}"}]),
                    is_original=False
                )
                db.session.add(sub_article)
        db.session.commit()

    passed_count = 0
    failed_count = 0
    audit_records = []

    for lang_item in CANONICAL_58_LANGUAGES:
        lang_id = lang_item["code"]
        voice_code = lang_item.get("voice_code")
        locale = lang_item.get("locale")

        # 1. Request audio for target language via API endpoint
        res = client.post(f"/api/articles/{orig_article_id}/audio", json={"language": lang_id})
        assert res.status_code == 200, f"HTTP status failed for {lang_id}: {res.status_code}"

        data = res.get_json()
        assert data["success"] is True, f"Success flag False for {lang_id}"

        audio_info = data["data"]
        assert audio_info["voiceAvailable"] is True, f"Voice unavailable for {lang_id}"
        assert audio_info["voice_code"] == voice_code, f"Voice mismatch for {lang_id}: expected {voice_code}, got {audio_info.get('voice_code')}"

        # 2. Test serve_audio endpoint
        audio_url = audio_info["audioUrl"]
        res_serve = client.get(audio_url)
        assert res_serve.status_code == 200, f"Serve audio HTTP failed for {lang_id}: {res_serve.status_code}"

        # Verify Content-Type MIME type and byte range headers
        expected_mime = "audio/wav" if audio_url.endswith(".wav") else "audio/mpeg"
        assert res_serve.mimetype == expected_mime, f"MIME mismatch for {lang_id}: {res_serve.mimetype}"
        assert res_serve.headers.get("Accept-Ranges") == "bytes"
        assert res_serve.headers.get("Access-Control-Allow-Origin") == "*"
        assert len(res_serve.data) > 0, f"Audio byte payload empty for {lang_id}"

        passed_count += 1
        audit_records.append({
            "lang": lang_id,
            "locale": locale,
            "voice": voice_code,
            "status": res.status_code,
            "size_bytes": len(res_serve.data)
        })

    print(f"\n================ 58-LANGUAGE AUDIO AUDIT SUMMARY ================")
    print(f"Total Languages Tested: {len(CANONICAL_58_LANGUAGES)}")
    print(f"Passed: {passed_count} / {len(CANONICAL_58_LANGUAGES)}")
    print(f"Failed: {failed_count} / {len(CANONICAL_58_LANGUAGES)}")
    assert passed_count == 58, f"Only {passed_count} of 58 languages passed audio audit."
