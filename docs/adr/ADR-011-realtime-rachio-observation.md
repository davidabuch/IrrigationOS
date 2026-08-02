# ADR-011: Real-Time Rachio Observation

## Status

Accepted for v0.4.2.

## Context

Five-minute polling provides a reliable observation baseline but delays watering-state changes. Rachio supports remote notification subscriptions, while Home Assistant supports both subscription-backed cloudhooks and standard external webhook URLs. IrrigationOS must not require Home Assistant Cloud and must not let push setup failures disable observation.

## Decision

Each config entry persists a unique local Home Assistant webhook ID and a random authorization secret. When an active Home Assistant Cloud subscription exists, IrrigationOS may create or reuse a cloudhook. Otherwise, and whenever Cloud is unavailable, it asks Home Assistant for a standard external HTTPS webhook URL. Clearly local, private, insecure, or malformed URLs are rejected.

The provider-neutral realtime manager owns Home Assistant URL selection, local registration, authentication, deduplication, lifecycle, diagnostics, and canonical coordinator refreshes. The Rachio adapter owns vendor event-category discovery and remote subscription create, update, list, and delete operations.

Legacy notification registration requires event-type ID objects. IrrigationOS therefore retains Rachio's public event-type discovery call, filters the returned catalog against the same fixed event names used by Home Assistant, and reports only safe failure categories and HTTP status metadata when discovery fails.

Remote subscriptions use an entry-scoped external-ID prefix. Setup lists existing subscriptions per controller, removes stale duplicates owned by the same entry, reuses an equivalent current registration, updates a changed registration, or creates one when absent. Unload removes owned remote subscriptions and local delivery; permanent config-entry removal also deletes an optional cloudhook. Later polling reconciles subscriptions for newly discovered or removed controllers.

Incoming events must carry both the entry authorization value and a valid HMAC-SHA256 signature derived from the Rachio API token and request body. Accepted observation events are deduplicated by event ID and trigger an immediate full canonical snapshot refresh. The five-minute coordinator interval remains active as reconciliation fallback.

## Consequences

- A paid Home Assistant Cloud subscription is optional.
- Push setup and registration failures are visible but nonfatal.
- Rachio IDs remain vendor bindings; webhook events never become canonical identities.
- Diagnostics expose health and counts without exposing delivery URLs or credentials.
- Remote writes are limited to notification-subscription administration and cannot control irrigation.
