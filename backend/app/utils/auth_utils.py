import os
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from app import db
from app.models.models import User

JWT_ALGO = "HS256"
JWT_EXPIRATION_DAYS = 7


def issue_token(user: User) -> str:
    secret = os.getenv("SECRET_KEY", "dev-secret-change-me")
    now = datetime.utcnow()
    payload = {
        "user_id": user.id,
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(days=JWT_EXPIRATION_DAYS)
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGO)


def _decode_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    secret = os.getenv("SECRET_KEY", "dev-secret-change-me")
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGO])
        return payload
    except jwt.PyJWTError:
        return None


def get_current_user_optional():
    payload = _decode_token()
    if not payload:
        return None
    user_id = payload.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        payload = _decode_token()
        if not payload:
            return jsonify({"success": False, "error": {
                "code": "UNAUTHORIZED", "message": "Please sign in to continue."}}), 401
        user_id = payload.get("user_id")
        user = db.session.get(User, user_id) if user_id else None
        if not user:
            return jsonify({"success": False, "error": {
                "code": "UNAUTHORIZED", "message": "Session invalid or user not found."}}), 401
        return f(user, *args, **kwargs)
    return wrapper
