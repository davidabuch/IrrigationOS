# ADR-028: Advisory Baseline Environmental Scaling

- **Status:** Accepted for IrrigationOS v1.0.56
- **Decision date:** 2026-08-24

## Context

A user-calibrated baseline records that a runtime was appropriate under a reference
condition, such as a dry 75°F day. Temperature alone does not establish landscape
water demand, and plant identification is intentionally optional in baseline mode.

## Decision

IrrigationOS compares normalized current FAO-56 reference evapotranspiration (ET₀)
with explicit ET₀ evidence for the baseline's matching reference period. The raw
demand ratio is `current net ET₀ / reference ET₀`. Reference temperature remains
descriptive calibration context and is never used as a multiplier.

The advisory scaling factor is bounded to 0.5–1.5 by policy version 1.0.0. This is a
product-safety envelope, not a physical claim. Current measured precipitation is
credited only through the canonical effective-precipitation policy. A qualifying
forecast may hold the advisory result through the canonical forecast-admission
policy, but forecast water is never treated as observed water.

Missing reference ET₀, incomplete or stale current observations, insufficient
confidence, positive precipitation without a site policy, and inadmissible baseline
evidence fail closed without an advisory runtime. Legacy baselines migrate with
reference ET₀ absent; no value is reconstructed from temperature.

Assessments are immutable, deterministic, transient, provider-neutral, and advisory.
They are not persisted as authority and do not enter scheduling, command, controller,
first-live, supervised-operation, or unattended-canary paths. Execution and Live
authorization remain false.

## Consequences

- Baseline-only zones can use environmental science without botanical identity.
- A reference ET₀ observation or reviewed source is required for quantitative scaling.
- Rain effectiveness remains explicitly site-policy dependent.
- A later milestone may guide calibration and delivery validation; it must separately
  review any advisory-to-execution bridge.
