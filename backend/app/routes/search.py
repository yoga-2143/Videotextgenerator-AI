from flask import Blueprint, request, jsonify
from app.models.models import Video, Article
from sqlalchemy import or_

search_bp = Blueprint("search", __name__)


@search_bp.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    if not query:
        # Return recent articles when query is empty
        results = Article.query.join(Video).order_by(Article.created_at.desc()).limit(30).all()
    else:
        results = Article.query.join(Video).filter(
            or_(
                Article.title.ilike(f"%{query}%"),
                Article.content.ilike(f"%{query}%"),
                Video.title.ilike(f"%{query}%")
            )
        ).limit(30).all()

    output = []
    for art in results:
        output.append({
            "id": art.id,
            "video_id": art.video_id,
            "title": art.title or (art.video.title if art.video else "Untitled Article"),
            "language": art.language,
            "video_title": art.video.title if art.video else "",
            "thumbnail_url": art.video.thumbnail_url if art.video else "",
            "created_at": art.created_at.isoformat(),
            "snippet": art.content[:200] + "..." if art.content and len(art.content) > 200 else (art.content or "")
        })

    return jsonify({"success": True, "data": output})
