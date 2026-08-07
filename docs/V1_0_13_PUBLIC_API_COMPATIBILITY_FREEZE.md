# IrrigationOS v1.0.13 — Public API and Compatibility Freeze

## Purpose

v1.0.13 freezes the public Python contracts for the completed v1.0 domain pipeline so future refactors cannot silently break downstream imports, persisted serialized structures, or integrations built against IrrigationOS.

## Frozen surface

The compatibility contract covers these public modules:

- `plant_water_requirement`
- `plant_stress`
- `plant_health`
- `recommendations`
- `planning`
- `scheduling`
- `execution`
- `runtime_monitoring`
- `pipeline`

`docs/V1_0_PUBLIC_API_CONTRACT.json` is the machine-readable source of truth for the v1.0 compatibility surface. It freezes:

- exact `__all__` exports and ordering;
- schema and algorithm version constants;
- public enum member names and serialized values;
- public dataclass field names and ordering.

## Compatibility policy

Changes to the frozen contract must be deliberate. Additive or breaking changes require an explicit compatibility decision, corresponding schema/version handling where applicable, documentation, and updated contract tests. Internal implementation details outside the exported surface may continue to evolve without being treated as public API.

## Safety boundary

This milestone changes compatibility validation only. It does not alter pipeline decisions, execution simulation, Home Assistant entity behavior, controller adapters, or irrigation actuation. Observation and simulation remain the operating boundary.
