# Changelog

All notable changes to IrrigationOS will be documented here.

## [0.3.0] - 2026-08-01

### Added

- Canonical Landscape Digital Twin and per-area landscape profiles.
- Provenance and confidence for landscape values.
- Conservative controller-derived defaults and user override support.
- Home Assistant landscape profile sensors and options-flow foundation.
- ADR-007 for the landscape/controller separation boundary.

## [0.2.0] - 2026-08-01

### Added

- Controller adapter protocol and runtime registry.
- Canonical controller and irrigation-area domain models.
- Rachio translation boundary and generic Home Assistant entities.
- ADR-006 documenting the controller domain model.

## [0.1.1] - 2026-08-01

### Added

- Product vision, master roadmap, and high-level architecture.
- Formal Observation, Simulation, Shadow, and Live operating-mode boundaries.
- Engineering and release standards.
- ADR-001 through ADR-005 covering controller adapters, staged execution, weather providers, soil modeling, and decision transparency.
- Governance-document repository validation and tests.

## [0.1.0] - 2026-08-01

### Added

- Standalone Rachio API-key authentication and account discovery.
- Typed controller and zone observation models.
- Read-only polling coordinator and Home Assistant observation entities.
- Redacted diagnostics and explicit API error handling.
- Expanded tests for API behavior and payload normalization.

## [Unreleased]

### Planned

- Home Assistant installation and live account commissioning.
- Weather and soil data foundations.

## [0.0.1] - 2026-08-01

### Added

- HACS-compatible Home Assistant custom integration scaffold
- Direct Rachio API-key config-flow foundation
- Observation-only coordinator and entities
- Repository quality tooling with pytest, Ruff, and MyPy
- GitHub Actions CI and repository metadata validation
- Architecture specification and contribution/security guidance
