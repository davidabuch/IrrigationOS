# ADR-004: Soil Model Architecture

- **Status:** Accepted
- **Date:** 2026-08-01

## Context

Users rarely know formal soil classifications, while neighborhood soil databases describe mapped native soil that may differ from landscaped fill or amendments.

## Decision

IrrigationOS uses USDA SSURGO data as an initial location-based recommendation with explicit provenance and confidence. Users may accept, simplify, or override the recommendation globally or per zone. The internal model stores continuous hydraulic properties even when setup uses ordinary-language choices.

## Consequences

- Setup remains approachable.
- Native-soil lookup is never treated as unquestioned ground truth.
- Guided infiltration, runoff, and texture observations can refine the model later.
