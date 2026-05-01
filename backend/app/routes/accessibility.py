from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from ..cache_manager import get_accessibility

bp = Blueprint("accessibility", __name__, url_prefix="/api")

STALE_THRESHOLD = timedelta(minutes=5)


@bp.route("/accessibility/<station_id>")
def station_accessibility(station_id):
    rows = get_accessibility(station_id=station_id)
    if not rows:
        return jsonify({"error": "No accessibility data for this station"}), 404

    fetched_at = max(r.fetched_at for r in rows)
    stale = (datetime.utcnow() - fetched_at) > STALE_THRESHOLD
    return jsonify({"data": [r.to_dict() for r in rows], "stale": stale})


@bp.route("/accessibility")
def accessible_stations():
    """Return stations. Pass ?operational_only=true to filter fully accessible ones."""
    operational_only = request.args.get("operational_only", "false").lower() == "true"
    rows = get_accessibility()

    if operational_only:
        non_op_ids = {r.station_id for r in rows if r.status != "Operational"}
        rows = [r for r in rows if r.station_id not in non_op_ids]

    return jsonify({"data": [r.to_dict() for r in rows]})
