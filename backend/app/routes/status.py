from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from ..cache_manager import get_service_status

bp = Blueprint("status", __name__, url_prefix="/api")

STALE_THRESHOLD = timedelta(minutes=5)


@bp.route("/status")
def all_statuses():
    rows = get_service_status()
    if not rows:
        return jsonify({"data": [], "stale": False}), 200

    fetched_at = max(r.fetched_at for r in rows)
    stale = (datetime.utcnow() - fetched_at) > STALE_THRESHOLD
    return jsonify({"data": [r.to_dict() for r in rows], "stale": stale})


@bp.route("/status/<route_id>")
def route_status(route_id):
    rows = get_service_status(route_id=route_id)
    if not rows:
        return jsonify({"error": "Route not found"}), 404

    row = rows[0]
    stale = (datetime.utcnow() - row.fetched_at) > STALE_THRESHOLD
    return jsonify({"data": row.to_dict(), "stale": stale})
