import hashlib
import logging
from flask import Blueprint, jsonify, request
from app import db
from app.models.models import Article, TranslationCache
from app.services.translator_service import translate_text, get_supported_languages, TranslationError
from app.services.language_config import is_translation_supported, is_tts_supported, get_language_config
from app.services.error_validator import contains_raw_error_text

logger = logging.getLogger(__name__)
translate_bp = Blueprint("translate", __name__)


def error_response(code, message, status=400):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


TRANSLATE_CACHE = {}


@translate_bp.route("/languages", methods=["GET"])
def languages():
    langs = get_supported_languages()
    return jsonify({
        "success": True,
        "data": langs,
        "availableLanguages": langs
    })


@translate_bp.route("/articles/<int:article_id>/translate", methods=["POST"])
def translate_article(article_id):
    payload = request.get_json(silent=True) or {}
    target_lang = payload.get("language") or payload.get("target_language")
    if not target_lang:
        return error_response("MISSING_LANGUAGE", "Target language is required.")

    lang_config = get_language_config(target_lang)
    if not lang_config or not lang_config["supports_translation"]:
        return error_response("TRANSLATION_LANGUAGE_UNSUPPORTED", f"Translation into '{target_lang}' is not supported.", 400)

    original = Article.query.filter_by(id=article_id).first()
    if not original:
        original = Article.query.filter_by(video_id=article_id, is_original=True).first()
    if not original:
        logger.error(f"[TRANSLATION_FAILED] article_id={article_id} | reason=NOT_FOUND")
        return error_response("NOT_FOUND", "Article not found.", 404)

    from app.utils.auth_utils import get_current_user_optional
    user = get_current_user_optional()
    user_id = user.id if user else None

    source_article = Article.query.filter_by(video_id=original.video_id, is_original=True).first() or original
    current_src_hash = hashlib.sha256(f"{source_article.content}".encode("utf-8")).hexdigest()[:16]

    snippet = source_article.content[:100].replace("\n", " ")
    logger.info(
        f"[TRANSLATION_START] article_id={source_article.id} | video_id={source_article.video_id} | "
        f"source_lang={source_article.language} | target_lang={target_lang} | "
        f"src_hash={current_src_hash} | snippet='{snippet}'"
    )

    # Cache key: original_content_hash + source_language + target_language + provider
    content_hash = hashlib.sha256(f"{source_article.content}:{source_article.language}:{target_lang}:google".encode("utf-8")).hexdigest()
    cache_key = f"{source_article.video_id}:{source_article.language}:{target_lang}:{content_hash[:16]}"

    if cache_key in TRANSLATE_CACHE:
        cached = TRANSLATE_CACHE[cache_key]
        if cached.get("content") and not contains_raw_error_text(cached["content"]):
            logger.info(f"[TRANSLATION_SUCCESS] [CACHE_HIT] video_id={source_article.video_id}, target_lang={target_lang}")
            return jsonify({"success": True, "data": cached})
        else:
            del TRANSLATE_CACHE[cache_key]

    existing = Article.query.filter_by(video_id=source_article.video_id, language=target_lang).first()
    if existing and existing.content and existing.content.strip():
        existing_src_hash = getattr(existing, "source_text_hash", None)
        is_stale_hash = bool(existing_src_hash and existing_src_hash != current_src_hash)
        is_stale_untranslated = (target_lang != source_article.language and existing.content.strip() == source_article.content.strip())
        if contains_raw_error_text(existing.content) or is_stale_untranslated or is_stale_hash:
            logger.info(f"[PURGING STALE TRANSLATION DB ROW] article_id={existing.id}, target_lang={target_lang}, is_stale_hash={is_stale_hash}")
            try:
                db.session.delete(existing)
                db.session.commit()
            except Exception:
                db.session.rollback()
            existing = None

    if existing and existing.content and existing.content.strip():
        trans_text_hash = hashlib.sha256(f"{existing.content}".encode("utf-8")).hexdigest()[:16]
        cached_data = {
            "id": existing.id,
            "article_id": existing.id,
            "original_article_id": source_article.id,
            "video_id": source_article.video_id,
            "source_hash": current_src_hash,
            "source_text_hash": current_src_hash,
            "target_language_id": target_lang,
            "target_nllb_code": lang_config.get("nllb_code", "eng_Latn"),
            "translated_text_hash": trans_text_hash,
            "language": existing.language,
            "sourceLanguage": source_article.language,
            "targetLanguage": existing.language,
            "title": existing.title,
            "content": existing.content,
            "translation": existing.content,
            "translated_text": existing.content,
            "translatedArticle": existing.content,
            "transcript_source": existing.video.transcript_source if existing.video else "youtube",
            "ttsSupported": is_tts_supported(target_lang),
            "video_overview": {
                "videoId": existing.video.youtube_id if existing.video else "",
                "title": existing.video.title if existing.video else "YouTube Video",
                "thumbnail": existing.video.thumbnail_url if existing.video else "",
                "channelName": existing.video.channel_name if existing.video else "YouTube Channel",
                "description": existing.video.description if existing.video else "Overview available.",
                "publishedAt": existing.video.published_at_str if existing.video else "N/A",
                "duration": existing.video.duration if existing.video else "N/A",
                "language": existing.language,
                "hasTranscript": True
            }
        }
        TRANSLATE_CACHE[cache_key] = cached_data
        logger.info(f"[TRANSLATION_SUCCESS] article_id={existing.id} | target_lang={target_lang}")
        return jsonify({"success": True, "data": cached_data})

    # Check TranslationCache DB table
    db_cache = TranslationCache.query.filter_by(article_id=source_article.id, target_language=target_lang).first()
    if db_cache and db_cache.content:
        db_cache_src_hash = getattr(db_cache, "source_text_hash", None)
        if contains_raw_error_text(db_cache.content) or (db_cache_src_hash and db_cache_src_hash != current_src_hash):
            logger.info(f"[PURGING STALE DB CACHE ROW] cache_id={db_cache.id}, target_lang={target_lang}")
            try:
                db.session.delete(db_cache)
                db.session.commit()
            except Exception:
                db.session.rollback()
            db_cache = None

    if db_cache and db_cache.content and not contains_raw_error_text(db_cache.content):
        # Ensure an Article entry exists for target_lang
        target_article = Article.query.filter_by(video_id=source_article.video_id, language=target_lang).first()
        if not target_article:
            target_article = Article(video_id=source_article.video_id, language=target_lang, title=db_cache.title, content=db_cache.content, source_text_hash=current_src_hash, is_original=False)
            db.session.add(target_article)
            db.session.commit()
        trans_text_hash = hashlib.sha256(f"{db_cache.content}".encode("utf-8")).hexdigest()[:16]
        cached_data = {
            "id": target_article.id,
            "article_id": target_article.id,
            "original_article_id": source_article.id,
            "video_id": source_article.video_id,
            "source_hash": current_src_hash,
            "source_text_hash": current_src_hash,
            "target_language_id": target_lang,
            "target_nllb_code": lang_config.get("nllb_code", "eng_Latn"),
            "translated_text_hash": trans_text_hash,
            "language": db_cache.target_language,
            "sourceLanguage": source_article.language,
            "targetLanguage": db_cache.target_language,
            "title": db_cache.title,
            "content": db_cache.content,
            "translation": db_cache.content,
            "translated_text": db_cache.content,
            "translatedArticle": db_cache.content,
            "transcript_source": source_article.video.transcript_source if source_article.video else "youtube",
            "ttsSupported": is_tts_supported(target_lang),
            "video_overview": {
                "videoId": source_article.video.youtube_id if source_article.video else "",
                "title": source_article.video.title if source_article.video else "YouTube Video",
                "thumbnail": source_article.video.thumbnail_url if source_article.video else "",
                "channelName": source_article.video.channel_name if source_article.video else "YouTube Channel",
                "description": source_article.video.description if source_article.video else "Overview available.",
                "publishedAt": source_article.video.published_at_str if source_article.video else "N/A",
                "duration": source_article.video.duration if source_article.video else "N/A",
                "language": db_cache.target_language,
                "hasTranscript": True
            }
        }
        TRANSLATE_CACHE[cache_key] = cached_data
        logger.info(f"[TRANSLATION_SUCCESS] article_id={target_article.id} | target_lang={target_lang}")
        return jsonify({"success": True, "data": cached_data})

    try:
        translated_title = translate_text(source_article.title, target_lang, source_article.language)
        translated_content = translate_text(source_article.content, target_lang, source_article.language)
        from app.services.verification_service import validate_translation
        val_res = validate_translation(translated_content, source_article.content, target_lang)
        if not val_res["valid"]:
            raise TranslationError(val_res["message"])

        logger.info(f"[TRANSLATION_VALIDATED] target_lang={target_lang} | file=translate.py | status=passed | len={len(translated_content)}")
    except TranslationError as e:
        logger.error(f"[TRANSLATION_FAILED] video_id={source_article.video_id}, target_lang={target_lang}, err={e}")
        return error_response("TRANSLATION_FAILED", str(e), 502)

    new_article = Article(video_id=source_article.video_id, language=target_lang,
                           title=translated_title, content=translated_content, source_text_hash=current_src_hash, is_original=False)
    db.session.add(new_article)
    try:
        t_cache = TranslationCache(article_id=source_article.id, target_language=target_lang, title=translated_title, content=translated_content, source_text_hash=current_src_hash)
        db.session.add(t_cache)
    except Exception:
        pass
    db.session.commit()

    src_text_hash = hashlib.sha256(f"{source_article.content}".encode("utf-8")).hexdigest()[:16]
    trans_text_hash = hashlib.sha256(f"{new_article.content}".encode("utf-8")).hexdigest()[:16]

    response_data = {
        "id": new_article.id,
        "article_id": new_article.id,
        "original_article_id": source_article.id,
        "video_id": source_article.video_id,
        "source_hash": src_text_hash,
        "source_text_hash": src_text_hash,
        "target_language_id": target_lang,
        "target_nllb_code": lang_config.get("nllb_code", "eng_Latn"),
        "translated_text_hash": trans_text_hash,
        "language": new_article.language,
        "sourceLanguage": source_article.language,
        "targetLanguage": new_article.language,
        "title": new_article.title,
        "content": new_article.content,
        "translation": new_article.content,
        "translated_text": new_article.content,
        "translatedArticle": new_article.content,
        "transcript_source": new_article.video.transcript_source if new_article.video else "youtube",
        "ttsSupported": is_tts_supported(target_lang),
        "video_overview": {
            "videoId": new_article.video.youtube_id if new_article.video else "",
            "title": new_article.video.title if new_article.video else "YouTube Video",
            "thumbnail": new_article.video.thumbnail_url if new_article.video else "",
            "channelName": new_article.video.channel_name if new_article.video else "YouTube Channel",
            "description": new_article.video.description if new_article.video else "Overview available.",
            "publishedAt": new_article.video.published_at_str if new_article.video else "N/A",
            "duration": new_article.video.duration if new_article.video else "N/A",
            "language": new_article.language,
            "hasTranscript": True
        }
    }
    TRANSLATE_CACHE[cache_key] = response_data
    logger.info(f"[TRANSLATION_SUCCESS] article_id={new_article.id} | target_lang={target_lang}")

    return jsonify({
        "success": True,
        "data": response_data
    })
