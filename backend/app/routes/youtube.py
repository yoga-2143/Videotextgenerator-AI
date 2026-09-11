import time
import uuid
import logging
import threading
from flask import Blueprint, request, jsonify
from app import db
from app.models.models import Video, Transcript, Article
from app.services.transcript_service import extract_video_id, get_transcript, clean_transcript, TranscriptError
from app.services.summarizer_service import rank_important_sentences
from app.services.llm_service import get_llm_provider, article_to_plain_text, synthesize_clean_prose
from app.services.language_config import is_translation_supported
from app.services.translator_service import translate_text
from app.utils.auth_utils import get_current_user_optional

logger = logging.getLogger(__name__)
youtube_bp = Blueprint("youtube", __name__)


def error_response(code, message, status=400, retryable=True):
    return jsonify({
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable
        }
    }), status


PROCESS_CACHE = {}
IN_FLIGHT_EVENTS = {}
IN_FLIGHT_LOCK = threading.Lock()


def run_async_video_processing(app, job_id: str, url: str, video_id: str, user_id=None, force_reprocess: bool = False):
    """Background worker function executed asynchronously by job manager thread pool."""
    t_start = time.time()
    logger.info(f"[PROCESS] Request started | JobID={job_id} | VideoID={video_id} | URL={url}")

    with app.app_context():
        try:
            logger.info(f"[PROCESS] URL validated | JobID={job_id} | VideoID={video_id}")
            update_job_stage(job_id, JobStage.VALIDATING_URL, progress_override=10, message_override="Checking YouTube URL...")

            # Check DB cache first if not forced reprocess
            video = Video.query.filter_by(youtube_id=video_id).first()
            if video and video.status == "done" and not force_reprocess:
                existing_article = Article.query.filter_by(video_id=video.id, is_original=True).first()
                if existing_article and existing_article.content:
                    if not existing_article.content.startswith("IMPORTANT CONTENT"):
                        clean_prose = synthesize_clean_prose(existing_article.content, video.title or "")
                        existing_article.content = f"IMPORTANT CONTENT\n\n{clean_prose}"
                        db.session.commit()

                    res_data = {
                        "video_id": video.id,
                        "youtube_id": video.youtube_id,
                        "title": video.title,
                        "thumbnail_url": video.thumbnail_url,
                        "original_language": video.original_language,
                        "transcript_source": video.transcript_source,
                        "article": {
                            "id": existing_article.id,
                            "language": existing_article.language,
                            "title": existing_article.title,
                            "content": existing_article.content,
                        },
                    }
                    PROCESS_CACHE[video_id] = res_data
                    set_job_result(job_id, res_data)
                    logger.info(f"[PROCESS] Response sent (cached) | JobID={job_id}")
                    return

            if not video:
                video = Video(youtube_id=video_id, youtube_url=url, status="processing", user_id=user_id)
                db.session.add(video)
                db.session.commit()
            else:
                video.status = "processing"
                video.error_message = None
                video.processing_error_code = None
                db.session.commit()

            # Stage: Fetching Transcript / Speech-to-Text Fallback
            update_job_stage(job_id, JobStage.FETCHING_TRANSCRIPT, progress_override=20, message_override="Checking transcript...")
            t_trans_start = time.time()

            # Helper callbacks passed to transcript service
            def on_audio_fallback():
                update_job_stage(job_id, JobStage.TRANSCRIPT_NOT_AVAILABLE, progress_override=25, message_override="Transcript unavailable. Preparing audio fallback...")
                update_job_stage(job_id, JobStage.DOWNLOADING_AUDIO, progress_override=30, message_override="Downloading audio...")

            def on_whisper_transcribing():
                update_job_stage(job_id, JobStage.LOADING_WHISPER, progress_override=45, message_override="Loading Whisper AI speech-to-text model...")

            def on_progress(stage_arg, p=None, msg=None):
                if isinstance(stage_arg, int):
                    p, msg = stage_arg, p
                    stage_name = JobStage.TRANSCRIBING
                else:
                    stage_name = stage_arg
                update_job_stage(job_id, stage_name or JobStage.TRANSCRIBING, progress_override=p, message_override=msg)

            cleaned, lang, source = get_transcript(
                video_id,
                request_id=job_id,
                on_audio_fallback=on_audio_fallback,
                on_whisper_transcribe=on_whisper_transcribing,
                on_progress=on_progress
            )
            t_trans_end = time.time()
            if source == "captions":
                update_job_stage(job_id, JobStage.TRANSCRIPT_FOUND, progress_override=30, message_override="Transcript found. Preparing text...")
            logger.info(f"[TRANSCRIPT_STAGE_SUCCESS] JobID={job_id} | Source={source} | Duration={round(t_trans_end - t_trans_start, 2)}s")

            # Enrich Metadata
            video.thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            try:
                meta = get_video_metadata(video_id, request_id=job_id)
                video.title = meta.get("title") or video.title or f"Video ({video_id})"
                video.channel_name = meta.get("channelName")
                video.description = meta.get("description")
                video.duration = meta.get("duration")
                video.published_at_str = meta.get("publishedAt")
                if meta.get("thumbnail"):
                    video.thumbnail_url = meta.get("thumbnail")
            except Exception as meta_err:
                logger.warning(f"Fast metadata fallback used for {video_id}: {meta_err}")
                video.title = video.title or f"Video ({video_id})"

            video.original_language = lang
            video.transcript_source = source

            existing_transcript = Transcript.query.filter_by(video_id=video.id).first()
            if existing_transcript:
                existing_transcript.raw_text = cleaned
                existing_transcript.cleaned_text = cleaned
            else:
                transcript = Transcript(video_id=video.id, raw_text=cleaned, cleaned_text=cleaned)
                db.session.add(transcript)

            import hashlib

            def _hash_text(t: str) -> str:
                return hashlib.sha256((t or "").encode("utf-8")).hexdigest()[:16]

            def _log_stage_hashes(stage_name: str, text: str):
                c_count = len(text or "")
                w_count = len((text or "").split())
                first_200 = (text or "")[:200].replace("\n", " ")
                last_200 = (text or "")[-200:].replace("\n", " ")
                h_val = _hash_text(text)
                logger.info(
                    f"[PIPELINE_HASH_LOG] JobID={job_id} | VideoID={video_id} | Stage={stage_name} | "
                    f"Hash={h_val} | Chars={c_count} | Words={w_count} | First200='{first_200}' | Last200='{last_200}'"
                )

            _log_stage_hashes("TRANSCRIPT", cleaned)

            # Stage: Fast Cleanup & Repetition Removal
            logger.info(f"[CLEANUP] Started | JobID={job_id}")
            update_job_stage(job_id, JobStage.CLEANING_TEXT, progress_override=75, message_override="Cleaning transcript...")
            update_job_stage(job_id, JobStage.REMOVING_REPETITION, progress_override=82, message_override="Removing repetition...")
            _log_stage_hashes("CLEANED_TEXT", cleaned)
            logger.info(f"[CLEANUP] Completed | JobID={job_id}")

            # Stage: Spelling & Grammar Check / Proofreading
            update_job_stage(job_id, JobStage.VALIDATING_TEXT, progress_override=88, message_override="Checking spelling and grammar...")

            # Stage: Content & Important Information Generation
            logger.info(f"[ARTICLE_GENERATION_STARTED] JobID={job_id} | VideoID={video_id}")
            update_job_stage(job_id, JobStage.GENERATING_IMPORTANT_CONTENT, progress_override=92, message_override="Preparing IMPORTANT CONTENT...")
            t_gen_start = time.time()
            ranked_text = rank_important_sentences(cleaned)
            llm = get_llm_provider()
            article_json = llm.generate_article(ranked_text, video_title=video.title or "")
            article_text = article_to_plain_text(article_json)
            t_gen_end = time.time()
            _log_stage_hashes("IMPORTANT_CONTENT", article_text)
            logger.info(f"[ARTICLE_GENERATION_COMPLETED] JobID={job_id} | VideoID={video_id} | Duration={round((t_gen_end - t_gen_start) * 1000, 2)}ms")

            # Stage: DB Persistence
            logger.info(f"[DATABASE] Save started | JobID={job_id}")
            update_job_stage(job_id, JobStage.SAVING, progress_override=98, message_override="Saving results...")
            orig_lang = lang if (lang and is_translation_supported(lang)) else "en"
            article = Article.query.filter_by(video_id=video.id, language=orig_lang).first()
            if article:
                article.title = article_json.get("title", video.title or "Untitled")
                article.content = article_text
            else:
                article = Article(
                    video_id=video.id,
                    language=orig_lang,
                    title=article_json.get("title", video.title or "Untitled"),
                    content=article_text,
                    is_original=True,
                )
                db.session.add(article)

            video.title = article.title
            video.status = "done"
            db.session.commit()
            logger.info(f"[DATABASE] Save completed | JobID={job_id}")

            src_hash = _hash_text(article.content)
            res_data = {
                "job_id": job_id,
                "video_id": video.id,
                "youtube_id": video.youtube_id,
                "title": video.title,
                "thumbnail_url": video.thumbnail_url,
                "original_language": video.original_language,
                "transcript_source": video.transcript_source,
                "source_hash": src_hash,
                "source_text_hash": src_hash,
                "article": {
                    "id": article.id,
                    "language": orig_lang,
                    "title": article.title,
                    "content": article.content,
                },
            }
            PROCESS_CACHE[video_id] = res_data
            set_job_result(job_id, res_data)
            logger.info(f"[PROCESS] Response sent | JobID={job_id} | Total duration={round(time.time() - t_start, 2)}s")

        except TranscriptError as e:
            db.session.rollback()
            logger.warning(f"[JOB_TRANSCRIPT_ERROR] JobID={job_id} | Code={e.code} | Message={e.message}")
            if 'video' in locals() and video and hasattr(video, 'id'):
                try:
                    v = db.session.get(Video, video.id)
                    if v:
                        v.status = "failed"
                        v.error_message = e.message
                        v.processing_error_code = e.code
                        db.session.commit()
                except Exception:
                    db.session.rollback()
            retryable = e.code not in ["INVALID_URL", "VIDEO_PRIVATE", "VIDEO_AGE_RESTRICTED", "VIDEO_UNAVAILABLE"]
            set_job_error(job_id, e.code, e.message, retryable=retryable)

        except Exception as e:
            db.session.rollback()
            err_str = str(e)
            if "no such table" in err_str.lower():
                logger.debug(f"[JOB_TEARDOWN_NOTE] JobID={job_id} | Database torn down during job execution.")
                set_job_error(job_id, "DATABASE_TEARDOWN", "Database closed during request processing.", retryable=False)
            else:
                logger.exception(f"[JOB_UNEXPECTED_ERROR] JobID={job_id} | Failure: {e}")
                if 'video' in locals() and video and hasattr(video, 'id'):
                    try:
                        v = db.session.get(Video, video.id)
                        if v:
                            v.status = "failed"
                            v.error_message = err_str
                            v.processing_error_code = "INTERNAL_PROCESSING_ERROR"
                            db.session.commit()
                    except Exception:
                        db.session.rollback()
                set_job_error(job_id, "INTERNAL_PROCESSING_ERROR", f"Processing failed: {err_str}", retryable=True)

        finally:
            # Guarantee no job is left permanently in "processing" state
            try:
                state = get_job_state(job_id)
                if state and state.get("status") == "processing":
                    set_job_error(job_id, "UNEXPECTED_JOB_HALT", "Video processing halted unexpectedly.", retryable=True)
            except Exception as final_err:
                logger.debug(f"[JOB_FINALLY_GUARD_NOTE] JobID={job_id} guard check note: {final_err}")


from app.services.job_manager import (
    create_video_job,
    update_job_stage,
    set_job_result,
    set_job_error,
    get_job_state,
    cancel_job,
    is_job_cancelled,
    submit_video_processing_task,
    JobStage,
)
from flask import current_app


@youtube_bp.route("/jobs/process", methods=["POST"])
@youtube_bp.route("/videos/process_async", methods=["POST"])
def submit_process_job():
    payload = request.get_json(silent=True) or {}
    url = payload.get("url") or payload.get("youtube_url") or ""

    try:
        video_id = extract_video_id(url)
    except TranscriptError as e:
        return error_response(e.code, e.message, 400 if e.code == "INVALID_URL" else 422, retryable=False)

    user = get_current_user_optional()
    user_id = user.id if user else None

    # Create tracked background job
    job_id = create_video_job(url, video_id)
    app = current_app._get_current_object()

    # Launch background worker task
    submit_video_processing_task(run_async_video_processing, app, job_id, url, video_id, user_id)

    return jsonify({
        "success": True,
        "data": {
            "job_id": job_id,
            "status": "queued",
            "message": "Processing job created successfully.",
        }
    })


@youtube_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    job_state = get_job_state(job_id)
    if not job_state:
        return error_response("JOB_NOT_FOUND", "Processing job not found.", 404, retryable=False)

    return jsonify({
        "success": True,
        "data": job_state
    })


@youtube_bp.route("/jobs/<job_id>/cancel", methods=["POST"])
def cancel_process_job(job_id):
    cancelled = cancel_job(job_id)
    if not cancelled:
        return error_response("JOB_NOT_FOUND", "Job not found or already completed.", 404, retryable=False)
    return jsonify({
        "success": True,
        "message": "Job cancelled successfully."
    })


@youtube_bp.route("/videos/process", methods=["POST"])
def process_video():
    """
    Backward-compatible process video endpoint.
    Submits processing job and polls synchronously for up to 25s for fast responses,
    or returns job_id if taking longer to avoid hanging the client HTTP request.
    """
    payload = request.get_json(silent=True) or {}
    url = payload.get("url") or payload.get("youtube_url") or ""

    try:
        video_id = extract_video_id(url)
    except TranscriptError as e:
        return error_response(e.code, e.message, 400 if e.code == "INVALID_URL" else 422, retryable=False)

    # 1. Quick check memory cache
    if video_id in PROCESS_CACHE:
        return jsonify({"success": True, "data": PROCESS_CACHE[video_id]})

    # 2. Check DB cache
    video = Video.query.filter_by(youtube_id=video_id).first()
    if video and video.status == "done":
        existing_article = Article.query.filter_by(video_id=video.id, is_original=True).first()
        if existing_article and existing_article.content:
            res_data = {
                "video_id": video.id,
                "youtube_id": video.youtube_id,
                "title": video.title,
                "thumbnail_url": video.thumbnail_url,
                "original_language": video.original_language,
                "transcript_source": video.transcript_source,
                "article": {"id": existing_article.id, "language": existing_article.language, "title": existing_article.title, "content": existing_article.content},
            }
            PROCESS_CACHE[video_id] = res_data
            return jsonify({"success": True, "data": res_data})

    # Submit job and wait up to 20s for completion
    user = get_current_user_optional()
    user_id = user.id if user else None
    job_id = create_video_job(url, video_id)
    app = current_app._get_current_object()

    submit_video_processing_task(run_async_video_processing, app, job_id, url, video_id, user_id)

    # Synchronous wait up to 20s
    start_wait = time.time()
    while time.time() - start_wait < 20:
        state = get_job_state(job_id)
        if state and state["status"] == "completed" and state.get("result"):
            return jsonify({"success": True, "data": state["result"]})
        if state and state["status"] == "failed" and state.get("error"):
            err = state["error"]
            return error_response(err["code"], err["message"], 422, retryable=err.get("retryable", True))
        time.sleep(0.5)

    # If exceeding 20s, return job status payload for frontend polling
    state = get_job_state(job_id)
    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": state.get("status", "processing"),
        "stage": state.get("stage", "processing"),
        "progress": state.get("progress", 30),
        "message": state.get("message", "Processing in progress..."),
        "result_available": False,
        "data": state
    })


from app.services.video_metadata_service import get_video_metadata
from app.services.error_validator import contains_raw_error_text


@youtube_bp.route("/videos/details", methods=["POST"])
def get_details():
    payload = request.get_json(silent=True) or {}
    url = payload.get("url", "")
    request_id = str(uuid.uuid4())
    try:
        video_id = extract_video_id(url)
        metadata = get_video_metadata(video_id, request_id=request_id)
        if contains_raw_error_text(metadata.get("title")) or contains_raw_error_text(metadata.get("description")):
            return error_response("VIDEO_METADATA_FAILED", "Video details could not be loaded. Please verify the URL and try again.", 422)
        return jsonify({"success": True, "data": metadata})
    except TranscriptError as e:
        return error_response(e.code, e.message, 400 if e.code in ["INVALID_URL", "VIDEO_PRIVATE", "VIDEO_AGE_RESTRICTED"] else 422)
    except Exception as e:
        logger.exception(f"Failed to fetch video details: {e}")
        return error_response("VIDEO_METADATA_FAILED", "Video details could not be loaded. Please verify the URL and try again.", 422)


@youtube_bp.route("/videos/<int:video_id>", methods=["GET"])
def get_video(video_id):
    video = db.session.get(Video, video_id)
    if not video:
        return error_response("NOT_FOUND", "Video not found.", 404)
    return jsonify({"success": True, "data": {
        "id": video.id, "youtube_id": video.youtube_id, "title": video.title,
        "channel_name": video.channel_name, "description": video.description,
        "duration": video.duration, "published_at": video.published_at_str,
        "thumbnail_url": video.thumbnail_url, "status": video.status,
        "transcript_source": video.transcript_source,
        "articles": [{"id": a.id, "language": a.language, "title": a.title} for a in video.articles],
    }})


@youtube_bp.route("/articles/<path:identifier>", methods=["GET"])
def get_article(identifier):
    article = None
    if str(identifier).isdigit():
        num_id = int(identifier)
        article = db.session.get(Article, num_id)
        if not article:
            article = Article.query.filter_by(video_id=num_id, is_original=True).first()
        if not article:
            article = Article.query.filter_by(video_id=num_id).first()
        if not article:
            v = db.session.get(Video, num_id)
            if v and v.articles:
                article = v.articles[0]

    if not article:
        v = Video.query.filter_by(youtube_id=str(identifier)).first()
        if v and v.articles:
            article = v.articles[0]

    if not article:
        return error_response("NOT_FOUND", "Article not found.", 404)

    if article.content and not article.content.startswith("IMPORTANT CONTENT"):
        clean_prose = synthesize_clean_prose(article.content, article.video.title if article.video else "")
        article.content = f"IMPORTANT CONTENT\n\n{clean_prose}"
        db.session.commit()

    video_obj = article.video
    return jsonify({"success": True, "data": {
        "id": article.id, "language": article.language, "title": article.title, "content": article.content,
        "is_published": article.is_published, "published_at": article.published_at.isoformat() if article.published_at else None,
        "transcript_source": video_obj.transcript_source if video_obj else "youtube",
        "video_overview": {
            "videoId": video_obj.youtube_id if video_obj else "",
            "title": (video_obj.title if video_obj else None) or "YouTube Video",
            "thumbnail": video_obj.thumbnail_url if video_obj else "",
            "channelName": (video_obj.channel_name if video_obj else None) or "YouTube Channel",
            "description": (video_obj.description if video_obj else None) or "Overview available.",
            "publishedAt": (video_obj.published_at_str if video_obj else None) or "N/A",
            "duration": (video_obj.duration if video_obj else None) or "N/A",
            "language": (video_obj.original_language if video_obj else None) or "en",
            "hasTranscript": True
        }
    }})


@youtube_bp.route("/videos/<int:video_id>/ask", methods=["POST"])
def ask_video_question(video_id):
    """RAG-powered Q&A endpoint grounded strictly in the specified video's transcript."""
    from app.services.rag_service import answer_video_query
    payload = request.get_json(silent=True) or {}
    question = payload.get("question") or payload.get("query") or ""
    target_lang = payload.get("language") or "en"

    if not question.strip():
        return error_response("MISSING_QUESTION", "Question parameter is required.", 400)

    result = answer_video_query(video_id, question, target_lang=target_lang)
    if not result.get("success"):
        return error_response("RAG_QUERY_FAILED", result.get("error", "Failed to answer query."), 404)

    return jsonify(result)


@youtube_bp.route("/articles/<int:article_id>/ask", methods=["POST"])
def ask_article_question(article_id):
    """RAG-powered Q&A endpoint resolving video from article_id."""
    article = db.session.get(Article, article_id)
    if not article:
        return error_response("NOT_FOUND", "Article not found.", 404)
    return ask_video_question(article.video_id)

