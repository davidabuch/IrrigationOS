# ADR-018: Plant Knowledge Framework

- Status: Accepted
- Date: 2026-08-03
- Decision owners: IrrigationOS maintainers
- Milestone: v0.6.2

## Context

IrrigationOS needs a stable way to represent evidence-backed general knowledge about plant
types. That knowledge is different from a plant observed at a particular property. It must be
curated, versioned, reviewable, regionally scoped, and explainable before future consumers can
use it safely.

Neither provider responses nor mutable display names are suitable canonical records. Source
claims can conflict, scientific names can change, and progressively more specific profiles may
need to inherit broad knowledge without losing its origin. A complete library also needs a
verifiable identity independent of insertion order.

This ADR defines the framework only. It contains no production botanical records and makes no
horticultural, diagnostic, irrigation, or scheduling decisions.

## Decision

Create a provider-neutral `plant_knowledge` domain with immutable, frozen, slotted dataclasses;
stable `StrEnum` values; deterministic plain-dictionary serialization; aggregate validation; and
an exact-match resolution algorithm.

The stable public boundary consists of:

- evidence sources, immutable source-review records, claims, ranges, and field contracts;
- explicit regional applicability;
- functional-group and profile hierarchies;
- conflict resolutions that preserve original claims;
- an immutable library manifest and aggregate;
- deterministic checksum calculation and profile resolution;
- candidates, claim traces, and explanations needed to audit a resolution.

Private validators, serializers, graph walkers, normalization functions, and low-level hash
helpers remain implementation details.

## Boundary and safety

Plant Knowledge represents general knowledge about plant types. It does not represent an
individual plant, property observation, current environmental condition, controller, or delivery
system.

The framework does not:

- calculate plant water demand or environmental conditions;
- diagnose disease or plant health;
- recommend irrigation, generate schedules, or execute commands;
- call providers, networks, controllers, weather services, or AI services;
- persist, download, publish, or remotely update a library;
- expose Home Assistant entities.

Consumer capability declarations are descriptive metadata only. They create no imports or
runtime coupling to visual identification, water demand, plant health, disease diagnostics,
irrigation planning, learning, or recommendations.

## Canonical identity

All library object IDs use readable lowercase canonical identifiers of the form
`pk.<namespace>.<identity>`, with additional dot-separated identity segments permitted. IDs are
assigned by curation and are never generated at runtime from display names.

Changing a scientific name, cultivar label, common name, provider, or display label does not
rename an existing canonical ID. The revised name becomes an alias, or a new profile supersedes
the old profile. Superseded and deprecated records remain serializable and auditable.

The same rule applies to source, claim, conflict-resolution, functional-group, profile, and
request identities.

## Sources and claims

`PlantKnowledgeSource` is a bibliographic record, not a document store. It holds organization,
title, normalized unique authors, publication and access dates, URL or formal citation, source
type, geographic scope, optional reuse notes, and an immutable review history. Review histories
begin `unreviewed` and record valid state transitions; no mutation method changes a source in
place.

Sources never contain downloaded document bodies, raw bytes, provider payloads, API credentials,
or secrets. Data URLs are rejected.

`PlantKnowledgeClaim` is the central evidence record. Every claim contains:

- a stable claim ID and canonical field path;
- one constrained typed value and optional canonical unit;
- explicit regional applicability;
- independent evidence grade and numeric confidence;
- source references, timestamps, review state, version, and consumer capabilities;
- optional notes, conflict status, and supersession reference.

Reviewed and approved claims require source IDs and a review timestamp. Aggregate validation
resolves every source and supersession reference and rejects supersession cycles. Original claims
are never altered or removed by conflict handling.

## Field contracts and ranges

The initial field-contract registry is explicit and closed. It covers the documented identity,
growth, water-characteristic, environmental-tolerance, soil, health-characteristic, visual, and
planning metadata paths introduced by this milestone. Adding a future path is a deliberate schema
change.

Each contract defines its canonical path, value kind, units, negative-value policy, range policy,
and optional numeric bounds or enum type. Claims reject unknown paths, mappings, arbitrary nested
payloads, wrong enums, incompatible units, non-finite values, and disallowed negative values.

`KnowledgeRange` preserves a minimum, optional typical value, maximum, and canonical unit. Values
must be finite and ordered. Negative values are accepted only when the enclosing field contract
explicitly allows them, such as a temperature field. Ranges express known bounds without adding
decimal precision or a statistical interpretation.

## Regional applicability

Applicability explicitly declares either `regional` or `unrestricted` scope. An unrestricted
record cannot carry regional constraints; a regional record requires at least one. Empty data is
therefore never silently interpreted as global applicability.

Regional constraints can identify countries, states or provinces, climate zones, WUCOLS regions,
USDA hardiness-zone bounds, coastal and inland applicability, elevation bounds, and seasons.
Collections are normalized, unique, and deterministically ordered; all ranges are validated.

## Functional groups and profile inheritance

Functional-group hierarchy and profile inheritance are separate graphs.

Functional groups provide descriptive membership and parent grouping. Membership does not import
claims. A profile inherits claims only through its explicit `parent_profile_id` chain. Both graphs
must resolve locally, remain acyclic, and contain no more than eight nodes from root through leaf.

Profile specificity is one of:

1. cultivar;
2. species;
3. genus;
4. functional group;
5. category fallback;
6. unknown fallback.

Profiles carry stable identity, aliases, optional scientific and cultivar names, category,
functional-group membership, directly owned claims, explicit regional applicability, consumer
metadata, schema and profile versions, lifecycle, timestamps, supersession, and small validated
explanation metadata.

When inherited and child claims use the same field path, the child layer overrides the parent
layer. The effective value records its originating profile. The trace retains the overridden
parent claim and identifies the overriding claim. Nothing is silently deleted.

Published profiles must have valid inheritance and supersession, approved source-backed identity
knowledge, and at least one approved source-backed claim relevant to a declared consumer. Those
supporting sources must be reviewed or approved. Provisional-only evidence, rejected sources, and
unresolved fatal claim conflicts cannot support publication. Water-related knowledge is not a
publication requirement.

## Claim conflicts

Competing claims remain independent immutable records. `ClaimResolution` refers to at least two
claims sharing one field path and records a selected claim or resolved range, regional weighting
metadata, method, resolver identity, confidence, unresolved issues, version, and timestamps.

A selected claim must be among the competitors. A resolved range must obey the same field
contract as the claims. A resolution marked `unresolved` does not satisfy a published profile's
conflict gate. Resolution does not rewrite or remove any source claim.

## Library and manifest

`PlantKnowledgeLibrary` owns immutable, canonical-ID-sorted tuples of sources, claims, claim
resolutions, functional groups, and profiles plus one manifest. Construction validates:

- unique IDs and deterministic ordering;
- every cross-reference and supersession relationship;
- acyclic, bounded group and profile inheritance;
- acyclic claim and profile supersession;
- publication evidence requirements;
- conflict-resolution integrity;
- exact manifest counts and confidence statistics;
- climate-region and USDA-zone summaries;
- duplicate published scientific/cultivar identities;
- duplicate published fallback identities at the same level and regional scope;
- the manifest checksum.

Malformed input is rejected. The aggregate never repairs it silently.

The manifest uses semantic library versions, a schema version, generation timestamp, regional
coverage summary, counts by resolution level and record type, published count, confidence
statistics, SHA-256 checksum, and optional previous library version.

The checksum is SHA-256 over canonical JSON serialization of the complete library. Aggregate
collections are sorted by canonical ID, dictionary keys are sorted, and compact deterministic
separators are used. The only omitted value is `manifest.validation_checksum` itself. Thus an
unchanged library produces the same digest regardless of input dictionary or collection insertion
order. `calculate_library_checksum` is public because checksum creation and verification are part
of the stable library-validation contract; lower-level hashing helpers remain private.

## Deterministic profile resolution

Resolution uses normalized exact matching only: surrounding whitespace is removed, internal
whitespace is collapsed, and text is case-folded. There is no fuzzy, semantic, probabilistic,
learned, external-taxonomy, or nondeterministic matching.

Algorithm version `1.0.0` applies this precedence:

1. valid user-confirmed profile override;
2. exact cultivar match;
3. exact species match;
4. exact genus match;
5. functional-group hint match;
6. broad category fallback;
7. unknown fallback.

Deprecated and superseded profiles remain among the candidates for audit but are ineligible by
default. At the first precedence level with eligible matches, regional score breaks ties; canonical
profile ID provides a deterministic final tie break while ambiguity remains explicitly reported.

Identity and region are scored separately. Fixed identity weights are 100 for a user override,
90 for cultivar, 80 for species, 70 for genus, 60 for functional group, 50 for category fallback,
and 10 for unknown fallback. Regional weighting is:

- `+10` when all supplied regional attributes match;
- `+5` when at least one matches and at least one is unavailable;
- `0` when regional context is absent or unavailable;
- `-10` when any supplied regional attribute mismatches.

Identity precedence is authoritative; region ranks only candidates at the same successful level.
Resolution confidence is the selected candidate's total score divided by 110, clamped to
`0.0..1.0` and rounded to six decimal places. This is an explainable policy score, not a learned or
provider-generated probability.

Every result retains all candidates, identity and regional scores, matched aliases, attempted
fallback levels, profile inheritance chain, effective claims with their originating profiles,
inherited and overridden claim traces, confidence, ambiguity, and an optional verification action.
When a conflict resolution supplies a range, the effective claim records both that range and the
resolution ID while retaining a deterministic supporting claim as its provenance anchor.

Effective claims are complete immutable evidence snapshots for downstream consumers. Each snapshot
contains its resolved scalar, enum, or `KnowledgeRange` value; unit; claim-specific sources; review
state; evidence grade; confidence; regional applicability; intended consumers; claim version;
inheritance state; and complete conflict-resolution metadata when applicable. A consumer can
interpret an effective claim after resolution without retaining or querying the originating
`PlantKnowledgeLibrary`. This additive evidence changes the stable serialized resolution contract,
so Plant Knowledge schema version 2 supersedes schema version 1.

The explanation includes a stable reason code, short human summary, algorithm version, candidate
references, evidence-source references, regional matches/unavailable attributes/mismatches, and
inherited/overridden claim references.

## Relationship to existing domains

- The Landscape Digital Twin represents property-specific conditions and plants; Plant Knowledge
  represents general type knowledge.
- Future `PlantInstance` and `PlantGroup` records may reference stable knowledge profile IDs. No
  existing Digital Twin migration occurs in this milestone.
- A future Landscape Water Demand Engine may consume resolved knowledge but owns all demand
  calculations.
- Visual Intelligence may propose profile matches. It cannot publish curated knowledge or bypass
  review gates.
- Environmental Intelligence remains a separate source of property and time-specific conditions.
- Water Delivery remains separate from biological plant demand.

## Consequences

The framework favors explicit validation and traceability over permissive ingestion. Library
authors must sort aggregate records, supply review provenance, declare applicability, maintain
manifest counts, and calculate a valid checksum. In return, future consumers receive stable,
provider-neutral, reproducible results with a complete audit trail.

The initial field registry and scoring algorithm are intentionally small and versioned. Expanding
either requires an explicit compatible schema or algorithm-version decision.

## Deferred decisions

ADR-018 explicitly defers:

- real curated plant content and production botanical records;
- source research, ingestion, licensing review, and community moderation;
- production JSON/database formats and persistence adapters;
- remote library updates and Home Assistant UI;
- visual recognition and Digital Twin `PlantInstance` migration;
- water-demand or environmental calculations;
- plant-health or disease diagnosis;
- irrigation recommendations, planning, schedules, and controller execution.
