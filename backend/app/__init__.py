import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    db.init_app(app)
    frontend_url = os.getenv("FRONTEND_URL")
    origins = []
    if frontend_url:
        origins.append(frontend_url.rstrip("/"))
    origins.extend(["http://localhost:5173", "http://127.0.0.1:5173"])
    allowed_origins = list(dict.fromkeys(origins))

    CORS(app, origins=allowed_origins, supports_credentials=True)


    from app.routes.health import health_bp
    from app.routes.youtube import youtube_bp
    from app.routes.translate import translate_bp
    from app.routes.tts import tts_bp
    from app.routes.history import history_bp
    from app.routes.search import search_bp
    from app.routes.stream import stream_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(youtube_bp, url_prefix="/api")
    app.register_blueprint(translate_bp, url_prefix="/api")
    app.register_blueprint(tts_bp, url_prefix="/api")
    app.register_blueprint(history_bp, url_prefix="/api")
    app.register_blueprint(search_bp, url_prefix="/api")
    app.register_blueprint(stream_bp, url_prefix="/api")

    try:
        from app.routes.auth import auth_bp
        app.register_blueprint(auth_bp, url_prefix="/api/auth")
    except ImportError:
        pass

    @app.route("/")
    def root():
        return jsonify({
            "success": True,
            "message": "Welcome to VETRI API",
            "api_health": "/api/health"
        })

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "Route not found"}}), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception(e)
        orig_err = getattr(e, 'original_exception', e)
        msg = str(orig_err) if orig_err and str(orig_err).strip() else "An unexpected server error occurred while processing the request."
        return jsonify({"success": False, "error": {"code": "SERVER_ERROR", "message": msg}}), 500

    with app.app_context():
        from app.models import models  # noqa
        try:
            db.create_all()
            with db.engine.connect() as conn:
                for alter_cmd in [
                    "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)",
                    "ALTER TABLE videos ADD COLUMN processing_error_code VARCHAR(100)",
                    "ALTER TABLE articles ADD COLUMN source_text_hash VARCHAR(64)",
                    "ALTER TABLE articles ADD COLUMN hard_words_json TEXT",
                    "ALTER TABLE articles ADD COLUMN is_published BOOLEAN DEFAULT 0",
                    "ALTER TABLE articles ADD COLUMN published_at DATETIME",
                    "ALTER TABLE articles ADD COLUMN qa_results TEXT",
                    "ALTER TABLE audio ADD COLUMN dubbing_source VARCHAR(50)",
                    "ALTER TABLE audio ADD COLUMN source_text_hash VARCHAR(64)",
                    "ALTER TABLE audio ADD COLUMN translated_text_hash VARCHAR(64)",
                    "ALTER TABLE audio ADD COLUMN voice_code VARCHAR(100)",
                    "ALTER TABLE translation_cache ADD COLUMN source_text_hash VARCHAR(64)",
                    "ALTER TABLE translation_cache ADD COLUMN translated_text_hash VARCHAR(64)",
                    "ALTER TABLE translation_cache ADD COLUMN hard_words_json TEXT"
                ]:
                    try:
                        conn.execute(db.text(alter_cmd))
                        conn.commit()
                    except Exception:
                        pass

                # Safely populate any pre-existing NULL source_text_hash entries for legacy data
                for update_cmd in [
                    "UPDATE articles SET source_text_hash = 'legacy_hash' WHERE source_text_hash IS NULL",
                    "UPDATE translation_cache SET source_text_hash = 'legacy_hash' WHERE source_text_hash IS NULL"
                ]:
                    try:
                        conn.execute(db.text(update_cmd))
                        conn.commit()
                    except Exception:
                        pass
        except Exception as e:
            app.logger.warning(f"DB not ready yet: {e}")

        # Pre-warm Whisper singleton to eliminate first-request model load latency
        try:
            from app.services.whisper_service import prewarm_whisper_model
            prewarm_whisper_model()
        except Exception as prewarm_err:
            app.logger.warning(f"Whisper prewarm note: {prewarm_err}")

    return app
