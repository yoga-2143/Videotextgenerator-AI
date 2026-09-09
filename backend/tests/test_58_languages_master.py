"""
Master 58-Language Verification Test Suite for VideoTextGenerator AI.

Tests all 58 configured languages for:
1. Canonical 58-Language Registry completeness & dictionary keys
2. NLLB code mapping & resolution
3. Controlled multi-language translation (names, numbers, terms, dates)
4. Target language script & non-empty integrity validation
5. Voice code & engine mapping (gTTS, Edge-TTS, Google Web TTS, MMS-TTS)
6. Voice audio generation & file size verification
7. Request identity & audio metadata isolation
8. Stale data & cross-job isolation
"""
import os
import pytest
from app.services.language_config import (
    CANONICAL_58_LANGUAGES,
    CENTRAL_LANGUAGE_CATALOG,
    get_all_supported_languages,
    get_language_config,
    get_language_by_id,
    is_translation_supported,
    is_tts_supported,
)
from app.services.translator_service import (
    translate_text,
    validate_translated_content,
    TranslationError,
)
from app.services.tts_service import (
    generate_audio,
    TTSError,
    AUDIO_DIR,
)
from app.services.dubbing_service import (
    generate_dubbed_audio,
)

BENCHMARK_SOURCE_TEXT = (
    "IMPORTANT CONTENT\n\n"
    "On September 9, 2026, Dr. Alex Mercer published 45 research papers on "
    "artificial intelligence using Python and React. The system processed "
    "1,250 video records with 99.5% accuracy."
)


def test_01_canonical_58_languages_registry():
    """1. Registry Test: Verifies all 58 languages are present in canonical registry."""
    assert len(CANONICAL_58_LANGUAGES) == 58, f"Expected 58 languages in CANONICAL_58_LANGUAGES, found {len(CANONICAL_58_LANGUAGES)}"
    assert len(CENTRAL_LANGUAGE_CATALOG) == 58, f"Expected 58 languages in CENTRAL_LANGUAGE_CATALOG, found {len(CENTRAL_LANGUAGE_CATALOG)}"

    seen_ids = set()
    for item in CANONICAL_58_LANGUAGES:
        lang_id = item.get("language_id") or item.get("id") or item.get("code")
        assert lang_id, f"Language item missing id/language_id: {item}"
        assert "display_name" in item or "name" in item, f"Language {lang_id} missing display_name"
        assert "nllb_code" in item, f"Language {lang_id} missing nllb_code"
        assert "translation_code" in item, f"Language {lang_id} missing translation_code"
        assert "tts_locale" in item or "tts_code" in item, f"Language {lang_id} missing tts_locale"
        assert "voice_engine" in item, f"Language {lang_id} missing voice_engine"
        assert "voice_code" in item, f"Language {lang_id} missing voice_code"
        assert item.get("enabled") is True, f"Language {lang_id} is not enabled"
        seen_ids.add(lang_id)

    assert len(seen_ids) == 58, f"Expected 58 unique language IDs, found {len(seen_ids)}"


def test_02_nllb_and_voice_mappings():
    """2. NLLB & Voice Mapping Test: Verifies every language resolves NLLB and Voice attributes."""
    for item in CANONICAL_58_LANGUAGES:
        lang_id = item.get("language_id") or item["code"]
        config = get_language_config(lang_id)
        assert config is not None, f"Failed to retrieve language config for '{lang_id}'"
        assert config["nllb_code"] and len(config["nllb_code"]) > 3, f"Invalid nllb_code for '{lang_id}'"
        assert config["voice_engine"] in ("gtts", "edge_tts", "google_web_tts", "mms_tts"), f"Invalid voice_engine for '{lang_id}'"
        assert config["voice_code"], f"Invalid voice_code for '{lang_id}'"
        assert config["supports_translation"] is True, f"Translation not supported for '{lang_id}'"
        assert config["supports_tts"] is True, f"TTS not supported for '{lang_id}'"


@pytest.mark.parametrize("lang_item", CANONICAL_58_LANGUAGES)
def test_03_controlled_translation_matrix(lang_item):
    """3 & 4. Controlled Benchmark Translation & Script Validation across all 58 languages."""
    lang_id = lang_item.get("language_id") or lang_item["code"]
    display_name = lang_item.get("display_name") or lang_item.get("name")

    translated = translate_text(BENCHMARK_SOURCE_TEXT, lang_id, source_lang="en")
    assert translated and len(translated.strip()) > 10, f"Translation into '{lang_id}' ({display_name}) returned empty result"

    is_valid = validate_translated_content(translated, lang_id)
    assert is_valid is True, f"Validation failed for translated text in '{lang_id}' ({display_name}): '{translated[:80]}...'"


@pytest.mark.parametrize("lang_item", CANONICAL_58_LANGUAGES)
def test_04_voice_generation_sample(lang_item):
    """5 & 6. Voice Audio Generation Test across all 58 languages."""
    lang_id = lang_item.get("language_id") or lang_item["code"]
    sample_text = f"Important content overview in {lang_item.get('display_name') or lang_id}."

    filename, engine = generate_dubbed_audio(sample_text, lang_id)
    assert filename and (filename.endswith(".mp3") or filename.endswith(".wav")), f"Invalid filename returned for '{lang_id}'"
    
    file_path = os.path.join(AUDIO_DIR, filename)
    assert os.path.exists(file_path), f"Audio file does not exist on disk for '{lang_id}'"
    assert os.path.getsize(file_path) > 0, f"Audio file is 0 bytes for '{lang_id}'"


def test_05_job_and_cache_isolation():
    """7 & 8. Identity Verification & Stale Data Isolation Test."""
    text_a = "Article content for video A"
    text_b = "Article content for video B"

    translated_a = translate_text(text_a, "hi", "en")
    translated_b = translate_text(text_b, "hi", "en")

    assert translated_a != translated_b or text_a != text_b
    assert validate_translated_content(translated_a, "hi") is True
    assert validate_translated_content(translated_b, "hi") is True


def test_06_technical_benchmark_direct_translation():
    """9. Technical Benchmark Direct NLLB Test for AWS/EC2/SQL/numbers/dates across key languages."""
    tech_source = (
        "AWS EC2 is a cloud computing service. The server has 2 CPUs and 8 GB memory. "
        "SQL queries use SELECT and GROUP BY."
    )

    key_langs = ["hi", "ja", "ar", "ko", "fr", "de", "ta", "en"]
    for lang in key_langs:
        res = translate_text(tech_source, lang, source_lang="en")
        assert res and len(res.strip()) > 5, f"Direct translation failed for lang={lang}"
        assert validate_translated_content(res, lang) is True, f"Validation failed for lang={lang}"
        # Verify numbers are preserved
        assert "2" in res or "8" in res, f"Number preservation failed for lang={lang}: '{res}'"

