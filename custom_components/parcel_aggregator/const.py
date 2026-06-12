"""Constants for the Parcel Aggregator integration."""
from homeassistant.const import Platform

DOMAIN = "parcel_aggregator"

PLATFORMS = [Platform.SENSOR]

# Integration domains the aggregator knows how to read entities from.
# Maps the HA integration domain → human-friendly carrier label used in attributes.
KNOWN_CARRIERS: dict[str, str] = {
    "dhl_nl": "DHL",
    "postnl": "PostNL",
    "dpd": "DPD",
}

# Source sensor unique_id suffix → aggregation bucket name.
SOURCE_SUFFIXES: dict[str, str] = {
    "_incoming_parcels": "incoming",
    "_outgoing_parcels": "outgoing",
    "_next_delivery": "next_delivery",
    "_delivered_parcels": "delivered",
}
