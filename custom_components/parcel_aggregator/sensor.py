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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ParcelAggregatorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Parcel Aggregator sensor entities from a config entry."""
    coordinator: ParcelAggregatorCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ParcelsIncomingSensor(coordinator),
            ParcelsOutgoingSensor(coordinator),
            ParcelsDeliveredSensor(coordinator),
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


class _BaseSumSensor(CoordinatorEntity[ParcelAggregatorCoordinator], SensorEntity):
    """Base for sum-style aggregator sensors."""

    _attr_native_unit_of_measurement = "parcels"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _bucket: str = ""

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
        return {"by_carrier": self._info().get("by_carrier", {})}


class ParcelsIncomingSensor(_BaseSumSensor):
    _attr_name = "Parcels Incoming"
    _attr_icon = "mdi:package-variant-closed"
    _bucket = "incoming"


class ParcelsOutgoingSensor(_BaseSumSensor):
    _attr_name = "Parcels Outgoing"
    _attr_icon = "mdi:package-variant-closed"
    _bucket = "outgoing"


class ParcelsDeliveredSensor(_BaseSumSensor):
    _attr_name = "Parcels Delivered"
    _attr_icon = "mdi:package-variant"
    _bucket = "delivered"


class ParcelsNextDeliverySensor(
    CoordinatorEntity[ParcelAggregatorCoordinator], SensorEntity
):
    """Earliest expected delivery datetime across all known carriers."""

    _attr_name = "Parcels Next Delivery"
    _attr_icon = "mdi:clock-fast"
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
        by_carrier = self._info().get("by_carrier", {})
        return {
            "by_carrier": {label: dt.isoformat() for label, dt in by_carrier.items()}
        }
