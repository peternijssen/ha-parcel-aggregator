"""Tests for the per-carrier event re-emit layer."""
import pytest

from custom_components.parcel_aggregator.const import (
    CARRIER_EVENT_PREFIXES,
    DOMAIN,
    EVENT_PARCEL_REGISTERED,
    EVENT_PARCEL_STATUS_CHANGED,
    ParcelStatus,
)


def _add_entry(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)
    return entry


def _capture(hass, event_type: str) -> list:
    """Subscribe to ``event_type`` and return the list captured events accumulate into."""
    events: list = []

    def _on_event(event):
        events.append(event)

    hass.bus.async_listen(event_type, _on_event)
    return events


@pytest.mark.asyncio
async def test_dhl_registered_event_is_reemitted_unified(hass):
    """A dhl_nl_parcel_registered event triggers parcel_aggregator_parcel_registered."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_PARCEL_REGISTERED)

    hass.bus.async_fire(
        "dhl_nl_parcel_registered",
        {
            "carrier": "DHL",
            "barcode": "BARCODE-1",
            "status": ParcelStatus.REGISTERED,
            "raw_status": "DATA_RECEIVED",
            "raw": {"big": "payload"},
        },
    )
    await hass.async_block_till_done()

    assert len(captured) == 1
    payload = captured[0].data
    assert payload["carrier"] == "DHL"
    assert payload["barcode"] == "BARCODE-1"
    assert payload["status"] == ParcelStatus.REGISTERED
    assert payload["raw_status"] == "DATA_RECEIVED"
    # raw payload is stripped to keep event size small
    assert "raw" not in payload


@pytest.mark.asyncio
async def test_dhl_status_changed_event_is_reemitted_unified(hass):
    """A dhl_nl_parcel_status_changed event triggers the unified status_changed event."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_PARCEL_STATUS_CHANGED)

    hass.bus.async_fire(
        "dhl_nl_parcel_status_changed",
        {
            "carrier": "DHL",
            "barcode": "BARCODE-2",
            "status": ParcelStatus.OUT_FOR_DELIVERY,
            "old_status": ParcelStatus.IN_TRANSIT,
            "new_status": ParcelStatus.OUT_FOR_DELIVERY,
            "raw": {"big": "payload"},
        },
    )
    await hass.async_block_till_done()

    assert len(captured) == 1
    payload = captured[0].data
    assert payload["old_status"] == ParcelStatus.IN_TRANSIT
    assert payload["new_status"] == ParcelStatus.OUT_FOR_DELIVERY
    assert "raw" not in payload


@pytest.mark.asyncio
async def test_unknown_carrier_event_is_ignored(hass):
    """Events from a carrier not in CARRIER_EVENT_PREFIXES do not get re-emitted."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "made_up" not in CARRIER_EVENT_PREFIXES.values()

    captured = _capture(hass, EVENT_PARCEL_REGISTERED)
    hass.bus.async_fire(
        "made_up_parcel_registered", {"carrier": "MadeUp", "barcode": "X"}
    )
    await hass.async_block_till_done()

    assert captured == []


@pytest.mark.asyncio
async def test_unload_stops_event_reemission(hass):
    """After unload, carrier events no longer trigger re-emitted events."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_PARCEL_REGISTERED)
    hass.bus.async_fire(
        "dhl_nl_parcel_registered", {"carrier": "DHL", "barcode": "B"}
    )
    await hass.async_block_till_done()

    assert captured == []
