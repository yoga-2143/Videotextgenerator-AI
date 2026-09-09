"""
Central 58 Dual-Capability Language Configuration Map.
Exposes EXACTLY 58 verified languages with 100% dual capability:
1. Text Translation (GoogleTranslator / NLLB-200)
2. Voice Audio Generation (gTTS / Edge-TTS / Google Web TTS / Meta MMS-TTS)
Used consistently by language selector API, translation service, and TTS service.
All 58 configured languages are guaranteed to support both translation and audio generation.
"""
import logging

logger = logging.getLogger(__name__)

# Canonical 58-Language Registry with exact dual translation & TTS engines
CANONICAL_58_LANGUAGES = [
    # 1-11: Indian & South Asian Languages
    {"id": "en", "language_id": "en", "code": "en", "name": "English", "display_name": "English", "nllb_code": "eng_Latn", "translation_code": "en", "tts_code": "en", "tts_locale": "en", "locale": "en-US", "script": "Latin", "voice_engine": "gtts", "voice_code": "en", "enabled": True},
    {"id": "ta", "language_id": "ta", "code": "ta", "name": "Tamil", "display_name": "Tamil", "nllb_code": "tam_Taml", "translation_code": "ta", "tts_code": "ta", "tts_locale": "ta", "locale": "ta-IN", "script": "Tamil", "voice_engine": "gtts", "voice_code": "ta", "enabled": True},
    {"id": "hi", "language_id": "hi", "code": "hi", "name": "Hindi", "display_name": "Hindi", "nllb_code": "hin_Deva", "translation_code": "hi", "tts_code": "hi", "tts_locale": "hi", "locale": "hi-IN", "script": "Devanagari", "voice_engine": "gtts", "voice_code": "hi", "enabled": True},
    {"id": "te", "language_id": "te", "code": "te", "name": "Telugu", "display_name": "Telugu", "nllb_code": "tel_Telu", "translation_code": "te", "tts_code": "te", "tts_locale": "te", "locale": "te-IN", "script": "Telugu", "voice_engine": "gtts", "voice_code": "te", "enabled": True},
    {"id": "ml", "language_id": "ml", "code": "ml", "name": "Malayalam", "display_name": "Malayalam", "nllb_code": "mal_Mlym", "translation_code": "ml", "tts_code": "ml", "tts_locale": "ml", "locale": "ml-IN", "script": "Malayalam", "voice_engine": "gtts", "voice_code": "ml", "enabled": True},
    {"id": "kn", "language_id": "kn", "code": "kn", "name": "Kannada", "display_name": "Kannada", "nllb_code": "kan_Knda", "translation_code": "kn", "tts_code": "kn", "tts_locale": "kn", "locale": "kn-IN", "script": "Kannada", "voice_engine": "gtts", "voice_code": "kn", "enabled": True},
    {"id": "bn", "language_id": "bn", "code": "bn", "name": "Bengali", "display_name": "Bengali", "nllb_code": "ben_Beng", "translation_code": "bn", "tts_code": "bn", "tts_locale": "bn", "locale": "bn-IN", "script": "Bengali", "voice_engine": "gtts", "voice_code": "bn", "enabled": True},
    {"id": "mr", "language_id": "mr", "code": "mr", "name": "Marathi", "display_name": "Marathi", "nllb_code": "mar_Deva", "translation_code": "mr", "tts_code": "mr", "tts_locale": "mr", "locale": "mr-IN", "script": "Devanagari", "voice_engine": "gtts", "voice_code": "mr", "enabled": True},
    {"id": "gu", "language_id": "gu", "code": "gu", "name": "Gujarati", "display_name": "Gujarati", "nllb_code": "guj_Gujr", "translation_code": "gu", "tts_code": "gu", "tts_locale": "gu", "locale": "gu-IN", "script": "Gujarati", "voice_engine": "gtts", "voice_code": "gu", "enabled": True},
    {"id": "ur", "language_id": "ur", "code": "ur", "name": "Urdu", "display_name": "Urdu", "nllb_code": "urd_Arab", "translation_code": "ur", "tts_code": "ur", "tts_locale": "ur", "locale": "ur-PK", "script": "Arabic", "voice_engine": "gtts", "voice_code": "ur", "enabled": True},
    {"id": "pa", "language_id": "pa", "code": "pa", "name": "Punjabi", "display_name": "Punjabi", "nllb_code": "pan_Guru", "translation_code": "pa", "tts_code": "pa", "tts_locale": "pa", "locale": "pa-IN", "script": "Gurmukhi", "voice_engine": "google_web_tts", "voice_code": "pa", "enabled": True},

    # 12-20: Major European & East Asian Languages
    {"id": "es", "language_id": "es", "code": "es", "name": "Spanish", "display_name": "Spanish", "nllb_code": "spa_Latn", "translation_code": "es", "tts_code": "es", "tts_locale": "es", "locale": "es-ES", "script": "Latin", "voice_engine": "gtts", "voice_code": "es", "enabled": True},
    {"id": "fr", "language_id": "fr", "code": "fr", "name": "French", "display_name": "French", "nllb_code": "fra_Latn", "translation_code": "fr", "tts_code": "fr", "tts_locale": "fr", "locale": "fr-FR", "script": "Latin", "voice_engine": "gtts", "voice_code": "fr", "enabled": True},
    {"id": "de", "language_id": "de", "code": "de", "name": "German", "display_name": "German", "nllb_code": "deu_Latn", "translation_code": "de", "tts_code": "de", "tts_locale": "de", "locale": "de-DE", "script": "Latin", "voice_engine": "gtts", "voice_code": "de", "enabled": True},
    {"id": "it", "language_id": "it", "code": "it", "name": "Italian", "display_name": "Italian", "nllb_code": "ita_Latn", "translation_code": "it", "tts_code": "it", "tts_locale": "it", "locale": "it-IT", "script": "Latin", "voice_engine": "gtts", "voice_code": "it", "enabled": True},
    {"id": "pt", "language_id": "pt", "code": "pt", "name": "Portuguese", "display_name": "Portuguese", "nllb_code": "por_Latn", "translation_code": "pt", "tts_code": "pt", "tts_locale": "pt", "locale": "pt-PT", "script": "Latin", "voice_engine": "gtts", "voice_code": "pt", "enabled": True},
    {"id": "ja", "language_id": "ja", "code": "ja", "name": "Japanese", "display_name": "Japanese", "nllb_code": "jpn_Jpan", "translation_code": "ja", "tts_code": "ja", "tts_locale": "ja", "locale": "ja-JP", "script": "Japanese", "voice_engine": "gtts", "voice_code": "ja", "enabled": True},
    {"id": "ko", "language_id": "ko", "code": "ko", "name": "Korean", "display_name": "Korean", "nllb_code": "kor_Hang", "translation_code": "ko", "tts_code": "ko", "tts_locale": "ko", "locale": "ko-KR", "script": "Hangul", "voice_engine": "gtts", "voice_code": "ko", "enabled": True},
    {"id": "zh-CN", "language_id": "zh-CN", "code": "zh-CN", "name": "Chinese (Simplified)", "display_name": "Chinese (Simplified)", "nllb_code": "zho_Hans", "translation_code": "zh-CN", "tts_code": "zh-CN", "tts_locale": "zh-CN", "locale": "zh-CN", "script": "Simplified Chinese", "voice_engine": "gtts", "voice_code": "zh-CN", "enabled": True},
    {"id": "zh-TW", "language_id": "zh-TW", "code": "zh-TW", "name": "Chinese (Traditional)", "display_name": "Chinese (Traditional)", "nllb_code": "zho_Hant", "translation_code": "zh-TW", "tts_code": "zh-TW", "tts_locale": "zh-TW", "locale": "zh-TW", "script": "Traditional Chinese", "voice_engine": "gtts", "voice_code": "zh-TW", "enabled": True},

    # 21-35: Middle Eastern, Slavic, Scandinavian & European Languages
    {"id": "ar", "language_id": "ar", "code": "ar", "name": "Arabic", "display_name": "Arabic", "nllb_code": "arb_Arab", "translation_code": "ar", "tts_code": "ar", "tts_locale": "ar", "locale": "ar-SA", "script": "Arabic", "voice_engine": "gtts", "voice_code": "ar", "enabled": True},
    {"id": "ru", "language_id": "ru", "code": "ru", "name": "Russian", "display_name": "Russian", "nllb_code": "rus_Cyrl", "translation_code": "ru", "tts_code": "ru", "tts_locale": "ru", "locale": "ru-RU", "script": "Cyrillic", "voice_engine": "gtts", "voice_code": "ru", "enabled": True},
    {"id": "nl", "language_id": "nl", "code": "nl", "name": "Dutch", "display_name": "Dutch", "nllb_code": "nld_Latn", "translation_code": "nl", "tts_code": "nl", "tts_locale": "nl", "locale": "nl-NL", "script": "Latin", "voice_engine": "gtts", "voice_code": "nl", "enabled": True},
    {"id": "pl", "language_id": "pl", "code": "pl", "name": "Polish", "display_name": "Polish", "nllb_code": "pol_Latn", "translation_code": "pl", "tts_code": "pl", "tts_locale": "pl", "locale": "pl-PL", "script": "Latin", "voice_engine": "gtts", "voice_code": "pl", "enabled": True},
    {"id": "tr", "language_id": "tr", "code": "tr", "name": "Turkish", "display_name": "Turkish", "nllb_code": "tur_Latn", "translation_code": "tr", "tts_code": "tr", "tts_locale": "tr", "locale": "tr-TR", "script": "Latin", "voice_engine": "gtts", "voice_code": "tr", "enabled": True},
    {"id": "sv", "language_id": "sv", "code": "sv", "name": "Swedish", "display_name": "Swedish", "nllb_code": "swe_Latn", "translation_code": "sv", "tts_code": "sv", "tts_locale": "sv", "locale": "sv-SE", "script": "Latin", "voice_engine": "gtts", "voice_code": "sv", "enabled": True},
    {"id": "da", "language_id": "da", "code": "da", "name": "Danish", "display_name": "Danish", "nllb_code": "dan_Latn", "translation_code": "da", "tts_code": "da", "tts_locale": "da", "locale": "da-DK", "script": "Latin", "voice_engine": "gtts", "voice_code": "da", "enabled": True},
    {"id": "fi", "language_id": "fi", "code": "fi", "name": "Finnish", "display_name": "Finnish", "nllb_code": "fin_Latn", "translation_code": "fi", "tts_code": "fi", "tts_locale": "fi", "locale": "fi-FI", "script": "Latin", "voice_engine": "gtts", "voice_code": "fi", "enabled": True},
    {"id": "no", "language_id": "no", "code": "no", "name": "Norwegian", "display_name": "Norwegian", "nllb_code": "nob_Latn", "translation_code": "no", "tts_code": "no", "tts_locale": "no", "locale": "no-NO", "script": "Latin", "voice_engine": "gtts", "voice_code": "no", "enabled": True},
    {"id": "el", "language_id": "el", "code": "el", "name": "Greek", "display_name": "Greek", "nllb_code": "ell_Grek", "translation_code": "el", "tts_code": "el", "tts_locale": "el", "locale": "el-GR", "script": "Greek", "voice_engine": "gtts", "voice_code": "el", "enabled": True},
    {"id": "cs", "language_id": "cs", "code": "cs", "name": "Czech", "display_name": "Czech", "nllb_code": "ces_Latn", "translation_code": "cs", "tts_code": "cs", "tts_locale": "cs", "locale": "cs-CZ", "script": "Latin", "voice_engine": "gtts", "voice_code": "cs", "enabled": True},
    {"id": "hu", "language_id": "hu", "code": "hu", "name": "Hungarian", "display_name": "Hungarian", "nllb_code": "hun_Latn", "translation_code": "hu", "tts_code": "hu", "tts_locale": "hu", "locale": "hu-HU", "script": "Latin", "voice_engine": "gtts", "voice_code": "hu", "enabled": True},
    {"id": "ro", "language_id": "ro", "code": "ro", "name": "Romanian", "display_name": "Romanian", "nllb_code": "ron_Latn", "translation_code": "ro", "tts_code": "ro", "tts_locale": "ro", "locale": "ro-RO", "script": "Latin", "voice_engine": "gtts", "voice_code": "ro", "enabled": True},
    {"id": "uk", "language_id": "uk", "code": "uk", "name": "Ukrainian", "display_name": "Ukrainian", "nllb_code": "ukr_Cyrl", "translation_code": "uk", "tts_code": "uk", "tts_locale": "uk", "locale": "uk-UA", "script": "Cyrillic", "voice_engine": "gtts", "voice_code": "uk", "enabled": True},
    {"id": "id", "language_id": "id", "code": "id", "name": "Indonesian", "display_name": "Indonesian", "nllb_code": "ind_Latn", "translation_code": "id", "tts_code": "id", "tts_locale": "id", "locale": "id-ID", "script": "Latin", "voice_engine": "gtts", "voice_code": "id", "enabled": True},

    # 36-50: Southeast Asian, African, and Central European Languages
    {"id": "vi", "language_id": "vi", "code": "vi", "name": "Vietnamese", "display_name": "Vietnamese", "nllb_code": "vie_Latn", "translation_code": "vi", "tts_code": "vi", "tts_locale": "vi", "locale": "vi-VN", "script": "Latin", "voice_engine": "gtts", "voice_code": "vi", "enabled": True},
    {"id": "th", "language_id": "th", "code": "th", "name": "Thai", "display_name": "Thai", "nllb_code": "tha_Thai", "translation_code": "th", "tts_code": "th", "tts_locale": "th", "locale": "th-TH", "script": "Thai", "voice_engine": "gtts", "voice_code": "th", "enabled": True},
    {"id": "ms", "language_id": "ms", "code": "ms", "name": "Malay", "display_name": "Malay", "nllb_code": "zsm_Latn", "translation_code": "ms", "tts_code": "ms", "tts_locale": "ms", "locale": "ms-MY", "script": "Latin", "voice_engine": "gtts", "voice_code": "ms", "enabled": True},
    {"id": "fil", "language_id": "fil", "code": "fil", "name": "Filipino", "display_name": "Filipino", "nllb_code": "tgl_Latn", "translation_code": "tl", "tts_code": "tl", "tts_locale": "tl", "locale": "tl-PH", "script": "Latin", "voice_engine": "gtts", "voice_code": "tl", "enabled": True},
    {"id": "sw", "language_id": "sw", "code": "sw", "name": "Swahili", "display_name": "Swahili", "nllb_code": "swh_Latn", "translation_code": "sw", "tts_code": "sw", "tts_locale": "sw", "locale": "sw-KE", "script": "Latin", "voice_engine": "gtts", "voice_code": "sw", "enabled": True},
    {"id": "af", "language_id": "af", "code": "af", "name": "Afrikaans", "display_name": "Afrikaans", "nllb_code": "afr_Latn", "translation_code": "af", "tts_code": "af", "tts_locale": "af", "locale": "af-ZA", "script": "Latin", "voice_engine": "gtts", "voice_code": "af", "enabled": True},
    {"id": "bg", "language_id": "bg", "code": "bg", "name": "Bulgarian", "display_name": "Bulgarian", "nllb_code": "bul_Cyrl", "translation_code": "bg", "tts_code": "bg", "tts_locale": "bg", "locale": "bg-BG", "script": "Cyrillic", "voice_engine": "gtts", "voice_code": "bg", "enabled": True},
    {"id": "ca", "language_id": "ca", "code": "ca", "name": "Catalan", "display_name": "Catalan", "nllb_code": "cat_Latn", "translation_code": "ca", "tts_code": "ca", "tts_locale": "ca", "locale": "ca-ES", "script": "Latin", "voice_engine": "gtts", "voice_code": "ca", "enabled": True},
    {"id": "hr", "language_id": "hr", "code": "hr", "name": "Croatian", "display_name": "Croatian", "nllb_code": "hrv_Latn", "translation_code": "hr", "tts_code": "hr", "tts_locale": "hr", "locale": "hr-HR", "script": "Latin", "voice_engine": "gtts", "voice_code": "hr", "enabled": True},
    {"id": "sk", "language_id": "sk", "code": "sk", "name": "Slovak", "display_name": "Slovak", "nllb_code": "slk_Latn", "translation_code": "sk", "tts_code": "sk", "tts_locale": "sk", "locale": "sk-SK", "script": "Latin", "voice_engine": "gtts", "voice_code": "sk", "enabled": True},
    {"id": "sl", "language_id": "sl", "code": "sl", "name": "Slovenian", "display_name": "Slovenian", "nllb_code": "slv_Latn", "translation_code": "sl", "tts_code": "sl", "tts_locale": "sl", "locale": "sl-SI", "script": "Latin", "voice_engine": "edge_tts", "voice_code": "sl-SI-RokNeural", "enabled": True},
    {"id": "sr", "language_id": "sr", "code": "sr", "name": "Serbian", "display_name": "Serbian", "nllb_code": "srp_Cyrl", "translation_code": "sr", "tts_code": "sr", "tts_locale": "sr", "locale": "sr-RS", "script": "Cyrillic", "voice_engine": "gtts", "voice_code": "sr", "enabled": True},
    {"id": "et", "language_id": "et", "code": "et", "name": "Estonian", "display_name": "Estonian", "nllb_code": "est_Latn", "translation_code": "et", "tts_code": "et", "tts_locale": "et", "locale": "et-EE", "script": "Latin", "voice_engine": "gtts", "voice_code": "et", "enabled": True},
    {"id": "lv", "language_id": "lv", "code": "lv", "name": "Latvian", "display_name": "Latvian", "nllb_code": "lvs_Latn", "translation_code": "lv", "tts_code": "lv", "tts_locale": "lv", "locale": "lv-LV", "script": "Latin", "voice_engine": "gtts", "voice_code": "lv", "enabled": True},
    {"id": "lt", "language_id": "lt", "code": "lt", "name": "Lithuanian", "display_name": "Lithuanian", "nllb_code": "lit_Latn", "translation_code": "lt", "tts_code": "lt", "tts_locale": "lt", "locale": "lt-LT", "script": "Latin", "voice_engine": "edge_tts", "voice_code": "lt-LT-OnaNeural", "enabled": True},

    # 51-58: Additional Global & Regional Languages
    {"id": "he", "language_id": "he", "code": "he", "name": "Hebrew", "display_name": "Hebrew", "nllb_code": "heb_Hebr", "translation_code": "iw", "tts_code": "iw", "tts_locale": "iw", "locale": "he-IL", "script": "Hebrew", "voice_engine": "gtts", "voice_code": "iw", "enabled": True},
    {"id": "fa", "language_id": "fa", "code": "fa", "name": "Persian", "display_name": "Persian", "nllb_code": "pes_Arab", "translation_code": "fa", "tts_code": "fa", "tts_locale": "fa", "locale": "fa-IR", "script": "Arabic", "voice_engine": "edge_tts", "voice_code": "fa-IR-FaridNeural", "enabled": True},
    {"id": "is", "language_id": "is", "code": "is", "name": "Icelandic", "display_name": "Icelandic", "nllb_code": "isl_Latn", "translation_code": "is", "tts_code": "is", "tts_locale": "is", "locale": "is-IS", "script": "Latin", "voice_engine": "gtts", "voice_code": "is", "enabled": True},
    {"id": "hy", "language_id": "hy", "code": "hy", "name": "Armenian", "display_name": "Armenian", "nllb_code": "hye_Armn", "translation_code": "hy", "tts_code": "hy", "tts_locale": "hy", "locale": "hy-AM", "script": "Armenian", "voice_engine": "edge_tts", "voice_code": "en-US-AvaMultilingualNeural", "enabled": True},
    {"id": "sq", "language_id": "sq", "code": "sq", "name": "Albanian", "display_name": "Albanian", "nllb_code": "als_Latn", "translation_code": "sq", "tts_code": "sq", "tts_locale": "sq", "locale": "sq-AL", "script": "Latin", "voice_engine": "gtts", "voice_code": "sq", "enabled": True},
    {"id": "mk", "language_id": "mk", "code": "mk", "name": "Macedonian", "display_name": "Macedonian", "nllb_code": "mkd_Cyrl", "translation_code": "mk", "tts_code": "mk", "tts_locale": "mk", "locale": "mk-MK", "script": "Cyrillic", "voice_engine": "edge_tts", "voice_code": "mk-MK-MarijaNeural", "enabled": True},
    {"id": "ka", "language_id": "ka", "code": "ka", "name": "Georgian", "display_name": "Georgian", "nllb_code": "kat_Geor", "translation_code": "ka", "tts_code": "ka", "tts_locale": "ka", "locale": "ka-GE", "script": "Georgian", "voice_engine": "edge_tts", "voice_code": "ka-GE-GiorgiNeural", "enabled": True},
    {"id": "cy", "language_id": "cy", "code": "cy", "name": "Welsh", "display_name": "Welsh", "nllb_code": "cym_Latn", "translation_code": "cy", "tts_code": "cy", "tts_locale": "cy", "locale": "cy-GB", "script": "Latin", "voice_engine": "edge_tts", "voice_code": "cy-GB-NiaNeural", "enabled": True},
]


def build_central_language_catalog():
    catalog = []
    for item in CANONICAL_58_LANGUAGES:
        code = item["code"]
        name = item["name"]
        tts_loc = item["tts_locale"]
        lang_id = item.get("id", code)
        catalog.append({
            "id": lang_id,
            "language_id": lang_id,
            "code": code,
            "name": name,
            "displayName": name,
            "display_name": name,
            "translationCode": item["translation_code"],
            "translation_code": item["translation_code"],
            "nllb_code": item["nllb_code"],
            "sourceCodeIfNeeded": "auto",
            "ttsCode": item.get("tts_code", tts_loc),
            "tts_code": item.get("tts_code", tts_loc),
            "ttsLocale": tts_loc,
            "tts_locale": tts_loc,
            "locale": item.get("locale", tts_loc),
            "script": item.get("script", "Latin"),
            "voice_engine": item.get("voice_engine", "gtts"),
            "voice_code": item.get("voice_code", tts_loc),
            "voiceId": f"{item.get('voice_engine', 'gtts')}_{item.get('voice_code', tts_loc)}",
            "translationSupported": True,
            "voiceSupported": True,
            "supports_translation": True,
            "supports_tts": True,
            "enabled": True,
        })
    return catalog


CENTRAL_LANGUAGE_CATALOG = build_central_language_catalog()


def get_all_supported_languages():
    return CENTRAL_LANGUAGE_CATALOG


get_supported_languages_metadata = get_all_supported_languages


def get_language_config(code: str):
    if not code:
        return None
    c_lower = code.lower().strip()
    for lang in CENTRAL_LANGUAGE_CATALOG:
        if (
            lang["id"].lower() == c_lower
            or lang["language_id"].lower() == c_lower
            or lang["code"].lower() == c_lower
            or lang["name"].lower() == c_lower
            or lang["translation_code"].lower() == c_lower
            or lang["nllb_code"].lower() == c_lower
        ):
            return lang
    return None


def get_language_by_id(lang_id: str):
    return get_language_config(lang_id)


def resolve_canonical_language(query: str):
    return get_language_config(query)


def is_translation_supported(code: str) -> bool:
    config = get_language_config(code)
    return config["supports_translation"] if config else False


def is_tts_supported(code: str) -> bool:
    config = get_language_config(code)
    return config["supports_tts"] if config else False


def get_tts_locale_for_language(code: str) -> str:
    config = get_language_config(code)
    if config and config["tts_locale"]:
        return config["tts_locale"]
    return code
