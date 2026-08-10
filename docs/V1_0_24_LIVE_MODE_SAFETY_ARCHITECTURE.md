# IrrigationOS v1.0.24 — Live-Mode Safety Architecture

## Purpose

v1.0.24 defines the safety architecture that must exist before IrrigationOS can even be considered for Live-mode commissioning. It does not add controller commands, command adapters, or any actuation path.

## Separation of evidence and implementation

Prior milestones established shadow/replay evidence, ownership commissioning, and fail-closed execution-authorization prerequisites. Those prerequisites are necessary but are not sufficient for Live mode.

v1.0.24 introduces a separate pre-Live safety architecture assessment. Even when all existing prerequisite evidence is satisfied, Live mode remains blocked until each required execution safeguard is implemented and validated.

## Required safeguards

The architecture requires all of the following before a future Live-mode commissioning milestone may proceed:

- command attribution and durable command receipts
- acknowledgement and timeout handling
- restart-safe command reconciliation
- safety preemption path
- sunrise hard stop
- manual override preservation

All six safeguards are intentionally marked unimplemented in v1.0.24.

## Fail-closed behavior

The operator-facing safety status can report prerequisite gaps or architecture gaps, but the following remain invariant:

- `live_mode_commissionable = false`
- `live_control_feature_enabled = false`
- `live_control_authorized = false`

No positive Live-mode state is persisted and no service call or controller command path is introduced.
