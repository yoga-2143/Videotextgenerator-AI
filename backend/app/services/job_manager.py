"""
Job Manager Service for Video Processing Jobs.
Provides thread-safe async job state tracking, stage metrics, progress (0-100%),
duration logging, and structured result/error handling.
"""
import uuid
import time
import logging
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Dedicated thread pool for async video processing jobs
JOB_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="vetri_job_")

# Thread-safe in-memory store for active and completed video processing jobs
VIDEO_JOBS = {}
JOBS_LOCK = Lock()


class JobStage:
    QUEUED = "QUEUED"
    VALIDATING_URL = "VALIDATING_URL"
    VALIDATING = "VALIDATING_URL"  # Alias
    FETCHING_TRANSCRIPT = "FETCHING_TRANSCRIPT"
    TRANSCRIPT_FOUND = "TRANSCRIPT_FOUND"
    TRANSCRIPT_NOT_AVAILABLE = "TRANSCRIPT_NOT_AVAILABLE"
    DOWNLOADING_AUDIO = "DOWNLOADING_AUDIO"
    PREPARING_AUDIO = "PREPARING_AUDIO"
    EXTRACTING_AUDIO = "PREPARING_AUDIO"  # Alias
    LOADING_WHISPER = "LOADING_WHISPER"
    TRANSCRIBING = "TRANSCRIBING"
    CLEANING_TEXT = "CLEANING_TEXT"
    REMOVING_REPETITION = "REMOVING_REPETITION"
    VALIDATING_TEXT = "VALIDATING_TEXT"
    GENERATING_IMPORTANT_CONTENT = "GENERATING_IMPORTANT_CONTENT"
    GENERATING_CONTENT = "GENERATING_IMPORTANT_CONTENT"  # Alias
    TEXT_READY = "TEXT_READY"
    SAVING = "SAVING"
    TRANSLATING = "TRANSLATING"
    TRANSLATION_PROCESSING = "TRANSLATING"  # Alias
    VALIDATING_TRANSLATION = "VALIDATING_TRANSLATION"
    GENERATING_VOICE = "GENERATING_VOICE"
    VOICE_PROCESSING = "GENERATING_VOICE"  # Alias
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


STAGE_PROGRESS = {
    JobStage.QUEUED: 5,
    JobStage.VALIDATING_URL: 10,
    JobStage.FETCHING_TRANSCRIPT: 20,
    JobStage.TRANSCRIPT_FOUND: 25,
    JobStage.TRANSCRIPT_NOT_AVAILABLE: 25,
    JobStage.DOWNLOADING_AUDIO: 30,
    JobStage.PREPARING_AUDIO: 40,
    JobStage.LOADING_WHISPER: 45,
    JobStage.TRANSCRIBING: 55,
    JobStage.CLEANING_TEXT: 75,
    JobStage.REMOVING_REPETITION: 82,
    JobStage.VALIDATING_TEXT: 88,
    JobStage.GENERATING_IMPORTANT_CONTENT: 92,
    JobStage.TEXT_READY: 95,
    JobStage.SAVING: 98,
    JobStage.COMPLETED: 100,
    JobStage.CANCELLED: 0,
    JobStage.FAILED: 0,
}

STAGE_MESSAGES = {
    JobStage.QUEUED: "Checking YouTube URL...",
    JobStage.VALIDATING_URL: "Checking YouTube URL...",
    JobStage.FETCHING_TRANSCRIPT: "Checking transcript...",
    JobStage.TRANSCRIPT_FOUND: "Transcript found. Preparing text...",
    JobStage.TRANSCRIPT_NOT_AVAILABLE: "Transcript unavailable. Preparing audio fallback...",
    JobStage.DOWNLOADING_AUDIO: "Downloading audio...",
    JobStage.PREPARING_AUDIO: "Preparing audio...",
    JobStage.LOADING_WHISPER: "Loading Whisper AI speech-to-text model...",
    JobStage.TRANSCRIBING: "Transcribing audio...",
    JobStage.CLEANING_TEXT: "Cleaning transcript...",
    JobStage.REMOVING_REPETITION: "Removing repetition...",
    JobStage.VALIDATING_TEXT: "Checking spelling and grammar...",
    JobStage.GENERATING_IMPORTANT_CONTENT: "Preparing IMPORTANT CONTENT...",
    JobStage.TEXT_READY: "Text Ready",
    JobStage.SAVING: "Saving results...",
    JobStage.COMPLETED: "Completed",
    JobStage.CANCELLED: "Job cancelled by user.",
    JobStage.FAILED: "Processing failed.",
}


def log_pipeline_stage(
    stage: str,
    request_id: str = None,
    job_id: str = None,
    start_time: float = None,
    end_time: float = None,
    error: str = None,
    tb: str = None,
    extra: dict = None
) -> dict:
    """Utility to emit and return structured logs with request_id, job_id, stage, start/end timestamps, duration, error, full traceback."""
    now = time.time()
    t0 = start_time if start_time is not None else now
    t1 = end_time if end_time is not None else now
    duration_ms = round((t1 - t0) * 1000, 2)
    duration_sec = round(t1 - t0, 3)

    req_str = str(request_id or job_id or "unknown")
    job_str = str(job_id or request_id or "unknown")

    log_payload = {
        "request_id": req_str,
        "job_id": job_str,
        "stage": stage,
        "start_timestamp": t0,
        "end_timestamp": t1,
        "duration_ms": duration_ms,
        "duration_seconds": duration_sec,
        "error": error,
        "full_traceback": tb,
    }
    if extra:
        log_payload.update(extra)

    err_msg = f" | Error={error}" if error else ""
    tb_msg = f"\nTraceback:\n{tb}" if tb else ""
    logger.info(
        f"[STRUCTURED_STAGE_LOG] Stage={stage} | ReqID={req_str[:8]} | JobID={job_str[:8]} | "
        f"Start={t0:.3f} | End={t1:.3f} | Duration={duration_ms}ms{err_msg}{tb_msg}"
    )
    return log_payload


import json

def _sync_job_to_db(job_data: dict):
    """Safely updates or inserts ProcessingJob database record."""
    try:
        from app import db
        from app.models.models import ProcessingJob
        job_id = job_data.get("job_id")
        if not job_id:
            return
        pj = db.session.get(ProcessingJob, job_id)
        res_json = json.dumps(job_data.get("result")) if job_data.get("result") is not None else None
        err_json = json.dumps(job_data.get("error")) if job_data.get("error") is not None else None
        if not pj:
            pj = ProcessingJob(
                job_id=job_id,
                video_id=job_data.get("video_id"),
                youtube_url=job_data.get("url"),
                status=job_data.get("status", "processing"),
                stage=job_data.get("stage", JobStage.QUEUED),
                progress=job_data.get("progress", 5),
                message=job_data.get("message", ""),
                result_json=res_json,
                error_json=err_json,
                cancelled=job_data.get("cancelled", False),
            )
            db.session.add(pj)
        else:
            if job_data.get("video_id"):
                pj.video_id = job_data.get("video_id")
            if job_data.get("url"):
                pj.youtube_url = job_data.get("url")
            pj.status = job_data.get("status", pj.status)
            pj.stage = job_data.get("stage", pj.stage)
            pj.progress = job_data.get("progress", pj.progress)
            pj.message = job_data.get("message", pj.message)
            if res_json is not None:
                pj.result_json = res_json
            if err_json is not None:
                pj.error_json = err_json
            pj.cancelled = job_data.get("cancelled", pj.cancelled)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.debug(f"[JOB_DB_SYNC_NOTE] Could not sync job {job_data.get('job_id')} to DB: {e}")


def _get_job_from_db(job_id: str) -> dict:
    """Reads ProcessingJob from database to support multi-worker process polling."""
    try:
        from app import db
        from app.models.models import ProcessingJob
        pj = db.session.get(ProcessingJob, job_id)
        if not pj:
            return None
        res_data = json.loads(pj.result_json) if pj.result_json else None
        err_data = json.loads(pj.error_json) if pj.error_json else None
        return {
            "job_id": pj.job_id,
            "video_id": pj.video_id,
            "url": pj.youtube_url,
            "status": pj.status,
            "stage": pj.stage,
            "progress": pj.progress,
            "message": pj.message,
            "result_available": bool(res_data),
            "stage_timings": {},
            "created_at": pj.created_at.timestamp() if pj.created_at else time.time(),
            "updated_at": pj.updated_at.timestamp() if pj.updated_at else time.time(),
            "result": res_data,
            "error": err_data,
            "cancelled": bool(pj.cancelled),
        }
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.debug(f"[JOB_DB_READ_NOTE] Could not read job {job_id} from DB: {e}")
        return None


def create_video_job(url: str, video_id: str) -> str:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now = time.time()
    job_data = {
        "job_id": job_id,
        "video_id": video_id,
        "url": url,
        "status": "processing",
        "stage": JobStage.QUEUED,
        "progress": STAGE_PROGRESS[JobStage.QUEUED],
        "message": STAGE_MESSAGES[JobStage.QUEUED],
        "result_available": False,
        "stage_timings": {},
        "extra_data": {},
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
        "cancelled": False,
    }
    with JOBS_LOCK:
        VIDEO_JOBS[job_id] = job_data
    _sync_job_to_db(job_data)
    logger.info(f"[JOB_CREATED] JobID={job_id} | VideoID={video_id} | URL={url}")
    return job_id


def update_job_stage(job_id: str, stage: str, message_override: str = None, progress_override: int = None, extra_data: dict = None):
    with JOBS_LOCK:
        if job_id not in VIDEO_JOBS:
            db_job = _get_job_from_db(job_id)
            if db_job:
                VIDEO_JOBS[job_id] = db_job
            else:
                return
        job = VIDEO_JOBS[job_id]
        if job.get("cancelled"):
            return
        now = time.time()
        
        # Log previous stage duration if any
        prev_stage = job.get("stage")
        if prev_stage and prev_stage != stage:
            stage_start = job["stage_timings"].get(f"{prev_stage}_start", now)
            duration_ms = round((now - stage_start) * 1000, 2)
            job["stage_timings"][f"{prev_stage}_duration_ms"] = duration_ms
            logger.info(f"[STAGE_COMPLETED] JobID={job_id} | Stage={prev_stage} | Duration={duration_ms}ms")

        job["stage"] = stage
        job["stage_timings"][f"{stage}_start"] = now
        job["progress"] = progress_override if progress_override is not None else STAGE_PROGRESS.get(stage, job["progress"])
        job["message"] = message_override or STAGE_MESSAGES.get(stage, stage)
        job["updated_at"] = now

        if extra_data and isinstance(extra_data, dict):
            if "extra_data" not in job or not isinstance(job.get("extra_data"), dict):
                job["extra_data"] = {}
            job["extra_data"].update(extra_data)
            for k, v in extra_data.items():
                job[k] = v

        if stage == JobStage.COMPLETED:
            job["status"] = "completed"
            job["result_available"] = True
        elif stage == JobStage.FAILED:
            job["status"] = "failed"
            job["result_available"] = False

        _sync_job_to_db(job)
        logger.info(f"[STAGE_UPDATED] JobID={job_id} | Stage={stage} | Progress={job['progress']}% | Message='{job['message']}'")


def set_job_result(job_id: str, result_data: dict):
    with JOBS_LOCK:
        if job_id not in VIDEO_JOBS:
            db_job = _get_job_from_db(job_id)
            if db_job:
                VIDEO_JOBS[job_id] = db_job
        if job_id in VIDEO_JOBS:
            job = VIDEO_JOBS[job_id]
            if job.get("cancelled"):
                return
            now = time.time()
            t_start = job.get("created_at", now)
            duration_ms = round((now - t_start) * 1000, 2)
            job["result"] = result_data
            job["result_available"] = True
            job["status"] = "completed"
            job["stage"] = JobStage.COMPLETED
            job["progress"] = 100
            job["message"] = STAGE_MESSAGES[JobStage.COMPLETED]
            job["updated_at"] = now
            _sync_job_to_db(job)
            logger.info(f"[JOB_COMPLETED] JobID={job_id} | TotalDuration={duration_ms}ms | Result payload attached.")


def set_job_error(job_id: str, error_code: str, user_message: str, retryable: bool = True):
    from app.services.error_validator import sanitize_user_error_message
    clean_msg = sanitize_user_error_message(error_code, user_message)
    with JOBS_LOCK:
        if job_id not in VIDEO_JOBS:
            db_job = _get_job_from_db(job_id)
            if db_job:
                VIDEO_JOBS[job_id] = db_job
        if job_id in VIDEO_JOBS:
            job = VIDEO_JOBS[job_id]
            if job.get("cancelled"):
                return
            now = time.time()
            t_start = job.get("created_at", now)
            duration_ms = round((now - t_start) * 1000, 2)
            job["error"] = {
                "code": error_code,
                "message": clean_msg,
                "retryable": retryable,
            }
            job["status"] = "failed"
            job["stage"] = JobStage.FAILED
            job["progress"] = 0
            job["message"] = clean_msg
            job["updated_at"] = now
            _sync_job_to_db(job)
            if error_code == "DATABASE_TEARDOWN":
                logger.debug(f"[JOB_FAILED] JobID={job_id} | Duration={duration_ms}ms | Code={error_code} | Message='{clean_msg}'")
            else:
                logger.error(f"[JOB_FAILED] JobID={job_id} | Duration={duration_ms}ms | Code={error_code} | Message='{clean_msg}'")


def cancel_job(job_id: str) -> bool:
    with JOBS_LOCK:
        if job_id not in VIDEO_JOBS:
            db_job = _get_job_from_db(job_id)
            if db_job:
                VIDEO_JOBS[job_id] = db_job
        if job_id in VIDEO_JOBS:
            job = VIDEO_JOBS[job_id]
            job["cancelled"] = True
            job["status"] = "failed"
            job["stage"] = JobStage.CANCELLED
            job["progress"] = 0
            job["message"] = STAGE_MESSAGES[JobStage.CANCELLED]
            job["error"] = {"code": "JOB_CANCELLED", "message": "Job was cancelled by the user.", "retryable": True}
            job["updated_at"] = time.time()
            _sync_job_to_db(job)
            logger.info(f"[JOB_CANCELLED] JobID={job_id}")
            return True
        return False


def is_job_cancelled(job_id: str) -> bool:
    with JOBS_LOCK:
        if job_id in VIDEO_JOBS:
            return VIDEO_JOBS[job_id].get("cancelled", False)
        db_job = _get_job_from_db(job_id)
        if db_job:
            VIDEO_JOBS[job_id] = db_job
            return db_job.get("cancelled", False)
        return False


def get_job_state(job_id: str) -> dict:
    with JOBS_LOCK:
        job = VIDEO_JOBS.get(job_id)
        if not job:
            job = _get_job_from_db(job_id)
            if job:
                VIDEO_JOBS[job_id] = job

        if job:
            # Stale job watchdog guard: if status is processing but no update for 1800s (30m), auto-fail
            now = time.time()
            updated_at = job.get("updated_at", now)
            if job.get("status") == "processing" and (now - updated_at) > 1800:
                logger.warning(f"[STALE_JOB_WATCHDOG] JobID={job_id} stalled for {round(now - updated_at, 1)}s. Auto-failing.")
                job["status"] = "failed"
                job["stage"] = JobStage.FAILED
                job["progress"] = 0
                job["message"] = "Processing job timed out. Please try again."
                job["error"] = {
                    "code": "JOB_STALLED",
                    "message": "Processing job timed out. Please try again.",
                    "retryable": True
                }
                job["updated_at"] = now
                _sync_job_to_db(job)

            return dict(job)

        return None



def submit_video_processing_task(target_func, *args, **kwargs):
    """Submits worker task to the dedicated thread pool."""
    return JOB_EXECUTOR.submit(target_func, *args, **kwargs)

