"""Coordinator for the Parcel Aggregator integration."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_KEY_BY_BUCKET,
    CARRIER_EVENT_PREFIXES,
    DOMAIN,
    EVENT_OUTGOING_PARCEL_DELIVERED,
    EVENT_OUTGOING_PARCEL_STATUS_CHANGED,
    EVENT_PARCEL_DELIVERY_TIME_CHANGED,
    EVENT_PARCEL_REGISTERED,
    EVENT_PARCEL_STATUS_CHANGED,
    KNOWN_CARRIERS,
    SOURCE_SUFFIXES,
)

NO_SOURCES_ISSUE_ID = "no_sources"

_LOGGER = logging.getLogger(__name__)

_UNAVAILABLE_STATES = {"unavailable", "unknown", "", None}


def parse_int_state(value: str | None) -> int | None:
    """Convert a sensor state to ``int``, or ``None`` if unavailable/unparseable."""
    if value in _UNAVAILABLE_STATES:
        return None
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def parse_timestamp_state(value: str | None) -> datetime | None:
    """Convert an ISO 8601 timestamp string to ``datetime``, or ``None`` if unparseable.

    Always returns a tz-aware datetime: naive ISO strings (which the source
    carriers do occasionally emit) are treated as UTC. Mixing naive and aware
    values in the same list would otherwise crash any downstream sort.
    """
    if value in _UNAVAILABLE_STATES:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def aggregate_sum(
    samples: list[tuple[str, int | None]],
) -> dict[str, Any]:
    """Sum (carrier_label, int_value) samples into a total + per-carrier breakdown."""
    total = 0
    by_carrier: dict[str, int] = {}
    any_available = False
    for label, value in samples:
        if value is None:
            continue
        any_available = True
        total += value
        by_carrier[label] = by_carrier.get(label, 0) + value
    return {"total": total, "by_carrier": by_carrier, "any_available": any_available}


def strip_raw(parcel: dict) -> dict:
    """Return a copy of a normalized parcel without the carrier-specific ``raw`` payload."""
    return {k: v for k, v in parcel.items() if k != "raw"}


def sort_parcels_by_ts(
    parcels: list[dict], key_field: str, *, descending: bool = False
) -> list[dict]:
    """Return parcels sorted by the ISO timestamp at ``key_field``.

    Parcels whose value is missing or unparseable always sort to the end,
    regardless of ``descending`` — so e.g. just-registered parcels with
    no ETA still show after the parcels that do have one rather than
    disappearing to the top.
    """
    with_ts: list[tuple[datetime, dict]] = []
    without_ts: list[dict] = []
    for parcel in parcels:
        ts = parse_timestamp_state(parcel.get(key_field))
        if ts is None:
            without_ts.append(parcel)
        else:
            with_ts.append((ts, parcel))
    with_ts.sort(key=lambda item: item[0], reverse=descending)
    return [p for _, p in with_ts] + without_ts


def next_delivery_from(parcels: list[dict]) -> dict[str, Any]:
    """Pick the earliest ``planned_from`` across a list of normalized parcels.

    Returns ``{"value": <datetime|None>, "by_carrier": {<label>: <datetime>},
    "parcel": <minimal parcel dict|None>}``.
    """
    earliest: datetime | None = None
    earliest_parcel: dict | None = None
    by_carrier: dict[str, datetime] = {}

    for parcel in parcels:
        dt = parse_timestamp_state(parcel.get("planned_from"))
        if dt is None:
            continue
        carrier = parcel.get("carrier") or "Unknown"
        cur = by_carrier.get(carrier)
        if cur is None or dt < cur:
            by_carrier[carrier] = dt
        if earliest is None or dt < earliest:
            earliest = dt
            earliest_parcel = parcel

    return {
        "value": earliest,
        "by_carrier": by_carrier,
        "parcel": strip_raw(earliest_parcel) if earliest_parcel else None,
    }


def awaiting_pickup_from(parcels: list[dict]) -> dict[str, Any]:
    """Count active parcels destined for a pickup point and provide the list."""
    matching = [
        p for p in parcels
        if p.get("pickup") and not p.get("delivered")
    ]
    by_carrier: dict[str, int] = {}
    for parcel in matching:
        carrier = parcel.get("carrier") or "Unknown"
        by_carrier[carrier] = by_carrier.get(carrier, 0) + 1
    return {
        "total": len(matching),
        "by_carrier": by_carrier,
        "parcels": [strip_raw(p) for p in matching],
    }


class ParcelAggregatorCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Tracks source carrier sensors and emits aggregated state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )
        # bucket -> {entity_id: carrier_platform}
        self._sources: dict[str, dict[str, str]] = {
            bucket: {} for bucket in SOURCE_SUFFIXES.values()
        }
        self._unsub_listener: CALLBACK_TYPE | None = None
        self._unsub_registry_listener: CALLBACK_TYPE | None = None
        self._unsub_event_listeners: list[CALLBACK_TYPE] = []

    async def async_setup(self) -> None:
        """Discover source entities and subscribe to their state changes.

        Discovery also re-runs whenever a known carrier's source sensor is
        added to or removed from the entity registry, so installing a carrier
        *after* the aggregator does not require a manual reload.
        """
        self._refresh_sources()
        self._subscribe_carrier_events()
        self._unsub_registry_listener = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_registry_updated
        )
        self.async_set_updated_data(self._compute())

    async def async_shutdown(self) -> None:
        if self._unsub_listener is not None:
            self._unsub_listener()
            self._unsub_listener = None
        if self._unsub_registry_listener is not None:
            self._unsub_registry_listener()
            self._unsub_registry_listener = None
        for unsub in self._unsub_event_listeners:
            unsub()
        self._unsub_event_listeners.clear()

    def _watched_entity_ids(self) -> set[str]:
        return {
            entity_id
            for bucket in self._sources.values()
            for entity_id in bucket
        }

    @callback
    def _refresh_sources(self) -> None:
        """(Re)discover source entities and (re)subscribe to their changes."""
        if self._unsub_listener is not None:
            self._unsub_listener()
            self._unsub_listener = None
        self._sources = {bucket: {} for bucket in SOURCE_SUFFIXES.values()}
        self._discover()
        watched = list(self._watched_entity_ids())
        if watched:
            self._unsub_listener = async_track_state_change_event(
                self.hass, watched, self._on_source_state_change
            )
            _LOGGER.debug(
                "Parcel Aggregator watching %d source entities", len(watched)
            )
            ir.async_delete_issue(self.hass, DOMAIN, NO_SOURCES_ISSUE_ID)
        else:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                NO_SOURCES_ISSUE_ID,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=NO_SOURCES_ISSUE_ID,
                translation_placeholders={
                    "carriers": ", ".join(KNOWN_CARRIERS.values()),
                },
            )

    @callback
    def _on_registry_updated(self, event: Event) -> None:
        """Re-discover when a carrier source sensor (dis)appears."""
        if not self._registry_event_is_relevant(event):
            return
        self._refresh_sources()
        self.async_set_updated_data(self._compute())

    def _registry_event_is_relevant(self, event: Event) -> bool:
        entity_id: str = event.data.get("entity_id", "")
        if event.data.get("action") == "remove":
            return entity_id in self._watched_entity_ids()
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is None or entry.platform not in KNOWN_CARRIERS:
            return False
        return any(entry.unique_id.endswith(suffix) for suffix in SOURCE_SUFFIXES)

    def _subscribe_carrier_events(self) -> None:
        """Listen to per-carrier parcel events and re-emit them unified.

        Each carrier that has adopted the canonical event contract fires
        ``<prefix>_parcel_registered``, ``<prefix>_parcel_status_changed``,
        ``<prefix>_parcel_delivery_time_changed`` and — for parcels the
        account holder sends — ``<prefix>_outgoing_parcel_status_changed`` and
        ``<prefix>_outgoing_parcel_delivered`` on the HA event bus. The
        aggregator forwards each under its own ``parcel_aggregator_``-prefixed
        name so users only need one listener for "any parcel from any carrier".
        """
        for prefix in CARRIER_EVENT_PREFIXES.values():
            self._unsub_event_listeners.append(
                self.hass.bus.async_listen(
                    f"{prefix}_parcel_registered", self._on_carrier_registered
                )
            )
            self._unsub_event_listeners.append(
                self.hass.bus.async_listen(
                    f"{prefix}_parcel_status_changed",
                    self._on_carrier_status_changed,
                )
            )
            self._unsub_event_listeners.append(
                self.hass.bus.async_listen(
                    f"{prefix}_parcel_delivery_time_changed",
                    self._on_carrier_delivery_time_changed,
                )
            )
            self._unsub_event_listeners.append(
                self.hass.bus.async_listen(
                    f"{prefix}_outgoing_parcel_status_changed",
                    self._on_carrier_outgoing_status_changed,
                )
            )
            self._unsub_event_listeners.append(
                self.hass.bus.async_listen(
                    f"{prefix}_outgoing_parcel_delivered",
                    self._on_carrier_outgoing_delivered,
                )
            )

    @callback
    def _on_carrier_registered(self, event: Event) -> None:
        self.hass.bus.async_fire(EVENT_PARCEL_REGISTERED, strip_raw(dict(event.data)))

    @callback
    def _on_carrier_status_changed(self, event: Event) -> None:
        self.hass.bus.async_fire(
            EVENT_PARCEL_STATUS_CHANGED, strip_raw(dict(event.data))
        )

    @callback
    def _on_carrier_delivery_time_changed(self, event: Event) -> None:
        self.hass.bus.async_fire(
            EVENT_PARCEL_DELIVERY_TIME_CHANGED, strip_raw(dict(event.data))
        )

    @callback
    def _on_carrier_outgoing_status_changed(self, event: Event) -> None:
        self.hass.bus.async_fire(
            EVENT_OUTGOING_PARCEL_STATUS_CHANGED, strip_raw(dict(event.data))
        )

    @callback
    def _on_carrier_outgoing_delivered(self, event: Event) -> None:
        self.hass.bus.async_fire(
            EVENT_OUTGOING_PARCEL_DELIVERED, strip_raw(dict(event.data))
        )

    def _discover(self) -> None:
        registry = er.async_get(self.hass)
        for ent in registry.entities.values():
            if ent.platform not in KNOWN_CARRIERS:
                continue
            # Longest suffix first: ``_outgoing_delivered_parcels`` also ends
            # with ``_delivered_parcels``, so the specific match must win.
            for suffix, bucket in sorted(
                SOURCE_SUFFIXES.items(), key=lambda kv: len(kv[0]), reverse=True
            ):
                if ent.unique_id.endswith(suffix):
                    self._sources[bucket][ent.entity_id] = ent.platform
                    break

    @callback
    def _on_source_state_change(self, event) -> None:  # noqa: ARG002 - event unused
        self.async_set_updated_data(self._compute())

    def _compute(self) -> dict[str, Any]:
        incoming_parcels = sort_parcels_by_ts(
            self._collect_parcels("incoming"), "planned_from"
        )
        outgoing_parcels = sort_parcels_by_ts(
            self._collect_parcels("outgoing"), "planned_from"
        )
        delivered_parcels = sort_parcels_by_ts(
            self._collect_parcels("delivered"), "delivered_at", descending=True
        )
        outgoing_delivered_parcels = sort_parcels_by_ts(
            self._collect_parcels("outgoing_delivered"), "delivered_at", descending=True
        )
        return {
            "incoming": {
                **self._sum_bucket("incoming"),
                "parcels": [strip_raw(p) for p in incoming_parcels],
            },
            "outgoing": {
                **self._sum_bucket("outgoing"),
                "parcels": [strip_raw(p) for p in outgoing_parcels],
            },
            "delivered": {
                **self._sum_bucket("delivered"),
                "parcels": [strip_raw(p) for p in delivered_parcels],
            },
            "outgoing_delivered": {
                **self._sum_bucket("outgoing_delivered"),
                "parcels": [strip_raw(p) for p in outgoing_delivered_parcels],
            },
            "next_delivery": next_delivery_from(incoming_parcels),
            "awaiting_pickup": awaiting_pickup_from(incoming_parcels),
        }

    def _sum_bucket(self, bucket: str) -> dict[str, Any]:
        samples: list[tuple[str, int | None]] = []
        for entity_id, platform in self._sources[bucket].items():
            state = self.hass.states.get(entity_id)
            value = parse_int_state(state.state if state else None)
            samples.append((KNOWN_CARRIERS.get(platform, platform), value))
        return aggregate_sum(samples)

    def _collect_parcels(self, bucket: str) -> list[dict]:
        attr_key = ATTR_KEY_BY_BUCKET[bucket]
        out: list[dict] = []
        for entity_id in self._sources[bucket]:
            state = self.hass.states.get(entity_id)
            if not state:
                continue
            parcels = state.attributes.get(attr_key) or []
            out.extend(parcels)
        return out
