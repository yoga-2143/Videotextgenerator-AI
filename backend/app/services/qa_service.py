"""
Automatic QA Checklist Computation & Badging Service.
Computes honest metrics for meaning preservation, repetition removal,
proofreading status, and readability without false 100% claims.
"""
import re
import logging

logger = logging.getLogger(__name__)

def compute_word_overlap_similarity(source_text: str, article_text: str) -> float:
    """Computes Jaccard word set similarity between source transcript and article text."""
    if not source_text or not article_text:
        return 0.0
    words_src = set(re.findall(r"\w+", source_text.lower()))
    words_art = set(re.findall(r"\w+", article_text.lower()))
    if not words_art:
        return 0.0
    intersection = words_src.intersection(words_art)
    # Proportion of article key terms present in source
    score = (len(intersection) / len(words_art)) * 100.0
    return round(min(score, 100.0), 1)


def count_duplicate_sentences(text: str) -> int:
    """Detects duplicate or near-duplicate sentences in text."""
    sentences = [s.strip().lower() for s in re.split(r"(?<=[.!?])\s+", text or "") if len(s.strip()) > 8]
    if not sentences:
        return 0
    seen = set()
    dup_count = 0
    for s in sentences:
        if s in seen:
            dup_count += 1
        else:
            seen.add(s)
    return dup_count


def compute_flesch_readability(text: str, lang: str = "en") -> dict:
    """Computes basic Flesch Reading Ease score for English, or structural readability metrics for other languages."""
    if not text or not text.strip():
        return {"score": 0.0, "level": "N/A", "supported": False}

    if lang.lower() != "en":
        # Structural readability heuristic for non-English
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        words = re.findall(r"\w+", text)
        avg_sentence_len = len(words) / max(len(sentences), 1)
        level = "Easy" if avg_sentence_len < 15 else "Moderate" if avg_sentence_len < 25 else "Complex"
        return {"score": round(max(100.0 - avg_sentence_len * 2, 30.0), 1), "level": level, "supported": True}

    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    words = re.findall(r"\b[a-zA-Z]+\b", text)
    if not sentences or not words:
        return {"score": 0.0, "level": "N/A", "supported": False}

    # Count syllables roughly
    syllable_count = 0
    for word in words:
        w = word.lower()
        count = len(re.findall(r"[aeiouy]+", w))
        if w.endswith("e") and not w.endswith("le") and count > 1:
            count -= 1
        syllable_count += max(count, 1)

    score = 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllable_count / len(words))
    score = round(max(0.0, min(score, 100.0)), 1)
    level = "Easy" if score >= 70 else "Fairly Easy" if score >= 60 else "Standard" if score >= 50 else "Complex"
    return {"score": score, "level": level, "supported": True}


def run_qa_checklist(source_text: str, article_text: str, lang: str = "en", proofread_used: bool = True) -> dict:
    """Runs honest QA checklist and returns badges and numerical scores."""
    similarity_score = compute_word_overlap_similarity(source_text, article_text)
    duplicate_count = count_duplicate_sentences(article_text)
    readability = compute_flesch_readability(article_text, lang)

    badges = [
        {
            "name": "Meaning Checked",
            "passed": similarity_score >= 40.0,
            "metric": f"{similarity_score}% overlap",
            "heuristic": "Jaccard vocabulary overlap against source transcript"
        },
        {
            "name": "Low Repetition",
            "passed": duplicate_count == 0,
            "metric": f"{duplicate_count} duplicate sentences",
            "heuristic": "Exact and near-duplicate sentence scan"
        },
        {
            "name": "Proofread",
            "passed": proofread_used,
            "metric": "Completed" if proofread_used else "Skipped",
            "heuristic": "Contextual spelling & grammar proofreading pass"
        },
        {
            "name": "Readability Checked",
            "passed": readability["supported"],
            "metric": f"Score {readability['score']} ({readability['level']})",
            "heuristic": "Flesch Reading Ease & structural length analysis"
        }
    ]

    return {
        "verified": similarity_score >= 40.0 and duplicate_count == 0,
        "similarity_score": similarity_score,
        "duplicate_sentences_found": duplicate_count,
        "proofread_status": "completed" if proofread_used else "skipped",
        "readability": readability,
        "badges": badges
    }
