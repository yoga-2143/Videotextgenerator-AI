"""
TextRank-based sentence importance ranking — implemented directly (not via a
library that needs downloaded corpora), so setup never requires an extra
'nltk.download(...)' step.

Algorithm, per the spec:
  calculate sentence similarity -> build sentence graph -> importance via
  PageRank -> rank sentences -> select the top N, keeping original order.
"""
import re
import numpy as np
import networkx as nx

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "to", "in",
    "on", "at", "for", "with", "by", "from", "is", "was", "were", "are", "be",
    "been", "being", "this", "that", "these", "those", "it", "its", "as",
    "i", "you", "he", "she", "we", "they", "them", "his", "her", "their",
    "um", "uh", "like", "just", "really", "okay", "yeah", "gonna", "going",
    "have", "has", "had", "do", "does", "did", "will", "would", "can", "could",
    "not", "no", "yes", "there", "here", "what", "which", "who", "how", "why",
}

def _split_sentences(text: str):
    # Simple, dependency-free sentence splitter.
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if len(s.strip()) > 0]


def _tokenize(sentence: str):
    words = re.findall(r"[a-zA-Z']+", sentence.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def _sentence_similarity(words1, words2):
    if not words1 or not words2:
        return 0.0
    vocab = list(set(words1) | set(words2))
    v1 = np.array([words1.count(w) for w in vocab])
    v2 = np.array([words2.count(w) for w in vocab])
    denom = (np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom == 0:
        return 0.0
    return float(np.dot(v1, v2) / denom)


def rank_important_sentences(text: str, sentence_count: int = 25) -> str:
    """Runs TextRank over the transcript and returns the top-ranked sentences,
    preserved in their original order, joined back into text.
    For long videos, uses chunking to preserve context and avoid O(N^2) graph memory bottlenecks."""
    sentences = _split_sentences(text)
    if len(sentences) <= sentence_count:
        return text  # already short enough, nothing to trim

    # For very long transcripts (1-10 hours), sample key sentences uniformly across the timeline to prevent CPU bottlenecks
    if len(sentences) > 300:
        step = len(sentences) / 200.0
        sampled_indices = sorted(list(set([0, len(sentences) - 1] + [int(i * step) for i in range(200)])))
        sentences = [sentences[i] for i in sampled_indices]

    if len(sentences) > 100:
        from app.services.chunker import chunk_transcript, merge_chunk_results
        chunks = chunk_transcript(sentences, max_words_per_chunk=600, overlap_sentences=2)
        chunk_summaries = []
        sentences_per_chunk = max(5, sentence_count // max(1, len(chunks)))
        for chunk_sentences in chunks:
            chunk_text = " ".join(chunk_sentences)
            chunk_summaries.append(rank_important_sentences(chunk_text, sentence_count=sentences_per_chunk))
        merged = merge_chunk_results(chunk_summaries)
        return rank_important_sentences(merged, sentence_count=sentence_count)

    tokenized = [_tokenize(s) for s in sentences]

    n = len(sentences)
    sim_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                sim_matrix[i][j] = _sentence_similarity(tokenized[i], tokenized[j])

    graph = nx.from_numpy_array(sim_matrix)
    try:
        scores = nx.pagerank(graph, max_iter=200)
    except Exception:
        scores = {i: 1.0 for i in range(n)}  # fall back to uniform importance

    ranked_indices = sorted(scores, key=scores.get, reverse=True)[:sentence_count]
    ranked_indices.sort()  # restore original document order

    return " ".join(sentences[i] for i in ranked_indices)
