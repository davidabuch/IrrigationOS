# ADR-029: Conversational and Photo-Assisted Commissioning

## Decision

Simple and advanced commissioning are presentation modes over the same canonical
`CommissionedZoneProfile`, plant, delivery-link, Water Delivery, and conflict contracts.
The conversational layer is a pure immutable proposal builder, not a second source of truth.

Approved visual findings retain structured facts, confidence, assessment IDs, and evidence
IDs. Raw image bytes are excluded. Conflicts never silently replace user-confirmed facts.

Emitter color is not a provider-neutral flow specification. A documented generic reference
may contribute a lower-confidence flow range, but never measured, manufacturer-rated, or
exact nominal flow. Without a documented reference, flow remains unknown. Later measured
evidence is preferred while the earlier range remains auditable.

Follow-up questions are deterministic and ranked by materiality. Summaries and questions are
transient; canonical evidence is persisted atomically before manager state changes. No result
authorizes execution or Live control.
