import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Register polling jobs and start the background scheduler."""

    def poll_service_status():
        with app.app_context():
            from .mta_client import fetch_service_alerts
            from .extensions import db
            from .models import ServiceStatus

            alerts = fetch_service_alerts()
            if not alerts:
                logger.warning("poll_service_status: no data returned from MTA API")
                return

            now = datetime.utcnow()
            # Upsert: delete existing rows for affected routes, then insert fresh ones
            route_ids = {a["route_id"] for a in alerts}
            ServiceStatus.query.filter(ServiceStatus.route_id.in_(route_ids)).delete(synchronize_session=False)
            for a in alerts:
                db.session.add(ServiceStatus(
                    route_id=a["route_id"],
                    route_name=a["route_name"],
                    status=a["status"],
                    alert_text=a["alert_text"],
                    fetched_at=now,
                ))
            db.session.commit()
            logger.info("poll_service_status: upserted %d rows", len(alerts))

    def poll_vehicle_positions():
        with app.app_context():
            from .mta_client import fetch_vehicle_positions
            from .extensions import db
            from .models import VehiclePosition

            positions = fetch_vehicle_positions()
            if not positions:
                logger.warning("poll_vehicle_positions: no data returned from MTA API")
                return

            now = datetime.utcnow()
            # Replace all vehicle positions on each poll (positions change constantly)
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
            logger.info("poll_vehicle_positions: upserted %d rows", len(positions))

    def poll_accessibility():
        with app.app_context():
            from .mta_client import fetch_accessibility_status
            from .extensions import db
            from .models import AccessibilityStatus

            items = fetch_accessibility_status()
            if not items:
                logger.warning("poll_accessibility: no data returned from MTA API")
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
            logger.info("poll_accessibility: upserted %d rows", len(items))

    _scheduler.add_job(poll_service_status, "interval", seconds=30, id="service_status")
    _scheduler.add_job(poll_vehicle_positions, "interval", seconds=30, id="vehicle_positions")
    _scheduler.add_job(poll_accessibility, "interval", seconds=60, id="accessibility")

    _scheduler.start()
    logger.info("Background scheduler started.")
