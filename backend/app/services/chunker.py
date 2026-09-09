"""
Intelligent Transcript Chunking and Cross-Chunk Merging Module.
Handles long video transcripts without hitting LLM context limits or losing cross-sentence context.
"""
import re


def chunk_transcript(sentences: list, max_words_per_chunk: int = 800, overlap_sentences: int = 2) -> list:
    """
    Splits sentences into manageable chunks based on word count while overlapping
    sentences across chunk boundaries to preserve semantic context.
    """
    chunks = []
    current_chunk = []
    current_word_count = 0

    for i, sentence in enumerate(sentences):
        words = sentence.split()
        word_count = len(words)

        if current_word_count + word_count > max_words_per_chunk and current_chunk:
            chunks.append(current_chunk)
            # Start next chunk with overlap sentences from previous chunk
            overlap = current_chunk[-overlap_sentences:] if len(current_chunk) >= overlap_sentences else current_chunk
            current_chunk = list(overlap)
            current_word_count = sum(len(s.split()) for s in current_chunk)

        current_chunk.append(sentence)
        current_word_count += word_count

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def merge_chunk_results(chunk_summaries: list) -> str:
    """
    Combines chunk summaries and removes duplicate sentences that may occur across chunk boundaries.
    """
    seen_sentences = set()
    merged_sentences = []

    for summary in chunk_summaries:
        sentences = re.split(r"(?<=[.!?])\s+", summary.strip())
        for s in sentences:
            cleaned = s.strip()
            if cleaned and cleaned.lower() not in seen_sentences:
                seen_sentences.add(cleaned.lower())
                merged_sentences.append(cleaned)

    return " ".join(merged_sentences)
