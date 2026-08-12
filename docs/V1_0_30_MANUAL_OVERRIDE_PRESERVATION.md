# v1.0.30 — Manual Override Preservation

## Purpose

This milestone implements the sixth required Live-mode safety safeguard while keeping IrrigationOS non-actuating.

A future IrrigationOS command lifecycle must not displace watering that is already active unless the active watering is explicitly and confidently attributed to IrrigationOS itself. This preserves direct manual watering, controller/provider schedules, and any activity whose ownership remains ambiguous.

## Fail-closed attribution policy

For active observed watering:

- `irrigationos` attribution is the only non-blocking attribution.
- `manual` watering is preserved.
- `provider_schedule` watering is preserved.
- `external_unknown` watering is preserved because ownership is ambiguous.
- any unrecognized future attribution value is preserved fail-closed.

The safeguard operates only on synthetic command lifecycles. It records local evidence and can terminate a pending synthetic acknowledgement lifecycle, but it has no controller dispatch capability.

## Evidence

Preservation events are immutable JSONL evidence retained for 30 days under the IrrigationOS log root. Evidence contains aggregate attribution/reason information and intentionally excludes controller and area identifiers.

## Live-mode boundary

With this milestone, all six required safeguards are represented in code:

1. command attribution and receipts
2. acknowledgement and timeout handling
3. restart-safe command reconciliation
4. safety preemption path
5. sunrise hard stop
6. manual override preservation

Completing the six safeguard implementations does **not** enable Live mode. `live_mode_commissionable`, `live_control_feature_enabled`, and `live_control_authorized` remain false. Integrated safety review and commissioning validation are required before any future actuation work is considered.
