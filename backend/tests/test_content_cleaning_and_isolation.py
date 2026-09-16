import pytest
from app.services.transcript_service import clean_transcript
from app.services.llm_service import synthesize_clean_prose, is_semantic_duplicate
from app.services.hard_words_service import extract_hard_words
from app.services.translator_service import translate_text
from app.services.tts_service import generate_audio, TTSError
from app.services.transcript_providers import TranscriptResult, validate_transcript


def test_A_exact_duplicate_transcript_segments():
    raw = "The system is secure. The system is secure. It operates smoothly."
    cleaned = clean_transcript(raw)
    assert cleaned.count("The system is secure.") == 1
    assert "It operates smoothly." in cleaned


def test_B_overlapping_chunk_duplication():
    raw = "AI improves accuracy across models AI improves accuracy across models for better performance."
    cleaned = clean_transcript(raw)
    assert cleaned.count("AI improves accuracy across models") == 1
    assert "better performance" in cleaned


def test_C_meaningful_repeated_speech_preserved():
    raw = "This step is very, very important for success."
    cleaned = clean_transcript(raw)
    assert "very, very important" in cleaned


def test_D_repeated_important_content():
    raw = "AI models process natural language effectively. AI models process natural language effectively."
    prose = synthesize_clean_prose(raw, "AI Video")
    paragraphs = [p for p in prose.split("\n\n") if p.strip()]
    assert len(paragraphs) == 5
    # Verify no two paragraphs are identical
    seen = set()
    for p in paragraphs:
        assert p not in seen
        seen.add(p)


def test_E_semantically_duplicate_important_content():
    p1 = "AI models improve transcription accuracy across multiple languages."
    p2 = "AI models enhance transcript accuracy in several languages."
    p3 = "Whisper is used as an audio fallback when native captions are unavailable."
    
    assert is_semantic_duplicate(p1, p2) is True
    assert is_semantic_duplicate(p1, p3) is False


def test_F_unrelated_injected_content_rejection():
    raw = "This video covers Python programming. Don't forget to subscribe and smash the like button! Visit sponsored link in description."
    cleaned = clean_transcript(raw)
    assert "subscribe" not in cleaned.lower()
    assert "like button" not in cleaned.lower()
    assert "sponsored" not in cleaned.lower()
    assert "Python programming" in cleaned


def test_G_previous_video_contamination_isolation():
    res_A = TranscriptResult(
        video_id="video_A_123",
        source="captions",
        source_language="en",
        transcript_text="Exclusively Video A transcript content about astronomy.",
    )
    res_B = TranscriptResult(
        video_id="video_B_456",
        source="captions",
        source_language="en",
        transcript_text="Exclusively Video B transcript content about biology.",
    )

    assert res_A.video_id != res_B.video_id
    assert res_A.source_text_hash != res_B.source_text_hash
    assert "biology" not in res_A.transcript_text
    assert "astronomy" not in res_B.transcript_text
    assert validate_transcript(res_A, "video_A_123") is True
    assert validate_transcript(res_B, "video_A_123") is False


def test_H_clean_transcript_to_translation():
    raw = "Artificial intelligence is expanding rapidly."
    cleaned = clean_transcript(raw)
    translated = translate_text(cleaned, target_lang="es")
    assert translated is not None
    assert len(translated) > 5


def test_I_clean_translation_to_audio():
    text = "La inteligencia artificial se está expandiendo rápidamente."
    audio_file = generate_audio(text, lang="es")
    assert audio_file is not None
    assert audio_file.endswith((".mp3", ".wav"))
