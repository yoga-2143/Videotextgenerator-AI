import pytest
from app.services.language_config import get_all_supported_languages, get_language_config, is_translation_supported, is_tts_supported
from app.services.translator_service import translate_text, validate_translated_content, TranslationError
from app.services.tts_service import generate_audio, TTSError


def test_canonical_58_languages_registry():
    langs = get_all_supported_languages()
    assert len(langs) >= 58, f"Expected at least 58 languages, got {len(langs)}"

    seen_codes = set()
    for l in langs:
        assert "code" in l
        assert "name" in l
        assert "nllb_code" in l
        assert "translation_code" in l
        assert "tts_locale" in l
        assert l["supports_translation"] is True
        assert l["supports_tts"] is True
        seen_codes.add(l["code"])

    # Verify key priority languages
    priority = ["en", "ta", "hi", "te", "ml", "kn", "bn", "mr", "gu", "ur", "pa", "es", "fr", "de", "it", "pt", "ja", "ko", "zh-CN", "ar", "ru"]
    for code in priority:
        assert code in seen_codes, f"Priority language code '{code}' missing from registry"


def test_language_config_resolution():
    tamil = get_language_config("ta")
    assert tamil is not None
    assert tamil["name"] == "Tamil"
    assert tamil["nllb_code"] == "tam_Taml"
    assert tamil["tts_locale"] == "ta"

    hindi = get_language_config("Hindi")
    assert hindi is not None
    assert hindi["code"] == "hi"
    assert hindi["nllb_code"] == "hin_Deva"


def test_script_validation():
    # Tamil script validation
    tamil_text = "இணையதள உருவாக்கம் மற்றும் வடிவமைப்பு"
    assert validate_translated_content(tamil_text, "ta") is True
    assert validate_translated_content("Hello World HTML", "ta") is False

    # Hindi script validation
    hindi_text = "वेब विकास और डिज़ाइन प्रक्रिया"
    assert validate_translated_content(hindi_text, "hi") is True
    assert validate_translated_content("Hello World HTML", "hi") is False


def test_multi_language_translations():
    sample_text = "Web development involves creating responsive websites using HTML, CSS, and JavaScript."

    # Tamil Translation
    ta_translated = translate_text(sample_text, "ta", "en")
    assert ta_translated and len(ta_translated) > 10
    assert validate_translated_content(ta_translated, "ta") is True

    # Hindi Translation
    hi_translated = translate_text(sample_text, "hi", "en")
    assert hi_translated and len(hi_translated) > 10
    assert validate_translated_content(hi_translated, "hi") is True

    # French Translation
    fr_translated = translate_text(sample_text, "fr", "en")
    assert fr_translated and len(fr_translated) > 10


def test_tts_generation_for_target_languages():
    # Tamil TTS
    ta_text = "இணையதள உருவாக்கம் மற்றும் வடிவமைப்பு"
    ta_audio = generate_audio(ta_text, "ta")
    assert ta_audio and ta_audio.endswith(".mp3")

    # Hindi TTS
    hi_text = "वेब विकास और डिज़ाइन प्रक्रिया"
    hi_audio = generate_audio(hi_text, "hi")
    assert hi_audio and hi_audio.endswith(".mp3")


def test_all_58_languages_translation_matrix():
    """Validates that all 58 configured languages in CANONICAL_58_LANGUAGES produce non-empty, valid translations."""
    from app.services.language_config import CANONICAL_58_LANGUAGES
    sample = "IMPORTANT CONTENT\n\nArtificial intelligence is transforming how video content is processed and summarized."

    passed = 0
    for lang in CANONICAL_58_LANGUAGES:
        code = lang["code"]
        res = translate_text(sample, code, "en")
        assert res and len(res.strip()) > 5, f"Translation for '{code}' ({lang['name']}) returned empty result"
        assert validate_translated_content(res, code) is True, f"Validation failed for '{code}' ({lang['name']})"
        passed += 1

    assert passed == 58, f"Expected 58 successful translations, got {passed}"

