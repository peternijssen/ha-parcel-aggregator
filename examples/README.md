# Examples

Ready-to-paste Home Assistant snippets for the Parcel Aggregator.

Examples cover two patterns:

- **Carrier-agnostic** — one trigger / one card that handles DHL, PostNL and DPD uniformly. The default starting point for most automations and dashboards.
- **Carrier-aware** — uses the `carrier` field on each parcel or the `by_carrier` attribute on a summary sensor to branch styling, route notifications, or render a per-carrier breakdown.

| Folder | Contents |
|---|---|
| [`automations/`](automations/) | YAML automation blueprints — paste into `automations.yaml` or the Automation editor in **raw editor** mode. |
| [`dashboards/`](dashboards/) | Lovelace card snippets — paste into the YAML editor of any card. |

A third pattern sits *upstream* of the aggregator:

- **Feeding carriers from e-mail** — code-based carriers (GLS, Dragonfly) need each tracking number registered before they can track it. [`automations/track_parcels_from_email.yaml`](automations/track_parcels_from_email.yaml) extracts tracking numbers from incoming shipping mails (core IMAP integration + regex, with an optional AI fallback) and registers them automatically; setup guide and pitfalls in [`automations/track_parcels_from_email.md`](automations/track_parcels_from_email.md).

## Events used in the examples

The aggregator's coordinator re-emits every carrier's per-parcel events
under a unified domain prefix, so you write one listener instead of
three:

| Event | When | Payload |
|---|---|---|
| `parcel_aggregator_parcel_registered` | A carrier announces a new parcel | The full normalised parcel dict (`carrier`, `barcode`, `sender`, `status`, `raw_status`, `delivered`, `delivered_at`, `planned_from`, `planned_to`, `pickup`, `pickup_point`, `url`) |
| `parcel_aggregator_parcel_status_changed` | A known parcel's normalised `status` changes | Same payload plus `old_status` and `new_status` (both `ParcelStatus` enum values) |

The carrier-specific `raw` payload is stripped from the unified events
to keep them small. Subscribe directly to the source carrier's own
event (`dhl_nl_parcel_status_changed`, etc.) if you need it.

Events only flow for carriers that have shipped the canonical event
contract (DHL today; DPD and PostNL on their next majors). The
aggregator's state-aggregation sensors work regardless.

## Multi-carrier attributes

Every summary sensor exposes the same trio of attributes that the
carrier-aware examples lean on:

| Attribute | Type | Notes |
|---|---|---|
| `parcels` | list[dict] | Every parcel across every installed carrier in the canonical shape. The `carrier` field on each entry is `"DHL"` / `"PostNL"` / `"DPD"` — filter with `selectattr('carrier', 'eq', 'DHL')`. |
| `by_carrier` | dict[str, int] | Count per carrier, e.g. `{"DHL": 3, "DPD": 1}`. Iterate in templates with `.items()`. |
| `total` *(via state)* | int | The sensor's `state` is the total count. |

The `next_delivery` sensor exposes a slightly different shape: a
single `parcel` (the earliest-arriving one, with its `carrier` baked
in) plus `by_carrier` mapping each carrier to its own earliest
datetime — useful for a "DHL eerst, daarna DPD" timeline card.
