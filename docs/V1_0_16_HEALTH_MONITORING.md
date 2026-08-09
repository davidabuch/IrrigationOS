# v1.0.16 — Health Monitoring and Incident Diagnostics

## Purpose

v1.0.16 adds operator-facing health monitoring to the released v1.0 architecture without changing irrigation science, recommendations, schedules, or controller behavior.

The health model distinguishes redundancy doing its job from loss of trustworthy observation.

## Aggregate health states

- `INITIALIZING` — six-minute startup/reload grace period; no new incident is created.
- `HEALTHY` — polling, realtime observation, controller availability, pipeline evaluation, health persistence, and daily logging are healthy.
- `DEGRADED` — IrrigationOS is still trustworthy but one redundant or diagnostic path is impaired. Examples include realtime registration failure with successful polling fallback, a single failed poll while observations remain fresh, partial controller unavailability, or daily-log persistence failure.
- `UNHEALTHY` — trustworthy operation is lost. Examples include observations older than twelve minutes, all configured controllers unavailable for ten minutes, or a missing synchronized pipeline after a successful observation refresh.

The health evaluator runs without issuing network/controller commands and is reevaluated every minute so elapsed-time thresholds do not depend on the five-minute polling schedule.

## Incident latching

A genuine `UNHEALTHY` transition starts a persistent incident and fires the Home Assistant event `irrigationos_health_unhealthy` once for that incident.

The incident remains active through intermediate `DEGRADED` states and closes only after IrrigationOS returns to `HEALTHY`, at which time `irrigationos_health_recovered` is fired with the approximate incident duration.

Historical incident state remains latched after recovery until the operator presses `button.irrigationos_reset_health_incident`. The button is available only while current health is `HEALTHY` and affects diagnostic history only.

## Home Assistant entities

- `sensor.irrigationos_health`
- `binary_sensor.irrigationos_health_incident`
- `button.irrigationos_reset_health_incident`

Existing cloud, realtime, polling-fallback, controller, refresh, and pipeline entities remain available for component-level diagnosis.

## Daily operational logs

IrrigationOS writes safe JSONL evidence to:

`/config/irrigationos_logs/irrigationos_YYYY-MM-DD.jsonl`

The filename follows the Home Assistant local calendar day. Each record includes local and UTC timestamps, integration version, event type, aggregate health, reason codes, observation age, polling/realtime state, controller-count summaries, pipeline status/stage/blocker codes, and incident state.

The recorder intentionally excludes API keys, webhook credentials, account IDs, controller IDs/native IDs, zone IDs, serial numbers, MAC addresses, and property coordinates.

Logs are retained for 30 local calendar days. A logging failure degrades diagnostics but does not make controller observation itself unhealthy.

## Notification contract

The integration emits transition events rather than hard-coding a user-specific notify service:

- `irrigationos_health_unhealthy`
- `irrigationos_health_recovered`

This allows a Home Assistant automation to send exactly one unhealthy notification and one recovery notification while keeping `DEGRADED` dashboard-only by default. An external watchdog may additionally treat `sensor.irrigationos_health` remaining `unavailable` as an integration-level outage that cannot be self-reported by code that failed to load.

## Safety boundary

This milestone is observability infrastructure only. It does not start, stop, enable, disable, reschedule, retry, or otherwise actuate irrigation equipment. It does not alter water requirement, stress, health, recommendation, planning, scheduling, execution-simulation, or runtime-monitoring decisions.
