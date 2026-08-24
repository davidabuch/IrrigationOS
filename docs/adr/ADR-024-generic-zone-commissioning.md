# ADR-024: Generic Zone Commissioning and Demand Sources

- **Status:** Accepted for IrrigationOS v1.0.52
- **Date:** 2026-08-24

## Context

The canonical Landscape Digital Twin, Water Delivery domain, Visual Assessment boundary, and
landscape factor resolver are already provider-neutral. Runtime commissioning nevertheless seeds
one property-specific Zone 1 profile and exposes it through a Zone-1-shaped manager. Extending that
pattern with a Python module per zone or property would make IrrigationOS impossible to onboard for
other installations.

Users also need multiple evidence paths. Some can describe plants, some can only provide a trusted
reference runtime, and others will eventually submit photos for structured assessment. These inputs
must converge before scientific reasoning, while retaining their different provenance and without
letting AI or a baseline runtime become hidden execution authority.

## Decision

### Generic commissioning aggregate

`CommissionedZoneProfile` is the immutable normalized commissioning boundary. It contains:

- stable property and zone IDs, independent of display names;
- an optional canonical controller slot and a permanent area slot;
- the existing advisory `LandscapeIntelligenceProfile` used by factor resolution;
- typed plant commissioning details;
- one or more explicit demand sources;
- plant-group links to separate canonical Water Delivery profiles/components; and
- immutable add/remove landscape events.

The aggregate validates cross-references, event ordering, current plant coverage, unique identities,
and the advisory-only safety boundary. Its serialization is deterministic plain data. It contains no
provider-native controller IDs, image bytes, arbitrary provider payloads, command methods, scheduling,
or weather-scaling behavior.

### Demand-source modes

The stable modes are `manual_plant_profile`, `user_calibrated_baseline`, `photo_ai_derived`, and
`hybrid`.

A manual source references user-described canonical plant groups. A calibrated baseline retains the
user's runtime and the conditions under which it was calibrated; it does not invent a temperature
multiplier or directly become a schedule. A photo/AI source references structured Visual Assessment
records only. Images, SDK payloads, and model-provider types remain outside commissioning. Hybrid
requires at least two evidence kinds and preserves each one.

### Delivery linkage and advice

`IrrigationDeliveryLink` associates a plant group with IDs owned by the existing Water Delivery
domain. Commissioning does not duplicate emitter measurements or calibration facts. The initial
compatibility assessment reports only whether delivery evidence is documented, missing, or requires
review. Establishing plants on documented shared delivery receive an explicit review advisory. The
assessment does not claim hydraulic compatibility without evidence and cannot authorize execution.

### Landscape history

Add and remove operations are immutable `LandscapeChangeEvent` records containing the plant snapshot
known at the effective time. Current plant groups remain explicit in the zone profile; removing a
plant does not erase its historical snapshot. Establishment progression will be represented by later
immutable evidence or events rather than in-place mutation.

### Zone 1 compatibility

The commissioned Zone 1 record is now built through the generic aggregate. The public
`build_zone_1_landscape_intelligence()` function remains as a compatibility fixture and returns the
identical v1 landscape profile. The manager owns a deterministic collection of commissioned zones but
keeps its existing `zone1`, `zone_1` diagnostics, and schema-1 Store payload for compatibility.
An additive `commissioned_zones` field is written only for a new Store; existing v1.0.50/v1.0.51
Store data is neither destroyed nor rewritten.

## Safety

Commissioning, demand sources, landscape events, and delivery compatibility are evidence only.
`execution_authorized` and `live_control_authorized` are fixed false. This ADR changes no controller
transport, physical-operation service, validated-target rule, runtime limit, confirmation phrase,
retry policy, production readiness rule, or scheduler behavior.

## Deferred

- Home Assistant onboarding UI and persistence CRUD for arbitrary user zones.
- Mapping approved Visual Assessment findings into proposed commissioning facts.
- Weather/ET scaling of user-calibrated baselines.
- Establishment-stage transition policy.
- Quantitative plant/delivery geometry compatibility and design recommendations.
- Migration of the runtime integration from the compatibility landscape profile to the full
  `LandscapeDigitalTwin` aggregate.

