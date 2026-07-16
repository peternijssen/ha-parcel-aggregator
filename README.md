# Parcel Aggregator

[![Release](https://img.shields.io/github/v/release/peternijssen/ha-parcel-aggregator.svg)](https://github.com/peternijssen/ha-parcel-aggregator/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 💬 Questions or feedback? Join the discussion on the [Home Assistant community](https://community.home-assistant.io/t/packages-postnl-dhl-nl-dpd-and-gls-parcel-integration/112433/).

A Home Assistant custom integration that rolls up parcel counts, next-delivery timestamps, and parcel-event notifications from the DHL, PostNL, DPD, GLS and Dragonfly integrations into a single set of sensors and a single unified event stream.

## Contents

- [Use cases](#use-cases)
- [How it works](#how-it-works)
- [Supported sources](#supported-sources)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Options](#options)
- [Removal](#removal)
- [Sensors](#sensors)
- [Parcel status reference](#parcel-status-reference)
- [Events](#events)
- [Examples](#examples)
- [Known limitations](#known-limitations)
- [Disclaimer](#disclaimer)
- [Contributing](#contributing)
- [License](#license)

## Use cases

- A single dashboard card that shows how many parcels you expect today across DHL, PostNL, DPD, GLS and Dragonfly without juggling per-carrier sensors.
- Carrier-agnostic automations — write one trigger like *"when any parcel is out for delivery"* instead of three per-carrier copies.
- Automations like *"announce when a parcel is awaiting pickup at a service point"* or *"remind me an hour before the earliest delivery"* that you write once and they cover every carrier.
- A unified parcel list you can iterate over in templates or custom cards.

## How it works

The aggregator does **not** talk to any carrier API itself. It reads the sensors and events the per-carrier integrations already publish and exposes:

- Summed count sensors with a per-carrier breakdown on the attributes
- A unified `parcel_aggregator_parcel_*` event stream so one automation can react to any carrier

Carriers you have not installed are silently skipped. If you add a carrier integration later, the aggregator picks up its sensors automatically — no reload needed.

## Supported sources

| Integration | Repository |
|-------------|------------|
| DHL NL | [peternijssen/ha-dhl-nl](https://github.com/peternijssen/ha-dhl-nl) |
| PostNL | [peternijssen/ha-postnl](https://github.com/peternijssen/ha-postnl) |
| DPD | [peternijssen/ha-dpd](https://github.com/peternijssen/ha-dpd) |
| GLS | [peternijssen/ha-gls](https://github.com/peternijssen/ha-gls) |
| Dragonfly | [HummelsTech/ha-dragonfly](https://github.com/HummelsTech/ha-dragonfly) |

## Requirements

- Home Assistant 2024.7 or newer
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
3. The entry is created immediately — no credentials needed

The aggregator discovers source entities at setup time and keeps watching the entity registry, so carrier integrations you add or remove later are picked up automatically.

## Options

This integration has no configurable options. It auto-discovers carrier source sensors (also when a carrier is installed later) and listens for state-change events from them.

## Removal

Standard HA removal applies: **Settings → Devices & Services → Parcel Aggregator → ⋮ → Delete**. No external cleanup is needed; deleting the config entry stops the state-change subscriptions and the event re-emit. The per-carrier integrations are not affected.

## Sensors

| Entity | Description |
|--------|-------------|
| `sensor.parcel_aggregator_incoming_parcels` | Sum of active incoming parcels across all carriers; merged parcel list on the `parcels` attribute |
| `sensor.parcel_aggregator_outgoing_parcels` | Sum of active outgoing parcels across all carriers; merged list on the `parcels` attribute |
| `sensor.parcel_aggregator_delivered_parcels` | Sum of recently delivered incoming parcels across all carriers (uses each carrier's own filter window); merged list on `parcels` |
| `sensor.parcel_aggregator_outgoing_delivered_parcels` | Sum of recently delivered outgoing parcels across all carriers; merged list on `parcels` |
| `sensor.parcel_aggregator_awaiting_pickup` | Sum of active incoming parcels destined for a pickup point (ServicePoint / PostNL Point / ParcelShop); merged list on `parcels` |
| `sensor.parcel_aggregator_next_delivery` | Earliest expected delivery datetime across all carriers; the matching parcel on the `parcel` attribute |

Every sensor exposes a `by_carrier` attribute with the per-carrier breakdown — handy for dashboard cards like "5 incoming (2 DHL · 3 PostNL)".

### Unified parcel shape

The `parcels` attribute on each summary sensor contains every parcel from every installed carrier in the carrier-agnostic shape:

| Key | Type | Meaning |
|---|---|---|
| `carrier` | string | `"DHL"`, `"PostNL"`, `"DPD"`, `"GLS"`, or `"Dragonfly"` |
| `barcode` | string | Parcel tracking number |
| `sender` | string \| null | Sender name (e.g. webshop) |
| `receiver` | string \| null | Recipient name |
| `status` | `ParcelStatus` | Canonical status — see the [status reference](#parcel-status-reference) |
| `raw_status` | string \| null | Original carrier-specific status string |
| `delivered` | bool | Whether the parcel has been delivered |
| `delivered_at` | ISO 8601 \| null | Delivery moment, if known |
| `planned_from` | ISO 8601 \| null | Expected delivery window start |
| `planned_to` | ISO 8601 \| null | Expected delivery window end |
| `pickup` | bool | Destined for a pickup point rather than a home address |
| `pickup_point` | string \| null | ServicePoint / Point / ParcelShop name when `pickup` is true |
| `url` | string \| null | Deep link to the parcel's tracking page |
| `weight` | float \| null | Parcel weight in kilograms. May be `null` depending on what the carrier exposes. |
| `dimensions` | dict \| null | Parcel dimensions in centimeters: `{length, width, height, text}` where `text` is a pre-formatted `"L x W x H cm"` string. May be `null` depending on the carrier. |
| `history` | list \| null | Ordered status timeline (oldest → newest), each entry `{timestamp, status, raw_status}`. `null` unless the source carrier integration has its **Parcel history** option enabled — it is opt-in and off by default on each carrier. |

The carrier-specific `raw` payload is omitted to keep attribute size small. Open the per-carrier sensor if you need the original payload.

## Parcel status reference

`status` on every parcel is one of the canonical `ParcelStatus` values below. Use these in your automations rather than carrier-specific raw strings — the raw value stays available on `raw_status` for power users.

| `status` | Meaning |
|---|---|
| `registered` | Carrier knows about the label but the parcel is not yet in transit |
| `in_transit` | Picked up; somewhere in the carrier's network |
| `out_for_delivery` | On the delivery vehicle today |
| `at_pickup_point` | Arrived at the chosen ServicePoint / PostNL Point / ParcelShop, ready to be collected |
| `delivered` | Handed over to the recipient, mailbox, neighbour, or picked up |
| `returning` | Failed delivery, on the way back to the sender |
| `problem` | Carrier reports an exception, intervention, or other issue |
| `unknown` | Raw status/category the carrier integration has not mapped yet |

Each carrier has its own raw-status mapping — see the per-carrier READMEs.

## Events

Unified events on the HA event bus let one automation react to changes from any carrier.

| Event | When | Payload |
|---|---|---|
| `parcel_aggregator_parcel_registered` | A carrier announces a new parcel | The full parcel dict (see the table above) |
| `parcel_aggregator_parcel_status_changed` | A known parcel's `status` value changes | Same payload plus `old_status` and `new_status` |
| `parcel_aggregator_parcel_delivery_time_changed` | A known parcel's expected delivery time changes to a new value | Same payload plus `old_planned_from`, `new_planned_from`, `old_planned_to`, `new_planned_to` |
| `parcel_aggregator_outgoing_parcel_status_changed` | A known **outgoing** parcel (something you sent) changes status, except the final hop to delivered | Same payload plus `old_status` and `new_status` |
| `parcel_aggregator_outgoing_parcel_delivered` | An outgoing parcel reaches the recipient | The full parcel dict |

See [`examples/automations/`](examples/automations/) for ready-to-paste carrier-agnostic event automations.

## Examples

Ready-to-paste carrier-agnostic automations live in [`examples/`](examples/).

### Community Lovelace cards

Third-party cards that work with these sensors:

- [jonisnet/hki-parcels-card](https://github.com/jonisnet/hki-parcels-card)
- [klaptafel/ha-package-tracker-card](https://github.com/klaptafel/ha-package-tracker-card)

## Known limitations

- The `next_delivery` timestamp is only as precise as the underlying carrier exposes. DPD gives a day window (midnight to midnight) until Follow My Parcel fires shortly before delivery — then it narrows to an hour window. Use it for "today/tomorrow" alerts rather than counting on precise hour windows being available all day.
- The `awaiting_pickup` sensor counts every parcel destined for a pickup point, including ones that are still en route. DHL exposes a distinct `at_pickup_point` status on the parcel dict for parcels that have *actually arrived* at the pickup point — DPD's API does not surface this signal yet. The sensor stays on the lowest-common-denominator semantics for now.

## Disclaimer

This is an independent, community-built project with no affiliation, endorsement, or connection to DHL, PostNL, DPD, GLS, Dragonfly Shipping, or any of their subsidiaries.

## Contributing

Pull requests and issues are welcome. Please open an issue before submitting a large change.

## License

MIT
