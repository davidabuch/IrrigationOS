# IrrigationOS v1.0.25 — Command Attribution and Receipt Foundation

## Purpose

This milestone implements the first concrete Live-mode execution safeguard while preserving the disabled command-delivery boundary.

## Delivered

- canonical future command intent records with stable correlation IDs
- explicit attribution for IrrigationOS, operator, and safety-manager origins
- validated start/stop intent vocabulary and one-hour maximum recorded runtime
- immutable local JSONL intent/receipt evidence with 30-day retention
- explicit `not_dispatched` receipts proving that recorded intents do not cross a controller boundary
- privacy-safe diagnostics for intent/receipt counts and latest evidence
- Live-mode safety architecture now recognizes command attribution and receipts as implemented

## Safety boundary

No Rachio or other controller command is sent by this subsystem. There is no dispatch method, controller API call, Home Assistant service call, or automatic promotion to Live mode. Every receipt created in v1.0.25 has outcome `not_dispatched` and detail code `live_command_delivery_disabled`.

The remaining Live-mode safeguards continue to block commissioning:

- acknowledgement and timeout handling
- restart-safe command reconciliation
- safety preemption path
- sunrise hard stop
- manual override preservation

Live control remains disabled and unauthorized.
