# IrrigationOS v1.0.29 — Sunrise Hard Stop

## Purpose

This milestone implements the fifth Live-mode execution safeguard while preserving the disabled controller-dispatch boundary.

A future command lifecycle must never remain eligible beyond its configured sunrise boundary. v1.0.29 provides deterministic sunrise evaluation and terminates an outstanding **synthetic** acknowledgement lifecycle at or after that boundary.

## Safety behavior

- The evaluator accepts timezone-aware current-time and sunrise timestamps and compares them in UTC.
- Before sunrise, the synthetic lifecycle is unchanged.
- At sunrise or later, the pending synthetic acknowledgement is terminated in the existing terminal `preempted` state with detail code `sunrise_hard_stop_reached`.
- A privacy-safe immutable JSONL event is retained for 30 days.
- Missing command identity, naive timestamps, and attempts to build an event before sunrise fail closed with explicit validation errors.
- The hard stop does not call Rachio, Home Assistant services, or any controller command interface.

## Live-mode boundary

The Live-mode safety architecture now records five of six safeguards as implemented. Manual override preservation remains incomplete. `live_mode_commissionable`, `live_control_feature_enabled`, and `live_control_authorized` remain false.
