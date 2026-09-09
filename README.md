# VETRI — VideoTextGenerator

A fast, reliable, user-friendly Video-to-Text, Translation, and Voice Platform.

YouTube URL → URL Validation → Caption Retrieval / Whisper STT Fallback → Two-Stage Cleanup → Important Content Extraction → Final Proofreading → Saved in History → 58-Language Translation → Voice Audio / Dubbing

---

## 1. System Architecture Flow

```
PUBLIC YOUTUBE URL
        ↓
Validate URL & Format
        ↓
Extract YouTube Captions if available
        ↓
Fallback to Audio Extraction + local faster-whisper STT
        ↓
Stage A: Fast Chunk Cleanup (Remove fillers, obvious noise, & duplicate words)
        ↓
Stage B: Final Full-Context Validation & Terminology Correction
        ↓
Extract Important Content (Preserves main ideas, steps, explanations, & code)
        ↓
Show text quickly to the user (Non-blocking async job workflow)
        ↓
Proofreading Pass & Honest QA Checklist Badging
        ↓
Save results and job status in History (SQLAlchemy Transaction Safe)
        ↓
Translate into 58 dual-capability languages (Google Translate / NLLB-200)
        ↓
Generate Voice Audio (gTTS / Meta SeamlessM4T dubbing fallback)
```

---

## 2. Infinite Spinner Prevention & Job Status Architecture

- **No Infinite Spinner**: Processing is powered by an asynchronous job workflow (`POST /api/jobs/process` + `GET /api/jobs/<job_id>`).
- **Live Progress & Stage Updates**: The frontend polls job status every 1.5 seconds and renders live stage messages and progress percentage (0–100%):
  - `queued` (5%) — Job queued for processing
  - `validating` (10%) — Validating YouTube URL
  - `fetching_transcript` (25%) — Retrieving captions from YouTube
  - `extracting_audio` (35%) — Extracting video audio
  - `transcribing` (50%) — Converting audio to text using Whisper
  - `cleaning` (65%) — Cleaning raw transcript and removing noise
  - `generating_content` (80%) — Synthesizing clean prose and important content
  - `validating_output` (90%) — Performing final proofreading
  - `saving` (95%) — Saving results to database
  - `completed` (100%) — Results available immediately!
- **Structured Error Handling**: Every failure returns a clear, user-friendly JSON error:
  ```json
  {
    "success": false,
    "error": {
      "code": "TRANSCRIPT_UNAVAILABLE",
      "message": "This video does not have an accessible transcript or captions.",
      "retryable": true
    }
  }
  ```
- **Retry & Cancellation**: The UI provides a Retry button on failure and allows cancelling long requests.

---

## 3. High-Quality Two-Stage Transcript Cleanup

- **Stage A: Fast Cleanup**: Processes chunks with rolling context overlap to remove filler speech ("um", "uh", "you know"), repeated words, and restore sentence boundaries without aggressive summarization.
- **Stage B: Final Full-Context Validation**: Reprocesses complete transcript with full context.
- **Context-Aware Terminology Correction**:
  - `"Pigma"` → `"Figma"` (ONLY when surrounding context refers to design software).
  - `"idex html"` / `"idx.html"` → `"index.html"` (ONLY when HTML context is present).
  - `"pangali"` → `"Patanjali"` (ONLY when Yoga philosophy context is confirmed).
  - `"samadi"` → `"Samadhi"` (ONLY when Yoga context is supported).
  - *No Hallucinations*: If confidence is insufficient, original wording is preserved or `[unclear]` is used.

---

## 4. Important Content Output

Extracts a separate **IMPORTANT CONTENT** result preserving:
- Main topic and core ideas
- Technical concepts and definitions
- Important explanations and steps
- Actionable conclusions and code snippets

---

## 5. Honest QA Checklist Badges

| Badge | Heuristic | Condition |
|---|---|---|
| **Meaning Checked** | Jaccard vocabulary overlap against source | ≥ 40% overlap |
| **Low Repetition** | Sentence-level exact and near-duplicate scan | 0 duplicate sentences |
| **Proofread** | Contextual spelling & grammar pass | Completed |
| **Readability Checked** | Flesch Reading Ease & structural length | Calculated Score & Level |

---

## 6. Supported 58 Languages & Translation Fallback

Supports **58 explicitly configured dual-capability languages** (Text Translation + Voice Audio):

- **Primary Translation Engine**: Google Translate multi-layer HTTP endpoints (`client=dict-chrome-ex`, `client=gtx`, `deep-translator`).
- **Optional Advanced Engine**: Meta NLLB-200 (`facebook/nllb-200-distilled-600M`) when `ENABLE_NLLB=true`.
- **Database Caching**: Saved in `translation_cache` table by `(article_id, target_language, content_hash)` to prevent duplicate network calls.
- **Searchable Dropdown**: Filterable UI component with clear "Text + Voice" vs "Text Only" indicators.

---

## 7. Voice Audio & Meta SeamlessM4T Dubbing

- **Decoupled TTS Failure Handling**: If voice generation fails, clean text remains fully accessible. The UI displays `"Voice generation failed. Original content is preserved."` with a Retry button.
- **Voice Engine**: `gTTS` (Google Translate TTS) fallback or Meta `SeamlessM4T` advanced dubbing.
- **Meta SeamlessM4T Dubbing**: Optional engine configured via environment flags (`DUBBING_ENGINE=seamless_m4t`, `ENABLE_SEAMLESS_M4T=true`).
- **Dubbing Source**: Tracked via `dubbing_source` DB field (`seamless_m4t`, `gtts_fallback`, `none`).

---

## 8. Hardware & Environment Configuration

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` / `DB_NAME` | `vetri_db` | SQLite or MySQL connection URI |
| `SECRET_KEY` | `random_secret` | Flask app session secret |
| `GEMINI_API_KEY` | *(Optional)* | Gemini 1.5 Flash API key for polished prose & proofreading |
| `WHISPER_FALLBACK_ENABLED` | `true` | Enables local OpenAI Whisper STT fallback |
| `WHISPER_MODEL_SIZE` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`) |
| `WHISPER_DEVICE` | `cpu` | Execution target (`cpu` or `cuda`) |
| `ENABLE_NLLB` | `false` | Enables Meta NLLB-200 translation |
| `ENABLE_SEAMLESS_M4T` | `false` | Enables Meta SeamlessM4T dubbing |
| `DUBBING_ENGINE` | `gtts_fallback` | Dubbing engine (`gtts_fallback` or `seamless_m4t`) |

---

## 9. Setup & Running Instructions

### Backend (Python / Flask)
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows PowerShell/CMD
pip install -r requirements.txt
copy .env.example .env
python run.py
```

### Frontend (React / Vite)
```bash
cd frontend
npm install
npm run dev
```

### Run Automated Tests
```bash
cd backend
pytest
```
