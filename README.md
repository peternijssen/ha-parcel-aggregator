# Parcel Aggregator

A Home Assistant custom integration that rolls up parcel counts and next-delivery timestamps from the DHL, PostNL, and DPD integrations into a single set of sensors.

## How it works

This integration does **not** talk to any carrier API directly. It reads the state of entities that other parcel-tracking integrations already publish, and exposes aggregated sensors with a per-carrier breakdown on the attributes. If a carrier integration is not installed, it's silently skipped — install only what you need.

## Supported sources

| Integration | Repository |
|-------------|-----------|
| DHL NL | [peternijssen/ha-dhl-nl](https://github.com/peternijssen/ha-dhl-nl) |
| PostNL | [peternijssen/ha-postnl](https://github.com/peternijssen/ha-postnl) |
| DPD | [peternijssen/ha-dpd](https://github.com/peternijssen/ha-dpd) |

## Requirements

- Home Assistant 2024.1 or newer
- At least one of the supported carrier integrations installed and authenticated

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add this repository URL and select category **Integration**
3. Search for **Parcel Aggregator** and install it
4. Restart Home Assistant

### Manual

1. Copy the `parcel_aggregator` folder into your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Parcel Aggregator**
3. Click **Submit** — no credentials needed

The aggregator discovers source entities at setup time. If you add a new carrier integration later, **reload Parcel Aggregator** to pick it up.

## Sensors

| Entity | Description |
|--------|-------------|
| `sensor.parcels_incoming` | Sum of active incoming parcels across all carriers |
| `sensor.parcels_outgoing` | Sum of active outgoing shipments across all carriers |
| `sensor.parcels_delivered` | Sum of recently delivered parcels across all carriers (uses each carrier's own filter window) |
| `sensor.parcels_next_delivery` | Earliest expected delivery datetime across all carriers |

Every sensor exposes a `by_carrier` attribute with the per-carrier breakdown — handy for dashboard cards like "5 incoming (2 DHL · 3 PostNL)".

## Disclaimer

This is an independent, community-built project with no affiliation, endorsement, or connection to DHL, PostNL, DPD, or any of their subsidiaries.

## Contributing

Pull requests and issues are welcome. Please open an issue before submitting a large change.

## License

MIT
