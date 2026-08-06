# v0.8.0D — Freeze Stress Risk Engine

## Scope

This milestone adds one deterministic assessment engine for the `freeze` plant-stress dimension.

The engine consumes only immutable upstream evidence:

- the resolved `environment.minimum_temperature_celsius` Plant Knowledge claim; and
- the Environmental Intelligence `freeze_potential` signal.

It produces one immutable `PlantStressDimensionAssessment` and one standard Plant Stress Risk
envelope. It does not diagnose tissue injury, recommend protective action, schedule irrigation, or
control hardware.

## Decision policy

Plant minimum-temperature evidence is grouped into four explicit hardiness classes:

- tender: 5 C or warmer;
- sensitive: 0 C through less than 5 C;
- moderate: -7 C through less than 0 C; and
- hardy: colder than -7 C.

The engine combines that class with the canonical Environmental Intelligence freeze-potential
classification using an explicit categorical matrix. Missing, conflicting, incomplete, or
below-policy evidence returns the typed outcomes required by ADR-021.

## Determinism and provenance

The engine performs no clock reads, network access, random generation, hidden library lookup, or
state mutation. Assessment identifiers are deterministic, explanations use stable reason codes,
and the output retains the exact Plant Knowledge claim, source, Environmental Intelligence report,
and signal identifiers used.
