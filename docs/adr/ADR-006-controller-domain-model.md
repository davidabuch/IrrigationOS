# ADR-006: Controller-Agnostic Domain Model

## Status

Accepted for v0.2.0.

## Context

Rachio calls irrigation outputs "zones," but IrrigationOS must support controllers with different terminology and future landscape models that may combine multiple delivery devices. Higher intelligence layers must not depend on Rachio payload shapes or identifiers.

## Decision

IrrigationOS defines controller-agnostic domain objects:

- `IrrigationController`
- `IrrigationArea`
- `ControllerCapabilities`
- `ControllerRegistrySnapshot`
- normalized availability and area-state enums

Each vendor adapter maps native API payloads into these objects. The Rachio adapter owns all Rachio-specific translation. Internal IDs are namespaced by provider while native IDs are retained only at the adapter boundary and in redacted diagnostics.

The term **Irrigation Area** is used above the adapter boundary. A Rachio Zone is one implementation of an Irrigation Area.

## Consequences

- Weather, soil, planning, and execution layers remain controller-independent.
- Additional controller adapters can be registered without changing the domain model.
- Capability flags prevent higher layers from assuming unsupported observations or commands.
- v0.2.0 remains read-only; all command capabilities are false.
