# v1.0.43 — First Bounded Unattended Canary

## Purpose

v1.0.43 permits exactly one explicitly approved unattended irrigation canary on one already validated production target. It is a tightly bounded commissioning experiment, not general autonomous irrigation, scheduler authority, recurring execution, multi-zone operation, or permission for the planning and recommendation pipelines to actuate hardware.

## Explicit single-use approval

`irrigationos.authorize_unattended_canary` records permission but never waters. The operator must supply the exact phrase `AUTHORIZE ONE UNATTENDED CANARY`, one canonical controller slot, one canonical area slot, and one exact runtime from 15 through 60 seconds.

Approval is:

- valid for ten minutes;
- bound to the exact config entry, canonical target, and runtime;
- usable once;
- held only in coordinator memory;
- removed by reload or restart;
- insufficient by itself to establish safety.

Only a target that is both a current configured/enabled/bound production target and a member of the durable validated-target registry may receive approval.

## One-shot execution

`irrigationos.run_unattended_canary` forces a fresh controller observation and requires the exact approval match. Execution additionally requires `ready_for_unattended_canary`, healthy and fresh polling/realtime evidence, commissioned ownership and acknowledged boundary review, matching topology, healthy persistence, integrated safety prerequisites, an online idle controller target, zero active watering, and no supervised or canary operation already in progress.

After durable dispatch intent is recorded, approval is consumed before transport. The Rachio start transport is invoked at most once. A failed or ambiguous transport attempt never restores approval and is never retried. The existing provider-independent canonical controller/area identity remains the public and durable identity; the native binding is resolved only inside the transport call.

## Readiness behavior

A valid matching approval supplies the explicit v1.0.42 canary prerequisite, allowing `ready_for_unattended_canary` only while all other readiness gates pass. Expiration, consumption, target invalidation, reload, or restart removes that prerequisite. Once dispatch is accepted, in-progress watering also blocks readiness. `live_control_authorized` remains `false`.

## Audit and terminal acceptance

Privacy-safe append-only evidence is written separately to:

- `/config/irrigationos_logs/unattended_canary_audit.jsonl`
- `/config/irrigationos_logs/unattended_canary_acceptance.jsonl`

Audit records contain only canary/approval correlation IDs, canonical controller and area slots, bounded runtime, event type, detail code, and timestamp. They contain no provider-native IDs or credentials.

Terminal acceptance is `pass`, `fail`, or `indeterminate` and records explicit approval, target/runtime match, production readiness, durable intent, approval consumption, preflight observation, start acknowledgement, observed watering, runtime ceiling, return to idle, concurrent watering, safety preemption, reconciliation, and terminal audit criteria. The latest terminal record is also persisted in Home Assistant storage.

## Home Assistant visibility

- `sensor.irrigationos_unattended_canary_approval`
- `binary_sensor.irrigationos_unattended_canary_in_progress`
- `sensor.irrigationos_unattended_canary_acceptance`

All attributes and diagnostics use privacy-safe canonical data only.

## Restart and failure semantics

Restart or reload restores only the latest completed acceptance. Approval returns to `none`, in-progress returns to `off`, no monitor is recreated, and no command is resumed or retried. Production readiness is recomputed from current evidence and cannot retain stale unattended authority.

This milestone adds no recurring trigger, scheduler dispatch, planning execution, recommendation execution, unattended multi-zone run, automatic retry, general Live mode, or autonomous watering authority.
