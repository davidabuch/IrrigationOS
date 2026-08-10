# v1.0.23 — Controller Ownership Commissioning

## Purpose

v1.0.23 replaces the hard-coded ownership placeholder from v1.0.22 with explicit, operator-driven commissioning evidence. It remains non-actuating and does not enable live irrigation control.

## Delivered

- Persistent ownership commissioning stored through Home Assistant Store.
- Commissioning bound to the exact canonical controller set present when confirmed.
- Automatic `stale_topology` fail-closed state when controller membership changes.
- Separate manual execution-boundary review acknowledgement.
- Operator buttons to confirm ownership, acknowledge the boundary review, and revoke ownership.
- Operator-facing ownership commissioning sensor and privacy-safe diagnostics.
- Execution authorization now requires both effective ownership confirmation and acknowledged boundary review.

## Safety semantics

Ownership confirmation is a commissioning fact, not command permission. The acknowledgement button becomes available only when every other v1.0.22 execution-authorization gate has passed and the boundary-review acknowledgement is the sole remaining blocker.

Controller topology changes invalidate effective ownership until the operator explicitly recommissions the new canonical controller set. Revocation immediately fails closed.

`live_control_feature_enabled` remains `false` and `live_control_authorized` remains `false` in this milestone.

## Persistence

Explicit operator ownership decisions are persisted. Positive execution authorization is still never persisted. On restart, ownership evidence is restored, current controller topology is re-evaluated, and execution authorization is recomputed from current safety evidence.
