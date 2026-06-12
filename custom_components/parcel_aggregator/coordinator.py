"""Coordinator for the Parcel Aggregator integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, KNOWN_CARRIERS, SOURCE_SUFFIXES

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
    """Convert a sensor state to ``datetime``, or ``None`` if unavailable/unparseable."""
    if value in _UNAVAILABLE_STATES:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def aggregate_sum(
    samples: list[tuple[str, int | None]],
) -> dict[str, Any]:
    """Sum a list of (carrier_label, int_value) samples.

    Returns ``{"total": <int>, "by_carrier": {<label>: <int>}, "any_available": <bool>}``.
    """
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


def aggregate_min_timestamp(
    samples: list[tuple[str, datetime | None]],
) -> dict[str, Any]:
    """Pick the earliest datetime across samples.

    Returns ``{"value": <datetime|None>, "by_carrier": {<label>: <datetime>}}``.
    """
    earliest: datetime | None = None
    by_carrier: dict[str, datetime] = {}
    for label, value in samples:
        if value is None:
            continue
        if earliest is None or value < earliest:
            earliest = value
        cur = by_carrier.get(label)
        if cur is None or value < cur:
            by_carrier[label] = value
    return {"value": earliest, "by_carrier": by_carrier}


class ParcelAggregatorCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Tracks source carrier sensors and emits aggregated state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        self._entry = entry
        # bucket name -> {entity_id: carrier_platform}
        self._sources: dict[str, dict[str, str]] = {
            bucket: {} for bucket in SOURCE_SUFFIXES.values()
        }
        self._unsub_listener: CALLBACK_TYPE | None = None

    async def async_setup(self) -> None:
        """Discover source entities and subscribe to their state changes."""
        self._discover()
        watched = [
            entity_id
            for bucket in self._sources.values()
            for entity_id in bucket
        ]
        if watched:
            self._unsub_listener = async_track_state_change_event(
                self.hass, watched, self._on_source_state_change
            )
            _LOGGER.debug(
                "Parcel Aggregator watching %d source entities", len(watched)
            )
        else:
            _LOGGER.info(
                "Parcel Aggregator started with no source entities — install or "
                "reload one of the carrier integrations (%s) and reload this one",
                ", ".join(KNOWN_CARRIERS),
            )
        self.async_set_updated_data(self._compute())

    async def async_shutdown(self) -> None:
        if self._unsub_listener is not None:
            self._unsub_listener()
            self._unsub_listener = None

    def _discover(self) -> None:
        registry = er.async_get(self.hass)
        for ent in registry.entities.values():
            if ent.platform not in KNOWN_CARRIERS:
                continue
            for suffix, bucket in SOURCE_SUFFIXES.items():
                if ent.unique_id.endswith(suffix):
                    self._sources[bucket][ent.entity_id] = ent.platform
                    break

    @callback
    def _on_source_state_change(self, event) -> None:  # noqa: ARG002 - event unused
        self.async_set_updated_data(self._compute())

    def _compute(self) -> dict[str, Any]:
        return {
            "incoming": self._sum_bucket("incoming"),
            "outgoing": self._sum_bucket("outgoing"),
            "delivered": self._sum_bucket("delivered"),
            "next_delivery": self._min_timestamp_bucket("next_delivery"),
        }

    def _samples_int(self, bucket: str) -> list[tuple[str, int | None]]:
        out: list[tuple[str, int | None]] = []
        for entity_id, platform in self._sources[bucket].items():
            state = self.hass.states.get(entity_id)
            value = parse_int_state(state.state if state else None)
            out.append((KNOWN_CARRIERS.get(platform, platform), value))
        return out

    def _samples_timestamp(self, bucket: str) -> list[tuple[str, datetime | None]]:
        out: list[tuple[str, datetime | None]] = []
        for entity_id, platform in self._sources[bucket].items():
            state = self.hass.states.get(entity_id)
            value = parse_timestamp_state(state.state if state else None)
            out.append((KNOWN_CARRIERS.get(platform, platform), value))
        return out

    def _sum_bucket(self, bucket: str) -> dict[str, Any]:
        return aggregate_sum(self._samples_int(bucket))

    def _min_timestamp_bucket(self, bucket: str) -> dict[str, Any]:
        return aggregate_min_timestamp(self._samples_timestamp(bucket))
