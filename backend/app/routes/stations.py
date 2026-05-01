from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from ..cache_manager import get_service_status, get_accessibility

bp = Blueprint("stations", __name__, url_prefix="/api")

STALE_THRESHOLD = timedelta(minutes=5)


@bp.route("/stations/<station_id>")
def station_detail(station_id):
    status_rows = get_service_status()
    access_rows = get_accessibility(station_id=station_id)

    stale = False
    if access_rows:
        fetched_at = max(r.fetched_at for r in access_rows)
        stale = (datetime.utcnow() - fetched_at) > STALE_THRESHOLD

    return jsonify({
        "station_id": station_id,
        "service_statuses": [r.to_dict() for r in status_rows],
        "accessibility": [r.to_dict() for r in access_rows],
        "stale": stale,
    })
