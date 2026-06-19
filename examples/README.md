# Examples

Ready-to-paste Home Assistant snippets for the Parcel Aggregator.

Every example here is **carrier-agnostic** — it triggers on the unified
`parcel_aggregator_*` events or aggregator sensors, so a single
automation covers DHL, PostNL and DPD without per-carrier copies.

| Folder | Contents |
|---|---|
| [`automations/`](automations/) | YAML automation blueprints — paste into `automations.yaml` or the Automation editor in **raw editor** mode. |

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
