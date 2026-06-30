"""Tests for the Parcel Aggregator combined deliveries calendar."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from custom_components.parcel_aggregator.calendar import ParcelAggregatorCalendar


def _make_coordinator(parcels: list[dict]) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = {"incoming": {"parcels": parcels}}
    return coordinator


def _parcel(
    carrier: str,
    barcode: str,
    planned_from: str | None = None,
    planned_to: str | None = None,
    pickup: bool = False,
    pickup_point: str | None = None,
) -> dict:
    return {
        "carrier": carrier,
        "barcode": barcode,
        "sender": "Example Sender",
        "status": "out_for_delivery",
        "planned_from": planned_from,
        "planned_to": planned_to,
        "pickup": pickup,
        "pickup_point": pickup_point,
        "url": "https://track/123",
    }


def _calendar(parcels: list[dict]) -> ParcelAggregatorCalendar:
    return ParcelAggregatorCalendar(_make_coordinator(parcels))


def test_event_returns_earliest_and_prefixes_carrier():
    cal = _calendar([
        _parcel("DPD", "LATE", planned_from="2099-01-02T10:00:00Z"),
        _parcel("DHL", "SOON", planned_from="2099-01-01T10:00:00Z"),
    ])
    event = cal.event
    assert event is not None
    assert event.uid == "DHL_SOON"
    assert event.summary == "DHL: Example Sender"


def test_event_none_when_no_planned_parcels():
    cal = _calendar([_parcel("DHL", "NOPLAN")])
    assert cal.event is None


def test_moment_gets_one_hour_duration():
    cal = _calendar([_parcel("DHL", "A", planned_from="2099-01-01T10:00:00Z")])
    events = cal._events()
    assert len(events) == 1
    assert events[0].end == datetime(2099, 1, 1, 11, 0, tzinfo=timezone.utc)


def test_interval_uses_window():
    cal = _calendar([
        _parcel(
            "DHL",
            "A",
            planned_from="2099-01-01T10:00:00Z",
            planned_to="2099-01-01T12:00:00Z",
        )
    ])
    assert cal._events()[0].end == datetime(2099, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_pickup_parcel_sets_location():
    cal = _calendar([
        _parcel(
            "PostNL",
            "A",
            planned_from="2099-01-01T10:00:00Z",
            pickup=True,
            pickup_point="PostNL Punt",
        )
    ])
    assert cal._events()[0].location == "PostNL Punt"


def test_events_merge_multiple_carriers():
    cal = _calendar([
        _parcel("DHL", "A", planned_from="2099-01-01T10:00:00Z"),
        _parcel("DPD", "B", planned_from="2099-01-03T10:00:00Z"),
        _parcel("PostNL", "C", planned_from="2099-01-02T10:00:00Z"),
    ])
    assert {e.uid for e in cal._events()} == {"DHL_A", "DPD_B", "PostNL_C"}


async def test_get_events_filters_by_range():
    cal = _calendar([
        _parcel("DHL", "PAST", planned_from="2000-01-01T10:00:00Z"),
        _parcel("DPD", "FUTURE", planned_from="2099-01-01T10:00:00Z"),
    ])
    start = datetime(2098, 1, 1, tzinfo=timezone.utc)
    end = datetime(2100, 1, 1, tzinfo=timezone.utc)
    events = await cal.async_get_events(MagicMock(), start, end)
    assert {e.uid for e in events} == {"DPD_FUTURE"}
