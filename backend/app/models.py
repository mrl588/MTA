from datetime import datetime
from .extensions import db


class ServiceStatus(db.Model):
    __tablename__ = "service_status"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Text, nullable=False, index=True)
    route_name = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False, default="Good Service")
    alert_text = db.Column(db.Text, nullable=True)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        # Include 'summary' and 'severity' so the frontend api.ts toRouteStatus() mapper
        # can pick them up directly without relying on fallback inference.
        severity_map = {
            "Good Service": "good",
            "Delays": "minor",
            "Service Change": "minor",
            "Suspended": "major",
        }
        return {
            "route_id": self.route_id,
            "route_name": self.route_name,
            "status": self.status,
            "summary": self.alert_text or self.status,   # frontend looks for 'summary' first
            "severity": severity_map.get(self.status, "unknown"),
            "alert_text": self.alert_text,
            "fetched_at": self.fetched_at.isoformat(),
        }


class VehiclePosition(db.Model):
    __tablename__ = "vehicle_positions"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Text, nullable=False, index=True)
    vehicle_id = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "route_id": self.route_id,
            "vehicle_id": self.vehicle_id,
            "lat": self.latitude,        # primary keys the frontend expects
            "lon": self.longitude,
            "latitude": self.latitude,   # kept for any other consumers
            "longitude": self.longitude,
            "fetched_at": self.fetched_at.isoformat(),
        }


class AccessibilityStatus(db.Model):
    __tablename__ = "accessibility_status"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Text, nullable=False, index=True)
    equipment_id = db.Column(db.Text, nullable=False)
    equipment_type = db.Column(db.Text, nullable=False)  # 'elevator' | 'escalator'
    status = db.Column(db.Text, nullable=False)           # 'Operational' | 'Out of Service' | 'Scheduled Maintenance'
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "equipment_id": self.equipment_id,
            "equipment_type": self.equipment_type,
            "status": self.status,
            "fetched_at": self.fetched_at.isoformat(),
        }


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    firebase_uid = db.Column(db.Text, unique=True, nullable=False)
    email = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    favorites = db.relationship("Favorite", backref="user", lazy=True, cascade="all, delete-orphan")


class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_type = db.Column(db.Text, nullable=False)   # 'route' | 'station'
    item_id = db.Column(db.Text, nullable=False)
    item_name = db.Column(db.Text, nullable=False)
    alerts_enabled = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "alerts_enabled": bool(self.alerts_enabled),
            "created_at": self.created_at.isoformat(),
        }
