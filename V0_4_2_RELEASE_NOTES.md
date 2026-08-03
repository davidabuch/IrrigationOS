# IrrigationOS v0.4.2 — Real-Time Rachio Observation

## Purpose

This release adds low-latency Rachio observations without changing IrrigationOS's read-only product boundary. It adapts Home Assistant's official Rachio webhook lifecycle to the IrrigationOS canonical controller and permanent-slot model.

## Highlights

- One persisted local Home Assistant webhook identity and authorization secret per config entry.
- Automatic use of an active Home Assistant Cloud cloudhook when available.
- Standard Home Assistant external HTTPS webhook URLs when Cloud is inactive or unavailable; no paid subscription is required.
- Remote URL suitability checks with nonfatal repair warnings when no usable external URL exists.
- Idempotent remote Rachio subscription reconciliation for device, zone, schedule, rain-delay, and rain-sensor status categories.
- Legacy event-type discovery with RachioPy-compatible request headers and redacted structured failure categories.
- HMAC-SHA256 signature validation, entry-specific authorization, and bounded event deduplication.
- Immediate canonical snapshot refresh after accepted start, stop, completion, pause, and related observation events.
- Reconciliation of subscriptions when polling discovers added or removed controllers.
- Realtime diagnostics covering enablement, URL source, remote health, last event, delivery counts, and fallback polling.
- Redaction of webhook URLs, webhook IDs, authorization secrets, API tokens, and signatures.

## Graceful fallback

Home Assistant must expose a publicly reachable HTTPS URL for Rachio delivery. If it cannot generate one, or if remote registration fails, config-entry setup still succeeds and the existing five-minute poll remains operational. A Home Assistant repair warning explains why realtime observation is unavailable.

## Safety boundary

Remote `POST`, `PUT`, and `DELETE` operations in this release manage notification subscriptions only. IrrigationOS does not start, stop, schedule, pause, resume, or delay irrigation. Observation remains the only implemented operating mode.

## Remaining limitations

- URL checks can reject clearly local or unsafe addresses but cannot prove end-to-end internet reachability before Rachio attempts delivery.
- Duplicate event memory is bounded and process-local; a retry received after a Home Assistant restart can cause another safe read-only refresh.
- Push events trigger a complete account snapshot refresh so canonical state remains authoritative; targeted provider reads may be added later if they preserve the same reconciliation semantics.
