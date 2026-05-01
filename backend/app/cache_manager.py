"""
On-demand MTA data cache.

Instead of a background scheduler (which doesn't work on Vercel serverless),
each endpoint calls the relevant `get_*` function here. The function checks
whether the cached data is fresh enough; if not, it fetches from the MTA API,
writes to the DB, and returns the fresh rows.

CACHE_TTL_SECONDS (default 30) controls how often we actually hit the MTA API.
"""

import logging
from datetime import datetime, timedelta
from flask import current_app

logger = logging.getLogger(__name__)


def _ttl() -> timedelta:
    return timedelta(seconds=current_app.config.get("CACHE_TTL_SECONDS", 30))


def _is_stale(fetched_at: datetime) -> bool:
    return (datetime.utcnow() - fetched_at) > _ttl()


# ── Service Status ────────────────────────────────────────────────────────────

def get_service_status(route_id: str = None):
    """
    Return cached ServiceStatus rows. Re-fetches from MTA API if cache is stale.
    Pass route_id to filter to a single route.
    """
    from .extensions import db
    from .models import ServiceStatus
    from .mta_client import fetch_service_alerts

    # Check freshness of most recent row
    latest = ServiceStatus.query.order_by(ServiceStatus.fetched_at.desc()).first()
    if latest is None or _is_stale(latest.fetched_at):
        _refresh_service_status(db, ServiceStatus, fetch_service_alerts)

    query = ServiceStatus.query
    if route_id:
        query = query.filter_by(route_id=route_id)
    return query.all()


def _refresh_service_status(db, ServiceStatus, fetch_fn):
    try:
        alerts = fetch_fn()
        if not alerts:
            return
        now = datetime.utcnow()
        route_ids = {a["route_id"] for a in alerts}
        ServiceStatus.query.filter(
            ServiceStatus.route_id.in_(route_ids)
        ).delete(synchronize_session=False)
        for a in alerts:
            db.session.add(ServiceStatus(
                route_id=a["route_id"],
                route_name=a["route_name"],
                status=a["status"],
                alert_text=a["alert_text"],
                fetched_at=now,
            ))
        db.session.commit()
        logger.info("cache_manager: refreshed %d service_status rows", len(alerts))
    except Exception as exc:
        logger.error("cache_manager: failed to refresh service_status: %s", exc)
        db.session.rollback()


# ── Vehicle Positions ─────────────────────────────────────────────────────────

def get_vehicle_positions():
    """Return cached VehiclePosition rows. Re-fetches if stale."""
    from .extensions import db
    from .models import VehiclePosition
    from .mta_client import fetch_vehicle_positions

    latest = VehiclePosition.query.order_by(VehiclePosition.fetched_at.desc()).first()
    if latest is None or _is_stale(latest.fetched_at):
        _refresh_vehicles(db, VehiclePosition, fetch_vehicle_positions)

    return VehiclePosition.query.all()


def _refresh_vehicles(db, VehiclePosition, fetch_fn):
    try:
        positions = fetch_fn()
        if not positions:
            return
        now = datetime.utcnow()
        VehiclePosition.query.delete()
        for p in positions:
            db.session.add(VehiclePosition(
                route_id=p["route_id"],
                vehicle_id=p["vehicle_id"],
                latitude=p["latitude"],
                longitude=p["longitude"],
                fetched_at=now,
            ))
        db.session.commit()
        logger.info("cache_manager: refreshed %d vehicle_position rows", len(positions))
    except Exception as exc:
        logger.error("cache_manager: failed to refresh vehicles: %s", exc)
        db.session.rollback()


# ── Accessibility ─────────────────────────────────────────────────────────────

def get_accessibility(station_id: str = None):
    """Return cached AccessibilityStatus rows. Re-fetches if stale."""
    from .extensions import db
    from .models import AccessibilityStatus
    from .mta_client import fetch_accessibility_status

    latest = AccessibilityStatus.query.order_by(
        AccessibilityStatus.fetched_at.desc()
    ).first()
    if latest is None or _is_stale(latest.fetched_at):
        _refresh_accessibility(db, AccessibilityStatus, fetch_accessibility_status)

    query = AccessibilityStatus.query
    if station_id:
        query = query.filter_by(station_id=station_id)
    return query.all()


def _refresh_accessibility(db, AccessibilityStatus, fetch_fn):
    try:
        items = fetch_fn()
        if not items:
            return
        now = datetime.utcnow()
        station_ids = {i["station_id"] for i in items}
        AccessibilityStatus.query.filter(
            AccessibilityStatus.station_id.in_(station_ids)
        ).delete(synchronize_session=False)
        for i in items:
            db.session.add(AccessibilityStatus(
                station_id=i["station_id"],
                equipment_id=i["equipment_id"],
                equipment_type=i["equipment_type"],
                status=i["status"],
                fetched_at=now,
            ))
        db.session.commit()
        logger.info("cache_manager: refreshed %d accessibility rows", len(items))
    except Exception as exc:
        logger.error("cache_manager: failed to refresh accessibility: %s", exc)
        db.session.rollback()
