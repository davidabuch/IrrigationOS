# IrrigationOS v1.0.26 — Command Acknowledgement & Timeout Foundation

## Purpose

v1.0.26 implements the second required Live-mode safety safeguard as a deterministic, non-actuating acknowledgement state machine. It proves how a future dispatched command must be acknowledged, rejected, or timed out before any provider delivery path exists.

## Delivered

- A canonical acknowledgement lifecycle: `waiting`, `acknowledged`, `rejected`, and `timed_out`.
- A provisional 30-second acknowledgement deadline.
- Deadline-first semantics: an acknowledgement observed after the deadline is classified as timed out even if the provider would otherwise report success.
- Immutable transition evidence with stable event identifiers and 30-day local JSONL retention.
- Synthetic-only manager methods and diagnostics; no controller, network, or Home Assistant service dispatch capability.
- Explicit diagnostics showing `synthetic_only: true`, `dispatch_capability: false`, and `restart_reconciliation: false`.
- Live-mode safety architecture revision 3 with acknowledgement/timeout handling marked implemented.

## Safety Boundary

This milestone does **not** send commands to Rachio or any other controller. The acknowledgement manager can only exercise synthetic state transitions. Restart-safe command reconciliation remains deliberately unimplemented and is the next separate safety milestone.

Live-mode commissioning, the Live control feature, and Live control authorization remain disabled.
