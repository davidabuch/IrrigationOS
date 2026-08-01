# ADR-002: Controller Adapter Boundary

- **Status:** Accepted
- **Date:** 2026-08-01

## Context

IrrigationOS begins with Rachio but is intended to support other controllers. Vendor APIs expose different identifiers, payloads, capabilities, and error behavior.

## Decision

All vendor interaction occurs behind a controller-adapter interface. Higher layers consume canonical controller observations and issue canonical irrigation operations. Vendor IDs remain adapter bindings.

## Consequences

- Rachio-specific code cannot leak into weather, soil, decision, scheduling, or execution policy.
- New controllers can be added without rewriting intelligence layers.
- The canonical contract must represent capability differences explicitly rather than assuming every controller behaves like Rachio.
