from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from ..cache_manager import get_vehicle_positions

bp = Blueprint("vehicles", __name__, url_prefix="/api")

STALE_THRESHOLD = timedelta(minutes=5)


@bp.route("/vehicles")
def all_vehicles():
    rows = get_vehicle_positions()
    if not rows:
        return jsonify({"data": [], "stale": False}), 200

    fetched_at = max(r.fetched_at for r in rows)
    stale = (datetime.utcnow() - fetched_at) > STALE_THRESHOLD
    return jsonify({"data": [r.to_dict() for r in rows], "stale": stale})
