# v1.0.39 — Bounded Supervised Operational Command Path

## Purpose

v1.0.39 transitions IrrigationOS from one-time first-live commissioning into a narrowly bounded manual operational command path without enabling general Live mode or autonomous scheduling.

## Operator boundary

The release registers exactly one Home Assistant service: `irrigationos.run_supervised_operation`.

A command is eligible only when all of the following are true:

- the latest persisted first-live acceptance result is `pass`;
- the requested controller slot and area slot exactly match that accepted first-live target;
- aggregate IrrigationOS health is `HEALTHY`;
- current integrated supervised-safety prerequisites remain satisfied;
- the canonical controller observation is fresh and `CONFIRMED`;
- controller ownership is confirmed and the execution-boundary review is acknowledged;
- no watering session is already active;
- the selected Rachio controller is online and enabled;
- the selected area is configured, enabled, bound, and currently `IDLE`;
- runtime is between 1 and 120 seconds;
- the operator types `RUN SUPERVISED OPERATIONAL WATERING` exactly; and
- no other IrrigationOS-supervised operational command is awaiting terminal observation.

## Dispatch behavior

Before actuation, IrrigationOS writes a durable provider-ID-free dispatch intent to `/config/irrigationos_logs/supervised_operation_audit.jsonl`. If that write fails, no command is sent.

The command transport performs one bounded Rachio zone-start request. Transport failures are terminal for that attempt and are never retried automatically.

After an accepted start, a background monitor uses canonical controller refreshes to observe the selected area enter `WATERING` and later return to `IDLE`. It records terminal audit evidence and appends a structured result to `/config/irrigationos_logs/supervised_operation_acceptance.jsonl`.

## Deliberate limits

v1.0.39 does not:

- enable a Home Assistant command button;
- permit a target other than the latest first-live validated controller/area pair;
- dispatch from the coordinator refresh loop;
- dispatch from the scheduling engine;
- retry ambiguous network outcomes;
- promote Observation to general Live mode;
- set `live_control_feature_enabled` or `live_control_authorized` true; or
- enable autonomous irrigation.

The supervised operational service is an explicit human-in-the-loop bridge for additional physical validation, not autonomous execution authority.
