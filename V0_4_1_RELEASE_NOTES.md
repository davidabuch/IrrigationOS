# IrrigationOS v0.4.1 — Canonical Controller Model and Observation Reliability

## Purpose

This release stabilizes identity and observation semantics before any execution work. It remains strictly read-only.

## Highlights

- Persisted IrrigationOS controller identities with explicit replaceable Rachio bindings.
- Permanent numbered controller slots through detected capacity, including unused placeholders.
- Stable `Zone N` device naming independent of vendor and landscape renames.
- Observation timestamps, freshness, source quality, and endpoint-specific partial failures.
- Confirmed idle state separated from unavailable current-watering status.
- Provider-factory runtime composition and dynamic entity additions.
- Safe last-known entity behavior for removed or temporarily unavailable hardware.
- Automatic migration of v0.4.0 entity/device identities and landscape profile overrides.
- Behavioral coverage for identity, slots, migration, partial failures, reconciliation, composition, and diagnostics.
- A dedicated Home Assistant CI smoke suite for config flow, dynamic entities, registry migration, and diagnostics redaction.
- HACS repository validation on every pull request and main-branch update.

## Safety boundary

No start, stop, scheduling, rain-delay, or command-delivery endpoint is included. Observation is the only implemented operating mode.

## Migration note

The first load upgrades config-entry schema version 1 to version 2. It requires a successful read-only provider discovery so existing vendor-derived registry identities can be mapped to their canonical controller slots.
