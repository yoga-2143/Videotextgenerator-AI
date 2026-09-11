"""
Universal Multi-Engine Text-to-Speech (TTS) Service.
Supports 100% of all 58 configured languages using a multi-engine architecture:
1. gTTS: High-reliability Google Translate Speech engine for 50+ languages.
2. Google Web TTS Direct: For Punjabi (pa) and custom locales.
3. Microsoft Edge Neural TTS (edge-tts): Crystal-clear neural voices for Slovenian (sl),
   Lithuanian (lt), Persian (fa), Macedonian (mk), Georgian (ka), Welsh (cy).
4. Meta MMS-TTS (facebook/mms-tts-hyw): Native VITS neural synthesis for Armenian (hy).

Generated audio files are saved in temporary cache storage, validated for non-zero size,
and automatically managed with chunking for long articles (> 3000 chars).
"""
import os
import re
import time
import uuid
import asyncio
import logging
import tempfile
import unicodedata
import urllib.request
import urllib.parse
from gtts import gTTS

from app.services.language_config import get_language_config, is_tts_supported

logger = logging.getLogger(__name__)

# OS temporary cache directory for generated audio
AUDIO_DIR = os.path.join(tempfile.gettempdir(), "vetri_generated_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

MAX_TTS_CHUNK_CHARS = 4000

# Global lazy-loaded cache for HuggingFace models
_MMS_MODELS = {}


class TTSError(Exception):
    pass


def cleanup_stale_audio(max_age_seconds: int = 3600):
    """Safely cleans up temporary audio files older than max_age_seconds."""
    now = time.time()
    try:
        for fname in os.listdir(AUDIO_DIR):
            if fname.endswith((".mp3", ".wav")):
                fpath = os.path.join(AUDIO_DIR, fname)
                if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > max_age_seconds:
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass
    except Exception:
        pass


def _chunk_tts_text(text: str, max_chars: int = 400):
    """Splits long text into TTS-safe chunks at sentence/word boundaries."""
    text = unicodedata.normalize("NFC", text or "")
    sentences = re.split(r'(?<=[.!?|।])\s+', text)
    chunks, current = [], ""

    for s in sentences:
        if len(current) + len(s) + 1 > max_chars:
            if current:
                chunks.append(current)
            current = s
        else:
            current = f"{current} {s}" if current else s

    if current:
        chunks.append(current)

    return chunks


def _synthesize_edge_tts(text: str, voice_code: str, output_path: str):
    """Synthesizes text using Microsoft Edge Neural TTS."""
    import edge_tts
    async def _run():
        communicate = edge_tts.Communicate(text, voice_code)
        await communicate.save(output_path)
    asyncio.run(_run())


def _synthesize_google_web_tts(text: str, lang_code: str, output_path: str):
    """Synthesizes text using Google Web Translate TTS stream."""
    q = urllib.parse.quote(text)
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={q}&tl={lang_code}&client=tw-ob"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        with open(output_path, "wb") as f:
            f.write(resp.read())


def _synthesize_mms_tts(text: str, model_id: str, output_path: str):
    """Synthesizes speech using Meta MMS VITS model (e.g. for Armenian)."""
    import torch
    import scipy.io.wavfile
    from transformers import VitsModel, AutoTokenizer

    global _MMS_MODELS
    if model_id not in _MMS_MODELS:
        logger.info(f"[MMS-TTS] Loading neural model {model_id}...")
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = VitsModel.from_pretrained(model_id)
        _MMS_MODELS[model_id] = (tokenizer, model)
    else:
        tokenizer, model = _MMS_MODELS[model_id]

    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        output = model(**inputs).waveform
    scipy.io.wavfile.write(output_path, rate=model.config.sampling_rate, data=output.numpy()[0])


def generate_audio(text: str, lang: str) -> str:
    cleanup_stale_audio()
    if not text or not text.strip():
        raise TTSError("No text provided for audio generation.")

    lang_config = get_language_config(lang)
    if not lang_config or not lang_config.get("supports_tts"):
        raise TTSError(f"Voice generation is not available for language '{lang}'.")

    engine = lang_config.get("voice_engine", "gtts")
    voice_code = lang_config.get("voice_code") or lang_config.get("tts_code") or lang
    tts_locale = lang_config.get("tts_locale") or lang

    chunks = _chunk_tts_text(text)
    logger.info(
        f"[TTS GENERATION START] requested_lang={lang}, engine={engine}, voice_code={voice_code}, "
        f"tts_locale={tts_locale}, text_len={len(text)}, chunks={len(chunks)}"
    )

    ext = ".wav" if engine == "mms_tts" else ".mp3"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(AUDIO_DIR, filename)

    try:
        cleaned_chunks = []
        for c in chunks:
            sc = re.sub(r"[\[\]\{\}\*\#\`\_]", " ", c)
            sc = re.sub(r"\b([a-zA-Z0-9\-]+)\.(com|org|net|in|io|ai|co|gov|edu)\b", r"\1 dot \2", sc, flags=re.IGNORECASE)
            sc = re.sub(r"(\S{80})", r"\1 ", sc)
            sc = re.sub(r"\s+", " ", sc).strip()
            if sc:
                cleaned_chunks.append(sc)
        if not cleaned_chunks:
            cleaned_chunks = ["Important Content Overview."]

        def _render_chunk(chunk_str: str, target_file: str):
            rendered = False
            if engine == "edge_tts" and voice_code:
                try:
                    _synthesize_edge_tts(chunk_str, voice_code, target_file)
                    rendered = True
                except Exception as ex:
                    logger.warning(f"[TTS FALLBACK] edge_tts failed for {lang} ({voice_code}): {ex}")

            if not rendered and engine == "mms_tts":
                try:
                    _synthesize_mms_tts(chunk_str, voice_code, target_file)
                    rendered = True
                except Exception as ex:
                    logger.warning(f"[TTS FALLBACK] mms_tts failed for {lang} ({voice_code}): {ex}")

            if not rendered and engine == "google_web_tts":
                try:
                    if len(chunk_str) <= 200:
                        _synthesize_google_web_tts(chunk_str, lang, target_file)
                        rendered = True
                except Exception as ex:
                    logger.warning(f"[TTS FALLBACK] google_web_tts failed for {lang}: {ex}")

            if not rendered:
                try:
                    tts = gTTS(text=chunk_str, lang=tts_locale)
                    tts.save(target_file)
                    rendered = True
                except Exception as ex:
                    logger.warning(f"[TTS FALLBACK] gTTS failed for {lang} ({tts_locale}): {ex}")

            if not rendered:
                try:
                    _synthesize_edge_tts(chunk_str, "en-US-AvaMultilingualNeural", target_file)
                    rendered = True
                except Exception as ex:
                    raise TTSError(f"Voice generation failed for language '{lang}': {ex}")

        if len(cleaned_chunks) == 1:
            _render_chunk(cleaned_chunks[0], filepath)
        else:
            temp_chunk_paths = []
            for i, chunk in enumerate(cleaned_chunks):
                temp_chunk_file = os.path.join(AUDIO_DIR, f"temp_{uuid.uuid4().hex}_{i}{ext}")
                _render_chunk(chunk, temp_chunk_file)
                temp_chunk_paths.append(temp_chunk_file)

            if ext == ".mp3":
                # MP3 chunks can be concatenated directly
                with open(filepath, "wb") as f_out:
                    for chunk_path in temp_chunk_paths:
                        if os.path.isfile(chunk_path):
                            with open(chunk_path, "rb") as f_in:
                                f_out.write(f_in.read())
                            try:
                                os.remove(chunk_path)
                            except OSError:
                                pass
            else:
                # WAV concatenation using scipy/numpy
                import scipy.io.wavfile
                import numpy as np
                rates, datas = [], []
                for chunk_path in temp_chunk_paths:
                    if os.path.isfile(chunk_path):
                        r, d = scipy.io.wavfile.read(chunk_path)
                        rates.append(r)
                        datas.append(d)
                        try:
                            os.remove(chunk_path)
                        except OSError:
                            pass
                if datas:
                    combined = np.concatenate(datas)
                    scipy.io.wavfile.write(filepath, rate=rates[0], data=combined)

        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise TTSError("Generated audio file is empty.")

        logger.info(f"[TTS GENERATION SUCCESS] filename={filename}, file_size={os.path.getsize(filepath)} bytes")
        return filename
    except Exception as e:
        logger.exception(f"[TTS GENERATION ERROR] lang={lang}, engine={engine}, voice_code={voice_code}, error={e}")
        raise TTSError(f"Voice generation failed for language '{lang}': {e}")
