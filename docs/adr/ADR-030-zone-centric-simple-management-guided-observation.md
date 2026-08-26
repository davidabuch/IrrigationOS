# ADR-030: Zone-Centric Simple Management and Guided Observation

## Decision

`Manage zones` is the permanent primary Home Assistant options-flow entry point for both initial setup and later updates. It reconstructs plain-language views from canonical commissioning, delivery, admission, and visual-evidence records. Advanced workflows remain available from each zone.

Photo selection uses Home Assistant media references. IrrigationOS persists only private opaque references associated with canonical property and zone identity; image bytes and provider-native controller identifiers never enter commissioning state. No image traversal or analysis runs at startup.

Guided observation is a separate operator-directed control boundary. Every start requires an explicit UI submission, targets exactly one currently selected configured area, is capped at 180 seconds, performs fresh fail-closed preflight, has no retry, and exposes an immediate operator stop. The local lifecycle is transient and resets to idle on restart. A provider adapter may implement the safest available stop primitive; Rachio requires controller-wide stop.

## Authority boundary

Guided observation is not a recommendation, schedule, autonomous operation, or persisted authority. It does not set `execution_authorized` or `live_control_authorized`, and it is never resumed after reload or restart.

## Consequences

- Existing v1.0.59 zones reopen through the same simple path without duplication.
- Meaningful plant updates preserve the prior plant snapshot in landscape history.
- Photo references add Store schema 7 through an additive migration from schemas 1–6.
- Direct camera capture depends on the Home Assistant media-source UI; this release does not implement a custom binary upload endpoint.
