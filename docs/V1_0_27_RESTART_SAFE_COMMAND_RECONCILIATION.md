# v1.0.27 — Restart-Safe Command Reconciliation

## Purpose

Make synthetic command acknowledgement state deterministic across Home Assistant restarts without adding any irrigation actuation capability.

## Behavior

At startup IrrigationOS replays the retained immutable acknowledgement JSONL evidence. For each command, only the latest lifecycle state is authoritative. An unexpired `waiting` record is restored into the in-memory pending set. A `waiting` record whose deadline passed while Home Assistant was offline is converted to a persisted `timed_out` transition. Terminal acknowledgement states are not reopened.

Malformed or unreadable acknowledgement evidence fails closed: no pending state is restored and reconciliation remains incomplete in diagnostics.

## Safety boundary

This milestone implements the third Live-mode safeguard, `restart_safe_command_reconciliation`. It does not dispatch commands, does not add a provider command path, and keeps `live_mode_commissionable`, `live_control_feature_enabled`, and `live_control_authorized` false.
