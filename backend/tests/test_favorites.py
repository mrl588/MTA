"""Integration tests for /api/favorites endpoints."""
from unittest.mock import patch, MagicMock
import pytest
from flask import g


def _auth_headers():
    return {"Authorization": "Bearer fake-token"}


def _mock_verify(uid="user-123", email="test@example.com"):
    """Patch firebase verify_id_token to return a fake decoded token."""
    mock = MagicMock(return_value={"uid": uid, "email": email})
    return patch("firebase_admin.auth.verify_id_token", mock)


def _patch_firebase_init():
    """Patch _firebase_initialized so the verify_token decorator doesn't 503."""
    return patch("app.firebase._firebase_initialized", True)


def test_get_favorites_unauthenticated(client):
    resp = client.get("/api/favorites")
    assert resp.status_code in (401, 503)


def test_get_favorites_authenticated(client):
    with _patch_firebase_init(), _mock_verify():
        resp = client.get("/api/favorites", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json["data"] == []


def test_add_favorite(client):
    with _patch_firebase_init(), _mock_verify():
        resp = client.post("/api/favorites", json={
            "item_type": "route",
            "item_id": "A",
            "item_name": "A Train",
        }, headers=_auth_headers())
    assert resp.status_code == 201
    assert resp.json["data"]["item_id"] == "A"


def test_add_favorite_missing_fields(client):
    with _patch_firebase_init(), _mock_verify():
        resp = client.post("/api/favorites", json={"item_type": "route"}, headers=_auth_headers())
    assert resp.status_code == 400


def test_add_duplicate_favorite(client):
    with _patch_firebase_init(), _mock_verify():
        client.post("/api/favorites", json={
            "item_type": "route", "item_id": "B", "item_name": "B Train"
        }, headers=_auth_headers())
        resp = client.post("/api/favorites", json={
            "item_type": "route", "item_id": "B", "item_name": "B Train"
        }, headers=_auth_headers())
    assert resp.status_code == 409


def test_remove_favorite(client):
    with _patch_firebase_init(), _mock_verify():
        add = client.post("/api/favorites", json={
            "item_type": "station", "item_id": "S1", "item_name": "Times Sq"
        }, headers=_auth_headers())
        fav_id = add.json["data"]["id"]
        resp = client.delete(f"/api/favorites/{fav_id}", headers=_auth_headers())
    assert resp.status_code == 200


def test_toggle_alerts(client):
    with _patch_firebase_init(), _mock_verify():
        add = client.post("/api/favorites", json={
            "item_type": "route", "item_id": "C", "item_name": "C Train"
        }, headers=_auth_headers())
        fav_id = add.json["data"]["id"]
        resp = client.patch(f"/api/favorites/{fav_id}/alerts",
                            json={"alerts_enabled": True},
                            headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json["data"]["alerts_enabled"] is True
