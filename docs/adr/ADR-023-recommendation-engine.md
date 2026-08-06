# ADR-023: Deterministic Recommendation Engine

- Status: Accepted
- Date: 2026-08-05
- Capability: Recommendations

## Decision

Create an advisory-only Recommendation capability that consumes immutable Plant Health, Aggregate
Plant Stress, and Plant Water Requirement assessments and returns deterministic, provenance-linked
recommendations.

Its bounded question is:

> Given accepted upstream assessments, what advisory action is supported by the available evidence?

Recommendations do not plan, schedule, authorize, or execute irrigation. They do not modify
upstream assessments or diagnose plant condition.

## Initial categories

- `adjust_irrigation`
- `inspect`
- `monitor`
- `no_action`
- `protect_from_freeze`
- `protect_from_heat`
- `seek_expert_review`

## Safety boundary

Every recommendation is advisory only and explicitly prohibits automatic execution. Irrigation
adjustment recommendations require confirmation of soil, delivery, restrictions, and site
conditions before any downstream planning capability may act.

## Determinism and provenance

Identical requests produce identical recommendation identifiers, ordering, reason codes,
serialization, and safety flags. Each recommendation preserves identifiers for Plant Health,
Aggregate Plant Stress, and Plant Water Requirement assessments.
