# v1.0.17 — Observation History and Watering Session Recorder

## Purpose

v1.0.17 turns canonical controller snapshots into persistent, replayable watering-session evidence for a multi-week control-readiness observation period. It does not change irrigation science, recommendations, planning, scheduling, execution simulation, runtime monitoring, or controller behavior.

## Architecture

```text
Polling refresh ───────────────┐
                              v
Accepted realtime event -> canonical refresh
                              |
                              v
                 WateringSessionReconciler
                    |        |        |
                    v        v        v
               HA Store   session   three compact
                          JSONL log   HA sensors
```

The recorder consumes only provider-neutral `ControllerRegistrySnapshot` objects. Realtime payloads never become session state directly: an accepted, deduplicated event marks the source of the immediate canonical refresh, and the refreshed snapshot remains authoritative.

The dedicated `observation_history` package contains:

- frozen canonical session and event models;
- deterministic per-area reconciliation;
- Home Assistant Store lifecycle persistence;
- a separate safe daily JSONL recorder; and
- vendor-ID-free presentation summaries.

## Session identity and boundaries

A session ID is a deterministic SHA-256 identity derived from canonical controller ID, canonical area ID, permanent slot number, and the first observed UTC timestamp. Mutable names and provider-native identifiers do not participate.

Transitions are reconciled independently per canonical area:

- trustworthy non-watering to watering opens a session;
- watering to watering updates the same session;
- trustworthy watering to non-watering closes it;
- unavailable, partial, offline, missing-controller, unknown, or otherwise untrustworthy observations never falsely close it.

Polling supplies observation windows rather than exact physical start/stop timestamps. Poll-discovered sessions are therefore marked incomplete with `polling_window` precision. Realtime-triggered refreshes use `event_bounded` precision, but the event alone does not prove ownership. A session may cross local midnight without splitting; only the evidence-log filename rolls to the new local day.

## Restart reconciliation

Active sessions and recent completed summaries are persisted through Home Assistant Store. On restart, active sessions retain their stable ID and are marked `reconstructed_after_restart`, incomplete, and reconstruction-precision. The first valid snapshot either continues the same logical session or closes it conservatively. No duplicate session is created.

## Attribution

Attribution is intentionally conservative:

- `external_unknown`
- `provider_schedule`
- `manual`
- `irrigationos`

The current Rachio adapter does not expose explicit, normalized evidence proving that observed watering was started by a provider schedule or manually. Consequently, every naturally observed v1.0.17 session defaults to `external_unknown` with zero specific-owner confidence and explicit reason codes. Realtime event type/subtype is observation-source evidence only.

Because IrrigationOS has no commissioned actuation path, naturally observed sessions are never labeled `irrigationos`.

## Persistence and evidence logging

Runtime restart state uses Home Assistant Store and does not depend on log replay. A separate JSONL stream is written under:

`/config/irrigationos_logs/irrigationos_sessions_YYYY-MM-DD.jsonl`

Filenames use the Home Assistant local day, records include local and UTC timestamps, and retention is 30 local calendar days. The existing `irrigationos_YYYY-MM-DD.jsonl` health/operational log remains unchanged in purpose.

Session logs include stable session identity, slot number, safe display name, boundaries, duration, attribution, observation source/quality, timestamp precision, restart reconstruction, and incompleteness. They exclude provider-native controller/zone IDs, account IDs, API keys, webhook data, signatures, serial numbers, MAC addresses, and coordinates.

## Home Assistant presentation

v1.0.17 adds only three aggregate sensors:

- `sensor.irrigationos_current_watering_session`
- `sensor.irrigationos_last_completed_watering_session`
- `sensor.irrigationos_watering_sessions_today`

No entity is created per historical session. Diagnostics expose the same safe summaries plus persistence and session-log health.

## Safety boundary

Observation and non-actuating Simulation remain the only commissioned operating boundaries. The observation-history package exposes no Home Assistant service call, valve action, controller command, start/stop operation, rain-delay operation, schedule modification, recommendation change, or automatic attribution to IrrigationOS.
