# v1.0.53 — Generic Commissioning Persistence & Onboarding

## Architecture

v1.0.53 makes the generic v1.0.52 commissioning aggregate durable and usable by installed
Home Assistant users. The path is:

```text
onboarding form or approved structured finding
  -> pure provider-neutral mapping
  -> immutable CommissionedZoneProfile
  -> fail-closed LandscapeIntelligenceManager save
  -> deterministic schema-2 commissioned-zone collection
```

No zone-specific Python file is required. Canonical public identity is the stable property/zone ID
plus optional controller slot and permanent area slot; mutable display names and provider-native IDs
never define identity.

## Persistence and migration

Home Assistant Store metadata remains version 1 for backward-compatible loading. A payload-level
`commissioning_store_schema_version` advances to 2. The Store retains:

- the exact legacy `zone_1` mapping;
- active schema-2 commissioned zones in canonical order; and
- complete deactivated-profile tombstones.

Legacy v1.0.50/v1.0.51 Zone-1-only records and the additive v1.0.52 collection load through explicit
validation and migrate without evidence loss. Unsupported or corrupt data fails closed and is not
automatically overwritten. CRUD writes candidate state first and changes the live manager only after
durable persistence succeeds.

## Onboarding modes

- `manual_plant_profile`: user-confirmed plant identity, planting date, source-container size,
  current height, establishment state, and optional independent delivery link.
- `user_calibrated_baseline`: runtime and reference temperature/rain condition only. No multiplier,
  weather scaling, schedule, or command is produced.
- `photo_ai_derived`: approved structured finding and opaque evidence IDs. No image bytes, provider
  objects, or external call enters commissioning.
- `hybrid`: manual and visual evidence coexist. Disagreement creates an explicit unresolved conflict
  with both candidates and provenance retained.

Landscape change mapping appends immutable add/remove events. A removed plant remains in history; a
new plant can remain newly planted with unresolved delivery, producing a delivery-information
advisory rather than guessed hydraulics.

## Home Assistant lifecycle and diagnostics

The existing options flow can add any configured, enabled, bound canonical area that is not already
commissioned. Its compact initial form is deliberately add-only, preventing accidental replacement
of Zone 1 or another durable multi-group profile. The manager restores all active zones on setup and
retains deterministic ordering across reloads. Diagnostics add
a bounded summary of zone count, identities, demand modes, conflicts, advisories, Store schema, and
legacy Zone 1 compatibility while preserving existing Zone 1 diagnostic contracts.

No entity stores the full collection, and no polling, task, timer, listener, or network operation was
added.

## Backward compatibility

Zone 1 remains `property.primary / zone.1`, retains its schema-1 landscape mapping, factor evidence,
diagnostic keys, and factor-resolution algorithm 1.1.0. It is a compatibility fixture using the same
generic aggregate—not a template requiring Zone 2 or Zone 3 Python modules.

## Safety boundary

Commissioning evidence never authorizes watering. `execution_authorized` and
`live_control_authorized` remain false. v1.0.53 changes no controller transport, first-live flow,
supervised operation, unattended canary, runtime ceiling, confirmation phrase, no-retry behavior,
production readiness, scheduler, or command path.
