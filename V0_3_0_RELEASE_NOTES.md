# IrrigationOS v0.3.0 — Landscape Digital Twin Foundation

## Summary

v0.3.0 introduces the canonical Landscape Digital Twin. Rachio continues to supply hardware observations; IrrigationOS now owns a separate, controller-agnostic description of the landscape served by each irrigation area.

## Added

- Typed `LandscapeProfile` and `IrrigationAreaProfile` models.
- Profile values with provenance and confidence.
- Plant, irrigation-method, sun-exposure, and soil-texture vocabularies.
- Conservative controller-to-landscape seed translation.
- Per-area profile completion scoring.
- Home Assistant profile sensors.
- Options-flow foundation for editing one area profile at a time.
- Landscape data in redacted diagnostics.
- ADR-007 documenting the Landscape Digital Twin boundary.

## Safety

This release remains Observation-only. It contains no Rachio start, stop, rain-delay, or schedule endpoints and creates no Home Assistant switch platform.

## Validation target

- Repository validator passes.
- 27 tests pass.
- Ruff passes.
- MyPy passes.
- `git diff --check` passes.


## RC2 validation corrections

- Modernized Python 3.13 generic syntax for Ruff compatibility.
- Corrected test import ordering.
- Added a targeted MyPy suppression for the Home Assistant callback decorator.
- Removed trailing whitespace at the end of the integration setup module.
