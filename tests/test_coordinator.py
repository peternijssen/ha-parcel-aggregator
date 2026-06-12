"""Tests for the Parcel Aggregator's parsing and aggregation helpers."""
from datetime import datetime, timezone

from custom_components.parcel_aggregator.coordinator import (
    aggregate_min_timestamp,
    aggregate_sum,
    parse_int_state,
    parse_timestamp_state,
)


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
# aggregate_min_timestamp
# ---------------------------------------------------------------------------


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def test_min_timestamp_picks_earliest():
    a = _ts("2026-06-15T10:00:00+00:00")
    b = _ts("2026-06-13T08:00:00+00:00")
    c = _ts("2026-06-14T12:00:00+00:00")
    result = aggregate_min_timestamp([("DHL", a), ("PostNL", b), ("DPD", c)])
    assert result["value"] == b
    assert result["by_carrier"] == {"DHL": a, "PostNL": b, "DPD": c}


def test_min_timestamp_keeps_earliest_per_carrier():
    earlier = _ts("2026-06-13T08:00:00+00:00")
    later = _ts("2026-06-15T08:00:00+00:00")
    result = aggregate_min_timestamp([("PostNL", later), ("PostNL", earlier)])
    assert result["value"] == earlier
    assert result["by_carrier"] == {"PostNL": earlier}


def test_min_timestamp_skips_none():
    a = _ts("2026-06-15T10:00:00+00:00")
    result = aggregate_min_timestamp([("DHL", None), ("PostNL", a)])
    assert result["value"] == a
    assert result["by_carrier"] == {"PostNL": a}


def test_min_timestamp_returns_none_when_no_data():
    result = aggregate_min_timestamp([])
    assert result == {"value": None, "by_carrier": {}}


def test_min_timestamp_returns_none_when_all_none():
    result = aggregate_min_timestamp([("DHL", None), ("PostNL", None)])
    assert result["value"] is None
    assert result["by_carrier"] == {}
