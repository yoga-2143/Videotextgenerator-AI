import pytest
from app.services.transcript_service import get_transcript, fetch_transcript

def test_jnqxac9ivrw_first_youtube_video_captions_success():
    """Verify that video jNQXAC9IVRw ('Me at the zoo') successfully extracts YouTube captions without triggering audio download fallback."""
    raw_text, lang = fetch_transcript("jNQXAC9IVRw")
    assert raw_text is not None
    assert len(raw_text) > 20
    assert lang == "en"
    assert "elephants" in raw_text.lower() or "zoo" in raw_text.lower() or "trunks" in raw_text.lower()

    cleaned, lang_code, source = get_transcript("jNQXAC9IVRw")
    assert source == "captions"
    assert lang_code == "en"
    assert len(cleaned) > 20
