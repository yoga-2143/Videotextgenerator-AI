import pytest
import os
import json
from app import db
from app.models.models import Video, Article, Audio, TranslationCache
from app.services.tts_service import AUDIO_DIR


import uuid

def create_sample_article(db_session, video_suffix=""):
    v_id = f"test_vid_{uuid.uuid4().hex[:8]}_{video_suffix}"
    video = Video(youtube_id=v_id, youtube_url=f"https://youtube.com/watch?v={v_id}", title="AWS Cloud Tutorial", status="done")
    db_session.add(video)
    db_session.commit()

    article = Article(video_id=video.id, language="en", title="AWS Cloud Tutorial", content="• Amazon EC2 provides scalable virtual servers in AWS.\n\n• Amazon S3 provides object storage.", is_original=True)
    db_session.add(article)
    db_session.commit()

    from app.routes.tts import AUDIO_CACHE
    AUDIO_CACHE.clear()

    return article


# Test 1: English text -> Tamil selected -> Tamil translation -> Tamil TTS input -> Tamil audio
def test_1_english_to_tamil_translation_and_voice(client, app, monkeypatch):
    with app.app_context():
        article = create_sample_article(db.session)

        def mock_translate_text(text, target_lang, source_lang="en"):
            if target_lang == "ta":
                return "• அமேசான் EC2 AWS இல் அளவிடக்கூடிய மெய்நிகர் சேவையகங்களை வழங்குகிறது."
            return text

        monkeypatch.setattr("app.routes.translate.translate_text", mock_translate_text)

        # 1. Call translate endpoint
        res_trans = client.post(f"/api/articles/{article.id}/translate", json={"language": "ta"})
        assert res_trans.status_code == 200
        trans_data = res_trans.get_json()["data"]
        assert trans_data["targetLanguage"] == "ta"
        assert "அமேசான்" in trans_data["translated_text"]

        tts_inputs = []

        def mock_generate_dubbed_audio(text, lang):
            tts_inputs.append({"text": text, "lang": lang})
            dummy_file = os.path.join(AUDIO_DIR, "test_tamil.mp3")
            with open(dummy_file, "wb") as f:
                f.write(b"ID3_TAMIL_AUDIO_TEST")
            return "test_tamil.mp3", "gtts_fallback"

        monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", mock_generate_dubbed_audio)

        # 2. Call voice endpoint with target language Tamil
        res_voice = client.post(f"/api/articles/{article.id}/audio", json={"language": "ta"})
        assert res_voice.status_code == 200
        voice_data = res_voice.get_json()["data"]
        assert voice_data["language"] == "ta"
        assert "audioUrl" in voice_data

        # Verify TTS input text was TAMIL translated text, NOT original English
        assert len(tts_inputs) == 1
        assert tts_inputs[0]["lang"] == "ta"
        assert "அமேசான்" in tts_inputs[0]["text"]
        assert "Amazon EC2 provides" not in tts_inputs[0]["text"]


# Test 2: Tamil -> Hindi switch -> Hindi translation -> Hindi voice
def test_2_tamil_to_hindi_voice_switch(client, app, monkeypatch):
    with app.app_context():
        article = create_sample_article(db.session)

        def mock_translate_text(text, target_lang, source_lang="en"):
            if target_lang == "hi":
                return "• अमेज़न EC2 AWS में स्केलेबल वर्चुअल सर्वर प्रदान करता है।"
            return text

        monkeypatch.setattr("app.routes.translate.translate_text", mock_translate_text)

        tts_inputs = []

        def mock_generate_dubbed_audio(text, lang):
            tts_inputs.append({"text": text, "lang": lang})
            filename = f"test_{lang}.mp3"
            dummy_file = os.path.join(AUDIO_DIR, filename)
            with open(dummy_file, "wb") as f:
                f.write(f"ID3_{lang}_AUDIO_TEST".encode())
            return filename, "gtts_fallback"

        monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", mock_generate_dubbed_audio)

        # Request Hindi Audio
        res_voice_hi = client.post(f"/api/articles/{article.id}/audio", json={"language": "hi"})
        assert res_voice_hi.status_code == 200
        hi_data = res_voice_hi.get_json()["data"]
        assert hi_data["language"] == "hi"

        assert len(tts_inputs) == 1
        assert tts_inputs[0]["lang"] == "hi"
        assert "अमेज़न" in tts_inputs[0]["text"]


# Test 3: Rapid language switching — API handles requested language properly
def test_3_rapid_language_switch_request_isolation(client, app, monkeypatch):
    with app.app_context():
        article = create_sample_article(db.session)

        def mock_translate_text(text, target_lang, source_lang="en"):
            return f"• Translated to {target_lang}: {text}"

        monkeypatch.setattr("app.routes.translate.translate_text", mock_translate_text)

        def mock_generate_dubbed_audio(text, lang):
            fname = f"rapid_{lang}.mp3"
            with open(os.path.join(AUDIO_DIR, fname), "wb") as f:
                f.write(b"AUDIO_DATA")
            return fname, "gtts_fallback"

        monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", mock_generate_dubbed_audio)

        # Request French Audio
        res_fr = client.post(f"/api/articles/{article.id}/audio", json={"language": "fr"})
        assert res_fr.status_code == 200
        assert res_fr.get_json()["data"]["language"] == "fr"

        # Request Spanish Audio
        res_es = client.post(f"/api/articles/{article.id}/audio", json={"language": "es"})
        assert res_es.status_code == 200
        assert res_es.get_json()["data"]["language"] == "es"


# Test 4: Translation succeeds but voice fails -> returns clear error
def test_4_voice_failure_handling(client, app, monkeypatch):
    with app.app_context():
        article = create_sample_article(db.session)

        def mock_translate_text(text, target_lang, source_lang="en"):
            return "• Translate OK"

        monkeypatch.setattr("app.routes.translate.translate_text", mock_translate_text)

        from app.services.tts_service import TTSError

        def mock_failing_dubbed_audio(text, lang):
            raise TTSError("TTS engine connection timeout")

        monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", mock_failing_dubbed_audio)

        res_voice = client.post(f"/api/articles/{article.id}/audio", json={"language": "fr"})
        assert res_voice.status_code == 500
        json_body = res_voice.get_json()
        assert json_body["success"] is False
        assert json_body["error"]["code"] == "VOICE_GENERATION_FAILED"


# Test 5: Cached audio from another language is NEVER played for selected language
def test_5_cached_audio_language_isolation(client, app, monkeypatch):
    with app.app_context():
        article = create_sample_article(db.session)

        # Seed DB with existing Audio row for English
        eng_audio_file = os.path.join(AUDIO_DIR, "english_audio_seed.mp3")
        with open(eng_audio_file, "wb") as f:
            f.write(b"ENGLISH_AUDIO_SEED")

        audio_seed = Audio(article_id=article.id, language="en", file_path="english_audio_seed.mp3", dubbing_source="gtts_fallback")
        db.session.add(audio_seed)
        db.session.commit()

        def mock_translate_text(text, target_lang, source_lang="en"):
            return "• German translated text"

        monkeypatch.setattr("app.routes.translate.translate_text", mock_translate_text)

        def mock_generate_dubbed_audio(text, lang):
            fname = f"german_new.mp3"
            with open(os.path.join(AUDIO_DIR, fname), "wb") as f:
                f.write(b"GERMAN_AUDIO_DATA")
            return fname, "gtts_fallback"

        monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", mock_generate_dubbed_audio)

        # Request German audio
        res_de = client.post(f"/api/articles/{article.id}/audio", json={"language": "de"})
        assert res_de.status_code == 200
        de_data = res_de.get_json()["data"]
        assert de_data["language"] == "de"
        assert "english_audio_seed.mp3" not in de_data["audioUrl"]


# Test 6: Same article + same language + same translated text -> Reuse correct cached audio
def test_6_cache_reuse_same_language(client, app, monkeypatch):
    with app.app_context():
        article = create_sample_article(db.session)

        def mock_translate_text(text, target_lang, source_lang="en"):
            return "• Spanish translated content"

        monkeypatch.setattr("app.routes.translate.translate_text", mock_translate_text)

        call_count = {"count": 0}

        def mock_generate_dubbed_audio(text, lang):
            call_count["count"] += 1
            fname = "spanish_cached.mp3"
            with open(os.path.join(AUDIO_DIR, fname), "wb") as f:
                f.write(b"SPANISH_AUDIO_DATA")
            return fname, "gtts_fallback"

        monkeypatch.setattr("app.routes.tts.generate_dubbed_audio", mock_generate_dubbed_audio)

        # First request: generates audio
        res1 = client.post(f"/api/articles/{article.id}/audio", json={"language": "es"})
        assert res1.status_code == 200
        assert call_count["count"] == 1

        # Second request: reuses cached audio
        res2 = client.post(f"/api/articles/{article.id}/audio", json={"language": "es"})
        assert res2.status_code == 200
        assert res2.get_json()["data"]["audioUrl"] == res1.get_json()["data"]["audioUrl"]
        assert call_count["count"] == 1  # No extra call to generate_dubbed_audio!
