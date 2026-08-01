# ADR-008: First Live Installation Boundary

## Status

Accepted for v0.4.0.

## Decision

The first field installation will validate cloud authentication, controller discovery, area discovery, current-watering observation, entity presentation, and diagnostics while preserving a hard read-only boundary.

## Consequences

- Setup presents discovered controllers and areas before creating the config entry.
- Invalid credentials use Home Assistant's reauthentication path.
- Current watering is a best-effort observation and failure of that secondary endpoint does not invalidate the base controller snapshot.
- No start, stop, schedule, or rain-delay endpoints are present.
