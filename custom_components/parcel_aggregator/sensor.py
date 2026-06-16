"""Sensor platform for the Parcel Aggregator integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ParcelAggregatorConfigEntry
from .const import DOMAIN
from .coordinator import ParcelAggregatorCoordinator

_LOGGER = logging.getLogger(__name__)

# The coordinator drives updates via source state-change events; HA's
# per-entity throttling adds nothing.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ParcelAggregatorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Parcel Aggregator sensor entities from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ParcelsIncomingSensor(coordinator),
            ParcelsOutgoingSensor(coordinator),
            ParcelsDeliveredSensor(coordinator),
            ParcelsAwaitingPickupSensor(coordinator),
            ParcelsNextDeliverySensor(coordinator),
        ]
    )


def _build_device_info() -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, "aggregator")},
        name="Parcel Aggregator",
        manufacturer="Community",
        entry_type=DeviceEntryType.SERVICE,
    )


class _BaseListSensor(CoordinatorEntity[ParcelAggregatorCoordinator], SensorEntity):
    """Base for sum-style aggregator sensors that also expose a parcel list."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "parcels"
    _attr_state_class = SensorStateClass.MEASUREMENT
    # Either "parcels" or "shipments" is set per subclass; listing both is
    # harmless since unknown keys are simply ignored by the recorder.
    _unrecorded_attributes = frozenset({"parcels", "shipments"})
    _bucket: str = ""
    _list_attr: str = "parcels"

    def __init__(self, coordinator: ParcelAggregatorCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{self._bucket}"
        self._attr_device_info = _build_device_info()

    def _info(self) -> dict[str, Any]:
        return ((self.coordinator.data or {}).get(self._bucket)) or {}

    @property
    def native_value(self) -> int:
        return int(self._info().get("total", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info()
        return {
            "by_carrier": info.get("by_carrier", {}),
            self._list_attr: info.get("parcels", []),
        }


class ParcelsIncomingSensor(_BaseListSensor):
    _attr_translation_key = "incoming"
    _bucket = "incoming"


class ParcelsOutgoingSensor(_BaseListSensor):
    _attr_translation_key = "outgoing"
    _bucket = "outgoing"
    _list_attr = "shipments"


class ParcelsDeliveredSensor(_BaseListSensor):
    _attr_translation_key = "delivered"
    _bucket = "delivered"


class ParcelsAwaitingPickupSensor(_BaseListSensor):
    _attr_translation_key = "awaiting_pickup"
    _bucket = "awaiting_pickup"


class ParcelsNextDeliverySensor(
    CoordinatorEntity[ParcelAggregatorCoordinator], SensorEntity
):
    """Earliest expected delivery datetime across all known carriers."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_delivery"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: ParcelAggregatorCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_next_delivery"
        self._attr_device_info = _build_device_info()

    def _info(self) -> dict[str, Any]:
        return ((self.coordinator.data or {}).get("next_delivery")) or {}

    @property
    def native_value(self) -> datetime | None:
        return self._info().get("value")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info()
        by_carrier = info.get("by_carrier", {})
        return {
            "by_carrier": {label: dt.isoformat() for label, dt in by_carrier.items()},
            "parcel": info.get("parcel"),
        }
