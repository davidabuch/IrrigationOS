# IrrigationOS v0.1.0 Release Notes

## Standalone Rachio API Foundation

This release establishes independent, read-only communication with Rachio. It does not depend on Home Assistant's built-in Rachio integration and does not issue irrigation commands.

### Included

- UI Config Flow for entering and validating a Rachio API key.
- Automatic Person ID discovery through `/public/person/info`.
- Automatic controller and zone discovery through `/public/person/{id}`.
- Typed, normalized account, controller, and zone models.
- Five-minute read-only polling coordinator.
- Controller and zone devices and observation entities.
- Authentication, connection, invalid-response, and rate-limit handling.
- Redacted diagnostics that exclude credentials, identifiers, serial numbers, MAC addresses, and coordinates.
- Observation-only safety boundary.
- Expanded automated tests.

### Explicitly excluded

- Starting or stopping zones.
- Changing schedules or rain delays.
- Weather, soil lookup, ET, moisture modeling, planning, or live execution.
