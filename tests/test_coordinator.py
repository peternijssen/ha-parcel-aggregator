"""Tests for the Parcel Aggregator's parsing and aggregation helpers."""
from datetime import datetime, timezone

import pytest

from custom_components.parcel_aggregator.coordinator import (
    aggregate_sum,
    awaiting_pickup_from,
    next_delivery_from,
    parse_int_state,
    parse_timestamp_state,
    sort_parcels_by_ts,
    strip_raw,
)


def _parcel(
    carrier: str = "DHL",
    barcode: str = "ABC",
    sender: str = "Sender",
    planned_from: str | None = None,
    pickup: bool = False,
    pickup_point: str | None = None,
    delivered: bool = False,
    delivered_at: str | None = None,
    raw: dict | None = None,
) -> dict:
    return {
        "carrier": carrier,
        "barcode": barcode,
        "sender": sender,
        "status": "IN_DELIVERY",
        "delivered": delivered,
        "delivered_at": delivered_at,
        "planned_from": planned_from,
        "planned_to": None,
        "pickup": pickup,
        "pickup_point": pickup_point,
        "url": None,
        "raw": raw if raw is not None else {"_": "carrier-specific"},
    }


# ---------------------------------------------------------------------------
# parse_int_state
# ---------------------------------------------------------------------------


def test_parse_int_parses_plain_number():
    assert parse_int_state("5") == 5


def test_parse_int_handles_float_strings():
    assert parse_int_state("5.0") == 5


def test_parse_int_returns_none_for_unavailable():
    assert parse_int_state("unavailable") is None
    assert parse_int_state("unknown") is None
    assert parse_int_state("") is None
    assert parse_int_state(None) is None


def test_parse_int_returns_none_for_garbage():
    assert parse_int_state("not a number") is None


# ---------------------------------------------------------------------------
# parse_timestamp_state
# ---------------------------------------------------------------------------


def test_parse_timestamp_parses_iso_with_tz():
    dt = parse_timestamp_state("2026-06-12T10:00:00+02:00")
    assert dt is not None
    assert dt.year == 2026 and dt.hour == 10


def test_parse_timestamp_parses_z_suffix():
    dt = parse_timestamp_state("2026-06-12T10:00:00Z")
    assert dt == datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)


def test_parse_timestamp_returns_none_for_unavailable():
    assert parse_timestamp_state("unavailable") is None
    assert parse_timestamp_state(None) is None


def test_parse_timestamp_returns_none_for_garbage():
    assert parse_timestamp_state("not a date") is None


def test_parse_timestamp_treats_naive_iso_as_utc():
    # Regression: when one source carrier emits "2026-06-12T10:00:00" without
    # a tz suffix and another emits "...Z", the downstream sort crashed with
    # "can't compare offset-naive and offset-aware datetimes". Naive values
    # must come back tagged so every result is mutually comparable.
    dt = parse_timestamp_state("2026-06-12T10:00:00")
    assert dt == datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# aggregate_sum
# ---------------------------------------------------------------------------


def test_sum_aggregates_across_carriers():
    result = aggregate_sum([("DHL", 2), ("PostNL", 3), ("DPD", 1)])
    assert result["total"] == 6
    assert result["by_carrier"] == {"DHL": 2, "PostNL": 3, "DPD": 1}
    assert result["any_available"] is True


def test_sum_sums_multiple_accounts_per_carrier():
    result = aggregate_sum([("PostNL", 2), ("PostNL", 3)])
    assert result["total"] == 5
    assert result["by_carrier"] == {"PostNL": 5}


def test_sum_skips_none_values():
    result = aggregate_sum([("DHL", 2), ("PostNL", None), ("DPD", 3)])
    assert result["total"] == 5
    assert result["by_carrier"] == {"DHL": 2, "DPD": 3}
    assert result["any_available"] is True


def test_sum_marks_unavailable_when_no_sources():
    result = aggregate_sum([])
    assert result == {"total": 0, "by_carrier": {}, "any_available": False}


def test_sum_marks_unavailable_when_all_none():
    result = aggregate_sum([("DHL", None), ("PostNL", None)])
    assert result["any_available"] is False
    assert result["total"] == 0


# ---------------------------------------------------------------------------
# strip_raw
# ---------------------------------------------------------------------------


def test_strip_raw_removes_raw_key():
    parcel = _parcel(raw={"big": "payload"})
    assert "raw" in parcel
    stripped = strip_raw(parcel)
    assert "raw" not in stripped
    assert stripped["carrier"] == "DHL"
    # original is untouched
    assert "raw" in parcel


def test_strip_raw_is_noop_when_raw_missing():
    parcel = {"carrier": "DHL", "barcode": "ABC"}
    assert strip_raw(parcel) == parcel


def test_strip_raw_keeps_top_level_history():
    """The opt-in history timeline is a top-level field, so it survives
    strip_raw() and flows through the aggregator unchanged."""
    history = [{"timestamp": "2026-06-24T17:23:13Z", "status": "delivered", "raw_status": "DELIVERED"}]
    parcel = {**_parcel(), "history": history}
    stripped = strip_raw(parcel)
    assert "raw" not in stripped
    assert stripped["history"] == history


def test_next_delivery_keeps_history_on_the_parcel():
    history = [{"timestamp": "2026-06-20T09:00:00Z", "status": "in_transit", "raw_status": "PARCEL_SORTED_AT_HUB"}]
    parcel = {**_parcel(planned_from="2026-06-20T09:00:00Z"), "history": history}
    result = next_delivery_from([parcel])
    assert result["parcel"]["history"] == history
    assert "raw" not in result["parcel"]


# ---------------------------------------------------------------------------
# sort_parcels_by_ts
# ---------------------------------------------------------------------------


def test_sort_parcels_orders_ascending_by_planned_from():
    parcels = [
        _parcel(barcode="late", planned_from="2026-06-15T10:00:00+00:00"),
        _parcel(barcode="early", planned_from="2026-06-13T08:00:00+00:00"),
        _parcel(barcode="mid", planned_from="2026-06-14T12:00:00+00:00"),
    ]
    ordered = [p["barcode"] for p in sort_parcels_by_ts(parcels, "planned_from")]
    assert ordered == ["early", "mid", "late"]


def test_sort_parcels_orders_descending_for_delivered_at():
    parcels = [
        _parcel(barcode="oldest", delivered=True, delivered_at="2026-06-13T08:00:00+00:00"),
        _parcel(barcode="newest", delivered=True, delivered_at="2026-06-15T10:00:00+00:00"),
        _parcel(barcode="mid", delivered=True, delivered_at="2026-06-14T12:00:00+00:00"),
    ]
    ordered = [p["barcode"] for p in sort_parcels_by_ts(parcels, "delivered_at", descending=True)]
    assert ordered == ["newest", "mid", "oldest"]


def test_sort_parcels_keeps_missing_timestamps_at_end():
    parcels = [
        _parcel(barcode="no-ts-1", planned_from=None),
        _parcel(barcode="early", planned_from="2026-06-13T08:00:00+00:00"),
        _parcel(barcode="no-ts-2", planned_from="garbage"),
        _parcel(barcode="late", planned_from="2026-06-15T10:00:00+00:00"),
    ]
    ordered = [p["barcode"] for p in sort_parcels_by_ts(parcels, "planned_from")]
    assert ordered[:2] == ["early", "late"]
    assert set(ordered[2:]) == {"no-ts-1", "no-ts-2"}


def test_sort_parcels_missing_timestamps_stay_at_end_when_descending():
    parcels = [
        _parcel(barcode="no-ts", delivered=True, delivered_at=None),
        _parcel(barcode="newer", delivered=True, delivered_at="2026-06-15T10:00:00+00:00"),
        _parcel(barcode="older", delivered=True, delivered_at="2026-06-13T10:00:00+00:00"),
    ]
    ordered = [p["barcode"] for p in sort_parcels_by_ts(parcels, "delivered_at", descending=True)]
    assert ordered == ["newer", "older", "no-ts"]


def test_sort_parcels_empty_input_returns_empty_list():
    assert sort_parcels_by_ts([], "planned_from") == []


# ---------------------------------------------------------------------------
# next_delivery_from
# ---------------------------------------------------------------------------


def test_next_delivery_picks_earliest_across_carriers():
    parcels = [
        _parcel(carrier="DHL", barcode="A", planned_from="2026-06-15T10:00:00+00:00"),
        _parcel(carrier="PostNL", barcode="B", planned_from="2026-06-13T08:00:00+00:00"),
        _parcel(carrier="DPD", barcode="C", planned_from="2026-06-14T12:00:00+00:00"),
    ]
    result = next_delivery_from(parcels)
    assert result["value"] == datetime(2026, 6, 13, 8, 0, 0, tzinfo=timezone.utc)
    assert result["parcel"]["barcode"] == "B"
    assert result["parcel"]["carrier"] == "PostNL"
    # raw is stripped from the surfaced parcel
    assert "raw" not in result["parcel"]


def test_next_delivery_by_carrier_keeps_earliest_per_carrier():
    parcels = [
        _parcel(carrier="DHL", barcode="A", planned_from="2026-06-15T10:00:00+00:00"),
        _parcel(carrier="DHL", barcode="B", planned_from="2026-06-13T10:00:00+00:00"),
    ]
    result = next_delivery_from(parcels)
    assert result["by_carrier"]["DHL"] == datetime(2026, 6, 13, 10, 0, 0, tzinfo=timezone.utc)


def test_next_delivery_skips_parcels_without_planned_from():
    parcels = [
        _parcel(carrier="DHL", barcode="A", planned_from=None),
        _parcel(carrier="PostNL", barcode="B", planned_from="2026-06-13T10:00:00+00:00"),
    ]
    result = next_delivery_from(parcels)
    assert result["parcel"]["barcode"] == "B"


def test_next_delivery_returns_none_when_no_data():
    result = next_delivery_from([])
    assert result == {"value": None, "by_carrier": {}, "parcel": None}


def test_next_delivery_returns_none_when_no_timestamps():
    result = next_delivery_from([_parcel(planned_from=None)])
    assert result["value"] is None
    assert result["parcel"] is None


# ---------------------------------------------------------------------------
# awaiting_pickup_from
# ---------------------------------------------------------------------------


def test_awaiting_pickup_counts_pickup_parcels():
    parcels = [
        _parcel(carrier="DHL", barcode="A", pickup=True, pickup_point="ServicePoint A"),
        _parcel(carrier="PostNL", barcode="B", pickup=True),
        _parcel(carrier="DHL", barcode="C", pickup=False),
    ]
    result = awaiting_pickup_from(parcels)
    assert result["total"] == 2
    assert result["by_carrier"] == {"DHL": 1, "PostNL": 1}
    assert {p["barcode"] for p in result["parcels"]} == {"A", "B"}


def test_awaiting_pickup_excludes_delivered():
    parcels = [
        _parcel(carrier="DHL", barcode="A", pickup=True, delivered=True),
        _parcel(carrier="DHL", barcode="B", pickup=True, delivered=False),
    ]
    result = awaiting_pickup_from(parcels)
    assert result["total"] == 1
    assert result["parcels"][0]["barcode"] == "B"


def test_awaiting_pickup_returns_zero_when_no_data():
    result = awaiting_pickup_from([])
    assert result == {"total": 0, "by_carrier": {}, "parcels": []}


def test_awaiting_pickup_strips_raw_from_list():
    parcels = [_parcel(pickup=True, raw={"big": "payload"})]
    result = awaiting_pickup_from(parcels)
    assert "raw" not in result["parcels"][0]


# ---------------------------------------------------------------------------
# Source discovery — bucket assignment by unique_id suffix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_buckets_sources_by_suffix(hass):
    """A carrier's outgoing-delivered sensor must land in its own bucket, not
    in ``delivered`` — its unique_id also ends with ``_delivered_parcels``."""
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.parcel_aggregator.const import DOMAIN
    from custom_components.parcel_aggregator.coordinator import (
        ParcelAggregatorCoordinator,
    )

    reg = er.async_get(hass)

    def _add(unique_id: str) -> str:
        return reg.async_get_or_create("sensor", "dhl_nl", unique_id).entity_id

    incoming = _add("acc_incoming_parcels")
    outgoing = _add("acc_outgoing_parcels")
    delivered = _add("acc_delivered_parcels")
    outgoing_delivered = _add("acc_outgoing_delivered_parcels")

    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = ParcelAggregatorCoordinator(hass, entry)
    coordinator._discover()

    assert incoming in coordinator._sources["incoming"]
    assert outgoing in coordinator._sources["outgoing"]
    assert delivered in coordinator._sources["delivered"]
    assert outgoing_delivered in coordinator._sources["outgoing_delivered"]
    # Regression: the outgoing-delivered sensor must NOT be swallowed by the
    # shorter ``_delivered_parcels`` suffix.
    assert outgoing_delivered not in coordinator._sources["delivered"]
