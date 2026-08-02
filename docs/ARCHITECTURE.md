# IrrigationOS Architecture

## System view

```text
Home Assistant UI / Services / Diagnostics
                 |
                 v
          IrrigationOS Runtime
                 |
    +------------+-------------+
    |                          |
Observation Plane        Decision Plane
    |                          |
Controller Adapter       Landscape Digital Twin
Weather Providers        Weather Intelligence
Local Sensors            Soil Intelligence
                         Plant Intelligence
                         Water Budget Engine
                         Policy / Decision Engine
                         Scheduling Engine
                                  |
                                  v
                           Execution Boundary
                                  |
                                  v
                          Controller Adapter
                                  |
                    Rachio / future controllers
```

## Architectural boundaries

### 1. Home Assistant boundary

Owns config entries, entities, services, device registry integration, options, diagnostics, and lifecycle management. Domain logic should not depend on entity IDs.

### 2. Controller-adapter boundary

Translates canonical controller observations and operations into vendor-specific API calls and responses. Rachio-specific IDs, payloads, errors, and endpoints remain inside the adapter.

### 3. Observation boundary

Normalizes remote controller data, weather data, local sensors, and future soil observations into typed immutable observations with timestamps, source, and quality metadata.

### 4. Landscape-model boundary

Maintains stable internal identifiers and profiles for zones, plants, soils, slopes, irrigation hardware, and subareas. Vendor zone IDs are bindings, not domain identities.

### 5. Decision boundary

Consumes a complete immutable evaluation context and returns a proposed plan plus alternatives, policy results, confidence, and explanations. It does not call controller APIs.

### 6. Execution boundary

Accepts approved canonical operations, evaluates runtime safety and ownership, registers command attribution, dispatches through the controller adapter, and records receipts.

### 7. Flight Recorder boundary

Records material observations, evaluations, plans, commands, acknowledgements, external operations, safety decisions, errors, and recovery actions. Secrets are never recorded.

## Data-flow principle

Data flows upward as observations and downward as explicit operations. Lower layers do not make irrigation-policy decisions, and higher layers do not issue vendor API calls directly.

## Canonical identities

Every controller, slot, landscape unit, plan, and operation receives an IrrigationOS identifier. Controller identifiers are generated and persisted by IrrigationOS. Permanent slot identifiers are based on canonical controller identity and physical slot number. Vendor IDs, mutable names, and Home Assistant entity IDs are replaceable bindings.

Controllers expose permanent slots from 1 through detected capacity. Unused slots remain explicit and are registered disabled by default so later configuration reuses the same identity.

## Failure behavior

- Authentication failure: mark provider unavailable and request reauthentication.
- Rate limiting: respect retry guidance and retain last-known observation with staleness metadata.
- Malformed payload: reject the update rather than silently inventing values.
- Missing weather/soil inputs: reduce confidence and remain conservative.
- Restart during live execution: reconcile actual controller state before issuing any command.
- Unattributed state change: classify as external/manual and preserve it unless safety requires intervention.

## Security

API tokens remain in Home Assistant config-entry storage. Logs, diagnostics, exceptions, fixtures, and Flight Recorder events must redact or omit credentials and identifying account data not required for support.
