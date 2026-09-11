"""
Translation service with robust multi-backend fallback system:
Layer 1: Direct Google Translate Endpoint (client=dict-chrome-ex) - 0 rate limits, ultra-fast.
Layer 2: Direct Google Translate Endpoint (client=gtx).
Layer 3: deep-translator GoogleTranslator.
Handles safe sentence boundary chunking, Unicode normalization, and internal dev logging.
"""
import re
import unicodedata
import urllib.request
import urllib.parse
import json
import logging
import html
from deep_translator import GoogleTranslator
from app.services.language_config import get_all_supported_languages, is_translation_supported, get_language_config
from app.services.error_validator import contains_raw_error_text

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 1800


class TranslationError(Exception):
    pass


def get_supported_languages():
    return get_all_supported_languages()


def _chunk_text(text: str, size: int = MAX_CHUNK_CHARS):
    """Splits text into chunks of at most 'size' characters at sentence/paragraph boundaries."""
    text = unicodedata.normalize("NFC", text or "")
    if len(text) <= size:
        return [text]

    paragraphs = text.split("\n")
    chunks, current = [], ""

    for p in paragraphs:
        if len(p) > size:
            sentences = re.split(r'(?<=[.!?|।\n])\s+', p)
            for s in sentences:
                if len(current) + len(s) + 1 > size:
                    if current:
                        chunks.append(current)
                    current = s
                else:
                    current = f"{current} {s}" if current else s
        else:
            if len(current) + len(p) + 1 > size:
                if current:
                    chunks.append(current)
                current = p
            else:
                current = f"{current}\n{p}" if current else p

    if current:
        chunks.append(current)

    return chunks


def _translate_google_endpoint(text_chunk: str, target_lang: str, source_lang: str = "auto", client: str = "dict-chrome-ex") -> str:
    """Direct HTTP request to Google Translate single API endpoint."""
    url = f"https://translate.googleapis.com/translate_a/single?client={client}&sl={source_lang}&tl={target_lang}&dt=t&q={urllib.parse.quote(text_chunk)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        raw_data = response.read().decode("utf-8")
        if contains_raw_error_text(raw_data):
            raise ValueError(f"Endpoint '{client}' returned error response")
        data = json.loads(raw_data)
        if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            translated_pieces = [item[0] for item in data[0] if item and len(item) > 0 and item[0]]
            res = "".join(translated_pieces)
            if res and not contains_raw_error_text(res):
                return res
    raise ValueError(f"Endpoint '{client}' returned empty or invalid translation")


def _translate_single_chunk(chunk: str, target_lang: str, source_lang: str = "auto") -> str:
    # If target language is identical to source language, return unchanged
    if source_lang != "auto" and target_lang.lower().strip() == source_lang.lower().strip():
        return chunk

    # Layer 1: Direct Google Translate Endpoint (client=dict-chrome-ex)
    try:
        res = _translate_google_endpoint(chunk, target_lang, source_lang if source_lang != "auto" else "auto", client="dict-chrome-ex")
        if res and res.strip() and not contains_raw_error_text(res):
            return unicodedata.normalize("NFC", res)
    except Exception as e:
        logger.warning(f"Translation Layer 1 (dict-chrome-ex) note for target={target_lang}: {e}")

    # Layer 2: Direct Google Translate Endpoint (client=gtx)
    try:
        res = _translate_google_endpoint(chunk, target_lang, source_lang if source_lang != "auto" else "auto", client="gtx")
        if res and res.strip() and not contains_raw_error_text(res):
            return unicodedata.normalize("NFC", res)
    except Exception as e:
        logger.warning(f"Translation Layer 2 (gtx) note for target={target_lang}: {e}")

    # Layer 3: deep-translator GoogleTranslator
    try:
        translator = GoogleTranslator(source="auto" if source_lang == "auto" else source_lang, target=target_lang)
        res = translator.translate(chunk)
        if res and res.strip() and not contains_raw_error_text(res):
            return unicodedata.normalize("NFC", res)
    except Exception as e:
        logger.warning(f"Translation Layer 3 (deep-translator) note for target={target_lang}: {e}")

    # If all translation layers failed, raise TranslationError
    raise TranslationError(f"Translation service was unable to translate content into target language '{target_lang}'.")


def _clean_translated_formatting(text: str) -> str:
    if not text:
        return text or ""
    # Safely unescape HTML entities in translated text & strip speaker tags
    text = html.unescape(text)
    text = re.sub(r"(?:^|\n|\s)>>+\s*", " ", text)
    # Normalize bullet point formatting
    text = re.sub(r"^\s*•\s*", "• ", text, flags=re.MULTILINE)
    # Normalize unbroken domain names & URLs (e.g. indiaabigs . com -> indiaabigs.com)
    text = re.sub(r"\b([a-zA-Z0-9\-]+)\s*\.\s*(com|org|net|in|io|ai|co|gov|edu)\b", r"\1.\2", text, flags=re.IGNORECASE)
    # Remove spacing before punctuation and duplicate punctuation
    text = re.sub(r"\s+([,.:;!?])", r"\1", text)
    text = re.sub(r"([,.:;!?])\1+", r"\1", text)
    return unicodedata.normalize("NFC", text.strip())


def validate_translated_content(text: str, target_lang: str) -> bool:
    """Verifies that translated text is valid and not an empty or untranslated fallback."""
    if not text or not text.strip():
        return False
    if contains_raw_error_text(text):
        return False

    # Non-Latin script verification map covering all non-Latin languages in 58-language catalog
    SCRIPT_PATTERNS = {
        "ta": r"[\u0B80-\u0BFF]",
        "hi": r"[\u0900-\u097F]",
        "te": r"[\u0C00-\u0C7F]",
        "ml": r"[\u0D00-\u0D7F]",
        "kn": r"[\u0C80-\u0CFF]",
        "bn": r"[\u0980-\u09FF]",
        "mr": r"[\u0900-\u097F]",
        "gu": r"[\u0A80-\u0AFF]",
        "ur": r"[\u0600-\u06FF\u0750-\u077F]",
        "pa": r"[\u0A00-\u0A7F]",
        "ar": r"[\u0600-\u06FF]",
        "fa": r"[\u0600-\u06FF\u0750-\u077F]",
        "ru": r"[\u0400-\u04FF]",
        "uk": r"[\u0400-\u04FF]",
        "bg": r"[\u0400-\u04FF]",
        "sr": r"[\u0400-\u04FF]",
        "mk": r"[\u0400-\u04FF]",
        "ja": r"[\u3040-\u30ff\u4e00-\u9fff]",
        "ko": r"[\uac00-\ud7af]",
        "zh-CN": r"[\u4e00-\u9fff]",
        "zh-TW": r"[\u4e00-\u9fff]",
        "th": r"[\u0E00-\u0E7F]",
        "el": r"[\u0370-\u03FF]",
        "he": r"[\u0590-\u05FF]",
        "hy": r"[\u0530-\u058F]",
        "ka": r"[\u10A0-\u10FF]",
    }

    clean_code = (target_lang or "").lower().split("-")[0]
    full_code = target_lang or ""

    pattern = SCRIPT_PATTERNS.get(full_code) or SCRIPT_PATTERNS.get(clean_code)
    if pattern:
        if not re.search(pattern, text):
            logger.warning(f"Translation validation failed: text lacks target script characters for lang={target_lang}")
            return False

    return True


def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    if not text or not text.strip():
        return text or ""

    lang_config = get_language_config(target_lang)
    if not lang_config:
        raise TranslationError(f"Target language '{target_lang}' is not supported.")

    effective_target = lang_config["translation_code"]
    nllb_code = lang_config.get("nllb_code", "eng_Latn")

    if source_lang != "auto" and target_lang.lower().strip() == source_lang.lower().strip():
        return _clean_translated_formatting(text)

    chunks = _chunk_text(text)
    logger.info(
        f"[TRANSLATION START] source={source_lang}, target={target_lang}, "
        f"effective_target={effective_target}, nllb_target_code={nllb_code}, "
        f"text_len={len(text)}, chunks={len(chunks)}"
    )

    if len(chunks) == 1:
        translated_chunks = [_translate_single_chunk(chunks[0], effective_target, source_lang)]
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(5, len(chunks))) as executor:
            translated_chunks = list(executor.map(lambda c: _translate_single_chunk(c, effective_target, source_lang), chunks))

    raw_translated = "\n".join(translated_chunks)
    final_translated = _clean_translated_formatting(raw_translated)

    if not validate_translated_content(final_translated, target_lang):
        raise TranslationError(f"Translation verification failed for target language '{target_lang}'.")

    logger.info(f"[TRANSLATION SUCCESS] target={target_lang}, effective={effective_target}, result_len={len(final_translated)}")
    return final_translated
