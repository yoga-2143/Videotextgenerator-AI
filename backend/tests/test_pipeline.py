import pytest
from app.services.mmr import apply_mmr
from app.services.chunker import chunk_transcript, merge_chunk_results
from app.services.verification_service import verify_source_consistency
from app.services.language_config import get_supported_languages_metadata, is_translation_supported, is_tts_supported


def test_mmr_deduplication():
    sentences = [
        "The quick brown fox jumps over the lazy dog.",
        "A fast brown fox leaps over a lazy hound.",  # Highly similar to first sentence
        "Artificial intelligence is transforming software development.",
        "Machine learning models process vast amounts of data."
    ]
    tokenized = [s.lower().split() for s in sentences]
    selected = apply_mmr(sentences, tokenized, lambda_param=0.6, top_n=2)
    assert len(selected) == 2
    assert "The quick brown fox jumps over the lazy dog." in selected


def test_chunk_transcript():
    sentences = [f"This is sentence number {i} for testing long video transcript chunking." for i in range(50)]
    chunks = chunk_transcript(sentences, max_words_per_chunk=100, overlap_sentences=1)
    assert len(chunks) > 1


def test_verification_service():
    source_text = "In 2024, VETRI processed over 1000 videos across 12 languages."
    article = {
        "title": "VETRI Milestones",
        "sections": [{"heading": "Growth", "body": "In 2024, VETRI processed 1000 videos."}],
        "conclusion": "It supports 12 languages."
    }
    report = verify_source_consistency(article, source_text)
    assert report["verified"] is True
    assert report["consistency_score"] == 100.0


def test_language_config():
    langs = get_supported_languages_metadata()
    codes = [l["code"] for l in langs]
    assert "en" in codes and "ta" in codes
    assert is_translation_supported("ta") is True
    assert is_tts_supported("ta") is True
    assert is_translation_supported("invalid_lang") is False
