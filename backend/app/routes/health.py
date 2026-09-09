from flask import Blueprint, jsonify
from app import db
from sqlalchemy import text

health_bp = Blueprint("health", __name__)


@health_bp.route("/", methods=["GET"])
def root():
    return jsonify({
        "success": True,
        "message": "Welcome to VETRI API",
        "api_health": "/api/health"
    })


@health_bp.route("/health", methods=["GET"])
def health():
    db_status = "up"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"
    return jsonify({
        "success": True,
        "message": "VETRI backend is running",
        "data": {
            "backend": "up",
            "database": db_status
        }
    })
