import os
import logging
from flask import Blueprint, request, jsonify
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app import db
from app.models.models import User
from app.utils.auth_utils import issue_token, require_auth

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/google", methods=["POST"])
@auth_bp.route("/google-login", methods=["POST"])
def google_auth():
    payload = request.get_json(silent=True) or {}
    token_str = payload.get("credential") or payload.get("token")
    if not token_str:
        return jsonify({
            "success": False,
            "error": {"code": "MISSING_CREDENTIAL", "message": "Google credential token is required."}
        }), 400

    google_client_id = os.getenv("GOOGLE_CLIENT_ID")

    try:
        # Cryptographically verify the Google ID token with Google's public keys
        id_info = id_token.verify_oauth2_token(
            token_str,
            google_requests.Request(),
            audience=google_client_id if google_client_id else None
        )

        google_sub = id_info.get("sub")
        email = id_info.get("email")
        name = id_info.get("name") or (email.split("@")[0] if email else "User")
        picture = id_info.get("picture")

        if not email:
            return jsonify({
                "success": False,
                "error": {"code": "INVALID_TOKEN", "message": "Google token does not contain an email address."}
            }), 400

        # Find existing user by google_id or email
        user = None
        if google_sub:
            user = User.query.filter_by(google_id=google_sub).first()
        if not user and email:
            user = User.query.filter_by(email=email).first()

        if user:
            if not user.google_id and google_sub:
                user.google_id = google_sub
            if not user.picture_url and picture:
                user.picture_url = picture
            if not user.name and name:
                user.name = name
            db.session.commit()
        else:
            user = User(
                google_id=google_sub,
                email=email,
                name=name,
                picture_url=picture
            )
            db.session.add(user)
            db.session.commit()

        jwt_token = issue_token(user)
        return jsonify({
            "success": True,
            "data": {
                "token": jwt_token,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "picture_url": user.picture_url
                }
            }
        })
    except ValueError as val_err:
        logger.warning(f"[GOOGLE_AUTH_FAILED] Invalid token or audience mismatch: {val_err}")
        return jsonify({
            "success": False,
            "error": {"code": "INVALID_TOKEN", "message": f"Google authentication failed: {val_err}"}
        }), 401
    except Exception as e:
        logger.exception(f"[GOOGLE_AUTH_ERROR] Unexpected error during Google authentication: {e}")
        return jsonify({
            "success": False,
            "error": {"code": "AUTH_ERROR", "message": "Authentication failed. Please try again."}
        }), 500


@auth_bp.route("/auth/register", methods=["POST"])
@auth_bp.route("/signup", methods=["POST"])
def register():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({
            "success": False,
            "error": {"code": "INVALID_INPUT", "message": "Email and password are required."}
        }), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({
            "success": False,
            "error": {"code": "USER_EXISTS", "message": "An account with this email already exists."}
        }), 400

    user = User(email=email, name=name or email.split("@")[0])
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    jwt_token = issue_token(user)
    return jsonify({
        "success": True,
        "data": {
            "token": jwt_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "picture_url": user.picture_url
            }
        }
    })


@auth_bp.route("/auth/login", methods=["POST"])
@auth_bp.route("/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({
            "success": False,
            "error": {"code": "INVALID_INPUT", "message": "Email and password are required."}
        }), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({
            "success": False,
            "error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}
        }), 401

    jwt_token = issue_token(user)
    return jsonify({
        "success": True,
        "data": {
            "token": jwt_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "picture_url": user.picture_url
            }
        }
    })


@auth_bp.route("/me", methods=["GET"])
@require_auth
def get_me(user):
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "picture_url": user.picture_url
            }
        }
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    return jsonify({
        "success": True,
        "message": "Signed out successfully."
    })

