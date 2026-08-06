# ADR-022: Plant Health Assessment Framework

- Status: Accepted
- Date: 2026-08-05
- Capability: Plant Health Intelligence

## Decision

Create a pure-Python, immutable, deterministic Plant Health capability that answers:

> What current plant health state is supported by direct evidence?

Plant Health consumes direct visual, manual, or sensor observations. Aggregate Plant Stress is
retained as context only and must never be treated as proof of plant condition.

## Public vocabulary

Health classifications are `excellent`, `good`, `fair`, `poor`, `critical`, and `unknown`.

## Evidence boundary

A concrete classification requires admitted direct evidence. Missing or low-confidence direct
evidence returns `insufficient_direct_evidence` and `unknown`. The engine does not diagnose a
specific disease, pest, nutrient disorder, or irrigation need.

## Determinism and provenance

Identical requests produce identical assessments, explanations, and serialization. Every conclusion
retains direct evidence IDs, source IDs, policy version, and aggregate-stress context.

## Non-goals

The capability does not recommend, plan, schedule, control hardware, or infer health solely from
stress exposure.
