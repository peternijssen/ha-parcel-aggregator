"""Tests for the per-carrier event re-emit layer."""
import pytest

from custom_components.parcel_aggregator.const import (
    CARRIER_EVENT_PREFIXES,
    DOMAIN,
    EVENT_OUTGOING_PARCEL_DELIVERED,
    EVENT_OUTGOING_PARCEL_STATUS_CHANGED,
    EVENT_PARCEL_DELIVERY_TIME_CHANGED,
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
async def test_dpd_registered_event_is_reemitted_unified(hass):
    """A dpd_parcel_registered event triggers parcel_aggregator_parcel_registered."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_PARCEL_REGISTERED)

    hass.bus.async_fire(
        "dpd_parcel_registered",
        {
            "carrier": "DPD",
            "barcode": "01XXXXXXXXXXXX",
            "status": ParcelStatus.REGISTERED,
            "raw_status": "ORDER_CREATED",
            "raw": {"big": "payload"},
        },
    )
    await hass.async_block_till_done()

    assert len(captured) == 1
    payload = captured[0].data
    assert payload["carrier"] == "DPD"
    assert payload["barcode"] == "01XXXXXXXXXXXX"
    assert payload["status"] == ParcelStatus.REGISTERED
    assert "raw" not in payload


@pytest.mark.asyncio
async def test_postnl_registered_event_is_reemitted_unified(hass):
    """A postnl_parcel_registered event triggers parcel_aggregator_parcel_registered."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_PARCEL_REGISTERED)

    hass.bus.async_fire(
        "postnl_parcel_registered",
        {
            "carrier": "PostNL",
            "barcode": "3SABC",
            "status": ParcelStatus.REGISTERED,
            "raw_status": "Pakket is aangemeld",
            "raw": {"big": "payload"},
        },
    )
    await hass.async_block_till_done()

    assert len(captured) == 1
    payload = captured[0].data
    assert payload["carrier"] == "PostNL"
    assert payload["barcode"] == "3SABC"
    assert payload["status"] == ParcelStatus.REGISTERED
    assert "raw" not in payload


@pytest.mark.asyncio
async def test_dhl_delivery_time_changed_event_is_reemitted_unified(hass):
    """A dhl_nl_parcel_delivery_time_changed event triggers the unified event."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_PARCEL_DELIVERY_TIME_CHANGED)

    hass.bus.async_fire(
        "dhl_nl_parcel_delivery_time_changed",
        {
            "carrier": "DHL",
            "barcode": "BARCODE-3",
            "status": ParcelStatus.OUT_FOR_DELIVERY,
            "old_planned_from": "2026-06-27T10:00:00+02:00",
            "new_planned_from": "2026-06-27T14:00:00+02:00",
            "old_planned_to": None,
            "new_planned_to": None,
            "raw": {"big": "payload"},
        },
    )
    await hass.async_block_till_done()

    assert len(captured) == 1
    payload = captured[0].data
    assert payload["barcode"] == "BARCODE-3"
    assert payload["new_planned_from"] == "2026-06-27T14:00:00+02:00"
    assert "raw" not in payload


@pytest.mark.asyncio
async def test_postnl_outgoing_status_changed_is_reemitted_unified(hass):
    """A <carrier>_outgoing_parcel_status_changed re-emits under the unified name."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_OUTGOING_PARCEL_STATUS_CHANGED)

    hass.bus.async_fire(
        "postnl_outgoing_parcel_status_changed",
        {
            "carrier": "PostNL",
            "barcode": "SENT-1",
            "status": ParcelStatus.IN_TRANSIT,
            "old_status": ParcelStatus.REGISTERED,
            "new_status": ParcelStatus.IN_TRANSIT,
            "raw": {"big": "payload"},
        },
    )
    await hass.async_block_till_done()

    assert len(captured) == 1
    payload = captured[0].data
    assert payload["carrier"] == "PostNL"
    assert payload["barcode"] == "SENT-1"
    assert payload["old_status"] == ParcelStatus.REGISTERED
    assert payload["new_status"] == ParcelStatus.IN_TRANSIT
    assert "raw" not in payload


@pytest.mark.asyncio
async def test_dhl_outgoing_delivered_is_reemitted_unified(hass):
    """A <carrier>_outgoing_parcel_delivered re-emits under the unified name."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_OUTGOING_PARCEL_DELIVERED)

    hass.bus.async_fire(
        "dhl_nl_outgoing_parcel_delivered",
        {
            "carrier": "DHL",
            "barcode": "RETURN-1",
            "status": ParcelStatus.DELIVERED,
            "raw": {"big": "payload"},
        },
    )
    await hass.async_block_till_done()

    assert len(captured) == 1
    payload = captured[0].data
    assert payload["carrier"] == "DHL"
    assert payload["barcode"] == "RETURN-1"
    assert payload["status"] == ParcelStatus.DELIVERED
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


@pytest.mark.asyncio
async def test_gls_registered_event_is_reemitted_unified(hass):
    """A gls_parcel_registered event triggers parcel_aggregator_parcel_registered."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_PARCEL_REGISTERED)

    hass.bus.async_fire(
        "gls_parcel_registered",
        {
            "carrier": "GLS",
            "barcode": "0085105093278",
            "status": ParcelStatus.REGISTERED,
            "raw_status": "Aangekondigd bij GLS",
            "raw": {"big": "payload"},
        },
    )
    await hass.async_block_till_done()

    assert len(captured) == 1
    payload = captured[0].data
    assert payload["carrier"] == "GLS"
    assert payload["barcode"] == "0085105093278"
    assert payload["status"] == ParcelStatus.REGISTERED
    assert "raw" not in payload


@pytest.mark.asyncio
async def test_dragonfly_registered_event_is_reemitted_unified(hass):
    """A dragonfly_parcel_registered event triggers parcel_aggregator_parcel_registered."""
    entry = _add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    captured = _capture(hass, EVENT_PARCEL_REGISTERED)

    hass.bus.async_fire(
        "dragonfly_parcel_registered",
        {
            "carrier": "Dragonfly",
            "barcode": "INTLCMB2C000123456",
            "status": ParcelStatus.REGISTERED,
            "raw_status": "Zending ontvangen",
            "raw": {"big": "payload"},
        },
    )
    await hass.async_block_till_done()

    assert len(captured) == 1
    payload = captured[0].data
    assert payload["carrier"] == "Dragonfly"
    assert payload["barcode"] == "INTLCMB2C000123456"
    assert payload["status"] == ParcelStatus.REGISTERED
    assert "raw" not in payload
