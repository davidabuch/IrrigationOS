# v0.8.0D — Heat Stress Risk Engine

## Scope

This milestone adds one deterministic assessment engine for the `heat` plant-stress dimension.

The engine answers:

> Given reviewed plant heat-tolerance evidence and an Environmental Intelligence heat-exposure
> signal, what categorical heat-stress risk is supported?

## Inputs

- resolved `environment.heat_tolerance` Plant Knowledge evidence;
- one `heat_exposure` Environmental Intelligence signal;
- the immutable Plant Stress Risk request, context, and policy.

## Behavior

The engine applies an explicit categorical matrix across environmental heat exposure (`none`,
`low`, `moderate`, `high`, `extreme`) and plant heat tolerance (`low`, `moderate`, `high`). It
returns a single immutable `PlantStressDimensionAssessment` for `heat`, preserves claim/source and
environmental signal provenance, and keeps confidence separate from completeness.

Missing or conflicting evidence produces typed non-success outcomes. Incomplete or below-policy
evidence follows the request's explicit partial-evidence policy.

## Boundaries

The engine does not diagnose tissue injury, recommend irrigation or shade, forecast future risk,
plan work, schedule actions, or control hardware. It does not use Plant Water Requirement to alter
heat risk.
