# Plant Knowledge Curation Guide

## Purpose

This guide defines the review rules for records added to the canonical IrrigationOS curated Plant
Knowledge library. ADR-018 defines the domain model and validation rules. ADR-019 defines the
curated-library boundary and scope.

Capability 6.2A establishes the deterministic library-construction boundary only. It intentionally
contains no production botanical records.

## Curation principles

- Prefer a small, well-supported library over a large weakly supported catalog.
- Assign stable canonical IDs; never derive IDs at runtime from display names.
- Preserve sources, original claims, conflicts, supersession, and review history.
- Declare regional applicability explicitly. Missing region data is not global applicability.
- Keep general plant knowledge separate from property observations and runtime state.
- Do not add irrigation recommendations, schedules, durations, or execution authority.

## Evidence

Preferred evidence sources include government agencies, university extension programs,
peer-reviewed publications, recognized botanical institutions, authoritative taxonomic databases,
and formally published regional landscape-water references.

Commercial pages, blogs, search summaries, AI-generated text, and unsourced community content do
not independently support a published profile.

## Review sequence

For each proposed record:

1. Assign the canonical source, claim, functional-group, or profile ID.
2. Record bibliographic provenance and any relevant reuse notes.
3. Normalize the factual claim into an existing ADR-018 field contract.
4. Assign evidence grade, confidence, review state, and regional applicability.
5. Preserve competing claims and add an explicit resolution when required.
6. Validate profile inheritance and functional-group membership separately.
7. Confirm the ADR-018 publication gate before marking a profile published.
8. Rebuild the library and review all manifest and checksum changes.
9. Increment the curated library version when canonical content changes.

## Checksum review

The manifest checksum is an intentional-change detector. A changed checksum must be explained by a
reviewed canonical content change. Never update an expected checksum merely to silence a failing
test.

## Deferred contributor format

The initial curated library is authored in typed Python using immutable ADR-018 objects. YAML,
JSON ingestion, databases, remote updates, and community-submission infrastructure remain deferred
until their requirements are explicitly designed.

## Initial canonical source catalog

The v1.1.0 library registers a deliberately small approved source catalog before adding claims:

- Calflora for California wild-plant identity, native status, and distribution support;
- Plants of the World Online for accepted names, synonyms, and broad native ranges;
- USDA PLANTS for United States identity, native-status, and distribution support; and
- WUCOLS IV for California regional landscape water-use classifications.

Registration does not authorize bulk copying. Curators must create independently normalized claims,
retain source attribution, respect the recorded reuse notes, and avoid importing source text,
images, or database payloads.

## Initial functional-group hierarchy

Functional groups are descriptive memberships, not claim inheritance. The initial hierarchy covers
woody trees and shrubs, herbaceous groundcovers and ornamental grasses, turfgrasses, succulents,
California natives, and Mediterranean-climate plants. Cross-cutting groups remain roots because a
profile may belong to several groups independently.
