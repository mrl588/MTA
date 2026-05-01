"""Unit tests for the MTA API client helper functions."""
import pytest
from app.mta_client import _classify_alert, _map_equipment_status


class TestClassifyAlert:
    def test_suspended(self):
        assert _classify_alert("No service on the A train") == "Suspended"

    def test_delays(self):
        assert _classify_alert("Expect delays due to signal problems") == "Delays"

    def test_service_change(self):
        assert _classify_alert("Trains will skip 34 St due to reroute") == "Service Change"

    def test_good_service(self):
        assert _classify_alert("Planned work this weekend") == "Good Service"

    def test_case_insensitive(self):
        assert _classify_alert("SUSPEND all service") == "Suspended"


class TestMapEquipmentStatus:
    def test_operational_empty(self):
        assert _map_equipment_status("") == "Operational"

    def test_operational_serving(self):
        assert _map_equipment_status("serving all floors") == "Operational"

    def test_scheduled_maintenance(self):
        assert _map_equipment_status("scheduled outage") == "Scheduled Maintenance"

    def test_out_of_service(self):
        assert _map_equipment_status("broken") == "Out of Service"
