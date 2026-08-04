# ADR-015: Canonical Water Delivery Model

- **Status:** Accepted for IrrigationOS v0.5.2
- **Date:** 2026-08-03

## Context

The Landscape Digital Twin needs a more precise description of how water reaches a landscape
area. A controller zone does not imply one homogeneous delivery method: a single area may combine
drippers, microjets, bubblers, or other devices, and some areas are watered manually. Vendor zone
metadata is often incomplete or nominal. Safe future recommendations require a canonical model
that can retain both nominal specifications and user-measured calibration evidence without
turning either into a controller command.

This model must remain useful if IrrigationOS changes controller vendors, inference providers,
Home Assistant entities, or storage technology. It must also distinguish physical delivery facts
from guided calibration workflow state.

## Decision

### Domain boundary

The canonical domain lives in `custom_components/irrigationos/water_delivery/`. It is a pure
Python package containing frozen, slotted dataclasses and stable string enums. It imports no Home
Assistant, controller adapter, weather service, AI provider, network client, or persistence layer.

`WaterDeliveryProfile` represents delivery for one canonical landscape area. It owns one or more
`DeliveryComponent` records and their `GuidedCalibration` records. Component and area identities
are stable IDs; mutable names are presentation only. The model contains no controller ID, vendor
zone ID, entity ID, or API payload.

### Mixed delivery components

A component describes one homogeneous delivery population. A profile may contain any mixture of:

- drippers;
- microjets;
- misters;
- sprays;
- rotors;
- bubblers;
- subsurface drip; and
- manual watering.

`WaterDeliveryProfile.is_mixed` is true when the profile contains more than one delivery type.
Mixed components keep independent quantity semantics rather than being coerced into one total.

A component quantity is explicitly one of:

- `count`, which must be a positive whole number;
- `percentage`, which is bounded to 100 and whose peer percentage components may not total more
  than 100; or
- `served_area`, which is positive and requires square-foot or square-meter units.

Counts and served areas do not participate in percentage totals.

### Delivery facts

Physical and qualitative properties use `DeliveryFact[T]`. Each fact carries a typed value or
explicit unknown, confidence from 0.0 through 1.0, provider-neutral provenance, and a
timezone-aware assessment timestamp. Unknown facts have zero confidence. Facts accept only plain
scalars or stable enums and reject embedded provider payloads and raw bytes.

Each component can represent:

- nominal flow in liters per hour;
- measured flow in liters per hour;
- flow basis: per emitter, component total, manual source, or unknown;
- application rate in millimeters per hour;
- coverage radius in meters;
- spray arc in degrees;
- spray pattern;
- distribution efficiency as a fraction;
- pressure-compensation behavior; and
- clogging risk.

Nominal and measured flow are retained side by side. `preferred_flow_liters_per_hour` selects a
known measured value before nominal value but does not erase either source. Flow, rate, radius,
and arc must be positive when known; arc is at most 360 degrees; efficiency is between zero and
one. A zero efficiency is representable as an observed failure.

### Guided calibration

`GuidedCalibration` is immutable workflow and evidence, not an instruction to operate a
controller. It records why a user-performed test matters, ordered instructions, a safety note,
optional timer duration, requested unit, lifecycle state, typed measurements, opaque photo
references, and completion time.

Supported tests are:

- drip counting;
- collected volume;
- spray radius;
- spray arc;
- photo reference; and
- function inspection.

Measurements enforce the corresponding type and unit. Drip counts are whole numbers, collected
volumes and distances are positive, arcs are at most 360 degrees, and function inspection is
boolean. A completed measurement-based test requires a matching measurement. A completed photo
test requires an opaque photo reference.

Components index their calibration IDs. Profile construction validates that every calibration
belongs to the same area, points to a known component, and appears exactly once in the owning
component index. This rejects dangling and orphaned calibration evidence.

### Image privacy

Calibration photos are represented by `CalibrationPhotoReference`: a stable evidence ID, opaque
reference token, capture time, source, and optional note. Raw image bytes and `data:` URLs are
rejected. The model does not fetch, store, retain, delete, upload, or log image content. Storage
and retention remain outside this milestone.

### Serialization

Every public model serializes deterministically to plain Python dictionaries. Enums become stable
string values, tuples become ordered lists, timestamps use ISO 8601, and nested models are
recursive. Serialization is suitable for future adapter boundaries and audit construction but
does not implement persistence.

### Safety boundary

This model is descriptive and calibration-only. It exposes no start, stop, schedule, duration,
rain-delay, valve, controller-write, or command-delivery operation. Guided calibration describes
tests that a person may choose to perform; IrrigationOS does not activate hardware for those
tests. No value in this model authorizes execution.

## Consequences

- Mixed delivery systems can be represented without flattening incompatible quantity modes.
- Nominal specifications and direct measurements remain separately auditable.
- Guided calibration produces validated evidence without coupling to a controller or UI.
- Manual watering is a first-class delivery type rather than fabricated controller hardware.
- The model can later be referenced by the Landscape Digital Twin without creating a runtime
  dependency in this milestone.
- No Home Assistant entity, OpenAI call, weather data, controller API, persistence, or irrigation
  execution is added.

## Deferred decisions

- Mapping this profile into `LandscapeDigitalTwin.IrrigationDeliveryProfile`.
- Home Assistant configuration and review UI.
- Storage, migrations, retention, and diagnostics redaction.
- Pressure measurement, manufacturer catalogs, hydraulic network topology, filtration, and pipe
  loss modeling.
- Translating calibrated measurements into proposed schedules or water-demand recommendations.
- Any execution or controller-command safety boundary.
