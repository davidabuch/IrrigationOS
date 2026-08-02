# ADR-009: Stable Controller Slot Identity

## Status

Accepted for v0.4.1.

## Context

Provider zones are mutable configuration records. Their names and native identifiers are unsuitable as the long-lived identity of a physical controller terminal, and controllers expose a fixed capacity even when only some terminals are configured.

## Decision

IrrigationOS models every detectable controller position from slot 1 through controller capacity. Each slot receives a canonical identifier beneath the persisted canonical controller identifier. Slot identity does not contain a provider zone ID or mutable name.

Configured provider zones bind to slots by their physical zone number. Unused slots remain explicit with an `unused` state and no vendor binding. Their Home Assistant entities are registered disabled by default. Default presentation names remain `Zone 1`, `Zone 2`, and so on; vendor and landscape names are separate metadata.

## Consequences

- Renaming or replacing a provider zone does not replace the Home Assistant device or canonical landscape identity.
- Capacity changes can add slots, while temporarily missing slots remain registered and unavailable rather than raising entity errors.
- Providers that cannot report capacity fall back to the highest observed slot or configured-zone count.
- A future hardware replacement may still require an explicit controller-binding migration; it must not be guessed from a mutable name.
