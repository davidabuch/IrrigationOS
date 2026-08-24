# ADR-025: Generic Commissioning Persistence and Onboarding

- **Status:** Accepted for IrrigationOS v1.0.53
- **Date:** 2026-08-24

## Context

ADR-024 established a provider-neutral `CommissionedZoneProfile`, but v1.0.52 runtime only seeded
the Zone 1 compatibility fixture. Its Home Assistant Store payload wrote a generic collection but did
not restore arbitrary entries, and no installed-user mapping existed from onboarding input to that
aggregate. Adding another property-specific Python module for each zone would not scale.

Commissioning evidence also has different trust characteristics. User-confirmed plant facts,
user-calibrated runtime baselines, and approved visual findings must remain distinguishable. When
they disagree, persistence must retain the conflict rather than silently selecting an answer.

## Decision

### Versioned additive Store payload

The Home Assistant Store metadata version remains 1 so existing records can be loaded without an
unsafe Store-level migration. The payload adds `commissioning_store_schema_version: 2` and contains:

- the exact legacy schema-1 `zone_1` mapping;
- a deterministically ordered `commissioned_zones` collection using commissioning model schema 2;
  and
- evidence-preserving `deactivated_zones` tombstones.

Loaders explicitly validate and reconstruct nested domain models. Legacy Zone-1-only payloads and
v1.0.52 commissioned-zone schema 1 payloads are upgraded additively. The original `zone_1` mapping is
preserved exactly. Corrupt or unsupported data is not silently repaired or overwritten; runtime
retains the safe Zone 1 fixture and exposes a persistence error.

The manager saves candidate state before publishing it in memory. A failed save therefore cannot
make a new or updated zone appear commissioned. Canonical property/zone IDs and bound
controller-slot/area-slot pairs are unique, and collection ordering is deterministic.

### Generic onboarding mapping

Pure mapping functions normalize four demand-source modes:

- manual plant profiles become high-confidence, user-confirmed plant facts;
- calibrated baselines preserve runtime and exact reference conditions without applying weather
  scaling;
- approved photo/AI findings reference opaque assessment/evidence IDs and never raw images or
  provider payloads; and
- hybrid inputs retain both user and visual provenance.

The Home Assistant options flow uses this mapping only for configured, enabled, bound targets that
are not already commissioned. It persists through the manager's add-only boundary, so a compact
initial form cannot overwrite the multi-group Zone 1 fixture or another durable profile. Explicit
internal update and evidence-preserving deactivation APIs remain separate. The flow creates no
controller command and performs no network request.

### Conflict and history semantics

`CommissioningEvidenceConflict` retains typed candidates, source, confidence, and evidence IDs.
Conflicting manual and visual plant identity remains unresolved and blocks authoritative downstream
use; v1.0.53 intentionally defines no automatic precedence algorithm.

Landscape add/remove input creates immutable events. Deactivation retains the complete last profile
inside a tombstone rather than deleting evidence. Zone 1 cannot be deactivated through the generic
manager because it remains the runtime compatibility fixture.

### Diagnostics

Diagnostics retain the existing Zone 1 keys and add a bounded commissioning summary containing
counts, canonical identities, demand-source modes, conflict/advisory state, Store schema, and the
last safe persistence error. Provider-native identifiers, images, secrets, and raw payloads are
excluded.

## Safety

Commissioning data is advisory evidence. Every mapped profile fixes `execution_authorized` and
`live_control_authorized` false. This decision adds no polling, tasks, listener, scheduler, weather
scaling, hydraulic calculation, controller write, retry, service call, or autonomous authority.
First-live, supervised operation, unattended canary, production readiness, and Rachio transport are
unchanged.

## Compatibility

The Zone 1 fixture, `zone1` manager property, `zone_1` diagnostics, legacy Store mapping, factor
evidence, and factor-resolution algorithm 1.1.0 remain intact. Arbitrary zones require no new Python
module and use stable canonical identities independent of display names.

## Deferred

- External photo capture and AI-provider calls.
- Automated conflict resolution or evidence precedence.
- Establishment-stage progression policy.
- Weather/ET scaling of calibrated baselines.
- Quantitative delivery compatibility, application depth, and runtime calculation.
- Public destructive removal or deactivation controls.
- General autonomous irrigation authority.
