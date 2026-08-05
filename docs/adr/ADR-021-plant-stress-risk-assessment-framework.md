# ADR-021: Plant Stress Risk Assessment Framework

- Status: Accepted
- Date: 2026-08-04
- Decision owners: IrrigationOS maintainers
- Capability: 7 — Plant Stress Risk Intelligence

## Context

IrrigationOS models environmental reasoning as a sequence of deterministic assessment engines.
Each engine answers one bounded scientific question using immutable upstream evidence and produces
one immutable downstream assessment.

Plant Knowledge owns evidence-backed facts about a plant. Plant Water Requirement interprets
reviewed plant-factor evidence. Environmental Intelligence describes current and forecast
environmental conditions. None of those capabilities answers:

> Given this plant evidence and this environmental exposure, what stress risk exists?

Environmental exposure is not proof of physiological injury. IrrigationOS does not currently know
whether a particular plant is dehydrated, wilted, damaged, diseased, or in need of irrigation unless
that state is directly observed by a future plant-instance sensing or visual-assessment capability.

A dedicated framework is therefore required to describe plant stress **risk** without presenting
modeled pressure as biological diagnosis.

## Decision

Create an independent pure-Python Plant Stress Risk Assessment Framework.

Recommended package:

```text
custom_components/irrigationos/plant_stress/
```

The framework is immutable, deterministic, provider-neutral, controller-neutral, advisory only,
and free of Home Assistant runtime dependencies.

Its scientific question is:

> Given immutable plant evidence, upstream assessments, and environmental exposure, what plant
> stress risk is supported by the available evidence?

It does not diagnose actual biological stress.

## Constitutional principles for assessment engines

### One capability, one scientific question

Each capability owns one bounded question:

- Plant Knowledge: What is known about the plant?
- Plant Water Requirement: What relative water requirement is supported?
- Plant Stress Risk: What environmental stress risk is supported?
- Plant Health: What observed health state is supported?
- Recommendations: What action should be considered?
- Planning: How should an approved action be organized?
- Execution: How is an approved plan delivered?

A capability must not answer a question owned by another layer.

### Monotonic intelligence

Downstream layers consume immutable upstream evidence. They must not modify, overwrite, or
reinterpret upstream truth.

```text
Observations
    -> Canonical Knowledge
    -> Deterministic Assessments
    -> Risk Assessments
    -> Recommendations
    -> Planning
    -> Execution
```

Every layer adds a new immutable conclusion. No downstream conclusion rewrites an upstream record.

### Evidence conservation

Assessment engines may select, filter, compare, and interpret evidence. They must retain
machine-readable provenance sufficient to trace each conclusion to the upstream assessments,
claims, sources, reports, and signals that supported it.

Human-readable explanation never replaces typed provenance.

### Compositional intelligence

IrrigationOS does not use one universal decision engine. Intelligence emerges through composition
of small deterministic engines.

Each engine consumes stable upstream contracts and produces one stable assessment contract.

### Determinism

Identical requests must produce identical assessments, identifiers, explanations, and
serialization.

Assessment engines must not depend on:

- the current clock;
- randomness or generated UUIDs;
- mutable global state;
- hidden library lookups;
- network services;
- AI-generated reasoning; or
- controller runtime state.

## Scientific interpretation boundary

Plant Stress Risk represents environmental risk, not confirmed plant physiology.

The framework must not claim:

- actual dehydration;
- actual tissue injury;
- observed wilting;
- observed disease;
- observed nutrient deficiency;
- confirmed root-zone depletion; or
- confirmed irrigation need.

A future capability may diagnose observed biological state only when direct plant-instance evidence
is available and a separate ADR defines that authority.

## Independent stress dimensions

The initial framework supports these independent dimensions:

- `water_deficit`;
- `heat`; and
- `freeze`.

Future dimensions may include wind, salinity, flooding, nutrient pressure, pest pressure,
transplant stress, and recovery state.

Dimensions are never averaged into a numeric composite. A future aggregate may report the highest
available categorical risk only when an explicit versioned policy authorizes that rule.

## Risk vocabulary

The public categorical vocabulary is:

- `none`;
- `low`;
- `moderate`;
- `high`;
- `very_high`; and
- `unknown`.

The framework does not publish unsupported percentages.

## Status vocabulary

Dimension and aggregate assessments use typed outcomes including:

- `available`;
- `partial`;
- `unavailable`;
- `insufficient_plant_knowledge`;
- `insufficient_environmental_evidence`;
- `regional_mismatch`; and
- `conflicting_evidence`.

Missing evidence produces typed outcomes rather than invented defaults.

## Compositional inputs

The foundation request references the existing immutable upstream contracts:

- `PlantKnowledgeResolution`;
- `PlantWaterRequirementAssessment`;
- `EnvironmentalIntelligenceReport`;
- explicit location, analysis-window, region, and season context; and
- one immutable versioned policy.

The request does not copy or mutate upstream evidence and does not perform hidden lookups.

Not every future dimension must use every upstream input. Dimension-specific engines must state
which inputs they require and preserve all evidence they actually consume.

## Public contracts

The foundation defines immutable contracts for:

- `PlantStressRiskContext`;
- `PlantStressRiskPolicy`;
- `PlantStressRiskRequest`;
- `PlantStressRiskConfidence`;
- `PlantStressRiskExplanation`;
- `PlantStressDimensionAssessment`; and
- `PlantStressRiskAssessment`.

The framework also defines canonical dimension, status, risk, missing-evidence, partial-evidence,
and aggregate-policy enums.

No engine is implemented in the foundation milestone.

## Confidence and completeness

Confidence and completeness remain separate:

- confidence expresses reliability of the evidence and interpretation actually used;
- completeness expresses how many required inputs were available.

High-confidence evidence may still be incomplete. Missing evidence must not receive fabricated
confidence.

## Dimension assessment contract

Each independent dimension assessment preserves:

- dimension;
- status;
- categorical risk;
- confidence and completeness;
- selected plant profile reference;
- Plant Knowledge claim and source references;
- Plant Water Requirement assessment reference when relevant;
- Environmental Intelligence report and signal references;
- regional applicability;
- policy and algorithm versions;
- deterministic explanation; and
- unresolved issues.

Available and partial outcomes require a concrete risk classification. Non-success outcomes use
`unknown` and must not contain a fabricated risk conclusion.

## Aggregate assessment contract

The aggregate envelope preserves:

- assessment and request identifiers;
- selected profile, location, and analysis-window references;
- independent dimension assessments;
- overall status;
- optional policy-authorized overall categorical risk;
- aggregate confidence and completeness;
- upstream resolution, assessment, and report references;
- policy and algorithm versions;
- deterministic explanation;
- unresolved issues;
- creation timestamp; and
- schema version.

The foundation does not calculate an overall risk.

## Capability boundaries

Plant Stress Risk has no authority to:

- recommend irrigation;
- calculate gallons, runtime, frequency, or watering days;
- alter plans or schedules;
- control hardware;
- diagnose plant health;
- interpret visual observations;
- infer soil moisture;
- mutate Plant Knowledge;
- mutate Environmental Intelligence; or
- mutate Plant Water Requirement assessments.

## Milestone decomposition

### v0.8.0A — Plant Stress Risk Foundation

Implement ADR-021, immutable public models, deterministic serialization, validation, exports, and
focused model tests. No engine.

### v0.8.0B — Curated Stress-Tolerance Evidence

Add reviewed claims for a deliberately small subset of profiles using existing or explicitly
approved Plant Knowledge field contracts. Do not force coverage.

### v0.8.0C — Water-Deficit Stress-Risk Engine

Implement only the water-deficit dimension from explicit plant susceptibility, Plant Water
Requirement, and environmental drying evidence.

### v0.8.0D — Heat and Freeze Stress-Risk Engines

Add independent heat and freeze dimensions using explicit versioned policies.

### v0.8.0E — Aggregate Plant Stress Risk

Combine independent dimension assessments without averaging or hiding their individual meaning.

## Consequences

### Positive

- Modeled exposure is not confused with biological diagnosis.
- Each scientific question remains independently testable.
- Provenance survives every reasoning layer.
- New stress dimensions can extend the framework without redesign.
- Intelligence remains portable across controllers and runtimes.
- Future recommendation, planning, and execution layers receive stable auditable inputs.

### Tradeoffs

- Many early requests will return partial or unavailable outcomes.
- Direct plant-state diagnosis remains deferred.
- Strict separation creates more small contracts than a monolithic engine.
- Evidence curation and dimension-specific policy work are required before useful risk
  engines exist.

These tradeoffs are accepted.

## Non-goal

IrrigationOS does not attempt to create one universal intelligence engine. It composes small,
deterministic, provenance-preserving assessment engines.

## Architectural vision

IrrigationOS is a deterministic environmental reasoning platform whose first application is
intelligent irrigation.

Future Plant Health, Landscape Intelligence, Recommendation, Planning, Scheduling, and Execution
capabilities must comply with these principles or explicitly document an ADR-backed departure.

## Acceptance criteria

v0.8.0A is complete when:

1. ADR-021 is accepted.
2. Immutable foundation contracts are implemented and exported.
3. Requests reference existing upstream contracts without hidden lookup or mutation.
4. Dimension and aggregate outcomes enforce valid risk/status combinations.
5. Confidence and completeness remain separate and internally consistent.
6. Provenance references are machine-readable and deterministically ordered.
7. No stress engine, recommendation, planning, scheduling, or execution authority is introduced.
8. All repository validation gates pass.
