# ADR-017: Environmental Intelligence Foundation

- **Status:** Accepted for IrrigationOS v0.6.1A
- **Date:** 2026-08-03

## Context

ADR-016 established a canonical, provider-neutral Environmental Weather Domain. IrrigationOS now
needs a separate layer that can describe conclusions derived from validated weather observations
and forecasts without confusing those conclusions with raw weather, landscape-specific demand, or
irrigation recommendations.

This milestone establishes only the immutable vocabulary and report envelope for future
environmental reasoning. It intentionally contains no environmental calculations. Separating the
models from the algorithms allows later calculation milestones to evolve under explicit policy and
versioning while preserving stable report contracts.

## Decision

### Independent environmental-intelligence package

The foundation lives in `custom_components/irrigationos/environment/`. It is a pure Python package
with frozen, slotted dataclasses, stable string enums, strict validation, and deterministic
plain-dictionary serialization.

The package is:

- weather-provider-neutral;
- controller-neutral;
- landscape-area-neutral in this first milestone;
- immutable and deterministic;
- advisory and descriptive only.

It contains no Home Assistant entities, network clients, persistence, OpenAI integration,
controller APIs, irrigation scheduling, or execution.

### Analysis window and evidence

`EnvironmentalAnalysisWindow` identifies one bounded analysis period for one canonical weather
location. It records the observation and forecast IDs that future engines are permitted to use.
The window does not embed raw provider payloads or image bytes.

`EnvironmentalEvidenceReference` links a derived conclusion to one canonical weather record or
fact path. Evidence references are stable, unique within a report, and provider-neutral.

### Signals and explanations

`EnvironmentalSignal` is the canonical envelope for a future deterministic conclusion. Every
signal includes:

- a stable signal ID and signal type;
- a stable classification;
- analysis period and creation timestamp;
- algorithm and policy versions;
- confidence and completeness;
- evidence references;
- machine-readable reason codes;
- a concise human-readable explanation; and
- threshold values used by the future algorithm.

Signals are not irrigation recommendations. They describe environmental conditions such as
atmospheric drying, heat exposure, freeze potential, wind exposure, or heavy-rain potential.

### Confidence and quality

`EnvironmentalConfidence` keeps completeness separate from confidence:

- completeness measures how much required source data was available;
- average confidence summarizes confidence among known inputs;
- quality counts preserve good, estimated, suspect, and unavailable input counts.

Missing data must not become zero-valued known data. Confidence values are not invented by this
foundation; future engines must derive them through explicit, versioned policies.

### Threshold policies

`EnvironmentalThresholdPolicy` stores named threshold values used by future deterministic
algorithms. Threshold values are plain finite numbers with canonical units and descriptions.
Policies are immutable, versioned, and serializable. This prevents hidden constants from becoming
unreviewable behavior.

### Report aggregate

`EnvironmentalIntelligenceReport` owns one analysis window, evidence references, signals,
confidence summary, provenance, and version metadata. Aggregate construction rejects duplicate
IDs, wrong-location signals, evidence references outside the analysis inputs, inconsistent
analysis periods, and dangling signal evidence.

### Safety boundary

The package exposes no method or model that can:

- start, stop, or run irrigation;
- modify a schedule or duration;
- set a rain delay;
- authorize execution;
- update a controller;
- claim plant-specific demand or stress.

## Relationship to ADR-016

ADR-016 remains the source of canonical weather observations and forecasts. Future environment
engines will consume only those validated canonical records. Raw provider responses must never
cross directly into environmental intelligence.

## Explicitly deferred

This foundation does not calculate:

- observed or forecast precipitation totals;
- reference ET0 totals;
- atmospheric water balance;
- drying classifications;
- heat, freeze, wind, or heavy-rain signals;
- forecast reliability;
- effective rainfall;
- canopy interception;
- infiltration or runoff;
- soil-water storage or root-zone moisture;
- landscape water deficit;
- plant-specific stress or water demand;
- Santa Ana or marine-layer detection;
- irrigation recommendations; or
- controller execution.

Those capabilities require later calculation milestones with explicit algorithms, policies, and
tests.

## Consequences

- Future reasoning engines receive a stable, explainable output contract.
- Raw weather remains distinct from derived environmental conclusions.
- Confidence, completeness, evidence, thresholds, and versions are first-class.
- Algorithms can evolve without changing the fundamental report envelope.
- No false precision or irrigation authority is introduced.
