# v0.8.0C — Water-Deficit Stress-Risk Engine

## Purpose

Implement the first deterministic Plant Stress Risk dimension defined by ADR-021.

The engine answers one bounded question:

> Given immutable plant susceptibility, Plant Water Requirement, and environmental drying evidence, what water-deficit stress risk is supported?

## Inputs

- resolved `water.water_stress_sensitivity` Plant Knowledge evidence;
- one immutable Plant Water Requirement assessment; and
- one explicit atmospheric water-balance or drying-trend signal.

## Output

The engine returns one immutable `PlantStressRiskAssessment` containing exactly one
`water_deficit` dimension assessment with typed status, categorical risk, confidence,
completeness, explanation, and machine-readable provenance.

## Deterministic interpretation

Risk is classified from an explicit susceptibility-by-drying matrix. Relative Plant Water
Requirement may move the matrix result by at most one category. Missing or conflicting evidence
returns typed non-success outcomes rather than inferred defaults.

## Boundaries

The engine does not diagnose actual plant physiology, infer soil moisture, recommend irrigation,
calculate runtime or gallons, schedule watering, or control hardware.
