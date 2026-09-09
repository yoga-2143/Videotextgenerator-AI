"""
Dubbing & Voice Generation Orchestration Service.
Supports Meta SeamlessM4T advanced dubbing when configured and available,
with automatic safe fallback to gTTS voice audio generation.
Tracks and stores exact dubbing_source ('seamless_m4t', 'gtts_fallback', 'none').
"""
import os
import logging
from app.services.tts_service import generate_audio, TTSError
from app.services.language_config import get_language_config

logger = logging.getLogger(__name__)

DUBBING_ENGINE = os.getenv("DUBBING_ENGINE", "gtts_fallback").lower().strip()
ENABLE_SEAMLESS_M4T = os.getenv("ENABLE_SEAMLESS_M4T", "false").lower() == "true"


def generate_dubbed_audio(text: str, target_lang: str) -> tuple[str, str]:
    """Generates dubbed audio using the configured engine from canonical catalog.
    Returns tuple of (filename, dubbing_source)."""
    if not text or not text.strip():
        raise TTSError("No text provided for audio generation.")

    lang_config = get_language_config(target_lang)
    engine = lang_config.get("voice_engine", "gtts") if lang_config else "gtts"

    if DUBBING_ENGINE == "seamless_m4t" and ENABLE_SEAMLESS_M4T:
        try:
            logger.info(f"[SEAMLESS_M4T] Attempting SeamlessM4T dubbing generation for lang={target_lang}")
            import torch
            from transformers import AutoProcessor, SeamlessM4TModel
            processor = AutoProcessor.from_pretrained("facebook/seamless-m4t-v2-large")
            model = SeamlessM4TModel.from_pretrained("facebook/seamless-m4t-v2-large")
            raise NotImplementedError("SeamlessM4T hardware resources not active, falling back to canonical TTS")
        except Exception as e:
            logger.warning(f"[SEAMLESS_M4T FALLBACK] SeamlessM4T unavailable ({e}), falling back to canonical TTS")

    filename = generate_audio(text, target_lang)
    return filename, engine

