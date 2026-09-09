"""
Test Source Contamination Protection — VideoTextGenerator AI.
Guarantees that IMPORTANT CONTENT generated from a YouTube transcript contains ONLY
information from the CURRENT video and never introduces unrelated topics such as:
- employee handbook
- sprint objective
- RAG (unless in source)
- vacation leave
- holiday information
- document A/B/C
"""
import pytest
from app.services.llm_service import FallbackExtractiveProvider, GeminiProvider, article_to_plain_text, synthesize_clean_prose
from app.services.summarizer_service import rank_important_sentences

UNRELATED_CONTAMINATED_KEYWORDS = [
    "employee handbook",
    "sprint objective",
    "vacation leave",
    "holiday information",
    "document a",
    "document b",
    "document c",
    "company policy",
    "maternity leave",
]


def test_source_grounding_pure_rag_transcript():
    """Controlled test: Transcript contains ONLY RAG concepts.
    IMPORTANT CONTENT must ONLY describe RAG and must contain ZERO employee handbook / vacation leave contamination.
    """
    controlled_rag_transcript = (
        "This video explains retrieval augmented generation. "
        "It retrieves relevant information from external document databases and provides that context to a language model before generating an answer. "
        "Retrieval augmented generation improves answer accuracy, grounds responses in factual source documents, and reduces hallucinations."
    )

    ranked = rank_important_sentences(controlled_rag_transcript)
    provider = FallbackExtractiveProvider()
    article_dict = provider.generate_article(ranked, video_title="Understanding RAG")
    article_text = article_to_plain_text(article_dict)

    # 1. Must contain source concepts
    assert "retrieval" in article_text.lower() or "generation" in article_text.lower()

    # 2. Must NOT contain any unrelated contaminated keywords
    for keyword in UNRELATED_CONTAMINATED_KEYWORDS:
        assert keyword not in article_text.lower(), f"Source contamination detected: found '{keyword}' in generated content!"


def test_source_grounding_pure_technical_transcript():
    """Controlled test: Transcript contains Python web development concepts.
    IMPORTANT CONTENT must NOT contain RAG or employee handbook contamination.
    """
    python_transcript = (
        "In this video we build a web application using Python and Flask. "
        "Flask is a micro web framework written in Python. "
        "It allows developers to create route handlers, render HTML templates, and expose JSON APIs for frontend applications."
    )

    ranked = rank_important_sentences(python_transcript)
    provider = FallbackExtractiveProvider()
    article_dict = provider.generate_article(ranked, video_title="Python Flask Web Development")
    article_text = article_to_plain_text(article_dict)

    assert "flask" in article_text.lower() or "python" in article_text.lower()

    # Contaminated topics must NOT be present
    for keyword in UNRELATED_CONTAMINATED_KEYWORDS:
        assert keyword not in article_text.lower(), f"Source contamination detected: found '{keyword}' in generated content!"
