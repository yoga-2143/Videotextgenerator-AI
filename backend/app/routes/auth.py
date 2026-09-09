from flask import Blueprint, jsonify
from app.utils.auth_utils import require_auth

auth_bp = Blueprint("auth", __name__)


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
            }
        }
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    return jsonify({
        "success": True,
        "message": "Signed out successfully."
    })
