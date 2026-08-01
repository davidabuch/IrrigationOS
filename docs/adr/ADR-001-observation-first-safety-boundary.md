# ADR-001: Observation-first safety boundary

- Status: Accepted
- Date: 2026-08-01

## Context

IrrigationOS will eventually make autonomous irrigation decisions and issue physical watering commands. Incorrect assumptions about zone precipitation rate, soil, slope, weather, or controller state can waste water or damage landscaping.

## Decision

Every installation starts in Observation mode. The initial integration may authenticate, discover equipment, retrieve state, calculate recommendations, and record explanations, but it must not issue autonomous watering commands.

Live control requires later milestones that implement command attribution, ownership, safety interlocks, restart reconciliation, simulation validation, and explicit user commissioning.

## Consequences

- Initial releases are safer and easier to validate.
- The decision system can be developed independently from the execution boundary.
- Live-control development takes longer but becomes auditable and reversible.
