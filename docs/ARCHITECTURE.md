# IrrigationOS Architecture

## Current v1.0 release-candidate architecture

IrrigationOS currently operates in an **Observation and simulation only** boundary. The Home Assistant coordinator reads canonical controller observations, builds the Landscape Digital Twin and scientific inputs, evaluates the complete deterministic domain pipeline, and exposes read-only entities and diagnostics. No pipeline output is dispatched to a controller.

```text
Home Assistant config / entities / diagnostics
                    |
                    v
            IrrigationOS Coordinator
        +-----------+------------+
        |                        |
        v                        v
Controller observations   Scientific inputs
        |                        |
        +-----------+------------+
                    v
          Landscape Digital Twin
                    |
                    v
             Domain Pipeline
Observations -> Knowledge -> Plant Water Requirement
             -> Plant Stress -> Plant Health
             -> Recommendations -> Planning
             -> Scheduling -> Execution simulation
             -> Runtime Monitoring
                    |
                    v
      Read-only HA entities / diagnostics

        [No controller command dispatch]
```

Each downstream layer consumes canonical immutable upstream outputs and preserves provenance. The pipeline public contract is frozen in `docs/V1_0_PUBLIC_API_CONTRACT.json`.

## Architectural boundaries

### 1. Home Assistant boundary

Owns config entries, entities, device-registry integration, options, diagnostics, lifecycle management, and coordinator refreshes. Domain logic does not depend on Home Assistant entity IDs.

### 2. Controller-adapter boundary

Translates vendor-specific Rachio observations into canonical controller models. Vendor IDs, payloads, errors, and endpoints remain inside the adapter boundary. The adapter contains future operation capabilities, but v1.0 release-candidate pipeline code does not invoke a watering-control endpoint.

### 3. Observation boundary

Normalizes controller and environmental observations into typed immutable inputs with timestamps, source, freshness, quality, and partial-failure metadata.

### 4. Landscape-model boundary

Maintains provider-neutral controller identities, permanent physical slot identities, and per-area landscape profiles. Vendor IDs, mutable names, and Home Assistant entity IDs are bindings rather than domain identity.

### 5. Domain-pipeline boundary

The synchronized pipeline is deterministic and layered. Plant Water Requirement, Stress, Health, Recommendations, Planning, Scheduling, Execution simulation, and Runtime Monitoring each have independent canonical models, policy/version contracts, and tests. Downstream stages do not recompute upstream science.

### 6. Execution-simulation boundary

The current Execution layer creates canonical command **models** only. It does not dispatch those commands. Runtime Monitoring evaluates only evidence that actually exists and does not fabricate acknowledgements, failures, or recovery execution.

### 7. Future live-execution boundary

Controller command dispatch, ownership, command attribution, automated recovery, and Flight Recorder-backed live accountability remain future commissioning work. Those features must stay behind explicit safety gates and must not bypass the canonical execution boundary.

## Data-flow principle

Data flows upward as observations and scientific evidence, then through explicit immutable domain outputs. Controller-specific code does not make irrigation-policy decisions, and domain code does not call vendor APIs.

## Canonical identities and compatibility

Controller identifiers are generated and persisted by IrrigationOS. Permanent slot identifiers are based on canonical controller identity and physical slot number. Unused slots remain explicit and are registered disabled by default so later configuration reuses the same identity.

The v1.0 public exports, enum values, schema/algorithm versions, and dataclass field order are protected by the machine-readable public API contract and compatibility tests.

## Failure behavior

- Authentication failure requests reauthentication rather than inventing current data.
- Rate limiting preserves explicit provider failure/freshness semantics.
- Malformed payloads are rejected rather than silently normalized into false facts.
- Missing scientific evidence produces conservative partial/blocked outputs.
- Runtime Monitoring does not fabricate command outcomes for simulated commands.
- Reload, migration, persistence, and permanent entity identities are regression-tested.

## Security

API tokens remain in Home Assistant config-entry storage. Logs and diagnostics redact credentials, webhook secrets/URLs, vendor bindings, serial/MAC identifiers, pipeline identifiers where appropriate, and exact property coordinates. Future Flight Recorder data must follow the same redaction boundary.
