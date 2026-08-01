# IrrigationOS v0.2.0 — Controller Foundation

## Purpose

Establish the controller-agnostic boundary that all future adapters and intelligence layers will use.

## Added

- Canonical `IrrigationController` and `IrrigationArea` domain models.
- Normalized controller availability and area states.
- Explicit controller capability reporting.
- Controller adapter protocol and runtime adapter registry.
- Rachio adapter that translates native account, controller, and zone payloads.
- Generic Home Assistant entities backed by controller-agnostic models.
- Provider and irrigation-area observations.
- ADR-006 documenting the controller domain model.

## Safety boundary

This release remains Observation-only. All command capabilities are false and no start, stop, rain-delay, or scheduling endpoint is present.

## Next milestone

v0.3.0 will commission the integration in a live Home Assistant instance and validate discovery of the user's controller and four irrigation areas.
