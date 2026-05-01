"""
Trip planner endpoint.

GET /api/stations/list
  Returns all stations with their serving routes (from bundled stations.json).

GET /api/trip?from=<station_id>&to=<station_id>
  Returns suggested routes connecting origin to destination.
  Uses route-stop graph + geographic proximity for transfers (stations within
  250m are considered walkable transfer points).
  Includes current service status for each suggested route.
"""

import json
import logging
import math
from pathlib import Path
from flask import Blueprint, jsonify, request
from ..models import ServiceStatus

bp = Blueprint("trip", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)

_STATIONS_FILE = Path(__file__).parent.parent / "data" / "stations.json"
TRANSFER_RADIUS_M = 400  # stations within this distance are walkable transfers

_stations = None
_station_map = None
_route_stations = None
_proximity_transfers = None  # station_id -> [nearby station_ids]


def _haversine(lat1, lon1, lat2, lon2):
    """Distance in metres between two lat/lon points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _load():
    global _stations, _station_map, _route_stations, _proximity_transfers
    if _stations is not None:
        return
    with open(_STATIONS_FILE, encoding="utf-8") as f:
        _stations = json.load(f)

    _station_map = {s["id"]: s for s in _stations}

    _route_stations = {}
    for s in _stations:
        routes = s["routes"]
        if isinstance(routes, str):
            routes = routes.split()
            s["routes"] = routes
        for r in routes:
            _route_stations.setdefault(r, []).append(s["id"])

    # Build proximity transfer map: for each station, find nearby stations
    # that serve different routes (walkable transfers)
    _proximity_transfers = {}
    for s in _stations:
        nearby = []
        for other in _stations:
            if other["id"] == s["id"]:
                continue
            dist = _haversine(s["lat"], s["lon"], other["lat"], other["lon"])
            if dist <= TRANSFER_RADIUS_M:
                nearby.append(other["id"])
        _proximity_transfers[s["id"]] = nearby


@bp.route("/stations/list")
def stations_list():
    _load()
    return jsonify({"data": _stations})


@bp.route("/trip")
def plan_trip():
    _load()
    from_id = request.args.get("from", "").strip()
    to_id = request.args.get("to", "").strip()

    if not from_id or not to_id:
        return jsonify({"error": "from and to query params are required"}), 400
    if from_id not in _station_map:
        return jsonify({"error": f"Unknown station: {from_id}"}), 404
    if to_id not in _station_map:
        return jsonify({"error": f"Unknown station: {to_id}"}), 404
    if from_id == to_id:
        return jsonify({"error": "Origin and destination are the same"}), 400

    origin = _station_map[from_id]
    dest = _station_map[to_id]

    # ── Step 1: direct routes (serve both stations) ──────────────────────────
    origin_routes = set(origin["routes"])
    dest_routes = set(dest["routes"])
    direct = sorted(origin_routes & dest_routes)

    # ── Step 2: one-transfer routes ──────────────────────────────────────────
    transfers = []
    if not direct:
        # Expand origin: all stations reachable by walking from origin
        origin_cluster = {from_id} | set(_proximity_transfers.get(from_id, []))
        # Expand dest: all stations reachable by walking to dest
        dest_cluster = {to_id} | set(_proximity_transfers.get(to_id, []))

        # Collect all routes serving origin cluster and dest cluster
        origin_routes_expanded = set()
        for sid in origin_cluster:
            origin_routes_expanded |= set(_station_map[sid]["routes"])

        dest_routes_expanded = set()
        for sid in dest_cluster:
            dest_routes_expanded |= set(_station_map[sid]["routes"])

        # Direct after proximity expansion
        direct_expanded = sorted(origin_routes_expanded & dest_routes_expanded)
        if direct_expanded:
            direct = direct_expanded
        else:
            # Find transfer: take r1 from origin cluster, find stations on r1
            # that are also in dest cluster or near a dest route station
            for r1 in origin_routes_expanded:
                for transfer_sid in _route_stations.get(r1, []):
                    transfer = _station_map.get(transfer_sid)
                    if not transfer:
                        continue
                    # Expand transfer station with proximity
                    transfer_cluster = {transfer_sid} | set(_proximity_transfers.get(transfer_sid, []))
                    transfer_routes = set()
                    for tsid in transfer_cluster:
                        transfer_routes |= set(_station_map[tsid]["routes"])

                    common = transfer_routes & dest_routes_expanded
                    for r2 in common:
                        if r2 != r1:
                            transfers.append({
                                "line1": r1,
                                "transfer_station": transfer["name"],
                                "transfer_station_id": transfer_sid,
                                "line2": r2,
                            })

        # Deduplicate by (line1, line2) keeping first occurrence
        seen = set()
        unique_transfers = []
        for t in transfers:
            key = (t["line1"], t["line2"])
            if key not in seen:
                seen.add(key)
                unique_transfers.append(t)
        transfers = unique_transfers[:8]  # cap at 8 suggestions

    # ── Step 3: attach current service status ────────────────────────────────
    all_route_ids = set(direct) | {t["line1"] for t in transfers} | {t["line2"] for t in transfers}
    status_rows = ServiceStatus.query.filter(
        ServiceStatus.route_id.in_(all_route_ids)
    ).all() if all_route_ids else []
    status_map = {}
    for row in status_rows:
        # Keep worst status per route
        existing = status_map.get(row.route_id)
        if not existing or _severity_rank(row.status) > _severity_rank(existing["status"]):
            status_map[row.route_id] = {"status": row.status, "alert": row.alert_text}

    def route_info(route_id: str) -> dict:
        s = status_map.get(route_id, {"status": "Good Service", "alert": None})
        return {"route_id": route_id, "status": s["status"], "alert": s["alert"]}

    return jsonify({
        "origin": {"id": origin["id"], "name": origin["name"]},
        "destination": {"id": dest["id"], "name": dest["name"]},
        "direct": [route_info(r) for r in direct],
        "transfers": [
            {
                **t,
                "line1_info": route_info(t["line1"]),
                "line2_info": route_info(t["line2"]),
            }
            for t in transfers
        ],
    })


def _severity_rank(status: str) -> int:
    return {"Suspended": 3, "Delays": 2, "Service Change": 1}.get(status, 0)
