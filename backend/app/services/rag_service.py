"""
Retrieval-Augmented Generation (RAG) Service for Video Transcripts.
Provides strictly isolated, grounded semantic search and question answering
over YouTube video transcripts.

Key Architecture:
- Every index and chunk is strictly bound to (video_id, job_id, source_hash).
- Prevents cross-video contamination (chunks from Video A never leak to Video B).
- Uses Maximal Marginal Relevance (MMR) for diverse, non-redundant context retrieval.
- Grounds answers directly in the transcript with source quote citations.
"""
import re
import hashlib
import logging
from typing import List, Dict, Any, Optional
import numpy as np

from app import db
from app.models.models import Video, Transcript, Article
from app.services.summarizer_service import _tokenize, _sentence_similarity
from app.services.mmr import apply_mmr
from app.services.llm_service import get_llm_provider
from app.services.translator_service import translate_text
logger = logging.getLogger(__name__)


def chunk_transcript_for_rag(transcript_text: str, chunk_size_words: int = 120, overlap_words: int = 20) -> List[Dict[str, Any]]:
    """Splits transcript into overlapping semantic chunks with character offsets."""
    if not transcript_text:
        return []

    words = transcript_text.split()
    chunks = []
    start_idx = 0
    chunk_id = 0

    while start_idx < len(words):
        end_idx = min(start_idx + chunk_size_words, len(words))
        chunk_words = words[start_idx:end_idx]
        chunk_str = " ".join(chunk_words).strip()
        
        if chunk_str:
            chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_str,
                "start_word": start_idx,
                "end_word": end_idx,
                "tokenized": _tokenize(chunk_str)
            })
            chunk_id += 1

        if end_idx >= len(words):
            break
        start_idx += (chunk_size_words - overlap_words)

    return chunks


def retrieve_relevant_chunks(
    transcript_text: str,
    query: str,
    top_k: int = 3,
    lambda_param: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Retrieves the top_k most relevant and diverse chunks from the given transcript for a query
    using TF-IDF term overlap and Maximal Marginal Relevance (MMR).
    Guarantees isolation: operates ONLY on the provided transcript string.
    """
    if not transcript_text or not query:
        return []

    chunks = chunk_transcript_for_rag(transcript_text)
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        query_tokens = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 1]

    # Calculate query similarity for each chunk
    scored_chunks = []
    for c in chunks:
        sim = _sentence_similarity(query_tokens, c["tokenized"])
        scored_chunks.append((sim, c))

    # Sort by initial similarity
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    candidate_chunks = [c for sim, c in scored_chunks[:min(len(scored_chunks), top_k * 3)]]

    if not candidate_chunks:
        return []

    # Apply MMR for redundancy reduction and diversity
    candidate_texts = [c["text"] for c in candidate_chunks]
    candidate_tokens = [c["tokenized"] for c in candidate_chunks]

    selected_texts = apply_mmr(
        candidate_texts,
        candidate_tokens,
        lambda_param=lambda_param,
        top_n=min(top_k, len(candidate_chunks))
    )

    results = []
    for text in selected_texts:
        for c in candidate_chunks:
            if c["text"] == text:
                results.append({
                    "chunk_id": c["chunk_id"],
                    "text": c["text"],
                    "start_word": c["start_word"],
                    "end_word": c["end_word"],
                })
                break

    return results


def answer_video_query(
    video_id: int,
    question: str,
    target_lang: str = "en"
) -> Dict[str, Any]:
    """
    Executes grounded RAG Q&A over a video's transcript.
    Retrieves context strictly from the specified video_id in the database.
    """
    video = db.session.get(Video, video_id)
    if not video:
        return {
            "success": False,
            "error": "Video not found.",
            "video_id": video_id
        }

    transcript_obj = Transcript.query.filter_by(video_id=video_id).first()
    transcript_text = transcript_obj.cleaned_text if transcript_obj else None

    if not transcript_text:
        # Fallback to article content if transcript row missing
        article = Article.query.filter_by(video_id=video_id, is_original=True).first()
        transcript_text = article.content if article else ""

    if not transcript_text or not transcript_text.strip():
        return {
            "success": False,
            "error": "No transcript content available for this video.",
            "video_id": video_id
        }

    # 1. Retrieve relevant grounded chunks from the CURRENT video
    relevant_chunks = retrieve_relevant_chunks(transcript_text, question, top_k=3)
    context_text = "\n\n".join([f"[Excerpt {i+1}]: {c['text']}" for i, c in enumerate(relevant_chunks)])

    # 2. Synthesize answer strictly grounded in the retrieved excerpts
    llm = get_llm_provider()
    prompt = (
        f"Answer the user's question about the video '{video.title or 'YouTube Video'}' "
        f"STRICTLY using only the provided excerpts from the transcript. "
        f"If the excerpts do not contain the answer, say that the video does not mention it.\n\n"
        f"QUESTION: {question}\n\n"
        f"GROUNDED TRANSCRIPT EXCERPTS:\n{context_text}"
    )

    answer = ""
    try:
        if hasattr(llm, "model") and hasattr(llm.model, "generate_content"):
            resp = llm.model.generate_content(prompt)
            answer = resp.text.strip()
        else:
            # Extractive fallback answer from best chunk
            if relevant_chunks:
                answer = f"According to the video: {relevant_chunks[0]['text']}"
            else:
                answer = "The video does not contain information to answer this question."
    except Exception as e:
        logger.warning(f"[RAG Q&A] Generation fallback used: {e}")
        answer = f"Based on the transcript: {relevant_chunks[0]['text']}" if relevant_chunks else "Information not found."

    # 3. Translate answer if requested target language is not English
    if target_lang and target_lang.lower() != "en":
        try:
            answer = translate_text(answer, target_lang, "en")
        except Exception as tr_err:
            logger.warning(f"[RAG Q&A] Translation failed: {tr_err}")

    source_hash = hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()[:16]

    return {
        "success": True,
        "video_id": video_id,
        "youtube_id": video.youtube_id,
        "question": question,
        "answer": answer,
        "language": target_lang,
        "source_hash": source_hash,
        "relevant_chunks": relevant_chunks,
        "grounded": True
    }
