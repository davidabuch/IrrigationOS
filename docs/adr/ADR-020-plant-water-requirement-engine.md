# ADR-020: Plant Water Requirement Engine

- Status: Accepted
- Date: 2026-08-04
- Decision owners: IrrigationOS maintainers
- Capability: 6.3 — Plant Water Requirement Engine

## Context

ADR-018 established immutable, source-backed Plant Knowledge, and ADR-019 established the
initial curated Plant Knowledge Dataset.

The Plant Knowledge field registry already supports evidence-backed water characteristics,
including `water.landscape_coefficient`, and declares `water_demand` as a potential consumer
capability. The current curated profiles intentionally contain identity evidence only. They do not
yet contain production water-requirement claims.

IrrigationOS now needs a stable boundary for interpreting water-related Plant Knowledge without
confusing general plant characteristics with current landscape water demand, irrigation runtime,
or controller behavior.

A plant type does not have one universally correct irrigation requirement. Water need can vary
with region, season, establishment stage, canopy density, exposure, microclimate, maintenance
objectives, and evidence quality. Current weather, soil moisture, irrigation efficiency, and
delivery hardware further affect actual irrigation demand, but belong to separate domains.

The engine must therefore preserve ranges, uncertainty, regional applicability, source
provenance, and missing-data states. It must not convert incomplete knowledge into false
precision.

## Decision

### Independent pure-Python domain

Create an independent pure-Python package for plant water-requirement assessment.

Recommended location:

```text
custom_components/irrigationos/plant_water_requirement/
```

The package is:

- immutable;
- deterministic;
- provider-neutral;
- weather-neutral;
- controller-neutral;
- advisory only; and
- free of Home Assistant runtime dependencies.

It consumes resolved Plant Knowledge through the stable ADR-018 public boundary. It does not read
raw curated-library internals or provider payloads directly.

### Meaning of plant water requirement

For this capability, plant water requirement means an evidence-backed description of a plant
type's relative landscape water requirement under an explicitly declared evaluation context.

It does not mean:

- irrigation runtime;
- gallons or liters to apply;
- valve duration;
- schedule frequency;
- current soil-water deficit;
- replacement of reference evapotranspiration;
- a controller command; or
- a watering recommendation.

Actual landscape water demand requires later composition with Environmental Intelligence,
Landscape Digital Twin data, soil and root-zone characteristics, water-delivery efficiency, and
operating policy.

### Stable input contract

The foundation defines an immutable `PlantWaterRequirementRequest` containing:

- a stable request ID;
- one successful or auditable `PlantKnowledgeResolution`;
- an explicit regional and seasonal evaluation context;
- establishment stage;
- optional exposure and microclimate classifications;
- one immutable policy;
- creation timestamp; and
- schema and algorithm versions.

The request must retain the selected knowledge profile ID and effective claim trace. It must not
copy or mutate canonical Plant Knowledge.

The initial foundation may define context vocabulary without using every field in the first
calculation algorithm. Unused fields must remain explicit and must not silently affect results.

### Policy contract

`PlantWaterRequirementPolicy` stores all interpretation choices that would otherwise become hidden
constants.

The policy includes:

- policy ID and semantic version;
- accepted claim paths;
- minimum review state;
- minimum evidence grade;
- minimum confidence;
- regional-match requirements;
- handling of scalar versus range claims;
- missing-data behavior;
- conflict behavior; and
- explanation reason codes.

A policy may reject insufficient evidence. It may not invent a coefficient, silently substitute a
category average, or convert an unknown value to zero.

### Result contract

`PlantWaterRequirementAssessment` is the canonical output envelope.

It contains:

- request ID;
- selected profile ID;
- assessment status;
- relative requirement value or preserved range;
- canonical unit;
- applicable region and season;
- confidence and completeness kept separate;
- source and claim references;
- inherited and overridden claim traces;
- policy and algorithm versions;
- machine-readable reason codes;
- concise human explanation;
- unresolved issues; and
- creation timestamp.

Assessment status is explicit and includes at least:

- `available`;
- `partial`;
- `unavailable`;
- `conflicting_evidence`;
- `regional_mismatch`; and
- `insufficient_quality`.

Missing or rejected knowledge produces a typed non-success result rather than an exception during
ordinary assessment.

Malformed requests, invalid policies, unsupported units, and structurally invalid knowledge remain
construction errors.

### Preserve ranges and uncertainty

If the effective approved knowledge is a `KnowledgeRange`, the assessment preserves that range.

The engine must not collapse a range to its midpoint, typical value, minimum, or maximum unless the
active versioned policy explicitly authorizes that transformation and records it in the
explanation.

A scalar claim remains scalar. Multiple unresolved competing claims do not become an average.

### Regional applicability

The engine evaluates claim applicability against the explicit request context.

Regional handling must distinguish:

- match;
- partial match;
- unavailable context;
- mismatch; and
- unrestricted applicability.

A mismatch cannot be treated as a match because a profile itself resolved successfully.

Plant identity resolution and water-claim applicability remain separate decisions.

### Confidence and completeness

Confidence and completeness are distinct:

- confidence reflects the assessed reliability of the evidence actually used;
- completeness reflects whether the required knowledge inputs were available.

A highly credible single claim can have high confidence but incomplete contextual coverage.

The engine must not increase confidence beyond the supporting Plant Knowledge evidence. Policy
transformations may reduce confidence but may not manufacture additional certainty.

### Evidence and explainability

Every successful or partial assessment retains:

- the effective claim ID;
- originating profile ID;
- source IDs;
- claim confidence and evidence grade;
- regional-applicability result;
- inheritance trace;
- conflict-resolution reference when applicable; and
- policy decisions used to produce the output.

The human explanation summarizes the result but never replaces the machine-readable evidence
trace.

### Deterministic algorithm boundary

The first calculation algorithm consumes only approved effective claims for explicitly accepted
water field paths.

The initial accepted path is expected to be:

```text
water.landscape_coefficient
```

Adding another field path requires an explicit compatible policy and schema decision.

The engine does not infer missing coefficients from plant category, common name, taxonomy, visual
appearance, functional-group membership, or external services unless a later ADR explicitly adds
a reviewed deterministic fallback policy.

### Separation from other domains

Plant Water Requirement remains separate from:

- **Plant Knowledge:** owns immutable general evidence and provenance.
- **Environmental Intelligence:** owns current and forecast environmental conditions.
- **Landscape Digital Twin:** owns property-specific plant instances and landscape context.
- **Water Delivery:** owns hydraulic delivery characteristics and efficiency.
- **Plant Stress:** owns current biological stress assessment.
- **Plant Health:** owns health and diagnostic conclusions.
- **Recommendation and Planning:** own irrigation advice and proposed actions.
- **Scheduling and Execution:** own timing and controller commands.

This engine may later be composed with those domains, but it does not import their runtime
authority.

### Public API

The stable foundation API should expose only domain-level contracts and the future assessment
entrypoint, such as:

```python
assess_plant_water_requirement(request)
```

Private normalization, scoring, selection, and explanation helpers remain implementation details.

### Safety boundary

The package exposes no capability to:

- start or stop irrigation;
- calculate valve runtime;
- choose watering days;
- modify a controller schedule;
- apply a rain delay;
- publish Home Assistant entities;
- call network or AI services;
- mutate Plant Knowledge;
- diagnose plant stress or disease; or
- recommend irrigation.

## Milestone decomposition

### Capability 6.3A — Water Requirement Foundation

Implement only:

- immutable request, context, policy, confidence, explanation, and assessment models;
- stable enums and reason codes;
- deterministic serialization;
- aggregate validation;
- public API exports; and
- tests for construction, invalid input, immutability, and serialization.

No calculation engine is included.

### Capability 6.3B — Curated Water Evidence

Expand the curated Plant Knowledge Dataset with reviewed water-related claims for a deliberately
small subset of published profiles.

This milestone must:

- use authoritative reviewed sources;
- preserve regional applicability;
- record scalar or range values without false precision;
- pass ADR-018 publication and conflict gates;
- version and checksum the curated library; and
- avoid runtime calculations.

Profiles without adequate evidence remain without water claims.

### Capability 6.3C — Deterministic Assessment Engine

Implement the first deterministic engine using only evidence admitted by the active policy.

The first algorithm must:

- consume `PlantKnowledgeResolution`;
- evaluate claim quality and regional applicability;
- preserve scalar or range form;
- return typed non-success outcomes for missing or conflicting evidence;
- retain complete provenance and explanations;
- avoid category or functional-group inference unless separately approved; and
- remain independent of weather, scheduling, runtime, and execution.

### Capability 6.3D — Integration Contract Tests

Prove composition boundaries without adding runtime authority:

- Plant Knowledge resolution to requirement request;
- deterministic assessment reproducibility;
- compatibility with future Landscape Digital Twin references;
- no imports from scheduling or controller execution; and
- no Home Assistant entity exposure.

This milestone may be folded into 6.3C if implementation remains small.

## Validation requirements

Every milestone must pass:

- Ruff;
- strict MyPy;
- the complete pytest suite;
- Home Assistant tests;
- repository validation;
- `git diff --check`; and
- GitHub Actions.

Tests must specifically prove:

- immutable deterministic models;
- typed missing-data outcomes;
- confidence and completeness separation;
- range preservation;
- no silent defaults;
- regional mismatch handling;
- provenance retention;
- deterministic repeated results; and
- absence of controller, scheduling, network, persistence, and AI dependencies.

## Consequences

### Positive

- Plant water knowledge remains distinct from current irrigation demand.
- Future algorithms receive a stable, explainable contract.
- Missing evidence cannot silently become a watering decision.
- Regional mismatch, uncertainty, and conflict remain visible.
- Ranges and source provenance survive calculation.
- Later demand, planning, and execution capabilities can compose this output safely.

### Tradeoffs

- The first useful assessment requires additional curated water evidence.
- Many profiles will initially return `unavailable`.
- Strict evidence gates slow dataset expansion.
- The engine will not provide irrigation runtimes or schedules by itself.

These tradeoffs are accepted.

## Explicitly deferred

This ADR does not define:

- authoritative coefficient values for specific plants;
- reference evapotranspiration calculations;
- effective rainfall;
- soil-water balance;
- root-zone depletion;
- plant density or canopy models;
- microclimate algorithms;
- establishment watering schedules;
- irrigation efficiency;
- runtime conversion;
- hydrozone design;
- stress or health diagnosis;
- recommendations;
- scheduling;
- Home Assistant entities; or
- controller execution.

## Acceptance criteria

Capability 6.3 is complete when:

1. The foundation contracts are accepted and implemented.
2. A reviewed subset of curated profiles has usable water evidence.
3. The deterministic assessment engine returns auditable typed results.
4. Ranges, confidence, completeness, regional applicability, and provenance are preserved.
5. Missing or conflicting evidence never becomes a silent default.
6. No weather, scheduling, runtime, recommendation, or execution authority is introduced.
7. All repository validation gates pass.
