# ADR-026: Commissioning Review and Multi-Plant Editing

- **Status:** Accepted for IrrigationOS v1.0.54
- **Date:** 2026-08-24

## Context

ADR-025 made generic commissioned zones durable, but its installed-user form was intentionally
add-only and captured one primary plant group. Real residential zones contain multiple plant groups,
and users must correct facts, document delivery, maintain calibrated baselines, and review visual
evidence without replacing the entire aggregate or erasing history.

The existing immutable `CommissionedZoneProfile`, landscape add/remove events, explicit conflicts,
and persist-before-publish manager already provide the correct foundation. A new parallel property
model or per-zone implementation would create duplication and unsafe divergence.

## Decision

### Pure generic edit operations

A provider-neutral editing module transforms one immutable `CommissionedZoneProfile` into another.
It supports:

- adding, editing, and removing active plant groups;
- replacing canonical plant-to-delivery links without copying hydraulic facts;
- adding, updating, and removing user-calibrated baseline evidence;
- building a bounded detailed review; and
- recording explicit human resolution of a commissioning conflict.

The operations perform no I/O. The existing manager remains the only persistence transaction
boundary and publishes candidate state in memory only after Home Assistant Store save succeeds.

### Review model

`CommissionedZoneReview` contains canonical identity, active plants, commissioning details,
provenance/confidence, delivery links, demand-source modes, calibrated baselines, approved structured
assessment IDs, unresolved conflicts, conflict resolutions, delivery advisories, and at most 20
recent landscape events. Detailed review belongs in the options flow and diagnostics; Recorder-facing
summaries retain only bounded counts and states.

### History semantics

Additions and removals keep the ADR-024 event behavior. A meaningful plant edit appends a
`plant_group_updated` event containing the complete prior plant/details snapshot. The current profile
contains the new facts. A no-op edit creates no event.

Removing the last plant or calibrated baseline leaves an explicit `unresolved` demand source rather
than inventing replacement evidence or deleting the commissioned zone. A later addition removes that
placeholder. This state is fail-closed and cannot authorize downstream use.

### Conflict resolution

Original `CommissioningEvidenceConflict` candidates remain immutable. Explicit human confirmation
adds a separate `CommissioningConflictResolution` with stable identity, selected value, timestamp,
human source, confidence, and optional note. The current plant identity is updated and its prior
snapshot is retained as a change event. Review derives unresolved conflicts by subtracting resolution
references; it never deletes AI or manual evidence.

### Home Assistant workflow

The options flow selects a canonical commissioned zone, displays a bounded review summary, and
offers generic operations for plant groups, delivery, baselines, and conflicts. Stable plant IDs are
allocated by a slot-like sequence independent of mutable names. Each successful edit is durably saved
before the workflow shows updated review. The same flow operates on Zone 1 and unrelated properties.

### Schema migration

The commissioned-zone model and additive payload schema advance from 2 to 3 because conflict
resolution and update-event values change the stable serialized contract. HA Store metadata remains
version 1. Explicit loaders accept commissioned-zone schemas 1, 2, and 3 and payload schemas 1, 2,
and 3. Older records receive empty resolution history and retain all existing Zone 1, visual,
delivery, baseline, and event evidence.

## Safety

All review/edit results fix `execution_authorized` and `live_control_authorized` false. This decision
adds no background task, listener, polling, network access, AI provider, weather/ET scaling,
temperature multiplier, hydraulic calculation, schedule, Rachio write, command retry, or physical
operation authority. Factor-resolution algorithm version 1.1.0 is unchanged.

## Deferred

- Photo upload and external AI inference.
- Automated conflict precedence or confidence promotion.
- Establishment-stage progression policy.
- Quantitative commissioning completeness/admission policy.
- Weather scaling of calibrated baselines.
- Hydraulic sufficiency and runtime calculation.
- Autonomous irrigation authority.
