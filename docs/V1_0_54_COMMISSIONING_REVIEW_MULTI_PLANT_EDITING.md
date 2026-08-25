# v1.0.54 — Commissioning Review & Multi-Plant Editing

## Architecture

v1.0.54 makes durable generic commissioning practically reviewable and editable:

```text
bounded HA review form
  -> pure immutable edit operation
  -> candidate CommissionedZoneProfile
  -> HA Store save
  -> in-memory publication only after success
  -> refreshed bounded review
```

No zone-specific Python or plant-specific UI path is used. Stable property/zone identity and
slot-like plant IDs remain independent of display names and provider-native identifiers.

## Review and editing

The detailed review contains active plants, planting/establishment facts, provenance, confidence,
demand-source modes, calibrated baselines, delivery state, structured visual-assessment references,
conflicts, advisories, and recent history. It is presented through options/diagnostics rather than
large Home Assistant state attributes.

The workflow supports:

- adding multiple user-confirmed plant groups;
- editing names, planting date, source container, height, establishment, irrigation role, and direct
  delivery facts;
- removing a plant while retaining its complete prior snapshot;
- changing a link between a plant and canonical delivery profile/components;
- adding, updating, or removing a calibrated runtime/reference-condition baseline; and
- reviewing and explicitly resolving manual/visual identity conflicts.

No baseline is scaled and no delivery link is interpreted as hydraulic sufficiency.

## History and conflicts

Add/remove events remain immutable. Scientifically meaningful edits append a
`plant_group_updated` event containing the prior state; no-op edits do not create noise. Removing the
last demand fact leaves an explicit unresolved source.

Conflict resolution never mutates or deletes original candidates. A separate immutable human
resolution record identifies the selected/corrected value, and a plant-update event preserves the
previous current identity. Original structured evidence IDs and AI confidence remain auditable.

## Persistence and compatibility

The additive commissioning payload and model schemas advance to 3. Loaders accept schemas 1, 2, and
3, preserve the exact legacy `zone_1` mapping, and migrate older records with empty conflict-resolution
history. HA Store metadata remains version 1. Every update continues to save before changing manager
state; failure leaves both durable and active state unchanged.

Zone 1 loads without user migration and retains its public diagnostics, factor evidence, and
factor-resolution algorithm 1.1.0.

## Safety boundary

Review and editing are advisory. `execution_authorized` and `live_control_authorized` remain false.
v1.0.54 adds no background loop, network call, external AI, weather scaling, hydraulic/runtime
calculation, scheduler behavior, controller write, retry, or autonomous irrigation authority.
