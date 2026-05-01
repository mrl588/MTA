from datetime import datetime
from flask import Blueprint, jsonify, request, g
from ..extensions import db
from ..models import User, Favorite
from ..firebase import verify_token

bp = Blueprint("favorites", __name__, url_prefix="/api")


def _get_or_create_user() -> User:
    """Resolve the Firebase UID from g to a local User row, creating one if needed."""
    user = User.query.filter_by(firebase_uid=g.firebase_uid).first()
    if not user:
        user = User(
            firebase_uid=g.firebase_uid,
            email=g.email,
            created_at=datetime.utcnow(),
        )
        db.session.add(user)
        db.session.commit()
    return user


@bp.route("/favorites", methods=["GET"])
@verify_token
def get_favorites():
    user = _get_or_create_user()
    return jsonify({"data": [f.to_dict() for f in user.favorites]})


@bp.route("/favorites", methods=["POST"])
@verify_token
def add_favorite():
    body = request.get_json(silent=True) or {}
    item_type = body.get("item_type")
    item_id = body.get("item_id")
    item_name = body.get("item_name")

    if not all([item_type, item_id, item_name]):
        return jsonify({"error": "item_type, item_id, and item_name are required"}), 400
    if item_type not in ("route", "station"):
        return jsonify({"error": "item_type must be 'route' or 'station'"}), 400

    user = _get_or_create_user()

    # Prevent duplicates
    existing = Favorite.query.filter_by(user_id=user.id, item_id=item_id).first()
    if existing:
        return jsonify({"error": "Already in favorites"}), 409

    fav = Favorite(
        user_id=user.id,
        item_type=item_type,
        item_id=item_id,
        item_name=item_name,
        alerts_enabled=0,
        created_at=datetime.utcnow(),
    )
    db.session.add(fav)
    db.session.commit()
    return jsonify({"data": fav.to_dict()}), 201


@bp.route("/favorites/<int:fav_id>", methods=["DELETE"])
@verify_token
def remove_favorite(fav_id):
    user = _get_or_create_user()
    fav = Favorite.query.filter_by(id=fav_id, user_id=user.id).first()
    if not fav:
        return jsonify({"error": "Favorite not found"}), 404

    db.session.delete(fav)
    db.session.commit()
    return jsonify({"message": "Removed"}), 200


@bp.route("/favorites/<int:fav_id>/alerts", methods=["PATCH"])
@verify_token
def toggle_alerts(fav_id):
    user = _get_or_create_user()
    fav = Favorite.query.filter_by(id=fav_id, user_id=user.id).first()
    if not fav:
        return jsonify({"error": "Favorite not found"}), 404

    body = request.get_json(silent=True) or {}
    enabled = body.get("alerts_enabled")
    if enabled is None:
        return jsonify({"error": "alerts_enabled (bool) is required"}), 400

    fav.alerts_enabled = 1 if enabled else 0
    db.session.commit()
    return jsonify({"data": fav.to_dict()})
