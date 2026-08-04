# ADR-013: Visual Landscape Intelligence

## Status

Accepted for the first IrrigationOS v0.5.0 architecture milestone.

## Context

IrrigationOS needs a structured way to use photographs, user measurements, and future
machine-assisted analysis during landscape setup and plant-health investigation. Visual
interpretation is uncertain: a photograph can suggest a plant category, irrigation hardware,
or soil class, but it cannot reliably establish every hydraulic, biological, or soil property.
Provider output must therefore be treated as evidence-backed advice rather than fact or an
irrigation command.

The domain must also survive changes in inference provider. A future implementation may use a
cloud model, a different hosted service, or a local model. Provider request and response formats
do not belong in the durable Landscape Digital Twin.

## Decision

### Provider-neutral domain boundary

`custom_components/irrigationos/visual_assessment/` owns the durable visual-assessment domain.
It contains no model-vendor SDK types, request payloads, response payloads, credentials, or
transport behavior. A future adapter will translate provider responses into these validated
models before they enter persistence, diagnostics, or review workflows.

The aggregate is `VisualLandscapeAssessment`. It links a `VisualAssessmentSession` to opaque
photo evidence, detected plants and hardware, soil evidence, uncertainties, guided tests, user
measurements, diagnostic hypotheses, recommendations, and adjustment proposals. Models are
frozen and slotted dataclasses. Enumerations provide stable serialized vocabulary. `to_dict()`
recursively emits deterministic plain Python dictionaries with enum values and ISO 8601
timestamps.

### Advice, verification, and safety

AI output is advisory only. It may:

- describe findings and uncertainty;
- request more evidence or a safe guided test;
- offer diagnostic hypotheses and alternatives;
- propose bounded temporary adjustments;
- propose persistent Landscape Digital Twin changes for explicit approval.

It may not start or stop irrigation, change a controller schedule, deliver a command, or silently
write a proposed value into the confirmed baseline. Temporary adjustments are marked as
proposal-only. Baseline adjustments must declare that explicit approval is required. The domain
objects deliberately expose no execution method or controller-adapter dependency.

Every inferred finding carries confidence from 0.0 through 1.0, provider-neutral provenance,
verification status, and a timezone-aware assessment timestamp. Inferences retain their source
even after review. A user-confirmed correction becomes the effective value while the original
inference and its provenance remain present. Soil sources are retained side by side so visual,
dataset, and measured conclusions can conflict without data loss.

Plant quantities keep their semantic mode. Counts are whole numbers, percentages are bounded,
and area quantities require an area unit. Count-based trees are not coerced into a percentage or
included in percentage-total constraints. Hardware can likewise be represented as a count or a
share. Physical estimates and adjustment limits reject impossible or inconsistent values.

### Session and evidence lifecycle

A session moves through `created`, `collecting_evidence`, `awaiting_user_input`,
`ready_for_review`, and `confirmed`, with terminal `superseded` and `failed` states. Transitions
create a new immutable state. Evidence, measurements, and findings use stable IDs so a review or
superseding assessment can preserve its audit trail.

Photographs are represented only by metadata and an optional opaque content reference. Raw image
bytes and data URLs are prohibited in domain records. The domain does not imply that an opaque
reference is indefinitely valid.

### Privacy, secrets, retention, and deletion

- Image content must never be written to logs. Logs may include safe counts and stable internal
  record IDs only when needed.
- Assessment records must never contain API keys, authorization headers, signatures, access
  tokens, or provider credentials.
- Photos use opaque references rather than embedded bytes, public URLs, or provider response
  objects.
- Retention is explicit per photo: session-scoped, a configured positive duration, or retained
  until user deletion. The storage layer must enforce the selected policy and make the duration
  configurable; the domain model does not delete storage itself.
- Deleting a photo must delete the referenced content and leave only the minimum tombstone or
  audit metadata required by configured policy. Deleting an assessment must cascade to
  session-scoped content unless another retained record owns it.
- Superseding an assessment preserves immutable findings and provenance for audit while normal
  views resolve to the replacement. Supersession does not extend photo retention.
- Before any future cloud inference is enabled, setup and privacy documentation must disclose the
  provider, categories of data sent, destination/region where known, retention behavior, and how
  the user can decline or delete cloud-processed evidence.

### Future adapter contract

A later milestone may introduce an inference-provider protocol outside this domain. It will be
responsible for authentication, transport, schema-constrained responses, retry policy, and safe
error translation. Its output is accepted only after construction of the validated domain models.
No provider is selected by this ADR and no image upload surface is introduced.

## Consequences

- Visual findings are portable, testable, serializable, and auditable independently of a model
  provider.
- Invalid confidence, identifiers, timestamps, physical quantities, lifecycle combinations, and
  adjustment ranges fail at the boundary.
- User truth can override an inference without destroying the original evidence or provenance.
- The initial milestone creates no network calls, image storage implementation, UI, or irrigation
  command path.
- Persistence schema, provider adapter protocols, content-reference storage, user approval UX,
  diagnostic redaction, and retention jobs remain explicit future decisions.

