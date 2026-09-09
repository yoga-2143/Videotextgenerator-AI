"""
Real-Time Transcript Chunk Processor & Streaming Engine.
High-accuracy, low-latency streaming pipeline supporting Stage 1 (Real-time fast cleanup)
and Stage 2 (Final full-context accuracy pass).

Modes Supported:
- REALTIME: Fast chunk processing with low latency & rolling context window.
- FINAL: Full transcript accuracy validation & complete clean text output.
- TRANSLATE: Multilingual translation of clean text preserving names, terms, code, and URLs.
- TTS_READY: Script formatting optimized for natural voice generation.
- DEBUG: Returns structured JSON metrics for technical diagnostics.
"""
import re
import json
import os
import logging
from typing import Generator, List, Optional, Union, Dict, Any
from app.services.llm_service import clean_speech_sentence, CONTEXT_STT_CORRECTIONS, synthesize_clean_prose

logger = logging.getLogger(__name__)

STAGE1_FAST_REALTIME_PROMPT = """You are a high-speed real-time transcript cleanup engine.

Process incoming speech-to-text chunks immediately and return clean text with minimal latency.

YOUR TASK:
1. Correct only obvious transcription errors when context strongly supports the correction.
2. Fix capitalization, punctuation, spacing, and broken words.
3. Correct technical terms, proper names, filenames, software names, and domain terminology only when confidence is high.
4. Remove meaningless fillers such as "um", "uh", excessive "okay", false starts, and obvious transcription noise.
5. Remove accidental repeated words and repeated phrases.
6. Preserve intentional repetition used for emphasis.
7. Preserve all important meaning.
8. Do NOT summarize.
9. Do NOT invent missing words, facts, names, or explanations.
10. Do NOT guess uncertain words. Keep them unchanged or use [unclear] only when absolutely necessary.
11. Use previous_context to continue incomplete sentences naturally.
12. Compare with recent_output and never repeat text already emitted unless intentionally repeated by the speaker.
13. Keep Tamil, English, Tanglish, technical words, code, filenames, and mixed-language speech accurate.
14. Return output as soon as possible.

IMPORTANT EXAMPLES:
- "பிக்மா" -> "Figma" when context clearly refers to the design tool.
- "இdex hடிml" -> "index.html" when context clearly refers to the HTML entry file.
- "pangali" -> "Patanjali" only when Yoga Sutras context strongly confirms it.
- Never force a correction based only on spelling similarity.

PRIORITY: Speed + Meaning Preservation + High-Confidence Correction.
"""

STAGE2_FINAL_VALIDATION_PROMPT = """You are a final transcript accuracy editor.

You receive the complete transcript after real-time processing.

Your goal is to produce the most accurate, clean, readable version possible while preserving the speaker's original meaning and important information.

TASK:
1. Read the COMPLETE transcript before making corrections.
2. Use full-document context to resolve errors that could not be safely corrected during real-time processing.
3. Correct obvious speech-to-text errors only when the complete context strongly supports the correction.
4. Correct: spelling errors, broken words, capitalization, punctuation, sentence boundaries, technical terminology, proper names, software names, filenames, domain-specific terms.
5. Remove accidental repetitions across the entire transcript.
6. Remove meaningless fillers, false starts, and obvious transcription noise.
7. Preserve meaningful repetition, examples, stories, explanations, arguments, instructions, questions, and answers.
8. Merge fragmented chunks into natural paragraphs.
9. Preserve the original language and mixed-language style unless translation is explicitly requested.
10. Never hallucinate.
11. Never invent missing facts.
12. Never replace an uncertain word with a guessed word.
13. If context is insufficient, preserve the original wording rather than guessing.
14. Do not oversummarize the transcript.

SPECIAL TERMINOLOGY RULE:
Use domain context.
- Pigma -> Figma
- idex.html / index htm -> index.html
- pangali -> Patanjali
- samadi -> Samadhi
- Yoga suas -> Yoga Sutras
NEVER apply these corrections automatically without strong contextual evidence.
"""


class RealTimeChunkProcessor:
    def __init__(self, rolling_window_size: int = 3):
        self.rolling_window_size = rolling_window_size
        self.context_history: List[str] = []
        self.recent_cleaned_output: List[str] = []

    def process_chunk(
        self,
        chunk_text: str,
        mode: str = "REALTIME",
        source_language: str = "en",
        target_language: Optional[str] = None,
        context_override: Optional[str] = None,
        recent_cleaned_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an incoming transcript chunk according to the specified mode.
        """
        if not chunk_text or not isinstance(chunk_text, str):
            if mode == "DEBUG":
                return {
                    "status": "success",
                    "mode": mode,
                    "detected_language": source_language,
                    "cleaned_text": "",
                    "duplicate_detected": False,
                    "uncertain_terms": [],
                    "warnings": ["Empty or invalid input chunk."]
                }
            return {
                "cleaned_text": "",
                "corrected_terms": [],
                "rolling_context": " ".join(self.context_history)
            }

        previous_context = context_override if context_override is not None else " ".join(self.context_history[-self.rolling_window_size:])
        recent_cleaned = recent_cleaned_override if recent_cleaned_override is not None else " ".join(self.recent_cleaned_output[-2:])

        combined = f"{previous_context} {chunk_text}".strip()

        corrections_made = []
        cleaned_chunk = chunk_text
        duplicate_detected = False

        # 1. Context-aware high-confidence evidence-based corrections
        for pattern, repl in CONTEXT_STT_CORRECTIONS:
            if re.search(pattern, combined, flags=re.IGNORECASE):
                if re.search(pattern, cleaned_chunk, flags=re.IGNORECASE):
                    match = re.search(pattern, cleaned_chunk, flags=re.IGNORECASE)
                    orig_matched = match.group(0) if match else ""
                    cleaned_chunk = re.sub(pattern, repl, cleaned_chunk, flags=re.IGNORECASE)
                    if orig_matched and orig_matched != repl:
                        corrections_made.append({"original": orig_matched, "replacement": repl})

        # 2. Single-pass speech cleaning & filler removal
        cleaned_chunk = clean_speech_sentence(cleaned_chunk)

        # 3. Duplicate overlap detection against recent cleaned output
        if recent_cleaned and cleaned_chunk:
            if cleaned_chunk.lower().strip() == recent_cleaned.lower().strip():
                duplicate_detected = True
                cleaned_chunk = ""

        # 4. Handle specific operational modes
        if mode == "TRANSLATE" and target_language and cleaned_chunk:
            from app.services.translator_service import translate_text
            cleaned_chunk = translate_text(cleaned_chunk, target_language, source_lang=source_language)
        elif mode == "TTS_READY" and cleaned_chunk:
            # TTS formatting: ensure clear punctuation, natural sentence boundaries, no fillers
            cleaned_chunk = re.sub(r"\s+", " ", cleaned_chunk).strip()
            if not cleaned_chunk.endswith((".", "!", "?")):
                cleaned_chunk += "."

        # 5. Update rolling history state
        if cleaned_chunk:
            self.context_history.append(cleaned_chunk)
            self.recent_cleaned_output.append(cleaned_chunk)
            if len(self.context_history) > self.rolling_window_size:
                self.context_history = self.context_history[-self.rolling_window_size:]
            if len(self.recent_cleaned_output) > 5:
                self.recent_cleaned_output = self.recent_cleaned_output[-5:]

        if mode == "DEBUG":
            return {
                "status": "success",
                "mode": mode,
                "detected_language": source_language,
                "cleaned_text": cleaned_chunk,
                "duplicate_detected": duplicate_detected,
                "uncertain_terms": [],
                "warnings": []
            }

        return {
            "cleaned_text": cleaned_chunk,
            "corrected_terms": corrections_made,
            "rolling_context": " ".join(self.context_history)
        }

    def process_stage2_final(self, complete_raw_transcript: str, title: str = "") -> str:
        """
        Stage 2 — Final Full-Context Accuracy Pass.
        Runs after complete transcript is accumulated to perform deeper consistency review,
        resolve sentence boundaries across chunks, and produce clean structured text.
        """
        if not complete_raw_transcript:
            return ""
        return synthesize_clean_prose(complete_raw_transcript, title)


def stream_realtime_chunks(chunks: List[str], mode: str = "REALTIME", target_language: Optional[str] = None) -> Generator[str, None, None]:
    """
    Low-latency generator function for streaming processed chunks to clients.
    """
    processor = RealTimeChunkProcessor(rolling_window_size=3)
    for chunk in chunks:
        if not chunk or not chunk.strip():
            continue
        res = processor.process_chunk(chunk, mode=mode, target_language=target_language)
        if mode == "DEBUG":
            yield f"data: {json.dumps(res)}\n\n"
        elif res.get("cleaned_text"):
            yield f"data: {json.dumps({'chunk': res['cleaned_text'], 'corrections': res['corrected_terms']})}\n\n"
