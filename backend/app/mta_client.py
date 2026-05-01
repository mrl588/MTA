"""
MTA API client — fetches GTFS-RT feeds and REST endpoints from api.mta.info.

Feed URLs (GTFS Realtime, protobuf):
  Service alerts : https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fall-alerts
  Vehicle positions (subway ACE): https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace
  Elevator/escalator: https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fnyct_ene_equipments

All feeds require the header: x-api-key: <MTA_API_KEY>

NOTE: MTA subway GTFS-RT vehicle entities do NOT include GPS coordinates.
Instead they carry a stop_id (current/next stop). We map stop_id → lat/lon
using the bundled GTFS static stops.txt file.
"""

import csv
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
from google.transit import gtfs_realtime_pb2

logger = logging.getLogger(__name__)

MTA_BASE = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds"

ALERT_FEED = f"{MTA_BASE}/camsys%2Fall-alerts"
VEHICLE_FEEDS = {
    "ACE":     f"{MTA_BASE}/nyct%2Fgtfs-ace",
    "BDFM":    f"{MTA_BASE}/nyct%2Fgtfs-bdfm",
    "G":       f"{MTA_BASE}/nyct%2Fgtfs-g",
    "JZ":      f"{MTA_BASE}/nyct%2Fgtfs-jz",
    "NQRW":    f"{MTA_BASE}/nyct%2Fgtfs-nqrw",
    "L":       f"{MTA_BASE}/nyct%2Fgtfs-l",
    "1234567": f"{MTA_BASE}/nyct%2Fgtfs",
    "SIR":     f"{MTA_BASE}/nyct%2Fgtfs-si",
}
ELEVATOR_FEED = f"{MTA_BASE}/nyct%2Fnyct_ene_equipments"

# Path to bundled GTFS static stops.txt
_STOPS_FILE = Path(__file__).parent / "data" / "stops.txt"

# Lazy-loaded stop lookup: stop_id -> (lat, lon)
_stop_coords: Optional[Dict[str, Tuple[float, float]]] = None


def _load_stop_coords() -> Dict[str, Tuple[float, float]]:
    """Load stop_id -> (lat, lon) from bundled stops.txt."""
    global _stop_coords
    if _stop_coords is not None:
        return _stop_coords
    coords: Dict[str, Tuple[float, float]] = {}
    try:
        with open(_STOPS_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row.get("stop_id", "").strip()
                try:
                    lat = float(row["stop_lat"])
                    lon = float(row["stop_lon"])
                    coords[sid] = (lat, lon)
                except (KeyError, ValueError):
                    pass
        logger.info("Loaded %d stop coordinates from stops.txt", len(coords))
    except Exception as exc:
        logger.error("Failed to load stops.txt: %s", exc)
    _stop_coords = coords
    return coords


def _headers():
    return {"x-api-key": os.getenv("MTA_API_KEY", "")}


def _fetch_gtfs_feed(url: str) -> Optional[gtfs_realtime_pb2.FeedMessage]:
    """Fetch and parse a GTFS-RT protobuf feed. Returns None on failure."""
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(resp.content)
        return feed
    except Exception as exc:
        logger.error("Failed to fetch GTFS feed %s: %s", url, exc)
        return None


def fetch_service_alerts() -> List[dict]:
    """
    Returns a list of dicts:
      { route_id, route_name, status, alert_text }
    """
    feed = _fetch_gtfs_feed(ALERT_FEED)
    if feed is None:
        return []

    alerts = []
    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue
        alert = entity.alert
        header = (
            alert.header_text.translation[0].text
            if alert.header_text.translation
            else ""
        )
        description = (
            alert.description_text.translation[0].text
            if alert.description_text.translation
            else ""
        )
        for informed in alert.informed_entity:
            route_id = informed.route_id or "unknown"
            alerts.append({
                "route_id": route_id,
                "route_name": route_id,
                "status": _classify_alert(header),
                "alert_text": description or header,
            })
    return alerts


def fetch_vehicle_positions() -> List[dict]:
    """
    Returns a list of dicts:
      { route_id, vehicle_id, latitude, longitude }

    MTA subway GTFS-RT vehicle entities carry a stop_id (current/next stop)
    but no GPS coordinates. We map stop_id -> lat/lon via the bundled stops.txt.
    """
    stop_coords = _load_stop_coords()
    positions = []
    for group, url in VEHICLE_FEEDS.items():
        feed = _fetch_gtfs_feed(url)
        if feed is None:
            continue
        for entity in feed.entity:
            if not entity.HasField("vehicle"):
                continue
            v = entity.vehicle

            # Try GPS position first (bus feeds may have it)
            if v.HasField("position"):
                positions.append({
                    "route_id": v.trip.route_id or group,
                    "vehicle_id": v.vehicle.id or entity.id,
                    "latitude": v.position.latitude,
                    "longitude": v.position.longitude,
                })
                continue

            # Fall back to stop_id -> lat/lon lookup (subway feeds)
            stop_id = v.stop_id
            if stop_id and stop_id in stop_coords:
                lat, lon = stop_coords[stop_id]
                positions.append({
                    "route_id": v.trip.route_id or group,
                    "vehicle_id": v.vehicle.id or entity.id,
                    "latitude": lat,
                    "longitude": lon,
                })

    return positions


def fetch_accessibility_status() -> List[dict]:
    """
    Fetches elevator/escalator equipment status.
    Returns a list of dicts:
      { station_id, equipment_id, equipment_type, status }
    """
    try:
        resp = requests.get(ELEVATOR_FEED, headers=_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("Failed to fetch accessibility data: %s", exc)
        return []

    results = []
    for item in data:
        results.append({
            "station_id": str(item.get("stationcomplexid", item.get("station", "unknown"))),
            "equipment_id": str(item.get("equipmentno", item.get("equipment", ""))),
            "equipment_type": item.get("equipmenttype", "elevator").lower(),
            "status": _map_equipment_status(item.get("serving", item.get("outagedate", ""))),
        })
    return results


# ── helpers ──────────────────────────────────────────────────────────────────

def _classify_alert(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ("suspend", "no service", "no train")):
        return "Suspended"
    if any(w in text_lower for w in ("delay", "slower", "extra travel")):
        return "Delays"
    if any(w in text_lower for w in ("change", "skip", "reroute", "divert", "alternate")):
        return "Service Change"
    return "Good Service"


def _map_equipment_status(value: str) -> str:
    if not value:
        return "Operational"
    v = value.lower()
    if "scheduled" in v or "planned" in v:
        return "Scheduled Maintenance"
    if v in ("", "none") or "serving" in v:
        return "Operational"
    return "Out of Service"
