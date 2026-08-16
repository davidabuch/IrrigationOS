# v1.0.44 — Canonical Production Recommendation Contract

## Purpose

v1.0.44 creates one deterministic, immutable, privacy-safe recommendation for every current production target. A recommendation explains what IrrigationOS can support scientifically and what quantitative delivery evidence is still missing. It never authorizes or invokes watering.

## Canonical targets

One shared selector is authoritative for both production readiness and recommendations. A production target is a canonical `(controller_slot, area_slot)` whose observed area is configured, enabled, and bound. Controller capacity and unused slots are excluded. Internal `area_id` values may correlate legacy scientific pipeline results but are not exposed as recommendation identity.

## Contract

Each current recommendation contains:

- canonical controller and area slots;
- recommendation state;
- scientific-need state, separate from delivery readiness;
- optional irrigation depth, estimated runtime, and scheduling window;
- privacy-safe evidence status, confidence, completeness, reasons, and blockers;
- calculation and expiry timestamps plus explicit schema and policy versions;
- `execution_authorized: false`.

Plant factor is general plant knowledge, not irrigation depth. Controller application rate and efficiency cannot produce runtime without a quantitative target depth. Missing evidence therefore yields `insufficient_evidence` with no invented depth, runtime, or scheduling window.

## Current installation expectation

The configured production targets are controller 1 areas 1, 2, 4, and 5. With the current generic `Trees` identity unresolved and no quantitative demand-to-depth contract, all four recommendations truthfully remain `insufficient_evidence`. Area 3 and other unused slots are absent.

## Freshness and history

Weather freshness uses the source Home Assistant weather entity timestamp. Re-evaluating the pipeline does not refresh unchanged weather. Current recommendation state is coordinator-owned and starts `not_available` after setup or reload until a successful fresh evaluation.

There is no recommendation persistence manager. Schema-2 shadow records retain immutable recommendation snapshots as audit history. Schema-1 shadow records remain readable by actual-vs-shadow matching. Persisted history is never restored as current recommendation or execution authority.

## Home Assistant visibility

- `sensor.irrigationos_production_recommendations` exposes the current aggregate snapshot.
- `sensor.zone_<slot>_production_recommendation` exposes one selected production-area result.

Attributes use canonical slots only and contain no provider-native identifiers.

## Safety boundary

The package has no imports from first-live, supervised-operation, unattended-canary, or Rachio actuation code. It creates no tasks, performs no I/O or network requests, retries nothing, and adds no execution authority. Existing physical-operation semantics, runtime ceilings, confirmations, validated-target persistence, and `live_control_authorized = false` remain unchanged.
