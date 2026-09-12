import os
from flask import Blueprint, jsonify
from app import db
from app.models.models import Video, Article, Audio, TranslationCache
from app.utils.auth_utils import get_current_user_optional, require_auth

history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"])
def get_history():
    user = get_current_user_optional()
    if user:
        videos = Video.query.filter(Video.user_id == user.id, Video.status == "done").order_by(Video.created_at.desc()).all()
    else:
        videos = Video.query.filter(Video.status == "done").order_by(Video.created_at.desc()).all()
    return jsonify({
        "success": True,
        "data": [{
            "id": v.id,
            "title": v.title,
            "thumbnail_url": v.thumbnail_url,
            "original_language": v.original_language,
            "status": v.status,
            "transcript_source": v.transcript_source,
            "created_at": v.created_at.isoformat(),
            "articles": [{"id": a.id, "language": a.language} for a in v.articles],
        } for v in videos]
    })


@history_bp.route("/history/<int:video_id>", methods=["DELETE"])
def delete_history_item(video_id):
    user = get_current_user_optional()
    if user:
        video = Video.query.filter(Video.id == video_id, Video.user_id == user.id).first()
    else:
        video = db.session.get(Video, video_id)

    if not video:
        return jsonify({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": "History item not found."}
        }), 404

    try:
        articles = Article.query.filter_by(video_id=video.id).all()
        article_ids = [a.id for a in articles]

        if article_ids:
            # 1. Clean up generated audio files on disk for deleted articles
            audio_records = Audio.query.filter(Audio.article_id.in_(article_ids)).all()
            for audio in audio_records:
                if audio.file_path and os.path.exists(audio.file_path):
                    try:
                        os.remove(audio.file_path)
                    except OSError:
                        pass

            # 2. Delete dependent TranslationCache rows referencing deleted articles
            TranslationCache.query.filter(TranslationCache.article_id.in_(article_ids)).delete(synchronize_session=False)

            # 3. Delete dependent Audio rows referencing deleted articles
            Audio.query.filter(Audio.article_id.in_(article_ids)).delete(synchronize_session=False)

        # 4. Transactional deletion of video and cascading relationships
        db.session.delete(video)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "History item deleted successfully."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": {"code": "DATABASE_ERROR", "message": f"Failed to delete history item: {e}"}
        }), 500


@history_bp.route("/history/clear_all", methods=["DELETE"])
@history_bp.route("/history/all", methods=["DELETE"])
def clear_all_history():
    user = get_current_user_optional()
    if user:
        videos = Video.query.filter(Video.user_id == user.id).all()
    else:
        videos = Video.query.all()

    if not videos:
        return jsonify({
            "success": True,
            "message": "No history items to clear."
        })

    try:
        video_ids = [v.id for v in videos]
        user_articles = Article.query.filter(Article.video_id.in_(video_ids)).all()
        article_ids = [a.id for a in user_articles]

        if article_ids:
            # 1. Clean up generated audio files on disk for user's articles
            audio_records = Audio.query.filter(Audio.article_id.in_(article_ids)).all()
            for audio in audio_records:
                if audio.file_path and os.path.exists(audio.file_path):
                    try:
                        os.remove(audio.file_path)
                    except OSError:
                        pass

            # 2. Delete TranslationCache rows for user's articles
            TranslationCache.query.filter(TranslationCache.article_id.in_(article_ids)).delete(synchronize_session=False)

            # 3. Delete Audio rows for user's articles
            Audio.query.filter(Audio.article_id.in_(article_ids)).delete(synchronize_session=False)

        for video in videos:
            db.session.delete(video)
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "All history deleted successfully."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": {"code": "DATABASE_ERROR", "message": f"Failed to clear history: {e}"}
        }), 500


@history_bp.route("/articles/<int:article_id>/publish", methods=["POST"])
def publish_article(article_id):
    from datetime import datetime
    from app.models.models import Article

    article = db.session.get(Article, article_id)
    user = get_current_user_optional()
    if not article or (user and article.video and article.video.user_id and article.video.user_id != user.id):
        return jsonify({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": "Article not found."}
        }), 404

    article.is_published = True
    article.published_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "data": {
            "id": article.id,
            "title": article.title,
            "language": article.language,
            "is_published": article.is_published,
            "published_at": article.published_at.isoformat() if article.published_at else None
        }
    })


@history_bp.route("/published", methods=["GET"])
def get_published():
    from app.models.models import Article
    published = Article.query.filter_by(is_published=True).order_by(Article.published_at.desc()).all()
    return jsonify({
        "success": True,
        "data": [{
            "id": a.id,
            "title": a.title,
            "language": a.language,
            "published_at": a.published_at.isoformat() if a.published_at else a.created_at.isoformat(),
            "author": a.video.user.name if (a.video and a.video.user) else "Anonymous",
            "thumbnail_url": a.video.thumbnail_url if a.video else None,
        } for a in published]
    })

