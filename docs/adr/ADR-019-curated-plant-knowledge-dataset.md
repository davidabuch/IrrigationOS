# ADR-019: Curated Plant Knowledge Dataset

- Status: Accepted
- Date: 2026-08-04
- Decision owners: IrrigationOS maintainers
- Milestone: v0.6.3
- Capability: 6.2 — Curated Plant Knowledge Dataset

## Context

ADR-018 established the immutable Plant Knowledge Framework, including canonical sources,
claims, profiles, functional groups, regional applicability, publication gates, deterministic
resolution, manifests, and checksums.

The framework intentionally contains no production botanical records.

IrrigationOS now needs an initial curated library that exercises this framework with reviewed,
source-backed plant knowledge. The library must be useful enough to support later Plant Water
Requirement, Plant Stress, and Plant Health capabilities without introducing calculations or
recommendations itself.

A large catalog assembled quickly would create substantial risks:

- weak or inconsistent evidence;
- unclear licensing and reuse rights;
- duplicate or unstable botanical identities;
- broad claims applied outside their supported region;
- false precision;
- premature coupling to future irrigation algorithms; and
- high maintenance and review costs.

The initial dataset therefore prioritizes evidence quality, traceability, regional relevance, and
architectural validation over record count.

## Decision

### Canonical curated-library package

Create a curated-library package under:

```text
custom_components/irrigationos/plant_knowledge/curated/
```

The package constructs one canonical `PlantKnowledgeLibrary` using the immutable domain objects
established by ADR-018.

The initial implementation is authored directly in typed Python. It does not introduce YAML,
JSON ingestion, databases, remote downloads, or persistence adapters.

This avoids creating a second validation architecture before production storage and update
requirements are understood.

### Library version

The initial curated library uses an independent semantic library version:

```text
1.0.0
```

The library version is distinct from:

- the IrrigationOS integration version;
- the Plant Knowledge schema version;
- the profile version;
- the claim version; and
- the resolution algorithm version.

Any change that alters canonical records, claims, source provenance, profile resolution, regional
applicability, or the resulting checksum requires an appropriate library-version change.

### Initial scope

The initial release contains a deliberately limited set of approximately 12–20 published profiles.

The catalog provides representative coverage of common Southern California landscape classes,
including:

- turf;
- trees;
- shrubs;
- groundcovers;
- succulents;
- ornamental grasses;
- California native plants;
- Mediterranean-climate plants; and
- selected commonly landscaped species.

Record count is not a release criterion. A smaller fully reviewed library is preferable to a
larger weakly supported library.

### Profile hierarchy

The initial library may contain:

- category fallback profiles;
- functional-group profiles;
- genus profiles;
- species profiles; and
- cultivar profiles only when cultivar-specific evidence is available.

Profiles must use explicit inheritance. Functional-group membership does not implicitly import
claims.

A child profile overrides a parent claim only through the existing ADR-018 inheritance rules.
Original inherited and overridden claims remain traceable.

### Evidence and source standards

Every published profile must satisfy the ADR-018 publication gate.

At minimum, a published profile requires:

1. approved source-backed identity knowledge;
2. at least one approved source-backed claim relevant to a declared consumer capability;
3. reviewed or approved supporting sources;
4. valid regional applicability;
5. resolved inheritance and supersession references;
6. no unresolved fatal claim conflicts; and
7. deterministic serialization and checksum validation.

Preferred sources include:

- university extension programs;
- government agricultural or horticultural agencies;
- peer-reviewed publications;
- recognized botanical institutions;
- formally published regional landscape-water references; and
- authoritative taxonomic databases.

Commercial nursery pages, gardening blogs, search-result summaries, AI-generated text, and
unsourced community content cannot independently support publication.

They may be retained only as clearly graded supplemental evidence when permitted by the source
model.

### Source reuse and licensing

The curated library stores bibliographic facts and normalized knowledge claims. It does not copy
source documents, photographs, tables, or substantial protected text.

Each source record must include reuse notes when licensing or attribution conditions are relevant.

Unclear licensing prevents bulk import of source material but does not prevent recording
independently verified factual claims with proper citation.

### Regional focus

The initial dataset is optimized for Southern California and Mediterranean-climate landscape use.

Regional applicability must remain explicit. Southern California relevance does not make a claim
globally applicable.

Claims may use:

- country and state constraints;
- WUCOLS regions;
- USDA hardiness zones;
- climate-zone identifiers;
- coastal or inland applicability;
- elevation ranges; and
- seasonal constraints

when supported by evidence.

An unrestricted claim must be intentionally designated unrestricted. Missing regional information
must not silently become global applicability.

### Water-related claims

The library may contain descriptive water-characteristic knowledge already supported by the
ADR-018 field registry, including qualitative classifications or evidence-backed ranges.

These claims remain general plant knowledge.

The curated dataset does not:

- calculate plant water requirements;
- assign irrigation coefficients;
- calculate evapotranspiration demand;
- determine irrigation frequency;
- determine runtime;
- account for current weather or soil moisture;
- identify current stress;
- recommend watering; or
- authorize controller execution.

All such calculations remain owned by later capabilities.

### Construction and public boundary

The curated package exposes one stable library-construction boundary:

```python
build_curated_plant_knowledge_library()
```

The function returns a fully validated immutable `PlantKnowledgeLibrary`.

Construction must fail if any source, claim, profile, functional group, conflict resolution,
manifest value, or checksum violates ADR-018.

The package must not expose mutable internal construction collections as public API.

### Internal organization

The implementation may separate records into private modules such as:

```text
curated/
    __init__.py
    library.py
    sources.py
    functional_groups.py
    claims.py
    profiles.py
```

Module boundaries are organizational and are not separate public APIs.

The final aggregate remains the canonical deliverable.

### Determinism

The same curated source tree must always produce:

- the same canonical record ordering;
- the same serialized library;
- the same manifest counts;
- the same confidence statistics;
- the same regional coverage summary; and
- the same SHA-256 validation checksum.

The checked-in expected checksum acts as an intentional-change detector.

A checksum change is not automatically accepted by updating the fixture. The underlying record
change must first be reviewed.

### Validation and tests

The milestone must include tests proving:

- the complete curated library constructs successfully;
- all aggregate collections use deterministic canonical ordering;
- all published profiles satisfy publication requirements;
- all cross-references resolve;
- inheritance and supersession graphs remain acyclic;
- canonical IDs are unique;
- published scientific and cultivar identities are not duplicated;
- aliases resolve deterministically;
- representative category, genus, species, and fallback resolution succeeds;
- regional tie-breaking remains deterministic;
- inherited and overridden claims retain traceability;
- manifest counts and statistics match the actual library;
- serialization is deterministic;
- the expected checksum matches;
- rebuilding from differently ordered construction inputs yields the same checksum; and
- no Home Assistant, controller, provider, network, persistence, or recommendation dependency is
  introduced.

### Documentation

The milestone includes a curation guide describing:

- canonical ID assignment;
- accepted source classes;
- evidence grading;
- review-state requirements;
- regional applicability;
- identity and alias handling;
- claim creation;
- conflict handling;
- inheritance;
- profile publication;
- library versioning;
- checksum review; and
- the process for proposing future plant records.

## Public API

The curated library adds only the following stable public boundary:

```python
build_curated_plant_knowledge_library
```

The existing ADR-018 domain models, checksum function, and deterministic resolver remain
authoritative.

No record-specific constants are added to the top-level public API.

## Safety and separation boundaries

The curated dataset is immutable general knowledge.

It does not represent:

- an individual plant;
- a Landscape Digital Twin plant instance;
- a property observation;
- current environmental conditions;
- current plant health or stress;
- an irrigation recommendation;
- an irrigation plan or schedule;
- controller state; or
- execution authority.

Runtime observations never modify canonical curated knowledge.

Future learning systems may propose candidate changes, but they cannot mutate or publish the
curated library without the same explicit review and versioning process used for human-authored
changes.

## Consequences

### Positive

- IrrigationOS gains a trustworthy starter knowledge library.
- The ADR-018 framework is validated using production-quality records.
- Future capabilities receive immutable, source-backed, regionally explicit knowledge.
- Dataset changes remain reviewable and reproducible.
- The implementation avoids premature persistence and ingestion architecture.
- A small initial catalog limits research and maintenance cost.

### Tradeoffs

- Initial plant coverage will be limited.
- Curation requires more effort per profile than bulk data import.
- Code-authored records are less convenient for nontechnical contributors.
- Dataset expansion remains intentionally slower than automated ingestion.

These tradeoffs are accepted for the initial library.

## Explicitly deferred

This milestone does not include:

- a YAML or JSON production dataset format;
- database persistence;
- remote or automatic library updates;
- community submission infrastructure;
- bulk ingestion;
- web scraping;
- AI-generated plant records;
- image assets;
- visual plant identification;
- Digital Twin plant-instance migration;
- plant water-demand calculations;
- plant stress calculations;
- plant health or disease diagnosis;
- water-savings calculations;
- irrigation recommendations;
- planning or scheduling;
- Home Assistant entities; or
- controller execution.

## Acceptance criteria

Capability 6.2 is complete when:

1. ADR-019 is accepted.
2. The canonical curated-library package exists.
3. The library contains a reviewed representative starter catalog.
4. Every published profile passes ADR-018 publication validation.
5. The library is immutable and deterministically reproducible.
6. The expected checksum is tested.
7. Representative profile-resolution behavior is tested.
8. The curation guide is complete.
9. Ruff passes.
10. MyPy passes.
11. The complete pytest suite passes.
12. Home Assistant tests pass.
13. Repository validation passes.
14. GitHub Actions are green.
15. No recommendation, scheduling, runtime, persistence, network, or execution behavior is
    introduced.
