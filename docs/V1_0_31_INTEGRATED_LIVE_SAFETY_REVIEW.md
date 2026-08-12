# v1.0.31 — Integrated Live Safety Review & Commissioning Validation

## Purpose

Validate the six pre-Live safeguards as one deterministic safety system before any controller actuation is designed or enabled.

## Integrated safety scenarios

The release validates these scenarios together:

1. acknowledgement timeout remains terminal and fail-closed;
2. restart reconciliation restores only still-valid acknowledgement windows;
3. safety degradation requires synthetic lifecycle preemption;
4. the sunrise boundary terminates a synthetic lifecycle at or after sunrise;
5. manual, provider-scheduled, ambiguous, and unknown watering are preserved;
6. only explicitly IrrigationOS-attributed watering is non-blocking;
7. loss of readiness, ownership, or another prerequisite revokes review eligibility;
8. completion of all six safeguards never automatically enables Live control.

## Commissioning result

A fully satisfied safety architecture may become `validated_review_eligible`. This is evidence for a later manual commissioning decision only. It is not permission to operate irrigation hardware.

The following remain hard-coded false:

- `live_mode_commissionable`
- `live_control_feature_enabled`
- `live_control_authorized`

No Rachio command, Home Assistant service call, valve write, switch write, or controller dispatch path is added by this milestone.

## Next boundary

Before any actuation work, IrrigationOS must define an explicit manual commissioning protocol, bounded first-live scope, rollback behavior, and acceptance criteria. Live control remains deferred.
