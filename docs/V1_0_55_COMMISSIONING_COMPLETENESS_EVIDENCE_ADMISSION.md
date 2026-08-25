# v1.0.55 — Commissioning Completeness & Evidence Admission Policy

## Architecture

v1.0.55 adds a pure derived boundary between durable commissioned facts and downstream engines:

```text
CommissionedZoneProfile (durable evidence)
  -> deterministic admission policy 1.0.0
  -> immutable CommissioningAssessment
       -> purpose-specific readiness
       -> admitted and withheld evidence
       -> blockers and advisories
       -> structured next-information requests
       -> no execution authority
```

The assessment is not one universal completeness boolean. It evaluates commissioning-side fitness
for landscape understanding, plant-demand estimation, future calibrated-baseline environmental
scaling, delivery quantification, water balance, and advisory-only use independently.

## Evidence admission

- Explicit user-confirmed facts remain authoritative commissioning evidence.
- Human-reviewed photo evidence at moderate or high confidence is admissible.
- Approved structured AI evidence is admissible only at high confidence.
- Imported or below-policy evidence is retained but withheld from authoritative use.
- Unresolved conflict candidates remain visible with their original source, confidence, and evidence
  references; no disputed identity is admitted.
- An explicit human resolution admits the corrected current fact while the original candidates remain
  durable history.
- Removed plants remain in landscape events but are excluded from current readiness and demand.
- A valid moderate/high-confidence user baseline is admissible without plant identity.

Unknown information remains unknown. The policy does not synthesize identity, establishment,
delivery, plant factor, weather, water, or runtime values.

## Purpose boundaries

Purpose readiness means commissioned evidence is fit to enter that downstream purpose. It is not a
claim that the downstream engine has all external evidence required to calculate a result.

- Plant-demand readiness admits current identity and establishment facts; `factor_resolution.py`
  remains solely responsible for source-backed plant-factor resolution.
- Delivery readiness requires documented canonical plant-to-delivery links. The separate Water
  Delivery domain must still validate quantitative flow/application evidence before runtime can be
  calculated.
- Water-balance readiness covers only commissioning inputs. ET, precipitation, plant-factor, and
  observed-irrigation admission remain the responsibility of the existing quantitative engine.
- Baseline readiness does not perform weather scaling and does not create a watering runtime.

## Follow-up information

The policy emits bounded structured requirements such as confirming disputed identity, confirming
establishment state, documenting a delivery profile, and confirming dedicated establishment
delivery. Baseline-only mode does not ask for plant identity. These records are deterministic UI
inputs, not generated advice from an external AI provider.

## Home Assistant and persistence

The existing options review displays the overall status, all purpose states, and at most eight next
information requests. Recorder-facing summaries add only counts and compact state. Detailed
diagnostics include immutable assessments and canonical IDs without provider-native identifiers.

Assessment output is derived and is never stored. Commissioning Store/model schema remains 3, so
schema-1/2/3 migration behavior and exact Zone 1 compatibility are unchanged. Reload and restart
restore evidence, then recompute readiness; no stale readiness becomes authority.

## Safety

`execution_authorized` and `live_control_authorized` are always false. v1.0.55 adds no background
task, polling, network access, external AI, weather scaling, temperature multiplier, hydraulic
calculation, schedule, retry, controller write, or autonomous irrigation authority. Factor-resolution
algorithm version remains 1.1.0.
