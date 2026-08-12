# v1.0.32 — Live Commissioning Protocol & First-Live Acceptance Criteria

## Purpose

Define the explicit human-controlled commissioning gate that must exist before any later milestone may introduce Rachio command delivery. This milestone remains completely non-actuating.

## Bounded first-live envelope

A future first-live trial is constrained to:

- exactly one canonical controller slot;
- exactly one canonical irrigation-area slot;
- a requested runtime of no more than 120 seconds;
- an explicitly open supervised daytime commissioning window;
- healthy IrrigationOS state and observation age no greater than 120 seconds;
- zero active external/manual/provider watering; and
- a still-valid `validated_review_eligible` integrated safety review.

## Operator approval

Approval is explicit, ephemeral, single-use, and restart-unsafe. It expires ten minutes after creation, is never written to Home Assistant storage, and is unusable after consumption. A Home Assistant restart therefore always requires new approval.

## Required acceptance evidence

Before a later first-live actuation milestone can be accepted, evidence must show:

1. command intent recorded;
2. operator approval recorded;
3. intended target observed during preflight;
4. start acknowledged;
5. watering observed on the intended target;
6. runtime remained within the approved ceiling;
7. stop acknowledged;
8. no safety preemption occurred;
9. no external watering was displaced; and
10. post-run reconciliation passed.

## Safety boundary

`first_live_trial_eligible` is evidence only. It is not command permission. The following remain false:

- `first_live_trial_dispatch_enabled`;
- `live_mode_commissionable`;
- `live_control_feature_enabled`;
- `live_control_authorized`.

No Rachio command, Home Assistant service call, valve write, switch write, or controller dispatch path is introduced by v1.0.32.

## Next boundary

Any later first-live milestone must implement only the minimum supervised command-delivery path necessary to execute this envelope and must consume the single-use approval before dispatch.
