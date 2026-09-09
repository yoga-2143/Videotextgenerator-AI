"""
Background Job Processing System for Async Translation & Voice Generation.
Executes non-blocking background workers with persisted/tracked job state
so article processing never waits for translation or TTS.
"""
import uuid
import time
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Controlled thread pool — bounded max_workers to prevent unbounded thread spawn
EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="vetri_worker_")

# In-memory tracked job status dictionary
JOB_STORE = {}


def submit_background_job(job_type: str, target_func, *args, **kwargs) -> str:
    job_id = f"{job_type}_{uuid.uuid4().hex[:12]}"
    now = time.time()
    JOB_STORE[job_id] = {
        "job_id": job_id,
        "job_type": job_type,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    def worker_wrapper():
        JOB_STORE[job_id]["status"] = "processing"
        JOB_STORE[job_id]["updated_at"] = time.time()
        logger.info(f"[JOB START] job_id={job_id}, type={job_type}")
        try:
            res = target_func(*args, **kwargs)
            JOB_STORE[job_id]["status"] = "completed"
            JOB_STORE[job_id]["result"] = res
            JOB_STORE[job_id]["updated_at"] = time.time()
            logger.info(f"[JOB SUCCESS] job_id={job_id}, type={job_type}")
        except Exception as e:
            JOB_STORE[job_id]["status"] = "failed"
            JOB_STORE[job_id]["error"] = str(e)
            JOB_STORE[job_id]["updated_at"] = time.time()
            logger.exception(f"[JOB FAILED] job_id={job_id}, type={job_type}: {e}")

    EXECUTOR.submit(worker_wrapper)
    return job_id


def get_job_status(job_id: str) -> dict:
    if job_id not in JOB_STORE:
        return {"job_id": job_id, "status": "not_found"}
    return JOB_STORE[job_id]
