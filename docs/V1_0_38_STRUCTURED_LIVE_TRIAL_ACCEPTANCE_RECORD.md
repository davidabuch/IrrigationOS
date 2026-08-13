# v1.0.38 — Structured Live Trial Acceptance Record

v1.0.38 turns the v1.0.37 terminal supervised-trial observations into an explicit persistent acceptance result without broadening command authority.

## Behavior

After a supervised first-live command is accepted, the existing asynchronous monitor continues to use canonical controller refreshes. The monitor records the approved area entering `WATERING`, watches for other concurrent watering, and records the approved area returning to `IDLE` within the bounded completion window.

At terminal evaluation IrrigationOS persists a privacy-safe structured record with an overall `pass`, `fail`, or `indeterminate` status and explicit criterion states for:

- durable command intent;
- single-use operator approval;
- fresh preflight target observation;
- accepted start transport outcome;
- target watering observed;
- requested runtime within the 120-second supervised ceiling;
- target returned to idle;
- no concurrent watering observed during the supervised monitor window; and
- post-run reconciliation to canonical idle state.

The record also contains canonical controller/area slots, the IrrigationOS attempt ID, polling-bounded observed runtime, refresh-error count, and terminal detail code. Native Rachio identifiers are not included.

## Home Assistant and restart behavior

The latest structured result is stored with Home Assistant storage and restored after restart. It is exposed by `sensor.irrigationos_first_live_trial_acceptance` and included in redacted diagnostics.

## Safety boundary

This milestone adds evidence only. It does not add a command service, command button, automatic retry, autonomous scheduler, multi-zone execution, or general Live authorization. Observation remains the default commissioned operating mode and all existing first-live commissioning gates remain authoritative.
