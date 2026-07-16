"""Constants for the Parcel Aggregator integration."""
from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "parcel_aggregator"

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]


class ParcelStatus(StrEnum):
    """Carrier-agnostic parcel status.

    Mirrors the enum the per-carrier integrations (DHL, DPD, PostNL)
    publish on the ``status`` field of each normalised parcel. Kept in
    sync with those repositories so cross-carrier automations can target
    ``status: out_for_delivery`` regardless of which integration fired
    the event.
    """

    REGISTERED = "registered"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    AT_PICKUP_POINT = "at_pickup_point"
    DELIVERED = "delivered"
    RETURNING = "returning"
    PROBLEM = "problem"
    UNKNOWN = "unknown"


# Integration domains the aggregator knows how to read entities from.
# Maps the HA integration domain → human-friendly carrier label used in attributes.
KNOWN_CARRIERS: dict[str, str] = {
    "dhl_nl": "DHL",
    "postnl": "PostNL",
    "dpd": "DPD",
    "gls": "GLS",
    "dragonfly": "Dragonfly",
}

# Per-carrier event-name prefix on the HA event bus. Carriers that have
# adopted the canonical event contract publish ``<prefix>_parcel_registered``
# and ``<prefix>_parcel_status_changed``. The aggregator subscribes to all
# of these and re-emits them under its own DOMAIN prefix, so users can
# write one carrier-agnostic automation.
#
# Carriers without an entry here are silently skipped — the state-attribute
# pass-through still works regardless. Add the carrier's domain once it
# ships the event contract.
CARRIER_EVENT_PREFIXES: dict[str, str] = {
    "dhl_nl": "dhl_nl",
    "dpd": "dpd",
    "postnl": "postnl",
    "gls": "gls",
    "dragonfly": "dragonfly",
}

EVENT_PARCEL_REGISTERED = f"{DOMAIN}_parcel_registered"
EVENT_PARCEL_STATUS_CHANGED = f"{DOMAIN}_parcel_status_changed"
EVENT_PARCEL_DELIVERY_TIME_CHANGED = f"{DOMAIN}_parcel_delivery_time_changed"
EVENT_OUTGOING_PARCEL_STATUS_CHANGED = f"{DOMAIN}_outgoing_parcel_status_changed"
EVENT_OUTGOING_PARCEL_DELIVERED = f"{DOMAIN}_outgoing_parcel_delivered"

# Source sensor unique_id suffix → aggregation bucket name.
#
# NB: ``_outgoing_delivered_parcels`` also ends with ``_delivered_parcels``,
# so matching MUST prefer the longest suffix (see ``_discover``) or delivered
# outgoing parcels would be mis-bucketed as incoming delivered.
SOURCE_SUFFIXES: dict[str, str] = {
    "_incoming_parcels": "incoming",
    "_outgoing_parcels": "outgoing",
    "_delivered_parcels": "delivered",
    "_outgoing_delivered_parcels": "outgoing_delivered",
}

# Attribute key on each source sensor that holds the parcel list.
# Every carrier-side sensor exposes `parcels` after the normalisation
# wave (DHL 2.0.0, DPD 2.0.0, PostNL 4.0.0); the old "shipments" key for
# outgoing is gone from all three.
ATTR_KEY_BY_BUCKET: dict[str, str] = {
    "incoming": "parcels",
    "outgoing": "parcels",
    "delivered": "parcels",
    "outgoing_delivered": "parcels",
}
