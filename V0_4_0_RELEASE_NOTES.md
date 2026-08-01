# IrrigationOS v0.4.0 — First Live Installation

## Purpose

This release is the first field-installation beta for Home Assistant and Rachio. It remains read-only.

## Highlights

- Two-step setup flow with a discovery review before entry creation.
- Rachio API-key reauthentication flow.
- Authentication failures trigger Home Assistant reauthentication.
- Best-effort observation of current watering through Rachio's current-schedule endpoint.
- Live discovery summary and last-refresh diagnostic sensors.
- Expanded redacted diagnostics and refresh telemetry.
- No irrigation control endpoints or switch platform.

## Field-test objective

Confirm installation, authentication, controller discovery, four-area discovery, external watering observation, and diagnostics in a real Home Assistant instance.
