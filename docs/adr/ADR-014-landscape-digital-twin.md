# ADR-014: Canonical Landscape Digital Twin

- **Status:** Accepted for IrrigationOS v0.5.1
- **Date:** 2026-08-03

## Context

ADR-007 established an initial per-zone landscape profile for Home Assistant setup. ADR-013 and
the v0.5.0 visual-assessment boundary established provider-neutral, advisory findings. The next
milestone needs a durable canonical representation of the property being managed: landscape
areas, plant groups, soil, irrigation delivery, static weather exposure, health observations,
water demand, goals, and replaceable controller bindings.

The twin must outlive mutable display names, controller replacements, vendor zone identifiers,
inference-provider changes, and individual observations. It also needs to distinguish two kinds
of uncertainty:

1. required facts that are absent; and
2. known facts that still have weak provenance or confidence.

Combining these into one score would hide whether the next useful action is collecting missing
information or verifying an existing inference.

## Decision

### Canonical package and compatibility boundary

The v0.5.1 canonical domain lives in
`custom_components/irrigationos/landscape_twin/`. It is an immutable, provider-neutral domain
package with no Home Assistant, controller-adapter, visual-model-provider, weather-provider, or
network dependency.

The existing `custom_components/irrigationos/landscape/` models remain unchanged for compatibility
with the current options flow and entities. They are not silently reinterpreted as the new
aggregate. A later migration ADR will define explicit conversion, persistence versioning, rollout,
and rollback behavior before runtime consumers switch to the new package.

The aggregate root is `LandscapeDigitalTwin`. It owns exactly one `PropertyProfile` and indexed
collections of:

- `LandscapeArea`;
- `PlantGroup`;
- `SoilProfile`;
- `IrrigationDeliveryProfile`;
- `WeatherExposureProfile`;
- `HealthObservation`;
- `WaterDemandProfile`;
- `LandscapeGoal`; and
- `ControllerBinding`.

Canonical property, area, plant-group, profile, goal, observation, and binding IDs are stable
identifiers. Display names are presentation and never form identity. Rachio or other vendor IDs
exist only on `ControllerBinding`; the area points to an IrrigationOS controller ID and permanent
slot number. Replacing a controller or changing a vendor name does not replace landscape identity.

### Facts, provenance, and correction history

Planning values use `LandscapeFact[T]`. Every fact contains:

- a typed value or explicit unknown;
- confidence from 0.0 through 1.0;
- provider-neutral provenance;
- verification status;
- a timezone-aware assessment timestamp; and
- immutable prior revisions.

An unknown fact has `None` and zero confidence. Enum values with the stable value `unknown` are
also incomplete. Superseding a fact creates a new object and appends the prior value, confidence,
provenance, verification status, and timestamp to history. User-confirmed, user-corrected, and
measured values resolve confidence debt without deleting the original reported confidence or
history.

Models reject unstable identifiers, naive timestamps, non-finite numbers, impossible physical
ranges, invalid plant quantity semantics, inconsistent cycle ranges, and invalid lifecycle dates.
Frozen, slotted dataclasses prevent in-place mutation. Deterministic serialization produces plain
Python dictionaries, stable enum values, ordered lists, and ISO 8601 timestamps.

### Aggregate integrity

`LandscapeDigitalTwin` validates the whole relationship graph at construction:

- property area IDs exactly match aggregate areas;
- every child belongs to a known area;
- area indexes exactly match their owned plant groups, observations, goals, and bindings;
- optional one-to-one soil, delivery, exposure, and demand references match their owned profile;
- health observations may reference only plant groups in the same area;
- identifiers are unique within every collection;
- percentage-based plant groups total no more than 100 percent per area;
- known active-area totals cannot exceed the known property landscape area;
- an area has at most one active controller binding; and
- one controller slot binds to at most one active landscape area.

Unavailable and retired bindings remain representable. No hardware disappearance deletes the
landscape area or its history.

### Completeness

Completeness measures coverage of the versioned planning-readiness fact set. Missing profiles do
not receive defaults. Each missing item is returned as an actionable stable path.

Schema version 1 requires the following property facts:

- total landscaped area; and
- climate zone.

For every active area it requires:

- area and slope;
- category, quantity, establishment stage, and root depth for each plant group, or four missing
  plant-inventory facts if no group exists;
- soil texture, infiltration rate, and available water capacity;
- irrigation delivery method, application rate, and distribution efficiency;
- sun, wind, and heat exposure;
- water-demand basis, crop coefficient, and peak daily demand; and
- at least one active goal target.

Inactive areas are excluded from planning readiness. Optional diagnostic, descriptive, and
calibration facts remain serialized but do not inflate the denominator. The report exposes the
required count, known count, rounded percentage, and ordered missing paths. Any change to this
fact set requires a schema-version decision and tests.

### Confidence debt

Confidence debt is deliberately separate from completeness. It evaluates only known required
facts. For each such fact, debt is `1 - effective confidence`; aggregate debt percentage is the
average deficit across known required facts. Missing facts are excluded because completeness
already reports them.

Measured, user-confirmed, and user-corrected facts have effective confidence 1.0 for debt
calculation while preserving their recorded confidence. The default review threshold is 0.8 and
may be changed by a caller. The report identifies every known fact below the threshold, its
effective confidence, and its debt contribution. A twin can therefore be complete but still have
confidence debt requiring verification.

### Visual assessment and weather boundaries

Visual-assessment results do not directly mutate the twin. A future application service may map a
validated finding into a proposed `LandscapeFact`, baseline adjustment, or user-review operation.
Approval and supersession must retain both visual provenance and prior twin fact history.

`WeatherExposureProfile` represents durable static microclimate facts such as sun, wind, shade,
and reflected heat. It does not fetch forecasts, current conditions, reference ET, or rainfall.
A future weather adapter will remain outside the canonical domain.

### Safety

The twin is descriptive state. It contains no start, stop, scheduling, rain-delay, controller
write, or command-delivery method. Water-demand and irrigation-delivery profiles may support
future planning, but no plan can execute through these models. AI remains advisory and cannot
write confirmed facts without an explicit review boundary.

## Consequences

- Landscape identity and history survive hardware replacement and renaming.
- Planning consumers receive a validated graph instead of loosely related dictionaries.
- Completeness and confidence debt guide different evidence-collection workflows.
- User truth can resolve uncertainty without erasing inferred provenance.
- The domain can be persisted and audited without a provider SDK or Home Assistant runtime.
- The milestone adds no OpenAI connection, image UI, live weather integration, or irrigation
  control.

## Deferred decisions

- Persistence format, storage location, migrations, and rollback from the v0.3 profile layer.
- Mapping approved v0.5.0 visual findings and baseline proposals into canonical facts.
- Home Assistant entities, configuration UI, diagnostics redaction, and edit concurrency.
- Property subdivision, overlapping hydrozones, shared delivery profiles, and multiple active
  controller bindings for intentionally combined areas.
- Live weather observations, ET calculations, learned demand, calibration history, and scenario
  planning.
- Approval policy and execution safety gates for any future irrigation plan.
