"""Tests for the Parcel Aggregator sensor properties."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from custom_components.parcel_aggregator.sensor import (
    ParcelsAwaitingPickupSensor,
    ParcelsDeliveredSensor,
    ParcelsIncomingSensor,
    ParcelsNextDeliverySensor,
    ParcelsOutgoingSensor,
)


def _coordinator(data: dict | None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_update_success = data is not None
    return coordinator


# ---------------------------------------------------------------------------
# Summary sensors (incoming / outgoing / delivered / awaiting_pickup)
# ---------------------------------------------------------------------------


def test_incoming_sensor_reports_total_and_parcels():
    parcels = [{"barcode": "A"}, {"barcode": "B"}]
    sensor = ParcelsIncomingSensor(
        _coordinator({"incoming": {"total": 2, "by_carrier": {"DHL": 2}, "parcels": parcels}})
    )
    assert sensor.native_value == 2
    attrs = sensor.extra_state_attributes
    assert attrs["by_carrier"] == {"DHL": 2}
    assert attrs["parcels"] == parcels


def test_outgoing_sensor_exposes_parcel_list_on_parcels_key():
    parcels = [{"barcode": "X"}]
    sensor = ParcelsOutgoingSensor(
        _coordinator({"outgoing": {"total": 1, "by_carrier": {"PostNL": 1}, "parcels": parcels}})
    )
    assert sensor.native_value == 1
    attrs = sensor.extra_state_attributes
    # Every aggregator summary sensor uses the same "parcels" attribute key
    # so templates can iterate uniformly across incoming / outgoing / delivered.
    assert attrs["parcels"] == parcels
    assert "shipments" not in attrs


def test_delivered_sensor_zero_when_no_data():
    sensor = ParcelsDeliveredSensor(_coordinator(None))
    assert sensor.native_value == 0
    assert sensor.extra_state_attributes == {"by_carrier": {}, "parcels": []}


def test_awaiting_pickup_sensor_reports_pickup_parcels():
    parcels = [{"barcode": "P", "pickup": True}]
    sensor = ParcelsAwaitingPickupSensor(
        _coordinator(
            {"awaiting_pickup": {"total": 1, "by_carrier": {"DPD": 1}, "parcels": parcels}}
        )
    )
    assert sensor.native_value == 1
    assert sensor.extra_state_attributes["parcels"] == parcels


# ---------------------------------------------------------------------------
# Next delivery sensor
# ---------------------------------------------------------------------------


def test_next_delivery_sensor_returns_value_and_parcel():
    when = datetime(2026, 6, 16, 10, 0, tzinfo=timezone.utc)
    sensor = ParcelsNextDeliverySensor(
        _coordinator(
            {
                "next_delivery": {
                    "value": when,
                    "by_carrier": {"DHL": when},
                    "parcel": {"barcode": "X", "carrier": "DHL"},
                }
            }
        )
    )
    assert sensor.native_value == when
    attrs = sensor.extra_state_attributes
    # by_carrier datetimes are serialized to ISO strings on the attribute
    assert attrs["by_carrier"] == {"DHL": when.isoformat()}
    assert attrs["parcel"] == {"barcode": "X", "carrier": "DHL"}


def test_next_delivery_sensor_handles_missing_data():
    sensor = ParcelsNextDeliverySensor(_coordinator(None))
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {"by_carrier": {}, "parcel": None}


def test_next_delivery_sensor_keeps_parcel_out_of_recorder():
    """The single ``parcel`` dict (which may carry a large history) is excluded
    from the recorder, mirroring how the list sensors exclude ``parcels``."""
    sensor = ParcelsNextDeliverySensor(_coordinator(None))
    assert "parcel" in sensor._unrecorded_attributes


def test_summary_sensors_keep_parcels_out_of_recorder():
    coord = _coordinator(None)
    for sensor in (
        ParcelsIncomingSensor(coord),
        ParcelsOutgoingSensor(coord),
        ParcelsDeliveredSensor(coord),
        ParcelsAwaitingPickupSensor(coord),
    ):
        assert "parcels" in sensor._unrecorded_attributes


def test_sensors_share_aggregator_device_identifiers():
    """All summary sensors and the next-delivery sensor sit under one device."""
    coord = _coordinator(None)
    sensors = [
        ParcelsIncomingSensor(coord),
        ParcelsOutgoingSensor(coord),
        ParcelsDeliveredSensor(coord),
        ParcelsAwaitingPickupSensor(coord),
        ParcelsNextDeliverySensor(coord),
    ]
    identifiers_per_sensor = [s.device_info["identifiers"] for s in sensors]
    assert all(ids == identifiers_per_sensor[0] for ids in identifiers_per_sensor)
