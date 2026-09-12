"""
Error Validator Utility.
Detects and rejects raw external HTTP error pages, 500 error strings, 
and HTML error fragments from being saved or displayed as video content.
"""

RAW_ERROR_PATTERNS = [
    "error 500",
    "server error",
    "that's an error",
    "that’s an error",
    "there was an error",
    "that's all we know",
    "that’s all we know",
    "<!doctype html",
    "<html",
    "500.",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway timeout",
    "403 forbidden",
    "internal server error",
    "sign in to confirm",
    "confirm you're not a bot",
    "requestblocked",
    "yt-dlp",
    "ytdlp",
    "youtube-dl",
    "traceback (most recent call last)",
    "sqlite3.",
    "sqlalchemy.",
    "pymysql.",
    "mysql.",
    "/app/services/",
    "c:\\users\\",
    "c:/users/",
]


def contains_raw_error_text(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    lower_text = text.lower()
    return any(pattern in lower_text for pattern in RAW_ERROR_PATTERNS)


def sanitize_text_field(text: str, fallback: str = "") -> str:
    if not text or contains_raw_error_text(text):
        return fallback
    return text.strip()


def sanitize_user_error_message(code: str, raw_message: str = "") -> str:
    """Guarantees that raw internal exceptions, tracebacks, or yt-dlp error strings never leak to end users."""
    clean_code = (code or "PROCESSING_ERROR").upper()

    SAFE_ERROR_MAP = {
        "INVALID_URL": "Please enter a valid YouTube URL (e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ).",
        "VIDEO_PRIVATE": "This video is private and cannot be processed.",
        "VIDEO_UNAVAILABLE": "This YouTube video is unavailable, deleted, or does not exist.",
        "VIDEO_AGE_RESTRICTED": "This video has age access restrictions and cannot be processed.",
        "TRANSCRIPT_UNAVAILABLE": "Unable to retrieve a transcript for this video right now. Please try again later.",
        "BOT_PROTECTION_BLOCKED": "Unable to retrieve a transcript for this video right now. Please try again later.",
        "WHISPER_TIMEOUT": "Speech-to-text processing took too long. Please try again.",
        "WHISPER_LIMIT_EXCEEDED": "Processing limit exceeded for video audio length.",
        "AUDIO_EXTRACTION_FAILED": "Unable to retrieve a transcript for this video right now. Please try again later.",
        "WHISPER_TRANSCRIPTION_FAILED": "Unable to retrieve a transcript for this video right now. Please try again later.",
        "TRANSLATION_FAILED": "Translation is temporarily unavailable for this language. Please try again later.",
        "TRANSLATION_LANGUAGE_UNSUPPORTED": "Translation into this language is not currently supported.",
        "VOICE_GENERATION_FAILED": "Voice audio generation is temporarily unavailable for this language. Please try again later.",
        "VOICE_LANGUAGE_MISMATCH": "Voice audio validation failed for this language. Please try again later.",
        "JOB_STALLED": "Processing job timed out. Please try again.",
        "PROCESSING_TIMEOUT": "Processing job timed out. Please try again.",
        "JOB_CANCELLED": "Job was cancelled by user.",
    }

    if raw_message and not contains_raw_error_text(raw_message):
        clean_msg = raw_message.split("\n")[0].strip()
        if clean_msg and not contains_raw_error_text(clean_msg):
            return clean_msg

    return SAFE_ERROR_MAP.get(clean_code, "Processing failed. Please try again later.")
