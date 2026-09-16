"""
Test suite validating long video safety and 300-second watchdog behavior.
Verifies that active jobs with periodic heartbeats/progress updates are never killed,
while genuinely stalled jobs (no activity > 300s) are marked as failed.
"""
import time
import pytest
from app.services.job_manager import (
    create_video_job,
    get_job_state,
    touch_job_heartbeat,
    update_job_stage,
    JobStage,
    VIDEO_JOBS,
)


def test_1_active_10min_job_with_heartbeat_not_stale():
    """1. Active 10-minute job created 600s ago with recent heartbeat is NOT marked stale."""
    job_id = create_video_job("https://www.youtube.com/watch?v=long_video_10m", "long_video_10m")
    # Job created 10 minutes (600s) ago
    VIDEO_JOBS[job_id]["created_at"] = time.time() - 600
    # But heartbeat refreshed 10 seconds ago
    touch_job_heartbeat(job_id)

    state = get_job_state(job_id)
    assert state["status"] == "processing"
    assert state["job_id"] == job_id


def test_2_active_1hour_job_with_periodic_heartbeat_not_stale():
    """2. Active 1-hour job (3600s elapsed) receiving periodic heartbeats is NOT marked stale."""
    job_id = create_video_job("https://www.youtube.com/watch?v=long_video_1h", "long_video_1h")
    # Job created 1 hour ago
    VIDEO_JOBS[job_id]["created_at"] = time.time() - 3600

    # Simulate periodic stage updates during 1-hour processing
    update_job_stage(job_id, JobStage.TRANSCRIBING, message_override="Transcribing long audio (45m)...", progress_override=60)
    touch_job_heartbeat(job_id)

    state = get_job_state(job_id)
    assert state["status"] == "processing"
    assert state["progress"] == 60


def test_3_genuinely_stalled_job_marked_stale():
    """3. Genuinely stalled job with no heartbeat or update for > 300s IS marked failed."""
    job_id = create_video_job("https://www.youtube.com/watch?v=stalled_video", "stalled_video")
    # No activity for 310 seconds
    VIDEO_JOBS[job_id]["updated_at"] = time.time() - 310

    state = get_job_state(job_id)
    assert state["status"] == "failed"
    assert state["error"]["code"] == "JOB_STALLED"


def test_4_long_video_processing_stage_updates_prevent_timeout():
    """4. Sequential long video stage updates keep job active over long total durations."""
    job_id = create_video_job("https://www.youtube.com/watch?v=long_video_full", "long_video_full")

    stages = [
        (JobStage.FETCHING_TRANSCRIPT, 20),
        (JobStage.TRANSCRIBING, 55),
        (JobStage.CLEANING_TEXT, 75),
        (JobStage.GENERATING_IMPORTANT_CONTENT, 92),
    ]

    for stage, progress in stages:
        update_job_stage(job_id, stage, progress_override=progress)
        state = get_job_state(job_id)
        assert state["status"] == "processing"
        assert state["progress"] == progress
