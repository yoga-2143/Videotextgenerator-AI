"""
Whisper fallback transcription.

Used only when YouTube has no usable captions (disabled, missing, or an
unsupported auto-caption language). Runs OpenAI's Whisper model **locally**
via faster-whisper — no API key, no per-request cost, nothing leaves your
machine.
"""
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
import tempfile
import shutil
import logging
import traceback
import threading
from threading import Thread
logger = logging.getLogger(__name__)

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")  # tiny/base/small/medium/large-v3
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")           # auto, cpu, or cuda
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "auto")

_model = None  # pre-warmed singleton instance
_model_device = None
_model_compute_type = None
_model_lock = threading.Lock()


class WhisperError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def _detect_compute_config():
    device = WHISPER_DEVICE.lower().strip()
    compute_type = WHISPER_COMPUTE_TYPE.lower().strip()

    if device == "auto":
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        except Exception:
            device = "cpu"

    if compute_type == "auto":
        if device == "cuda":
            compute_type = "float16"
        else:
            compute_type = "int8"

    return device, compute_type


def _get_model(timeout_seconds: int = 90):
    global _model, _model_device, _model_compute_type
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        t0 = time.time()
        device, compute_type = _detect_compute_config()
        logger.info(f"[WHISPER_MODEL_LOADING_STARTED] Model={WHISPER_MODEL_SIZE} | Device={device} | ComputeType={compute_type}")

        model_res = {"model": None, "error": None}

        def _loader():
            try:
                from faster_whisper import WhisperModel
                num_threads = max(4, os.cpu_count() or 4)
                m = WhisperModel(
                    WHISPER_MODEL_SIZE,
                    device=device,
                    compute_type=compute_type,
                    cpu_threads=num_threads,
                )
                model_res["model"] = m
            except Exception as e:
                model_res["error"] = e

        loader_thread = Thread(target=_loader, name="whisper_model_loader", daemon=True)
        loader_thread.start()
        loader_thread.join(timeout=timeout_seconds)

        t1 = time.time()
        elapsed = round((t1 - t0) * 1000, 2)

        if loader_thread.is_alive():
            logger.error(f"[WHISPER_MODEL_LOADING_FAILED] Duration={elapsed}ms | Error=Timeout after {timeout_seconds}s")
            raise WhisperError("WHISPER_MODEL_TIMEOUT", f"Whisper AI model loading timed out after {timeout_seconds} seconds.")

        if model_res["error"]:
            err_trace = traceback.format_exc()
            logger.error(f"[WHISPER_MODEL_LOADING_FAILED] Duration={elapsed}ms | Error={model_res['error']}\nTraceback:\n{err_trace}")
            raise WhisperError("WHISPER_INIT_FAILED", f"Failed to initialize Whisper model: {model_res['error']}")

        _model = model_res["model"]
        _model_device = device
        _model_compute_type = compute_type
        logger.info(f"[WHISPER_MODEL_LOADING_COMPLETED] Duration={elapsed}ms | Model={WHISPER_MODEL_SIZE} | Device={device}")
        return _model


def prewarm_whisper_model():
    """Pre-warms the Whisper model singleton during backend startup so first-request latency is zero."""
    try:
        def _bg_prewarm():
            try:
                _get_model(timeout_seconds=60)
            except Exception as e:
                logger.warning(f"[WHISPER] model pre-warm background note: {e}")
        Thread(target=_bg_prewarm, name="whisper_prewarm", daemon=True).start()
    except Exception as e:
        logger.warning(f"[WHISPER] model pre-warm skipped or failed: {e}")


def _download_full_audio(video_id: str, workdir: str) -> str:
    import yt_dlp
    t0 = time.time()
    logger.info(f"[AUDIO] extraction started | start_timestamp={t0} | video={video_id}")
    
    out_template = os.path.join(workdir, "audio.%(ext)s")
    ydl_opts = {
        "format": "ba[ext=m4a]/ba[ext=mp3]/worstaudio/worst",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "max_filesize": 500 * 1024 * 1024,
        "nocheckcertificate": True,
        "prefer_insecure": True,
        "geo_bypass": True,
        "concurrent_fragment_downloads": 8,
        "extractor_args": {
            "youtube": {
                "player_client": ["mweb", "android", "ios", "web"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "32",
        }],
        "postprocessor_args": {
            "FFmpegExtractAudio": ["-ac", "1", "-ar", "16000"]
        },
    }

    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        err_str = str(e)
        err_lower = err_str.lower()
        t1 = time.time()
        elapsed = round((t1 - t0) * 1000, 2)
        err_trace = traceback.format_exc()
        logger.warning(f"[AUDIO] ERROR download failed after {elapsed}ms: {err_str}\nTraceback:\n{err_trace}")
        if "private video" in err_lower or "this video is private" in err_lower:
            raise WhisperError("VIDEO_PRIVATE", "This video is private and cannot be processed.")
        if any(kw in err_lower for kw in ["confirm your age", "age-gated", "sign in to confirm your age"]):
            raise WhisperError("VIDEO_AGE_RESTRICTED", "This video has access restrictions.")
        if any(kw in err_lower for kw in ["video unavailable", "404", "does not exist"]):
            raise WhisperError("VIDEO_UNAVAILABLE", "This YouTube video is unavailable, deleted, or does not exist.")
        raise WhisperError("AUDIO_EXTRACTION_FAILED", "Unable to retrieve a transcript for this video right now. Please try again later.")

    expected = os.path.join(workdir, "audio.mp3")
    t1 = time.time()
    elapsed = round((t1 - t0) * 1000, 2)
    if os.path.exists(expected) and os.path.getsize(expected) > 0:
        logger.info(f"[AUDIO] extraction success | end_timestamp={t1} | duration_ms={elapsed} | size={os.path.getsize(expected)}B | file={expected}")
        return expected
    else:
        logger.warning(f"[AUDIO] ERROR failed: extracted file {expected} does not exist or is 0 bytes after {elapsed}ms")
        raise WhisperError("AUDIO_EXTRACTION_FAILED", "Unable to retrieve a transcript for this video right now. Please try again later.")


def transcribe_with_whisper(video_id: str, request_id: str = None, job_id: str = None, on_progress=None):
    """
    Fast single-pass speech-to-text with VAD filtering, greedy decoding,
    dynamic progress updates, and stall detection.
    """
    t_start = time.time()
    req_id = request_id or job_id or "local"

    if not shutil.which("ffmpeg"):
        logger.error("[AUDIO] failed: ffmpeg missing from system path")
        raise WhisperError(
            "FFMPEG_MISSING",
            "ffmpeg is required for Whisper fallback transcription but isn't installed.",
        )

    result_container = {"data": None, "error": None}
    last_progress_time = [time.time()]

    def _worker():
        workdir = tempfile.mkdtemp(prefix="vetri_whisper_")
        try:
            if callable(on_progress):
                on_progress("DOWNLOADING_AUDIO", 30, "Downloading video audio...")

            audio_path = _download_full_audio(video_id, workdir)
            last_progress_time[0] = time.time()

            if callable(on_progress):
                on_progress("LOADING_WHISPER", 45, "Loading Whisper AI speech-to-text model...")

            logger.info(f"[WHISPER_MODEL_LOADING_STARTED] JobID={req_id[:8]} | VideoID={video_id}")
            model = _get_model()
            last_progress_time[0] = time.time()

            t_tr0 = time.time()
            logger.info(f"[WHISPER_TRANSCRIPTION_STARTED] JobID={req_id[:8]} | VideoID={video_id} | Start={t_tr0}")
            # Fast greedy decoding with temperature=0.0 to prevent 6x retries on silence/music windows
            try:
                segments, info = model.transcribe(
                    audio_path,
                    beam_size=1,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    condition_on_previous_text=False,
                    temperature=0.0
                )
            except Exception as vad_err:
                logger.warning(f"[WHISPER] VAD transcribe fallback to vad_filter=False: {vad_err}")
                segments, info = model.transcribe(
                    audio_path,
                    beam_size=1,
                    vad_filter=False,
                    condition_on_previous_text=False,
                    temperature=0.0
                )

            t_tr_ret = time.time()
            last_progress_time[0] = t_tr_ret

            duration_info = info.duration if (info and hasattr(info, "duration")) else 60.0
            detected_language = info.language if (info and hasattr(info, "language")) else "en"
            logger.info(f"[WHISPER] transcribe returned generator | request_id={req_id} | end_timestamp={t_tr_ret} | duration_ms={round((t_tr_ret-t_tr0)*1000, 2)} | audio_duration={duration_info}s")

            # Iterate over lazy segments generator
            t_seg0 = time.time()
            logger.info(f"[WHISPER] segment iteration started | request_id={req_id} | start_timestamp={t_seg0}")
            seg_texts = []
            seg_count = 0

            for seg in segments:
                seg_count += 1
                t_seg_item = time.time()
                last_progress_time[0] = t_seg_item
                txt_item = seg.text.strip() if hasattr(seg, "text") else str(seg).strip()
                if txt_item:
                    seg_texts.append(txt_item)

                if duration_info > 0 and hasattr(seg, "end") and seg.end:
                    pct = min(84, int(55 + (seg.end / duration_info) * 29))
                    msg = f"Transcribing speech to text ({round(seg.end)}s / {round(duration_info)}s)..."
                    if callable(on_progress):
                        on_progress("TRANSCRIBING", pct, msg)

                if seg_count <= 3 or seg_count % 10 == 0:
                    logger.info(f"[WHISPER] processed segment {seg_count} | request_id={req_id} | timestamp={t_seg_item} | snippet='{txt_item[:30]}'")

            # Secondary fallback if VAD yielded 0 segments (e.g. music tracks)
            if not seg_texts:
                logger.info(f"[WHISPER] VAD yielded 0 segments, retrying with vad_filter=False | request_id={req_id}")
                try:
                    segments_fallback, info_fb = model.transcribe(audio_path, beam_size=1, vad_filter=False)
                    for seg in segments_fallback:
                        seg_count += 1
                        t_seg_item = time.time()
                        last_progress_time[0] = t_seg_item
                        txt_item = seg.text.strip() if hasattr(seg, "text") else str(seg).strip()
                        if txt_item:
                            seg_texts.append(txt_item)
                except Exception as fb_err:
                    logger.warning(f"[WHISPER] fallback transcription note: {fb_err}")

            t_seg_end = time.time()
            elapsed_seg = round((t_seg_end - t_seg0) * 1000, 2)
            logger.info(f"[WHISPER] segment iteration completed | request_id={req_id} | end_timestamp={t_seg_end} | total_segments={seg_count} | duration_ms={elapsed_seg}")

            full_text = " ".join(seg_texts).strip()
            if not full_text:
                logger.warning(f"[WHISPER] failed: Audio was obtained, but speech transcription produced no text.")
                result_container["error"] = WhisperError("WHISPER_TRANSCRIPTION_FAILED", "Audio was obtained, but speech transcription produced no usable text.")
                return

            total_elapsed = round((time.time() - t_start) * 1000, 2)
            logger.info(f"[WHISPER_TRANSCRIPTION_COMPLETED] JobID={req_id[:8]} | VideoID={video_id} | Duration={total_elapsed}ms | TextLen={len(full_text)}")

            if callable(on_progress):
                on_progress("CLEANING_TEXT", 85, "Cleaning transcript content...")

            result_container["data"] = (full_text, detected_language)
        except WhisperError as we:
            result_container["error"] = we
        except Exception as e:
            err_trace = traceback.format_exc()
            logger.error(f"[WHISPER] ERROR unexpected failure during worker execution: {e}\nTraceback:\n{err_trace}")
            result_container["error"] = WhisperError("WHISPER_TRANSCRIPTION_FAILED", "Speech transcription failed.")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    worker_thread = Thread(target=_worker, name=f"whisper_tr_{video_id}", daemon=True)
    worker_thread.start()

    # Stall detection loop: monitors progress every 2 seconds
    STALL_TIMEOUT_SECONDS = 300      # 300s without any segment progress update
    MAX_TOTAL_LIMIT_SECONDS = 36000  # 10 hours total cap for ultra-long videos

    while worker_thread.is_alive():
        now = time.time()
        time_since_last_progress = now - last_progress_time[0]
        total_time = now - t_start

        if time_since_last_progress > STALL_TIMEOUT_SECONDS:
            logger.warning(f"[WHISPER] ERROR stalled process detected: no progress for {round(time_since_last_progress, 1)}s for video {video_id}")
            result_container["error"] = WhisperError("WHISPER_TIMEOUT", "Speech-to-text processing took too long. Please try again.")
            break

        if total_time > MAX_TOTAL_LIMIT_SECONDS:
            logger.warning(f"[WHISPER] ERROR total processing limit reached ({round(total_time, 1)}s) for video {video_id}")
            result_container["error"] = WhisperError("WHISPER_LIMIT_EXCEEDED", "Processing limit exceeded for video audio length.")
            break

        worker_thread.join(timeout=2.0)

    if result_container["error"]:
        raise result_container["error"]

    if result_container["data"]:
        return result_container["data"]

    raise WhisperError("WHISPER_TRANSCRIPTION_FAILED", "Whisper transcription ended without returning data.")
