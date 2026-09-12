import os
import re
import time
import uuid
import hashlib
import logging
import requests
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TranscriptResult:
    video_id: str
    source: str  # "captions", "alternative_api", "whisper", "client_provided"
    source_language: str
    transcript_text: str
    source_text_hash: str = ""
    confidence: float = 1.0
    validation_info: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.source_text_hash and self.transcript_text:
            self.source_text_hash = hashlib.sha256(self.transcript_text.encode("utf-8")).hexdigest()
        w_count = len((self.transcript_text or "").split())
        c_count = len(self.transcript_text or "")
        self.validation_info.update({
            "word_count": w_count,
            "char_count": c_count,
            "hash": self.source_text_hash[:16],
            "valid": bool(w_count >= 10 and self.video_id)
        })


def validate_transcript(result: TranscriptResult, expected_video_id: str) -> bool:
    """Strict validation rules to ensure transcript belongs to requested video_id and is valid."""
    if not result:
        return False
    if result.video_id != expected_video_id:
        logger.error(f"[VALIDATION_FAIL] VideoID mismatch! Expected={expected_video_id}, Received={result.video_id}")
        return False
    if not result.transcript_text or not isinstance(result.transcript_text, str):
        logger.error(f"[VALIDATION_FAIL] Empty or invalid transcript_text type for video {expected_video_id}")
        return False

    text = result.transcript_text.strip()
    words = text.split()
    if len(words) < 1:
        logger.error(f"[VALIDATION_FAIL] Empty transcript for video {expected_video_id}")
        return False

    # Check for raw error snippets or bot protection messages in transcript content
    err_markers = [
        "sign in to confirm",
        "confirm you're not a bot",
        "requestblocked",
        "too many requests",
        "video unavailable",
        "private video",
    ]
    lowered = text.lower()[:300]
    for marker in err_markers:
        if marker in lowered:
            logger.error(f"[VALIDATION_FAIL] Raw error marker '{marker}' found in transcript content for video {expected_video_id}")
            return False

    # Re-verify source_text_hash
    computed_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if result.source_text_hash and result.source_text_hash != computed_hash:
        logger.warning(f"[VALIDATION_WARN] Hash mismatch recalculated for video {expected_video_id}. Updating hash.")
        result.source_text_hash = computed_hash

    return True


class TranscriptProvider(ABC):
    name: str = "base_provider"

    @abstractmethod
    def fetch(self, video_id: str, request_id: Optional[str] = None) -> Optional[TranscriptResult]:
        pass


class YouTubeCaptionProvider(TranscriptProvider):
    name: str = "youtube_captions"

    def fetch(self, video_id: str, request_id: Optional[str] = None) -> Optional[TranscriptResult]:
        req_id = request_id or str(uuid.uuid4())
        logger.info(f"[PROVIDER_ATTEMPT] Provider=youtube_captions | JobID={req_id[:8]} | VideoID={video_id}")
        
        from app.services.transcript_service import fetch_transcript, clean_transcript, TranscriptError
        try:
            raw_text, lang = fetch_transcript(video_id, req_id)
            cleaned = clean_transcript(raw_text)
            if cleaned:
                res = TranscriptResult(
                    video_id=video_id,
                    source="captions",
                    source_language=lang or "en",
                    transcript_text=cleaned,
                    confidence=1.0,
                )
                if validate_transcript(res, video_id):
                    return res
        except TranscriptError as e:
            logger.warning(f"[PROVIDER_FAILED] Provider=youtube_captions | JobID={req_id[:8]} | Code={e.code} | Message={e.message}")
            if e.code in ["VIDEO_PRIVATE", "INVALID_URL", "VIDEO_UNAVAILABLE", "VIDEO_AGE_RESTRICTED", "BOT_PROTECTION_BLOCKED", "PROVIDER_RATE_LIMIT"]:
                raise e
        except Exception as e:
            logger.warning(f"[PROVIDER_FAILED] Provider=youtube_captions | JobID={req_id[:8]} | Exception={e}")

        return None


class AlternativeTranscriptProvider(TranscriptProvider):
    """Integrates third-party YouTube transcript services (Supadata API, RapidAPI, microservice proxy, or public timedtext proxy)."""
    name: str = "alternative_api"

    def __init__(self):
        self.supadata_api_key = os.getenv("SUPADATA_API_KEY", "").strip()
        self.alternative_api_url = os.getenv("ALTERNATIVE_TRANSCRIPT_API_URL", "").strip()
        self.proxy_url = os.getenv("YOUTUBE_TRANSCRIPT_PROXY_URL", "").strip()

    def is_available(self) -> bool:
        return True

    def fetch(self, video_id: str, request_id: Optional[str] = None) -> Optional[TranscriptResult]:
        req_id = request_id or str(uuid.uuid4())
        logger.info(f"[PROVIDER_ATTEMPT] Provider=alternative_api | JobID={req_id[:8]} | VideoID={video_id}")

        # Option A: Supadata API (https://api.supadata.ai/v1/youtube/transcript)
        if self.supadata_api_key:
            try:
                url = f"https://api.supadata.ai/v1/youtube/transcript?videoId={video_id}"
                headers = {"x-api-key": self.supadata_api_key, "User-Agent": "VETRI/1.0"}
                r = requests.get(url, headers=headers, timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    chunks = []
                    lang = data.get("lang") or data.get("language") or "en"
                    content = data.get("content") or data.get("transcript") or []
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                chunks.append(item["text"])
                            elif isinstance(item, str):
                                chunks.append(item)
                    elif isinstance(content, str):
                        chunks.append(content)

                    raw_text = " ".join(chunks).strip()
                    if raw_text:
                        from app.services.transcript_service import clean_transcript
                        cleaned = clean_transcript(raw_text)
                        res = TranscriptResult(
                            video_id=video_id,
                            source="alternative_api",
                            source_language=lang,
                            transcript_text=cleaned,
                            confidence=0.95,
                        )
                        if validate_transcript(res, video_id):
                            logger.info(f"[PROVIDER_SUCCESS] Provider=alternative_api (Supadata) | JobID={req_id[:8]} | VideoID={video_id}")
                            return res
            except Exception as e:
                logger.warning(f"[PROVIDER_FAILED] Provider=alternative_api (Supadata) | JobID={req_id[:8]} | Error={e}")

        # Option B: Alternative microservice URL
        if self.alternative_api_url:
            try:
                endpoint = f"{self.alternative_api_url.rstrip('/')}/transcript?video_id={video_id}"
                r = requests.get(endpoint, timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    raw_text = data.get("transcript") or data.get("text") or ""
                    lang = data.get("language") or "en"
                    if raw_text:
                        from app.services.transcript_service import clean_transcript
                        cleaned = clean_transcript(raw_text)
                        res = TranscriptResult(
                            video_id=video_id,
                            source="alternative_api",
                            source_language=lang,
                            transcript_text=cleaned,
                            confidence=0.95,
                        )
                        if validate_transcript(res, video_id):
                            logger.info(f"[PROVIDER_SUCCESS] Provider=alternative_api (Microservice) | JobID={req_id[:8]} | VideoID={video_id}")
                            return res
            except Exception as e:
                logger.warning(f"[PROVIDER_FAILED] Provider=alternative_api (Microservice) | JobID={req_id[:8]} | Error={e}")

        # Option C: Public Timedtext Proxy Fallback (bypasses datacenter IP blocks)
        try:
            timedtext_url = f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en"
            proxy_endpoint = f"https://api.allorigins.win/raw?url={requests.utils.quote(timedtext_url)}"
            r = requests.get(proxy_endpoint, timeout=15)
            if r.status_code == 200 and "<text" in r.text:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(r.text)
                chunks = [t.text.strip() for t in root.findall(".//text") if t.text and t.text.strip()]
                raw_text = " ".join(chunks)
                if raw_text:
                    from app.services.transcript_service import clean_transcript
                    cleaned = clean_transcript(raw_text)
                    res = TranscriptResult(
                        video_id=video_id,
                        source="alternative_api",
                        source_language="en",
                        transcript_text=cleaned,
                        confidence=0.95,
                    )
                    if validate_transcript(res, video_id):
                        logger.info(f"[PROVIDER_SUCCESS] Provider=alternative_api (Public Proxy) | JobID={req_id[:8]} | VideoID={video_id}")
                        return res
        except Exception as e:
            logger.warning(f"[PROVIDER_FAILED] Provider=alternative_api (Public Proxy) | JobID={req_id[:8]} | Error={e}")

        return None


class WhisperProvider(TranscriptProvider):
    """Whisper STT audio transcription provider (only used when audio download is possible and succeeds)."""
    name: str = "whisper"

    def __init__(self, on_audio_fallback=None, on_whisper_transcribe=None, on_progress=None):
        self.on_audio_fallback = on_audio_fallback
        self.on_whisper_transcribe = on_whisper_transcribe
        self.on_progress = on_progress

    def fetch(self, video_id: str, request_id: Optional[str] = None) -> Optional[TranscriptResult]:
        req_id = request_id or str(uuid.uuid4())
        logger.info(f"[PROVIDER_ATTEMPT] Provider=whisper | JobID={req_id[:8]} | VideoID={video_id}")

        if callable(self.on_audio_fallback):
            try:
                self.on_audio_fallback()
            except Exception:
                pass

        from app.services.whisper_service import transcribe_with_whisper, WhisperError
        from app.services.transcript_service import clean_transcript, TranscriptError

        try:
            if callable(self.on_whisper_transcribe):
                try:
                    self.on_whisper_transcribe()
                except Exception:
                    pass

            raw_text, lang = transcribe_with_whisper(video_id, request_id=req_id, job_id=req_id, on_progress=self.on_progress)
            cleaned = clean_transcript(raw_text)
            res = TranscriptResult(
                video_id=video_id,
                source="whisper",
                source_language=lang or "en",
                transcript_text=cleaned,
                confidence=0.9,
            )
            if validate_transcript(res, video_id):
                logger.info(f"[PROVIDER_SUCCESS] Provider=whisper | JobID={req_id[:8]} | VideoID={video_id}")
                return res
        except WhisperError as e:
            logger.warning(f"[PROVIDER_FAILED] Provider=whisper | JobID={req_id[:8]} | Code={e.code} | Message={e.message}")
            raise TranscriptError(e.code, e.message)
        except Exception as e:
            logger.exception(f"[PROVIDER_FAILED] Provider=whisper | JobID={req_id[:8]} | Error={e}")
            raise TranscriptError("WHISPER_TRANSCRIPTION_FAILED", "Audio was obtained, but speech transcription failed.")

        return None


class ClientProvidedTranscriptProvider(TranscriptProvider):
    """Integrates client-assisted transcript text provided directly by the frontend browser proxy."""
    name: str = "client_provided"

    def fetch(self, video_id: str, request_id: Optional[str] = None, provided_transcript: Optional[str] = None) -> Optional[TranscriptResult]:
        if not provided_transcript or not provided_transcript.strip():
            return None
        req_id = request_id or str(uuid.uuid4())
        logger.info(f"[PROVIDER_ATTEMPT] Provider=client_provided | JobID={req_id[:8]} | VideoID={video_id}")
        try:
            from app.services.transcript_service import clean_transcript
            cleaned = clean_transcript(provided_transcript)
            if cleaned:
                res = TranscriptResult(
                    video_id=video_id,
                    source="client_provided",
                    source_language="en",
                    transcript_text=cleaned,
                    confidence=0.95,
                )
                if validate_transcript(res, video_id):
                    logger.info(f"[PROVIDER_SUCCESS] Provider=client_provided | JobID={req_id[:8]} | VideoID={video_id}")
                    return res
        except Exception as e:
            logger.warning(f"[PROVIDER_FAILED] Provider=client_provided | JobID={req_id[:8]} | Error={e}")
        return None


class SupadataTranscriptProvider(TranscriptProvider):
    """Primary cloud-safe transcript provider that uses the Supadata YouTube transcript API."""
    name: str = "supadata"

    def __init__(self):
        self.api_key = os.getenv("SUPADATA_API_KEY", "").strip()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def fetch(self, video_id: str, request_id: Optional[str] = None) -> Optional[TranscriptResult]:
        req_id = request_id or str(uuid.uuid4())
        if not self.is_available():
            logger.info(f"[PROVIDER_SKIP] Provider=supadata | Reason=NO_SUPADATA_API_KEY_CONFIGURED")
            return None

        logger.info(f"[PROVIDER_ATTEMPT] Provider=supadata | JobID={req_id[:8]} | VideoID={video_id}")

        try:
            url = f"https://api.supadata.ai/v1/youtube/transcript?videoId={video_id}"
            headers = {"x-api-key": self.api_key, "User-Agent": "VETRI/1.0"}
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                data = r.json()
                chunks = []
                lang = data.get("lang") or data.get("language") or "en"
                content = data.get("content") or data.get("transcript") or []
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            chunks.append(item["text"])
                        elif isinstance(item, str):
                            chunks.append(item)
                elif isinstance(content, str):
                    chunks.append(content)

                raw_text = " ".join(chunks).strip()
                if raw_text:
                    from app.services.transcript_service import clean_transcript
                    cleaned = clean_transcript(raw_text)
                    res = TranscriptResult(
                        video_id=video_id,
                        source="supadata",
                        source_language=lang,
                        transcript_text=cleaned,
                        confidence=0.98,
                    )
                    if validate_transcript(res, video_id):
                        logger.info(f"[PROVIDER_SUCCESS] Provider=supadata | JobID={req_id[:8]} | VideoID={video_id} | Hash={res.source_text_hash[:16]}")
                        return res
            else:
                logger.warning(f"[PROVIDER_FAILED] Provider=supadata | JobID={req_id[:8]} | Status={r.status_code} | Text={r.text[:200]}")
        except Exception as e:
            logger.warning(f"[PROVIDER_FAILED] Provider=supadata | JobID={req_id[:8]} | Error={e}")

        return None


class TranscriptProviderChain:
    """Executes configured transcript providers in exact sequence with structured logging and error isolation."""

    def __init__(self, providers: Optional[List[TranscriptProvider]] = None):
        self.providers = providers or [
            SupadataTranscriptProvider(),
            YouTubeCaptionProvider(),
            ClientProvidedTranscriptProvider(),
            AlternativeTranscriptProvider(),
        ]

    def execute(
        self,
        video_id: str,
        request_id: Optional[str] = None,
        on_audio_fallback=None,
        on_whisper_transcribe=None,
        on_progress=None,
        provided_transcript: Optional[str] = None
    ) -> TranscriptResult:
        req_id = request_id or str(uuid.uuid4())
        logger.info(f"[PROVIDER_CHAIN_STARTED] JobID={req_id[:8]} | VideoID={video_id} | ProviderCount={len(self.providers)}")

        last_error = None

        for provider in self.providers:
            try:
                if provider.name == "client_provided" and provided_transcript:
                    res = provider.fetch(video_id, req_id, provided_transcript=provided_transcript)
                else:
                    res = provider.fetch(video_id, req_id)

                if res and validate_transcript(res, video_id):
                    logger.info(
                        f"[PROVIDER_CHAIN_SUCCESS] JobID={req_id[:8]} | VideoID={video_id} | "
                        f"Provider={provider.name} | Source={res.source} | Hash={res.source_text_hash[:16]}"
                    )
                    return res
            except Exception as e:
                from app.services.transcript_service import TranscriptError
                if isinstance(e, TranscriptError):
                    last_error = e
                    logger.warning(f"[PROVIDER_CHAIN_NOTE] Provider '{provider.name}' failed for video {video_id}: Code={e.code} Message={e.message}")
                    if e.code in ["VIDEO_PRIVATE", "VIDEO_UNAVAILABLE", "INVALID_URL", "VIDEO_AGE_RESTRICTED"]:
                        # Absolute video accessibility failure - stop chain
                        raise e
                else:
                    logger.warning(f"[PROVIDER_CHAIN_NOTE] Provider '{provider.name}' raised unexpected error for video {video_id}: {e}")

        # If captions & alternative providers failed, check if Whisper STT audio fallback should be attempted
        whisper_enabled = os.getenv("WHISPER_FALLBACK_ENABLED", "true").lower() == "true"
        if whisper_enabled:
            try:
                whisper_prov = WhisperProvider(on_audio_fallback, on_whisper_transcribe, on_progress)
                res = whisper_prov.fetch(video_id, req_id)
                if res and validate_transcript(res, video_id):
                    return res
            except Exception as whisper_err:
                from app.services.transcript_service import TranscriptError
                from app.services.error_validator import sanitize_user_error_message
                code = getattr(whisper_err, "code", "TRANSCRIPT_UNAVAILABLE")
                if code in ["VIDEO_PRIVATE", "VIDEO_UNAVAILABLE", "INVALID_URL", "VIDEO_AGE_RESTRICTED"]:
                    raise whisper_err
                clean_msg = sanitize_user_error_message(code, str(whisper_err))
                raise TranscriptError(code, clean_msg)

        # If all transcript providers failed, raise a clean, user-safe error message
        from app.services.transcript_service import TranscriptError
        raise TranscriptError(
            "TRANSCRIPT_UNAVAILABLE",
            "Unable to retrieve a transcript for this video right now. Please try again later."
        )
