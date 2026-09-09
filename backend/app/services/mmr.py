"""
Maximal Marginal Relevance (MMR) Redundancy Reduction Module.
Used after TextRank sentence scoring to eliminate repetitive/duplicate sentences while preserving diverse information.
"""
import numpy as np


def _cosine_similarity(words1, words2):
    if not words1 or not words2:
        return 0.0
    vocab = list(set(words1) | set(words2))
    v1 = np.array([words1.count(w) for w in vocab])
    v2 = np.array([words2.count(w) for w in vocab])
    denom = (np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom == 0:
        return 0.0
    return float(np.dot(v1, v2) / denom)


def apply_mmr(sentences: list, tokenized_sentences: list, lambda_param: float = 0.6, top_n: int = 15) -> list:
    """
    Selects top_n sentences using Maximal Marginal Relevance.
    lambda_param: 1.0 focuses purely on relevance to document, 0.0 focuses purely on diversity.
    0.6 balances relevance and redundancy reduction.
    """
    if len(sentences) <= top_n:
        return sentences

    selected_indices = []
    unselected_indices = list(range(len(sentences)))

    # Compute overall document representation vector (centroid)
    all_words = []
    for words in tokenized_sentences:
        all_words.extend(words)

    # First sentence is the one most similar to document centroid
    doc_sims = [_cosine_similarity(words, all_words) for words in tokenized_sentences]
    first_idx = int(np.argmax(doc_sims))
    selected_indices.append(first_idx)
    unselected_indices.remove(first_idx)

    while len(selected_indices) < top_n and unselected_indices:
        mmr_scores = {}
        for idx in unselected_indices:
            # Relevance to document
            sim1 = doc_sims[idx]
            # Max similarity to already selected sentences
            sim2 = max(_cosine_similarity(tokenized_sentences[idx], tokenized_sentences[s_idx]) for s_idx in selected_indices)
            mmr_score = lambda_param * sim1 - (1 - lambda_param) * sim2
            mmr_scores[idx] = mmr_score

        best_idx = max(mmr_scores, key=mmr_scores.get)
        selected_indices.append(best_idx)
        unselected_indices.remove(best_idx)

    selected_indices.sort()  # Preserve original chronological transcript order
    return [sentences[i] for i in selected_indices]
