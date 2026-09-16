import pytest
import json
import hashlib
from app import db
from app.models.models import Video, Article, Audio, TranslationCache
from app.services.hard_words_service import extract_hard_words
from app.services.translator_service import translate_hard_words
from app.services.language_config import CANONICAL_58_LANGUAGES, get_language_config

def test_hard_words_extraction():
    transcript = (
        "In this video we demonstrate machine learning algorithms and neural networks. "
        "We optimize the backend microservice architecture and implement asynchronous pipeline processing."
    )
    words = extract_hard_words(transcript)
    assert isinstance(words, list)
    assert len(words) > 0
    for item in words:
        assert "word" in item
        assert "simple_meaning" in item
        assert "explanation" in item
        assert "example" in item

def test_58_languages_translation_mapping():
    assert len(CANONICAL_58_LANGUAGES) == 58
    for lang in CANONICAL_58_LANGUAGES:
        code = lang["code"]
        config = get_language_config(code)
        assert config is not None
        assert "nllb_code" in config
        assert isinstance(config["nllb_code"], str)
        assert len(config["nllb_code"]) > 0

def test_58_languages_tts_voice_mapping():
    for lang in CANONICAL_58_LANGUAGES:
        code = lang["code"]
        config = get_language_config(code)
        voice = config.get("voice_code") if config else None
        assert voice is not None, f"Language {code} returned no Edge voice"
        assert isinstance(voice, str) and len(voice) > 0

def test_hard_words_translation():
    hard_words = [
        {
            "word": "Algorithm",
            "simple_meaning": "A step-by-step procedure for calculations.",
            "explanation": "It is a set of rules to follow.",
            "example": "Sorting a list of numbers."
        }
    ]
    # Test translating hard words to Tamil
    translated_hw = translate_hard_words(hard_words, "ta")
    assert isinstance(translated_hw, list)
    assert len(translated_hw) == 1
    assert translated_hw[0]["word"] == "Algorithm"  # Original word token preserved
    assert translated_hw[0]["simple_meaning"] != ""

def test_matching_audio_identity(client, app):
    with app.app_context():
        # Create a test video and article
        video = Video(youtube_id="voice111111", youtube_url="https://www.youtube.com/watch?v=voice111111", status="done")
        db.session.add(video)
        db.session.commit()

        article = Article(
            video_id=video.id,
            language="en",
            title="AI Architecture",
            content="IMPORTANT CONTENT\n\n- Machine learning powers modern software systems.",
            hard_words_json=json.dumps([{"word": "Machine learning", "simple_meaning": "Computer learning from data"}])
        )
        db.session.add(article)
        db.session.commit()

        art_id = article.id

    # Request audio for English
    res_en = client.post(f"/api/articles/{art_id}/audio", json={"language": "en"})
    assert res_en.status_code == 200
    res_en_json = res_en.get_json()
    assert res_en_json["success"] is True
    data_en = res_en_json.get("data", res_en_json)
    assert "audio_url" in data_en or "audioUrl" in data_en
    assert data_en.get("language") == "en"

    # Verify database entry has voice_code and hash fields set
    with app.app_context():
        audio_entry = Audio.query.filter_by(article_id=art_id, language="en").first()
        assert audio_entry is not None
        assert audio_entry.voice_code != ""
        assert audio_entry.translated_text_hash != ""

def test_stale_audio_protection(client, app):
    with app.app_context():
        video = Video(youtube_id="staleaudio1", youtube_url="https://www.youtube.com/watch?v=staleaudio1", status="done")
        db.session.add(video)
        db.session.commit()

        article = Article(
            video_id=video.id,
            language="en",
            title="Neural Nets",
            content="IMPORTANT CONTENT\n\n- Neural networks process complex patterns."
        )
        db.session.add(article)
        db.session.commit()
        art_id = article.id

    # Request English audio
    res_en = client.post(f"/api/articles/{art_id}/audio", json={"language": "en"})
    assert res_en.status_code == 200
    res_en_json = res_en.get_json()
    data_en = res_en_json.get("data", res_en_json)
    audio_en_url = data_en.get("audio_url") or data_en.get("audioUrl")

    # Request Tamil audio
    res_ta = client.post(f"/api/articles/{art_id}/audio", json={"language": "ta"})
    assert res_ta.status_code == 200
    res_ta_json = res_ta.get_json()
    data_ta = res_ta_json.get("data", res_ta_json)
    audio_ta_url = data_ta.get("audio_url") or data_ta.get("audioUrl")

    # Must NOT serve English audio for Tamil request
    assert audio_en_url != audio_ta_url

def test_stale_translation_protection(client, app):
    with app.app_context():
        video = Video(youtube_id="transstale1", youtube_url="https://www.youtube.com/watch?v=transstale1", status="done")
        db.session.add(video)
        db.session.commit()

        article = Article(
            video_id=video.id,
            language="en",
            title="Original Title",
            content="IMPORTANT CONTENT\n\n- Original English content."
        )
        db.session.add(article)
        db.session.commit()
        art_id = article.id

    # Translate to French
    res_fr = client.post(f"/api/articles/{art_id}/translate", json={"target_language": "fr"})
    assert res_fr.status_code == 200
    res_fr_json = res_fr.get_json()
    data_fr = res_fr_json.get("data", res_fr_json)
    assert data_fr["target_language_id"] == "fr"

    # Translate to Spanish
    res_es = client.post(f"/api/articles/{art_id}/translate", json={"target_language": "es"})
    assert res_es.status_code == 200
    res_es_json = res_es.get_json()
    data_es = res_es_json.get("data", res_es_json)
    assert data_es["target_language_id"] == "es"

    assert data_fr["content"] != data_es["content"]

def test_new_video_isolation(client, app):
    with app.app_context():
        video1 = Video(youtube_id="video111111", youtube_url="https://www.youtube.com/watch?v=video111111", status="done")
        video2 = Video(youtube_id="video222222", youtube_url="https://www.youtube.com/watch?v=video222222", status="done")
        db.session.add_all([video1, video2])
        db.session.commit()

        hw1 = [{"word": "V1Word", "simple_meaning": "Meaning 1", "explanation": "Expl 1", "example": "Ex 1"}]
        hw2 = [{"word": "V2Word", "simple_meaning": "Meaning 2", "explanation": "Expl 2", "example": "Ex 2"}]

        art1 = Article(video_id=video1.id, language="en", title="Video 1 Title", content="IMPORTANT CONTENT\n\n- Video 1 content", hard_words_json=json.dumps(hw1))
        art2 = Article(video_id=video2.id, language="en", title="Video 2 Title", content="IMPORTANT CONTENT\n\n- Video 2 content", hard_words_json=json.dumps(hw2))
        db.session.add_all([art1, art2])
        db.session.commit()

        art1_id = art1.id
        art2_id = art2.id

    res1 = client.get(f"/api/articles/{art1_id}")
    res2 = client.get(f"/api/articles/{art2_id}")

    assert res1.status_code == 200
    assert res2.status_code == 200

    data1 = res1.get_json()["data"]
    data2 = res2.get_json()["data"]

    assert data1["title"] == "Video 1 Title"
    assert data2["title"] == "Video 2 Title"
    assert data1["hard_words"] == hw1
    assert data2["hard_words"] == hw2
