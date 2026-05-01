"""Tests for GET /api/status endpoints."""
from datetime import datetime
from unittest.mock import patch
from app.extensions import db
from app.models import ServiceStatus


def _no_refresh():
    """Patch _is_stale so cache_manager never calls MTA API during tests."""
    return patch("app.cache_manager._is_stale", return_value=False)


def test_all_statuses_empty(app, client):
    # Patch at the route import level so no live data comes in
    with patch("app.routes.status.get_service_status", return_value=[]):
        resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json["data"] == []


def test_all_statuses_returns_data(app, client):
    with app.app_context():
        db.session.add(ServiceStatus(
            route_id="A",
            route_name="A Train",
            status="Delays",
            alert_text="Signal problems at Jay St",
            fetched_at=datetime.utcnow(),
        ))
        db.session.commit()

    with _no_refresh():
        resp = client.get("/api/status")

    assert resp.status_code == 200
    data = [r for r in resp.json["data"] if r["route_id"] == "A"]
    assert len(data) >= 1


def test_single_route_found(app, client):
    with app.app_context():
        db.session.add(ServiceStatus(
            route_id="AA",
            route_name="AA Train",
            status="Delays",
            alert_text="Signal problems",
            fetched_at=datetime.utcnow(),
        ))
        db.session.commit()

    with _no_refresh():
        resp = client.get("/api/status/AA")

    assert resp.status_code == 200
    assert resp.json["data"]["status"] == "Delays"
    assert resp.json["data"]["severity"] == "minor"
    assert "summary" in resp.json["data"]


def test_single_route_not_found(client):
    with _no_refresh():
        resp = client.get("/api/status/ZZZZ")
    assert resp.status_code == 404
