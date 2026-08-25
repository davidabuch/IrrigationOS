# v1.0.57 — Guided Baseline Reference & Irrigation Delivery Calibration

v1.0.57 turns two expert-only evidence gaps into deterministic guided calibration workflows. Calibration records facts; it never authorizes or schedules irrigation.

## Guided baseline reference capture

A user-calibrated runtime remains the user's statement about a representative condition. The options workflow can now capture the trailing exact 24- or 48-hour normalized environmental period as its scientific reference. Capture requires:

- an admitted, unambiguous user-calibrated baseline;
- explicit confirmation that the period is representative and dry;
- one complete contiguous hourly record for every hour;
- fresh normalized ET₀, precipitation, and temperature-context facts;
- good or estimated quality and minimum 0.60 confidence;
- positive ET₀ and exactly zero observed precipitation; and
- explicit confirmation before replacing an existing reference.

The captured ET₀ is the sum of normalized reference-evapotranspiration evidence over the selected period. Temperature is retained as measured descriptive context and is never used to derive ET₀. A rainy, stale, missing, incomplete, low-confidence, or invalid period is rejected without changing durable state.

Successful capture immediately supplies the explicit reference consumed by the unchanged v1.0.56 advisory scaling algorithm. Both scaling algorithm and policy remain version 1.0.0.

## Delivery calibration

Canonical delivery profiles are stored separately from plant groups. A plant link may reference the same physical component as another plant link, allowing one shared microjet to serve multiple groups without pretending that each group owns a separate emitter. Dedicated delivery remains an explicit independent fact.

Flow evidence is classified as:

- `unknown`: the component is documented but no flow is claimed;
- `manufacturer_rated`: nominal specification evidence;
- `user_estimated`: an explicitly estimated nominal value; or
- `measured`: a raw collected-volume and elapsed-time observation.

Each known flow also declares whether it is per emitter or the total for the physical component group; component count is retained independently.

For measured evidence only:

`flow_liters_per_hour = collected_volume_liters × 3600 / duration_seconds`

One US gallon is converted as exactly 3.785411784 liters. The raw volume, unit, duration, provenance, confidence, and calibration timestamp are retained. IrrigationOS does not infer pressure, coverage uniformity, application rate, efficiency, delivered depth, or runtime from this measurement.

## Persistence and history

Commissioning model and Store schemas advance to 5. Schemas 1–4 remain readable and migrate additively; absent historical reference or delivery calibration stays absent. Current environmental-reference replacement moves the prior reference into chronological immutable history. Measured component recalibration retains every prior guided calibration and raw measurement.

Zone and delivery-profile changes use one persistence transaction. In-memory state changes only after Home Assistant Store save succeeds. A failed save publishes neither the edited zone link nor the new calibration profile.

## Home Assistant and lifecycle

The established commissioning review flow adds:

- **Capture current conditions as baseline reference**; and
- **Calibrate irrigation-delivery evidence**.

Detailed evidence remains in the review workflow and diagnostics. Recorder-facing zone summaries add only a bounded calibrated-component count. No new task, timer, listener, polling loop, provider request, raw image, or controller operation is introduced.

`execution_authorized` and `live_control_authorized` remain false. First-live, supervised operation, unattended canary, scheduler, Rachio transport, confirmation phrases, runtime ceilings, retry policy, and lifecycle cleanup are unchanged.
