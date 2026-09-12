import os
import hashlib
import logging
from flask import Blueprint, jsonify, request, send_file
from app import db
from app.models.models import Article, Audio
from app.services.tts_service import generate_audio, TTSError, AUDIO_DIR
from app.services.dubbing_service import generate_dubbed_audio
from app.services.language_config import is_tts_supported, get_language_config

logger = logging.getLogger(__name__)
tts_bp = Blueprint("tts", __name__)


def error_response(code, message, status=400):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


AUDIO_CACHE = {}


@tts_bp.route("/articles/<int:article_id>/audio", methods=["POST"])
def create_audio(article_id):
    from app.services.tts_service import AUDIO_DIR
    payload = request.get_json(silent=True) or {}
    requested_lang = payload.get("language") or payload.get("target_language")

    article = db.session.get(Article, article_id)
    if not article:
        logger.error(f"[VOICE_FAILED] article_id={article_id} | reason=NOT_FOUND")
        return error_response("NOT_FOUND", "Article not found.", 404)

    from app.utils.auth_utils import get_current_user_optional
    user = get_current_user_optional()
    user_id = user.id if user else None

    target_lang = requested_lang or article.language

    # Single Source of Truth resolution: resolve translated article for target_lang
    target_article = None
    if article.language == target_lang:
        target_article = article
    else:
        target_article = Article.query.filter_by(video_id=article.video_id, language=target_lang).first()
        if not target_article:
            # Perform translation on demand if not existing
            try:
                from app.services.translator_service import translate_text
                translated_content = translate_text(article.content, target_lang, article.language)
                translated_title = translate_text(article.title or "Article", target_lang, article.language)
                target_article = Article(video_id=article.video_id, language=target_lang, title=translated_title, content=translated_content, is_original=False)
                db.session.add(target_article)
                db.session.commit()
            except Exception as e:
                logger.error(f"[VOICE_FAILED] article_id={article_id} | target_lang={target_lang} | err={e}")
                return error_response("VOICE_GENERATION_FAILED", f"Could not translate article content for {target_lang}", 500)

    if not is_tts_supported(target_lang):
        logger.warning(f"[VOICE_FAILED] article_id={target_article.id} | lang={target_lang} | reason=VOICE_UNSUPPORTED")
        return jsonify({
            "success": True,
            "data": {
                "article_id": target_article.id,
                "language": target_lang,
                "voiceAvailable": False,
                "message": "Voice is not available for this language."
            }
        })

    source_text = target_article.content or ""
    if not source_text.strip():
        logger.error(f"[VOICE_FAILED] article_id={target_article.id} | reason=EMPTY_SOURCE_TEXT")
        return error_response("VOICE_GENERATION_FAILED", "Source text for voice generation is empty.", 400)

    text_hash = hashlib.sha256(f"{source_text}:{target_lang}".encode("utf-8")).hexdigest()
    cache_key = f"{target_article.id}:{target_lang}:{text_hash[:16]}"

    logger.info(f"[VOICE_START] article_id={target_article.id} | video_id={target_article.video_id} | target_lang={target_lang}")
    logger.info(f"[VOICE_INPUT_LANGUAGE] lang={target_lang}")
    logger.info(f"[VOICE_INPUT_TEXT_HASH] hash={text_hash[:16]}")

    # Check RAM Cache
    if cache_key in AUDIO_CACHE:
        cached_data = AUDIO_CACHE[cache_key]
        cached_file = cached_data.get("audioUrl", "").split("/")[-1]
        full_cached_path = os.path.join(AUDIO_DIR, cached_file)
        if os.path.isfile(full_cached_path) and os.path.getsize(full_cached_path) > 0:
            logger.info(f"[VOICE_SUCCESS] [CACHE_HIT] article_id={target_article.id} | lang={target_lang}")
            return jsonify({"success": True, "data": cached_data})
        else:
            del AUDIO_CACHE[cache_key]

    # Check DB Audio Cache by (article_id, language, source_text_hash)
    existing_audio = Audio.query.filter_by(article_id=target_article.id, language=target_lang, source_text_hash=text_hash).first()

    l_cfg = get_language_config(target_lang) or {}
    v_code = l_cfg.get("voice_code", target_lang)
    v_engine = l_cfg.get("voice_engine", "gtts")

    if existing_audio:
        full_path = os.path.join(AUDIO_DIR, existing_audio.file_path)
        if os.path.isfile(full_path) and os.path.getsize(full_path) > 0:
            res_data = {
                "article_id": target_article.id,
                "video_id": target_article.video_id,
                "language": target_lang,
                "target_language_id": target_lang,
                "translated_text_hash": text_hash[:16],
                "voice_code": v_code,
                "voice_engine": existing_audio.dubbing_source or v_engine,
                "audioUrl": f"/api/audio/{existing_audio.file_path}",
                "audio_url": f"/api/audio/{existing_audio.file_path}",
                "dubbing_source": existing_audio.dubbing_source,
                "voiceAvailable": True
            }
            AUDIO_CACHE[cache_key] = res_data
            logger.info(f"[VOICE_SUCCESS] [DB_CACHE_HIT] article_id={target_article.id} | lang={target_lang}")
            return jsonify({"success": True, "data": res_data})
        else:
            try:
                db.session.delete(existing_audio)
                db.session.commit()
            except Exception:
                db.session.rollback()

    try:
        filename, dubbing_src = generate_dubbed_audio(source_text, target_lang)
        full_audio_path = os.path.join(AUDIO_DIR, filename)

        from app.services.verification_service import validate_audio_generation
        val_audio = validate_audio_generation(full_audio_path, source_text)
        if not val_audio["valid"]:
            logger.error(f"[VOICE_LANGUAGE_MISMATCH] article_id={target_article.id} | lang={target_lang} | err={val_audio['message']}")
            return error_response("VOICE_LANGUAGE_MISMATCH", val_audio["message"], 500)

        logger.info(f"[VOICE_VALIDATED] article_id={target_article.id} | lang={target_lang} | provider={dubbing_src} | size={val_audio.get('file_size_bytes')}B")
    except TTSError as e:
        logger.error(f"[VOICE_FAILED] article_id={target_article.id} | lang={target_lang} | err={e}")
        return error_response("VOICE_GENERATION_FAILED", str(e), 500)

    audio = Audio(article_id=target_article.id, language=target_lang, source_text_hash=text_hash, file_path=filename, dubbing_source=dubbing_src)
    db.session.add(audio)
    db.session.commit()

    res_data = {
        "article_id": target_article.id,
        "video_id": target_article.video_id,
        "language": target_lang,
        "target_language_id": target_lang,
        "translated_text_hash": text_hash[:16],
        "voice_code": v_code,
        "voice_engine": dubbing_src,
        "audioUrl": f"/api/audio/{filename}",
        "audio_url": f"/api/audio/{filename}",
        "dubbing_source": dubbing_src,
        "voiceAvailable": True
    }
    AUDIO_CACHE[cache_key] = res_data
    logger.info(f"[VOICE_SUCCESS] article_id={target_article.id} | lang={target_lang} | file={filename}")

    return jsonify({
        "success": True,
        "data": res_data
    })


@tts_bp.route("/audio/<path:filename>", methods=["GET"])
def serve_audio(filename):
    from app.services.tts_service import AUDIO_DIR
    full_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.isfile(full_path):
        return error_response("NOT_FOUND", "Audio file not found on server.", 404)
    mimetype = "audio/wav" if filename.lower().endswith(".wav") else "audio/mpeg"
    return send_file(full_path, mimetype=mimetype)
