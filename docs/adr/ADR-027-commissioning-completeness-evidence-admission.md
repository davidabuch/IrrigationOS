# ADR-027: Commissioning Completeness and Evidence Admission

- **Status:** Accepted for IrrigationOS v1.0.55
- **Date:** 2026-08-24

## Context

ADRs 024–026 established generic durable commissioned zones, onboarding, history, and editing. The
same profile can contain manual facts, approved structured visual evidence, calibrated baselines,
delivery links, conflicts, and historical plants. Downstream consumers require different evidence;
a universal `complete` flag would either reject useful baseline-only zones or admit unsafe gaps.

## Decision

Add a pure, provider-neutral admission policy that derives one immutable `CommissioningAssessment`
from the current `CommissionedZoneProfile`. The assessment separately evaluates six stable purposes:
landscape understanding, plant-demand estimation, baseline environmental scaling, delivery
quantification, water balance, and advisory-only use.

Every result retains canonical zone identity, admitted and withheld evidence, provenance,
confidence, deterministic blockers/advisories, and structured follow-up requirements. The assessment
is advisory and fixes execution and Live-control authorization false.

### Admission policy 1.0.0

User-confirmed evidence is admissible. Human-reviewed photo evidence requires at least moderate
confidence; approved structured AI evidence requires high confidence. Imported or lower-confidence
evidence is retained but withheld. An unresolved conflict withholds the disputed current identity and
retains every candidate. A separate explicit human resolution admits the selected current fact
without deleting original candidates. Only active plant groups participate; removed plants remain
auditable in events.

A valid calibrated baseline is purpose-ready without requiring plant identity. Missing delivery
blocks delivery purposes, not landscape understanding or advisory use. Newly planted/establishing
groups with unresolved or shared delivery produce a dedicated establishment-delivery follow-up.

### Responsibility boundaries

Commissioning admission determines whether facts are fit to enter a purpose. It does not resolve
plant-factor evidence, validate quantitative Water Delivery profiles, ingest weather, calculate water
balance, scale baselines, generate runtime, schedule, or execute. Factor resolution remains algorithm
1.1.0. Quantitative water balance remains fail-closed on its own evidence.

### Persistence and Home Assistant

Assessment is recomputed and is not persisted. No commissioning schema change is required. The
options flow shows bounded readiness/follow-up text, compact Recorder summaries expose counts, and
detailed diagnostics may include the deterministic assessment. No provider-native identifiers are
introduced.

## Consequences

Downstream milestones can consume one explicit evidence-admission result instead of interpreting
onboarding modes independently. Readiness for calculation remains separate from execution authority.
Future delivery-profile and baseline-scaling integration can extend their own policies without
weakening commissioning or migrating durable evidence.

## Deferred

- Environmental scaling of user-calibrated baselines.
- Automatic establishment-stage progression.
- Quantitative delivery-profile registry/resolution and hydraulic runtime.
- External photo/AI providers.
- Scheduler or controller authority.
