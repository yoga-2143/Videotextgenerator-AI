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
