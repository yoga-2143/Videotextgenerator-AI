import os
import re
import time
import uuid
import logging
import html
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

logger = logging.getLogger(__name__)
YOUTUBE_ID_PATTERNS = [
    r"(?:youtube\.com\/watch\?.*v=)([\w-]{11})",
    r"(?:youtu\.be\/)([\w-]{11})",
    r"(?:youtube\.com\/shorts\/)([\w-]{11})",
    r"(?:youtube\.com\/embed\/)([\w-]{11})",
]

WHISPER_FALLBACK_ENABLED = os.getenv("WHISPER_FALLBACK_ENABLED", "true").lower() == "true"
_FALLBACK_ELIGIBLE_CODES = {"TRANSCRIPT_UNAVAILABLE", "NO_TRANSCRIPT", "TRANSCRIPT_DISABLED", "TRANSCRIPT_FETCH_FAILED", "TRANSCRIPT_FETCH_TIMEOUT"}


class TranscriptError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def log_provider_call(request_id: str, video_id: str, provider_name: str, operation_name: str, attempt: int, elapsed_ms: float, status_code: int, error_code: str = None):
    err_str = f" | Error={error_code}" if error_code else ""
    logger.info(
        f"[PROVIDER_METRICS] ReqID={request_id[:8]} | Video={video_id} | Provider={provider_name} | "
        f"Op={operation_name} | Attempt={attempt} | Time={elapsed_ms}ms | Status={status_code}{err_str}"
    )


def extract_video_id(url: str) -> str:
    logger.info("[URL] validation started")
    if not url or not isinstance(url, str):
        logger.warning("[URL] validation failed: missing or non-string URL")
        raise TranscriptError("INVALID_URL", "Please enter a valid YouTube URL.")
    url = url.strip()

    if "..." in url:
        logger.warning("[URL] validation failed: truncated URL")
        raise TranscriptError("INVALID_URL", "Please enter a complete YouTube URL (e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ).")

    if re.match(r"^[\w-]{11}$", url):
        logger.info("[URL] validation success")
        return url

    patterns = [
        r"(?:v=|\/v\/|\/embed\/|\/shorts\/|youtu\.be\/)([\w-]{11})",
        r"(?:youtube\.com\/watch\?.*v=)([\w-]{11})",
        r"(?:youtube\.com\/shorts\/)([\w-]{11})",
        r"(?:youtube\.com\/embed\/)([\w-]{11})",
        r"(?:youtu\.be\/)([\w-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            logger.info("[URL] validation success")
            return match.group(1)

    logger.warning("[URL] validation failed: invalid YouTube URL format")
    raise TranscriptError("INVALID_URL", "Invalid YouTube URL format. Please paste a valid link (e.g. https://www.youtube.com/watch?v=dQw4w9WgXcQ).")


def _get_configured_session():
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


def fetch_direct_innertube_captions(video_id: str, session=None):
    """Fallback extractor that parses captionTracks directly from YouTube video page HTML."""
    import requests, re, json, xml.etree.ElementTree as ET
    s = session or _get_configured_session()
    try:
        r = s.get(f"https://www.youtube.com/watch?v={video_id}", timeout=15)
        if r.status_code != 200:
            return None, None
        match = re.search(r'"captionTracks":\s*(\[.*?\])', r.text)
        if not match:
            return None, None
        tracks = json.loads(match.group(1))
        if not tracks:
            return None, None
        track = tracks[0]
        for t in tracks:
            if t.get("languageCode", "").startswith("en"):
                track = t
                break
        base_url = track.get("baseUrl")
        lang = track.get("languageCode", "en")
        if not base_url:
            return None, None
        r_xml = s.get(base_url, timeout=15)
        if r_xml.status_code == 200 and r_xml.text.strip():
            root = ET.fromstring(r_xml.text)
            chunks = [t.text.strip() for t in root.findall(".//text") if t.text and t.text.strip()]
            full_text = " ".join(chunks)
            if full_text:
                return full_text, lang
    except Exception as e:
        logger.debug(f"[INNER_TUBE_CAPTIONS_NOTE] Direct HTML extraction note for {video_id}: {e}")
    return None, None


def fetch_transcript(video_id: str, request_id: str = None, timeout_seconds: int = 45):
    """Returns (raw_text, detected_language_code).
    Single-pass transcript list extraction with structured provider metrics, rate limit protection, and timeout control."""
    import concurrent.futures

    def _internal_fetch():
        req_id = request_id or str(uuid.uuid4())
        t0 = time.time()
        attempt = 1

        logger.info(f"[TRANSCRIPT_LOOKUP_STARTED] JobID={req_id[:8]} | VideoID={video_id}")

        session = _get_configured_session()

        # Pass 1: Direct ytt.fetch call with browser session
        try:
            ytt_direct = YouTubeTranscriptApi(http_client=session)
            if hasattr(ytt_direct, "fetch"):
                res_direct = ytt_direct.fetch(video_id, languages=("en", "en-US", "en-GB", "de", "es", "fr", "hi", "ta", "ja"))
                snippets = [getattr(c, "text", str(c)).strip() for c in res_direct if hasattr(c, "text") and getattr(c, "text", "").strip()]
                if snippets:
                    text = " ".join(snippets)
                    lang = getattr(res_direct, "language_code", "en")
                    logger.info(f"[CAPTIONS_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Language={lang} (ytt_direct_fetch)")
                    return text, lang
        except (VideoUnavailable, TranscriptsDisabled, NoTranscriptFound) as known_err:
            pass
        except Exception as direct_err:
            logger.debug(f"[TRANSCRIPT] Direct fetch note for {video_id}: {direct_err}")

        # Pass 2: List transcripts with browser session
        transcript_list = None
        try:
            if hasattr(YouTubeTranscriptApi, "list_transcripts"):
                list_func = getattr(YouTubeTranscriptApi, "list_transcripts")
                try:
                    transcript_list = list_func(video_id)
                except TypeError:
                    ytt = YouTubeTranscriptApi(http_client=session)
                    transcript_list = ytt.list(video_id)
            else:
                ytt = YouTubeTranscriptApi(http_client=session)
                transcript_list = ytt.list(video_id)

            elapsed = round((time.time() - t0) * 1000, 2)
            log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 200)
        except VideoUnavailable as e:
            elapsed = round((time.time() - t0) * 1000, 2)
            err_str = str(e).lower()
            if "private" in err_str:
                log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 403, "VIDEO_PRIVATE")
                logger.warning(f"[CAPTIONS_NOT_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Code=VIDEO_PRIVATE | Message={e}")
                raise TranscriptError("VIDEO_PRIVATE", "This video is private and cannot be processed.")
            log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 404, "VIDEO_UNAVAILABLE")
            logger.warning(f"[CAPTIONS_NOT_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Code=VIDEO_UNAVAILABLE | Message={e}")
            raise TranscriptError("VIDEO_UNAVAILABLE", "This YouTube video is unavailable, deleted, or does not exist.")
        except TranscriptsDisabled as e:
            elapsed = round((time.time() - t0) * 1000, 2)
            log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 422, "TRANSCRIPT_DISABLED")
            logger.warning(f"[CAPTIONS_NOT_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Code=TRANSCRIPT_DISABLED | Message={e}")
            raise TranscriptError("TRANSCRIPT_UNAVAILABLE", "No transcript was available, and audio transcription could not be completed.")
        except NoTranscriptFound as e:
            elapsed = round((time.time() - t0) * 1000, 2)
            log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 422, "NO_TRANSCRIPT")
            logger.warning(f"[CAPTIONS_NOT_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Code=NO_TRANSCRIPT | Message={e}")
            raise TranscriptError("TRANSCRIPT_UNAVAILABLE", "No transcript was available, and audio transcription could not be completed.")
        except Exception as e:
            elapsed = round((time.time() - t0) * 1000, 2)
            err_str = str(e).lower()
            err_type = type(e).__name__
            logger.warning(f"[CAPTIONS_NOT_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Code={err_type} | Message={e}")

            if "private video" in err_str or "this video is private" in err_str:
                log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 403, "VIDEO_PRIVATE")
                raise TranscriptError("VIDEO_PRIVATE", "This video is private and cannot be processed.")
            if any(kw in err_str for kw in ["confirm your age", "age-gated", "sign in to confirm your age", "confirm you're not a bot"]):
                log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 403, "BOT_PROTECTION_BLOCKED")
                raise TranscriptError("BOT_PROTECTION_BLOCKED", "YouTube anti-bot verification is active for this video on cloud server. Please try again or paste transcript text.")
            if any(kw in err_str for kw in ["requestblocked", "429", "too many requests", "bot", "captcha", "ip has been blocked"]):
                log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 429, "BOT_PROTECTION_BLOCKED")
                raise TranscriptError("BOT_PROTECTION_BLOCKED", "YouTube anti-bot verification is active for this video on cloud server. Please try again or paste transcript text.")
            if any(kw in err_str for kw in ["unavailable", "404", "does not exist", "not found"]):
                log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 404, "VIDEO_UNAVAILABLE")
                raise TranscriptError("VIDEO_UNAVAILABLE", "This YouTube video is unavailable, deleted, or does not exist.")

            log_provider_call(req_id, video_id, "youtube_transcript_api", "list_transcripts", attempt, elapsed, 500, err_type)

        # Multi-stage caption discovery if transcript_list was obtained
        transcript = None
        if transcript_list:
            try:
                transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"])
            except Exception:
                pass

            if not transcript:
                try:
                    for t in transcript_list:
                        if not getattr(t, "is_generated", False):
                            transcript = t
                            break
                except Exception:
                    pass

            if not transcript:
                try:
                    transcript = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"])
                except Exception:
                    pass

            if not transcript:
                try:
                    for t in transcript_list:
                        if getattr(t, "is_generated", False):
                            transcript = t
                            break
                except Exception:
                    pass

            if not transcript:
                manual_map = getattr(transcript_list, "_manually_created_transcripts", {})
                if manual_map:
                    transcript = next(iter(manual_map.values()), None)

            if not transcript:
                generated_map = getattr(transcript_list, "_generated_transcripts", {})
                if generated_map:
                    transcript = next(iter(generated_map.values()), None)

            if not transcript:
                try:
                    for t in transcript_list:
                        transcript = t
                        break
                except Exception:
                    pass

        if transcript:
            t0_fetch = time.time()
            try:
                data = transcript.fetch()
                elapsed_fetch = round((time.time() - t0_fetch) * 1000, 2)
                log_provider_call(req_id, video_id, "youtube_transcript_api", "fetch_chunks", 1, elapsed_fetch, 200)

                chunks = []
                for chunk in data:
                    txt = (chunk.get("text", "") if isinstance(chunk, dict) else getattr(chunk, "text", "")).strip()
                    if txt:
                        chunks.append(txt)
                text = " ".join(chunks)
                if text:
                    lang = getattr(transcript, "language_code", "en")
                    logger.info(f"[CAPTIONS_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Language={lang}")
                    return text, lang
            except Exception as e:
                elapsed_fetch = round((time.time() - t0_fetch) * 1000, 2)
                err_str = str(e).lower()
                log_provider_call(req_id, video_id, "youtube_transcript_api", "fetch_chunks", 1, elapsed_fetch, 500, type(e).__name__)
                logger.warning(f"[CAPTIONS_NOT_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Code=FETCH_CHUNKS_FAILED | Message={e}")
                if any(kw in err_str for kw in ["confirm your age", "age-gated", "sign in to confirm", "bot", "429", "requestblocked"]):
                    raise TranscriptError("BOT_PROTECTION_BLOCKED", "YouTube anti-bot verification is active for this video on cloud server. Please try again or paste transcript text.")

        # Pass 3: Direct InnerTube HTML caption parsing fallback
        html_text, html_lang = fetch_direct_innertube_captions(video_id, session=session)
        if html_text:
            logger.info(f"[CAPTIONS_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Language={html_lang} (direct_innertube_html)")
            return html_text, html_lang

        logger.warning(f"[CAPTIONS_NOT_FOUND] JobID={req_id[:8]} | VideoID={video_id} | Code=NO_MATCHING_TRACK")
        raise TranscriptError("TRANSCRIPT_UNAVAILABLE", "No transcript was available, and audio transcription could not be completed.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_internal_fetch)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            logger.warning(f"[CAPTIONS_NOT_FOUND] JobID={(request_id or 'unknown')[:8]} | VideoID={video_id} | Code=TRANSCRIPT_FETCH_TIMEOUT")
            raise TranscriptError("TRANSCRIPT_FETCH_TIMEOUT", "Retrieving captions timed out. Processing audio fallback.")


def get_transcript_result(video_id: str, request_id: str = None, on_audio_fallback=None, on_whisper_transcribe=None, on_progress=None):
    from app.services.transcript_providers import TranscriptProviderChain, TranscriptResult
    chain = TranscriptProviderChain()
    return chain.execute(video_id, request_id, on_audio_fallback, on_whisper_transcribe, on_progress)


def get_transcript(video_id: str, request_id: str = None, on_audio_fallback=None, on_whisper_transcribe=None, on_progress=None):
    """Primary entry point used by the video-processing route.
    Delegates to TranscriptProviderChain to try YouTube captions, alternative APIs, and Whisper fallback."""
    res = get_transcript_result(video_id, request_id, on_audio_fallback, on_whisper_transcribe, on_progress)
    if callable(on_progress):
        try:
            on_progress(85, "Transcript completed")
        except Exception:
            pass
    return res.transcript_text, res.source_language, res.source


from app.services.error_validator import contains_raw_error_text

PROMOTIONAL_PATTERNS = [
    r"\[.*?\]",
    r"\(.*?\)",
    r"♪|♫",
    r"(?i)\b(don't forget to|make sure to|be sure to|remember to|please|smash|hit)\b.*?\b(like|subscribe|share|bell|comment|notification)s?\b[^.!?]*[.!?]?",
    r"(?i)\b(welcome back to|welcome to|thanks for watching|see you in the next|catch you in the next|hope you enjoyed|enjoy the video|see ya next time|bye guys|peace out)\b[^.!?]*[.!?]?",
    r"(?i)\b(hey guys|hi everyone|what's up guys|hello everyone|bye guys|see ya|peace out)\b[,.]?",
    r"(?i)\b(check out the link in the description|link in description|sponsored by|brought to you by|patreon|discord server|follow me on)\b[^.!?]*[.!?]?",
]

SPEECH_NOISE_PATTERNS = [
    r"\b(all right|alright|so yeah|right so|you know|i mean|basically|actually|sort of|kind of|pretty much|you see|as you can see|here we are|so here we are|like i said|as i said|as i mentioned|you know what i mean|without further ado)\b[,.]?",
    r"\b(the cool thing about|cool thing is|that's cool and|and that's cool|and that's pretty much all there is to say|that's pretty much all there is to say|all there is to say)\b[,.]?",
    r"\b(um+h?|uh+h?|hmm+|mhm+|err+|ah+)\b[,.]?",
]


def clean_transcript(raw_text: str) -> str:
    if not raw_text or contains_raw_error_text(raw_text):
        raise TranscriptError("TRANSCRIPT_UNAVAILABLE", "This video does not have an accessible transcript or captions, so it cannot currently be converted to text.")

    # 0. Unescape HTML entities & strip YouTube speaker change markers (>> / >>>)
    text = html.unescape(raw_text)
    text = re.sub(r"(?:^|\n|\s)>>+\s*", " ", text)

    # 1. Remove timestamps like [00:12], (1:23), 04:56
    text = re.sub(r"\[?\b\d{1,2}:\d{2}(:\d{2})?\b\]?", "", text)

    # 2. Remove bracketed & parenthetical noise tags / music notes
    text = re.sub(r"\[.*?\]|\(.*?\)|♪|♫", "", text)

    # 3. Filter promotional phrases & greetings/outros
    for pattern in PROMOTIONAL_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # 4. Remove speech fillers & conversational noise
    for pattern in SPEECH_NOISE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # 5. Remove phrase-level and word-level accidental repetitions ("in order to, in order to" -> "in order to", "the, the" -> "the")
    for _ in range(5):
        t_prev = text
        text = re.sub(r"\b(\w+(?:\s+\w+){1,4})[\s,;:-]+\1\b", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(\w+)[\s,;:-]+(?:\1\b)+", r"\1", text, flags=re.IGNORECASE)
        if text == t_prev:
            break

    # 6. Clean up extra spaces & punctuation artifacts
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r"([,.!?])\1+", r"\1", text)

    # 7. Deduplicate sentences using normalized alphanumeric checking
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    unique_sentences = []
    seen_normalized = set()

    for s in sentences:
        norm = re.sub(r"[^\w\s]", "", s.lower()).strip()
        if norm and norm not in seen_normalized and len(norm) > 2:
            seen_normalized.add(norm)
            unique_sentences.append(s)

    text = " ".join(unique_sentences)

    if contains_raw_error_text(text) or not text.strip():
        raise TranscriptError("TRANSCRIPT_UNAVAILABLE", "This video does not have an accessible transcript or captions, so it cannot currently be converted to text.")
    return text
