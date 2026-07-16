# Working in this repository

This is a Home Assistant custom integration that rolls up parcel counts
and next-delivery timestamps from the DHL, PostNL, DPD, GLS and Dragonfly
integrations
into a single set of sensors. Distributed via HACS; not part of HA core.

## Always consult HA developer documentation

Home Assistant's integration patterns evolve continuously. **Do not rely
on memory of past patterns** — fetch the canonical page before changing
a topic area, and check the developer blog before introducing anything
you only "know" from training data.

| When you change | Fetch first |
|---|---|
| Entity properties, naming, lifecycle, attributes | https://developers.home-assistant.io/docs/core/entity/ |
| Sensor specifics (state/device classes, units) | https://developers.home-assistant.io/docs/core/entity/sensor |
| Config flow, options flow, reauth, reconfigure | https://developers.home-assistant.io/docs/config_entries_config_flow_handler |
| DataUpdateCoordinator pattern | https://developers.home-assistant.io/docs/integration_fetching_data |
| Quality scale rules | https://developers.home-assistant.io/docs/core/integration-quality-scale |
| Diagnostics | https://developers.home-assistant.io/docs/core/integration/diagnostics |
| Repair issues | https://developers.home-assistant.io/docs/core/platform/repairs |
| Translations (entity names, issues, exceptions) | https://developers.home-assistant.io/docs/internationalization/core |

### Recent developer-facing changes

Before introducing patterns you only know from training data, check:

- https://developers.home-assistant.io/blog — API deprecations, new
  patterns, breaking changes. Recent posts trump older recollection.
- https://github.com/home-assistant/architecture/discussions — design
  decisions in flight that have not made it into stable docs yet.

## What is already in place

The integration is aligned with the **gold** quality scale tier. Don't
re-propose these as improvements:

- `quality_scale: "gold"` in manifest, minimum HA version `2024.7.0`
- `ConfigEntry.runtime_data` (the coordinator is the runtime data)
- `PARALLEL_UPDATES = 0` in `sensor.py`
- `has_entity_name = True` on all sensors + `translation_key` per
  sensor; entity names come from `strings.json` and `translations/{en,nl}.json`
- Icons via `icons.json` (per-`translation_key`), not `_attr_icon`
- Repair issue (`ir.async_create_issue` / `async_delete_issue`) when no
  source carrier integrations are detected; clears on reload once a
  carrier appears
- Diagnostics handler in `diagnostics.py` that lists watched source
  entities and redacts per-parcel PII fields (`barcode`, `sender`,
  `pickup_point`, `url`, `raw`) from the aggregated data dump
- Tests for config flow, sensor properties, diagnostics, repair issue,
  and setup/unload lifecycle — coverage 98%
- `_unrecorded_attributes = frozenset({"parcels", "shipments"})` on the
  base list sensor — the aggregated lists are kept out of the recorder
  long-term tables

### Adopted in 1.0.0 (do not refactor away)

- **Canonical `ParcelStatus` enum** in `const.py` — mirrors the enum
  the per-carrier integrations (DHL, DPD, PostNL, GLS, Dragonfly) publish on the
  `status` field of each normalised parcel. Kept in sync across all
  four repositories so cross-carrier automations can target
  `status: out_for_delivery` regardless of source.
- **Carrier event re-emit layer** — the coordinator subscribes to every
  `<prefix>_parcel_registered` / `<prefix>_parcel_status_changed` /
  `<prefix>_parcel_delivery_time_changed` **and** the outgoing pair
  `<prefix>_outgoing_parcel_status_changed` /
  `<prefix>_outgoing_parcel_delivered` published by carriers listed in
  `CARRIER_EVENT_PREFIXES`, re-firing each under the matching
  `parcel_aggregator_*` name (`EVENT_*` constants in `const.py`).
  Carrier-specific `raw` payload is stripped to keep events small. To
  onboard a new carrier that ships the canonical event contract, add its HA
  domain to `CARRIER_EVENT_PREFIXES` — no other change needed. GLS is in the
  prefix list but never fires the outgoing pair (account-less, no outgoing),
  and the same holds for Dragonfly;
  subscribing to an event that never fires is harmless.
- **Translated unit of measurement** — `entity.sensor.<key>.unit_of_measurement`
  in strings/translations. `_attr_native_unit_of_measurement` is
  intentionally absent from the sensor classes. Dutch users see
  `pakketten` / `zendingen` instead of the literal English.
- **Skipped confirm form in config flow** — single-call create, no
  empty form first.
- **Coordinator `config_entry=entry` kwarg** — passed to
  `super().__init__()`; `self.config_entry` provided by the base class.

### Adopted in 1.2.0 — history pass-through (do not refactor away)

- **Per-parcel `history`** (the opt-in carrier timeline) is a **top-level**
  canonical field, so it survives `strip_raw()` (which only drops `raw`)
  and flows through the aggregated `parcels` lists and the
  re-emitted events **automatically** — no field-specific handling. Do
  not add `history` to `strip_raw`'s drop set.
- **Recorder:** the list sensors already exclude `parcels`; the
  next-delivery sensor excludes its singular `parcel` attribute
  (`_unrecorded_attributes = frozenset({"parcel"})`) so the potentially
  large history never hits the recorder DB. `history` is `null` unless
  the source carrier has its own history option enabled.

### Adopted in 1.3.0 — combined calendar (do not refactor away)

- **Combined deliveries `calendar`** (`Platform.CALENDAR` in `PLATFORMS`,
  `calendar.py`). One `ParcelAggregatorCalendar` on the aggregator device,
  unique_id `{DOMAIN}_deliveries`, `translation_key="deliveries"`.
  Read-only view over the already-merged `coordinator.data["incoming"]
  ["parcels"]` — **no own polling**, enabled by default. One
  `CalendarEvent` per active incoming parcel with a `planned_from`; `end`
  is `planned_to` or `planned_from + 1h`. Summary is **carrier-prefixed**
  (`"DHL: <sender>"`) and `uid` is `{carrier}_{barcode}` so the merged
  agenda stays unambiguous across carriers. This is the cross-carrier
  calendar; the per-carrier integrations each ship their own single-account
  one.
- **README stays lean:** the calendar is **not** documented in the README
  (user feedback) even though the sensors are — it is discoverable in the
  HA UI. CLAUDE.md documents it here.

## What was deliberately skipped

- **No `_attr_attribution`**: the aggregator does not talk to any single
  upstream provider, so a single attribution string would be misleading.
  Attribution lives on the per-carrier integrations.
- **Platinum tier**: requires `mypy --strict` clean throughout the
  module and ≥95% coverage. Doable but the user chose to stop at gold.

## Repo-specific quirks

- **No external API**: the coordinator subscribes to *source sensor
  state changes* (`async_track_state_change_event`) instead of polling.
  Freshness is bound to how often each carrier integration polls.
- **Source discovery is event-driven, not per-poll.** `async_setup`
  discovers once (`_refresh_sources`) and then listens to
  `EVENT_ENTITY_REGISTRY_UPDATED`: when a known carrier's source sensor
  is added or removed, discovery re-runs, the state-change subscription
  is rebuilt and the repair issue is created/cleared — no manual reload.
  Do NOT refactor the discovery onto every poll/compute; the registry
  listener is the only re-discovery trigger.
- **Source contract**: `KNOWN_CARRIERS` maps HA integration domains to
  human labels; `SOURCE_SUFFIXES` maps `unique_id` suffixes to buckets
  (`incoming` / `outgoing` / `delivered` / `outgoing_delivered`);
  `ATTR_KEY_BY_BUCKET` maps buckets to the attribute key on the source
  sensor (always `parcels`). All three live in `const.py` and must stay
  in sync — adding a new carrier means updating all three.
- **Longest-suffix matching in `_discover`**: `_outgoing_delivered_parcels`
  also ends with `_delivered_parcels`, so discovery iterates the suffixes
  **longest-first** and breaks on the first match. Do not revert to plain
  dict-order iteration — delivered outgoing parcels would be mis-bucketed
  as incoming delivered.

## Running tests

```
python -m pytest tests/ --cov=custom_components.parcel_aggregator
```

Coverage must stay **above 95%** (gold-tier target). Run before
committing.
