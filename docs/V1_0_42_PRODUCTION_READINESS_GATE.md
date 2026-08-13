# v1.0.42 — Production Readiness Gate

## Purpose and authority boundary

v1.0.42 adds a deterministic, fail-closed answer to whether an IrrigationOS installation has enough current evidence to progress beyond commissioning into supervised production or a future bounded unattended canary. The result is advisory only. It does not authorize watering, start a canary, schedule commands, expand validated targets, change the 120-second ceiling, or alter any existing confirmation or no-retry rule.

The readiness result is recomputed from current coordinator evidence and is not persisted. A restart begins with `INITIALIZING` health and therefore `not_ready`; no stale readiness, commissioning approval, pending operation, monitor, watering command, or retry is restored.

## Production target set

A canonical area counts as a production target only when all three current facts are true:

- `configured == True`
- `enabled == True`
- a controller binding exists

Identity is the privacy-safe `(controller_slot, area_slot)` pair. Total controller capacity is irrelevant. Consequently, the live installation's production set is exactly areas 1, 2, 4, and 5 on controller slot 1. Area 3 and every other unused slot among the controller's 16 possible slots do not block readiness.

Every production target must exist in the durable validated-target registry. An enabled configured bound target without its own first-live PASS produces `configured_target_not_validated`.

## Readiness states

- `not_ready`: one or more supervised-production blockers exist.
- `ready_for_supervised_production`: all current installation, commissioning, observation, persistence, conflict, and safety prerequisites pass. Operation remains manually invoked and exactly confirmed.
- `ready_for_unattended_canary`: all supervised-production requirements pass and an explicit unattended-canary approval prerequisite is present.

No unattended-canary approval surface or executor exists in v1.0.42, so normal runtime evaluation cannot reach the canary state. Keeping the prerequisite explicit prevents the two readiness levels from silently becoming equivalent.

## Fail-closed blockers

The engine emits deterministic sorted blocker codes including:

- `system_not_healthy`
- `controller_ownership_not_confirmed`
- `execution_boundary_review_not_acknowledged`
- `controller_topology_mismatch`
- `observation_stale`
- `cloud_connection_unhealthy`
- `realtime_observation_unhealthy`
- `configured_target_not_validated`
- `validated_target_persistence_unhealthy`
- `first_live_persistence_unhealthy`
- `supervised_operation_persistence_unhealthy`
- `critical_persistence_or_runtime_fault`
- `active_watering_conflict`
- `supervised_operation_in_progress`
- `safety_prerequisites_not_met`
- `no_configured_production_targets`

The future canary level separately reports `unattended_canary_approval_required`.

## Inputs and visibility

The coordinator-owned manager reuses current aggregate health, polling/cloud and realtime health, observation age, ownership and topology evidence, validated-target persistence, first-live and supervised-operation persistence, operational-log and aggregate persistence health, active canonical watering observations, supervised-operation progress, and integrated supervised-safety prerequisites.

`sensor.irrigationos_production_readiness` exposes the state and privacy-safe evidence. `binary_sensor.irrigationos_production_ready` is on only for supervised-production readiness or higher. Diagnostics expose the same summary. No provider-native controller or zone IDs, API credentials, or official Home Assistant Rachio integration data are consumed or exposed.
