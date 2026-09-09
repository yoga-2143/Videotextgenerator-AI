import json
import re
from flask import Blueprint, request, jsonify, Response
from app.services.realtime_processor import RealTimeChunkProcessor, stream_realtime_chunks

stream_bp = Blueprint("stream", __name__)


@stream_bp.route("/stream/chunk", methods=["POST"])
def process_single_chunk():
    """
    Process an incoming transcript chunk immediately with low latency.
    Supports modes: REALTIME, FINAL, TRANSLATE, TTS_READY, DEBUG
    """
    payload = request.get_json(silent=True) or {}
    chunk_text = payload.get("chunk", "") or payload.get("current_chunk", "")
    mode = (payload.get("mode") or payload.get("MODE") or "REALTIME").upper()
    source_language = payload.get("source_language") or payload.get("SOURCE_LANGUAGE") or "en"
    target_language = payload.get("target_language") or payload.get("TARGET_LANGUAGE") or None
    context_override = payload.get("context") or payload.get("PREVIOUS_CONTEXT") or None
    recent_cleaned_override = payload.get("recent_cleaned_output") or payload.get("RECENT_CLEANED_OUTPUT") or None

    if not chunk_text or not isinstance(chunk_text, str):
        if mode == "DEBUG":
            return jsonify({
                "status": "error",
                "mode": mode,
                "error_code": "INVALID_CHUNK",
                "message": "Please provide a valid text chunk."
            }), 400
        return jsonify({
            "success": False,
            "error": {"code": "INVALID_CHUNK", "message": "Please provide a valid text chunk."}
        }), 400

    processor = RealTimeChunkProcessor(rolling_window_size=3)
    result = processor.process_chunk(
        chunk_text=chunk_text,
        mode=mode,
        source_language=source_language,
        target_language=target_language,
        context_override=context_override,
        recent_cleaned_override=recent_cleaned_override
    )

    if mode == "DEBUG":
        return jsonify(result)

    return jsonify({
        "success": True,
        "mode": mode,
        "data": {
            "cleaned_text": result.get("cleaned_text", ""),
            "corrected_terms": result.get("corrected_terms", []),
            "rolling_context": result.get("rolling_context", "")
        }
    })


@stream_bp.route("/stream/transcript", methods=["POST"])
def stream_transcript_chunks():
    """
    Accepts raw transcript text or an array of text chunks and streams
    cleaned content progressively via Server-Sent Events (SSE).
    """
    payload = request.get_json(silent=True) or {}
    chunks = payload.get("chunks", [])
    raw_text = payload.get("raw_text") or payload.get("COMPLETE_RAW_TRANSCRIPT", "")
    mode = (payload.get("mode") or payload.get("MODE") or "REALTIME").upper()
    target_language = payload.get("target_language") or payload.get("TARGET_LANGUAGE") or None

    if not chunks and raw_text:
        chunks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_text) if s.strip()]

    if not chunks or not isinstance(chunks, list):
        return jsonify({
            "success": False,
            "error": {"code": "INVALID_INPUT", "message": "Please provide an array of text chunks or raw_text string."}
        }), 400

    return Response(
        stream_realtime_chunks(chunks, mode=mode, target_language=target_language),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


    processor = RealTimeChunkProcessor()
    final_text = processor.process_stage2_final(raw_transcript, title=title)

    return jsonify({
        "success": True,
        "mode": "FINAL",
        "data": {
            "final_cleaned_transcript": final_text
        }
    })


@stream_bp.route("/jobs/<job_id>/stream", methods=["GET"])
def stream_job_progress(job_id):
    """
    SSE endpoint to stream live job progress and stage updates to the frontend.
    """
    import time
    from app.services.job_manager import get_job_state

    def generate_events():
        last_stage = None
        last_progress = -1
        while True:
            state = get_job_state(job_id)
            if not state:
                yield f"data: {json.dumps({'status': 'failed', 'error': {'code': 'JOB_NOT_FOUND', 'message': 'Job not found'}})}\n\n"
                break

            current_stage = state.get("stage")
            current_progress = state.get("progress", 0)

            if current_stage != last_stage or current_progress != last_progress:
                last_stage = current_stage
                last_progress = current_progress
                yield f"data: {json.dumps(state)}\n\n"

            if state.get("status") in ["completed", "failed"]:
                break

            time.sleep(0.5)

    return Response(
        generate_events(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
