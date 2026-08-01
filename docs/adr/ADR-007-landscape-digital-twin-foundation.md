# ADR-007: Landscape Digital Twin Foundation

- **Status:** Accepted
- **Date:** 2026-08-01

## Context

Controller integrations describe hardware: controllers, valves, native zones, enabled state, and observed watering. Autonomous irrigation requires a separate model of what the hardware waters: plants, soil, slope, exposure, root depth, application rate, and distribution efficiency.

Mixing those facts would make the decision engine dependent on Rachio terminology and would prevent a landscape area from surviving a future controller replacement.

## Decision

IrrigationOS owns a canonical **Landscape Digital Twin** composed of `LandscapeProfile` and `IrrigationAreaProfile` objects.

Each profile value carries:

- the value,
- its source or provenance,
- a confidence percentage.

Controller facts may seed initial profile values, but they remain controller observations. User overrides are stored separately in config-entry options and become the authoritative source for the edited fields.

The initial model includes:

- display name,
- plant type and description,
- irrigation method,
- sun exposure,
- continuous slope percentage,
- soil texture and description,
- root depth,
- application rate,
- distribution efficiency.

## Consequences

- Rachio zones can be replaced without losing landscape identity.
- Future USDA, weather, calibration, and learning sources can contribute values without erasing provenance.
- Unknown fields remain explicitly unknown rather than receiving unsafe assumptions.
- Planning engines can require profile completeness before producing live recommendations.
- The Home Assistant options flow can edit one area profile at a time without changing controller metadata.

## Safety boundary

This ADR adds no command delivery. IrrigationOS remains Observation-only. The Landscape Digital Twin is descriptive state and cannot start, stop, or schedule irrigation.
