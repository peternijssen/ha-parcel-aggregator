# Parcel Aggregator

A Home Assistant custom integration that rolls up parcel counts, next-delivery timestamps, and parcel-event notifications from the DHL, PostNL, and DPD integrations into a single set of sensors and a single unified event stream.

## Contents

- [Use cases](#use-cases)
- [How it works](#how-it-works)
- [How updates work](#how-updates-work)
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

- A single dashboard card that shows how many parcels you expect today across DHL, PostNL and DPD without juggling per-carrier sensors.
- Carrier-agnostic automations — write one trigger like *"when any parcel is out for delivery"* instead of three per-carrier copies.
- Automations like *"announce when a parcel is awaiting pickup at a service point"* or *"remind me an hour before the earliest delivery"* that you write once and they cover every carrier.
- A unified parcel list you can iterate over in templates or custom cards.

## How it works

This integration does **not** talk to any carrier API directly. It does two things:

1. **State aggregation** — reads the state and parcel-list attributes of entities the per-carrier integrations already publish, and exposes summed sensors with a per-carrier breakdown on the attributes.
2. **Event re-emission** — subscribes to the per-carrier parcel events (`dhl_nl_parcel_registered`, etc.) and re-fires them as `parcel_aggregator_parcel_registered` / `parcel_aggregator_parcel_status_changed` so you only need one listener for "any parcel from any carrier".

If a carrier integration is not installed, it's silently skipped — install only what you need.

## How updates work

The aggregator is event-driven, not polling. At setup time it discovers source sensors from the installed carrier integrations and subscribes to their state-change events. Whenever any carrier sensor updates, the aggregator recomputes its sensors immediately. This means the aggregator's freshness is bound to how often each carrier integration polls (typically every 5–15 minutes).

If you install a new carrier integration after Parcel Aggregator was set up, **reload Parcel Aggregator** (Settings → Devices & Services → Parcel Aggregator → ⋮ → Reload) so it picks up the new source sensors.

## Supported sources

| Integration | Repository |
|-------------|------------|
| DHL NL | [peternijssen/ha-dhl-nl](https://github.com/peternijssen/ha-dhl-nl) |
| PostNL | [peternijssen/ha-postnl](https://github.com/peternijssen/ha-postnl) |
| DPD | [peternijssen/ha-dpd](https://github.com/peternijssen/ha-dpd) |

All three carrier integrations publish the canonical `ParcelStatus` enum and the canonical parcel events, so the state-aggregation and event re-emit layers both cover every installed carrier without further configuration.

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

The aggregator discovers source entities at setup time. If you add a new carrier integration later, **reload Parcel Aggregator** to pick it up.

## Options

This integration has no configurable options. It auto-discovers carrier source sensors at setup time and listens for state-change events from them.

## Removal

Standard HA removal applies: **Settings → Devices & Services → Parcel Aggregator → ⋮ → Delete**. No external cleanup is needed; deleting the config entry stops the state-change subscriptions and the event re-emit. The per-carrier integrations are not affected.

## Sensors

| Entity | Description |
|--------|-------------|
| `sensor.parcel_aggregator_incoming` | Sum of active incoming parcels across all carriers; merged parcel list on the `parcels` attribute |
| `sensor.parcel_aggregator_outgoing` | Sum of active outgoing parcels across all carriers; merged list on the `parcels` attribute |
| `sensor.parcel_aggregator_delivered` | Sum of recently delivered parcels across all carriers (uses each carrier's own filter window); merged list on `parcels` |
| `sensor.parcel_aggregator_awaiting_pickup` | Sum of active incoming parcels destined for a pickup point (ServicePoint / PostNL Point / ParcelShop); merged list on `parcels` |
| `sensor.parcel_aggregator_next_delivery` | Earliest expected delivery datetime across all carriers; the matching parcel on the `parcel` attribute |

Every sensor exposes a `by_carrier` attribute with the per-carrier breakdown — handy for dashboard cards like "5 incoming (2 DHL · 3 PostNL)".

### Unified parcel shape

The `parcels` attribute on each summary sensor contains every parcel from every installed carrier in the carrier-agnostic shape:

| Key | Type | Meaning |
|---|---|---|
| `carrier` | string | `"DHL"`, `"PostNL"`, or `"DPD"` |
| `barcode` | string | Parcel tracking number |
| `sender` | string \| null | Sender name (e.g. webshop) |
| `receiver` | string \| null | Recipient name. Filled by DHL and DPD today; PostNL surfaces it in a later release. |
| `status` | `ParcelStatus` | Canonical status — see the [status reference](#parcel-status-reference) |
| `raw_status` | string \| null | Original carrier-specific status string (for power users) |
| `delivered` | bool | Whether the parcel has been delivered |
| `delivered_at` | ISO 8601 \| null | Delivery moment, if known |
| `planned_from` | ISO 8601 \| null | Expected delivery window start |
| `planned_to` | ISO 8601 \| null | Expected delivery window end |
| `pickup` | bool | Destined for a pickup point rather than a home address |
| `pickup_point` | string \| null | ServicePoint / Point / ParcelShop name when `pickup` is true |
| `url` | string \| null | Deep link to the parcel's tracking page |
| `weight` | float \| null | Parcel weight in kilograms. Filled by DPD today; DHL's consumer API doesn't expose it (always `null`); PostNL surfaces it in a later release. |
| `dimensions` | dict \| null | Parcel dimensions in centimeters: `{length, width, height, text}` — `text` is a pre-formatted `"L x W x H cm"` string. Same coverage as `weight`. |

The carrier-specific `raw` payload is stripped to keep aggregator-attribute size small — open the per-carrier sensor if you need the original payload.

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

Each carrier ships its own raw-status → `ParcelStatus` mapping (see the per-carrier READMEs). The aggregator passes the carrier's mapped value through unchanged.

## Events

The coordinator fires unified events on the HA event bus when something interesting happens to any parcel from any carrier, so automations can react without polling per-parcel sensors and without listening to each carrier separately.

| Event | When | Payload |
|---|---|---|
| `parcel_aggregator_parcel_registered` | A carrier announces a new parcel | The full normalised parcel dict (`carrier`, `barcode`, `sender`, `receiver`, `status`, `raw_status`, `delivered`, `delivered_at`, `planned_from`, `planned_to`, `pickup`, `pickup_point`, `url`, `weight`, `dimensions`) |
| `parcel_aggregator_parcel_status_changed` | A known parcel's `status` value changes | Same payload as above plus `old_status` and `new_status` |
| `parcel_aggregator_parcel_delivery_time_changed` | A known parcel's `planned_from` or `planned_to` ends up with a non-null value that differs from the previous one. Value-to-null transitions are intentionally silent. | Same payload as above plus `old_planned_from`, `new_planned_from`, `old_planned_to`, `new_planned_to` |

The carrier-specific `raw` payload is stripped from the event to keep it small. Inspect the source carrier's own event (e.g. `dhl_nl_parcel_status_changed`) if you need the raw payload.

The aggregator does not introduce its own first-refresh suppression — that is the responsibility of each carrier integration. DHL already suppresses events on the very first refresh after start-up so you don't get a stampede of "registered" events for parcels that were already in your account before HA started; the aggregator inherits that behaviour.

See [`examples/automations/`](examples/automations/) for ready-to-paste carrier-agnostic event automations.

## Examples

Ready-to-paste carrier-agnostic automations live in [`examples/`](examples/).

### Community Lovelace cards

The aggregator's bucket sensors pair well with the same third-party cards
that work for the individual carrier integrations:

- [jonisnet/hki-parcels-card](https://github.com/jonisnet/hki-parcels-card) — multi-carrier (PostNL, DHL, DPD) Home Kit-style card. Reads the per-carrier sensors directly, but is a natural companion to the aggregator's unified view.
- [klaptafel/ha-package-tracker-card](https://github.com/klaptafel/ha-package-tracker-card) — purpose-built card for parcel integrations.

Both are maintained by their respective authors — please raise UI issues
in those repos.

## Known limitations

- The aggregator only discovers source sensors **at setup time**. Install a new carrier integration → reload Parcel Aggregator before its sensors appear.
- The `next_delivery` timestamp is only as precise as the underlying carrier exposes. DPD gives a day window (midnight to midnight) until Follow My Parcel fires shortly before delivery — then it narrows to an hour window. Use it for "today/tomorrow" alerts rather than counting on precise hour windows being available all day.
- The `awaiting_pickup` sensor counts every parcel destined for a pickup point, including ones that are still en route. DHL exposes a distinct `at_pickup_point` status on the parcel dict for parcels that have *actually arrived* at the pickup point — DPD's API does not surface this signal yet. The sensor stays on the lowest-common-denominator semantics for now.

## Disclaimer

This is an independent, community-built project with no affiliation, endorsement, or connection to DHL, PostNL, DPD, or any of their subsidiaries.

## Contributing

Pull requests and issues are welcome. Please open an issue before submitting a large change.

## License

MIT
