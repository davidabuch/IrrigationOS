# v1.0.22 — Safety Manager and Execution Authorization Foundation

## Purpose

v1.0.22 adds a deterministic, fail-closed safety and authorization evidence layer between control-readiness evidence and any future live execution boundary.

This milestone **does not enable irrigation equipment control**.

## Safety gates

The authorization assessment requires all of the following before it can become `manual_review_eligible`:

- v1.0.21 control-readiness criteria are met;
- aggregate IrrigationOS health is `HEALTHY`;
- trustworthy controller observation is no more than 12 minutes old;
- every configured controller is online;
- the synchronized decision pipeline is available;
- controller ownership is explicitly commissioned;
- no watering session is currently active; and
- any candidate start command is within the provisional one-hour single-command runtime ceiling.

The current integration deliberately reports controller ownership as `uncommissioned`, because no explicit execution-ownership commissioning contract exists yet.

## Fail-closed restart behavior

Positive authorization is never persisted. On every Home Assistant restart the authorization layer begins blocked and must recompute from current evidence. The summary exposes `restart_policy=fail_closed_recompute_required` and `positive_authorization_persisted=false`.

## Manual review boundary

Even a synthetic context that passes every safety prerequisite is only `manual_review_eligible`. The integration keeps both `live_control_feature_enabled` and `live_control_authorized` hard-coded `false`.

## Home Assistant surface

`sensor.irrigationos_execution_authorization` exposes the current status, gate outcomes, blocker codes, runtime ceiling, ownership state, restart policy, and explicit non-authorization flags.

## Safety boundary

v1.0.22 adds no controller command dispatch, valve actuation, schedule upload, rain-delay mutation, or other write path. Existing execution models remain simulation-only.
