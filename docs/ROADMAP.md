# IrrigationOS Roadmap

## v1.0.48 — Recorder Payload Hotfix

- Keeps the aggregate quantitative-water-balance sensor below Home Assistant Recorder attribute limits.
- Retains detailed per-zone water-balance entities and complete audit/diagnostic evidence.
- Adds no scientific, controller, scheduling, or execution behavior.

## v1.0.47 — Weather Evidence Ingestion

- Normalizes the single Home Assistant hourly forecast into canonical forecast evidence.
- Ingests estimated recent Open-Meteo historical precipitation and FAO-56 ET0 with bounded freshness.
- Feeds canonical weather evidence into quantitative water balance while preserving forecast separation and fail-closed blockers.
- Adds no execution authority, scheduler dispatch, retry, or autonomous watering.

## v1.0.46 — Shadow Stability Hotfix

- Deduplicates shadow history from explicit decision semantics rather than derived evaluation timestamps.
- Aggregates shadow commissioning counts without retaining or repeatedly scanning full payload history.
- Avoids unchanged shadow Store writes and exposes bounded privacy-safe performance diagnostics.
- Adds no scientific capability or execution authority.

## v1.0.45 — Quantitative Water Balance & Forecast Reconciliation

- Canonical actual water balance for production targets only.
- Explicit separation of observed water, forecast adjustment, and carry-forward deficit.
- Deterministic forecast deferral/reconciliation with immutable restart-safe ledger evidence.
- Quantitative evidence feeds production recommendations without runtime or execution authority.
- Missing ET0, precipitation history, plant factor, effective-precipitation policy, and calibrated irrigation remain fail-closed blockers.

## v1.0.44 — Canonical Production Recommendation Contract

- Adds one privacy-safe immutable current recommendation per canonical production target.
- Separates scientific irrigation need from quantitative delivery and scheduling readiness.
- Uses one shared configured/enabled/bound target selector with production readiness.
- Retains source weather freshness and stores recommendation snapshots only as shadow audit history.
- Adds no execution authorization, scheduler dispatch, retry, or autonomous watering.

## Current status

- **Installable Home Assistant release:** v1.0.49
- **Completed domain milestone:** v0.9.5 Runtime Monitoring
- **Current operating boundary:** Observation remains the default commissioned mode; recommendations are advisory and cannot authorize watering; existing supervised and one-shot canary paths remain separately gated
- **Current epic:** connect scientific evidence to canonical production targets without expanding authority
- **Next milestone:** shadow-evaluate recommendation evidence quality against observed watering before considering any scheduler authority

## Delivery model

Versions are implementation milestones. Epics represent product capabilities. A milestone is complete only when its code, tests, documentation, release notes, local validation, and GitHub Actions are green.

## Epic 1 — Foundation

**Status: Complete**

Delivered:

- GitHub and HACS-compatible repository
- Home Assistant custom-integration scaffold
- typed Python, pytest, Ruff, MyPy, and CI
- standalone Rachio API foundation
- observation-only safety boundary
- diagnostics framework
- architecture specification and governance documents

### Releases

- `v0.0.1` — Repository foundation
- `v0.1.0` — Standalone Rachio API foundation
- `v0.1.1` — Project governance and architecture records
- `v0.2.0` — Controller foundation
- `v0.3.0` — Landscape Digital Twin foundation
- `v0.4.0` — First live Home Assistant installation
- `v0.4.1` — Canonical controller model and observation reliability
- `v0.4.2` — Real-time Rachio observation

## v1.0 Release Completion

**Status: Stable v1.0.15 released; v1.0.16 health, v1.0.17 observation history, and v1.0.18 shadow evaluation and v1.0.19 actual-vs-shadow reconciliation milestones complete**

Completed domain layers:

- Plant Water Requirement
- Plant Stress
- Plant Health
- Recommendations
- Planning
- Scheduling
- Execution simulation
- Runtime Monitoring

Release-candidate completion:

- final public semantic version resolved as `v1.0.15`, preserving monotonic SemVer after the internal v1.0.x milestone line
- `pyproject.toml`, Home Assistant manifest, runtime constant, tests, and validation metadata synchronized at 1.0.15
- stable release notes and release-candidate documentation completed
- frozen API and Home Assistant lifecycle contracts retained as release gates
- live execution remains disabled; Observation is the only commissioned operating mode

Stable distribution completed:

- `v1.0.15` was tagged and published from the validated merged `main` commit.

Post-release v1.0.16 health milestone:

- aggregate `INITIALIZING / HEALTHY / DEGRADED / UNHEALTHY` health
- six-minute startup/reload grace and elapsed-time failure thresholds
- persistent health-incident latching with non-actuating reset button
- one-shot unhealthy/recovery Home Assistant events
- 30-day safe JSONL daily logs under `/config/irrigationos_logs/`

Post-release v1.0.17 observation-history milestone:

- canonical watering-session reconstruction from trustworthy controller snapshots
- polling/realtime source and timestamp-precision evidence
- independent simultaneous-slot sessions and conservative partial/offline handling
- Home Assistant Store restart continuity and reconstructed-session marking
- separate 30-day session JSONL evidence plus three compact operator sensors
- default `external_unknown` attribution until explicit provider ownership evidence exists

See `docs/V1_0_ARCHITECTURE_AUDIT.md`.

## Epic 2 — Rachio Integration

**Goal:** Provide a complete standalone Rachio integration without depending on Home Assistant's built-in Rachio integration.

### v0.2.0 — Controller foundation

**Status:** Complete


- controller adapter protocol and registry
- canonical controller and irrigation-area models
- normalized availability and state vocabulary
- capability reporting
- Rachio payload translation at the adapter boundary

### v0.4.0 — First live installation

**Status: Complete**

- HACS/custom-repository installation validation
- Rachio API-key config flow in a real Home Assistant instance
- controller and irrigation-area discovery against a live account
- entity/device registry validation
- diagnostics validation with secret redaction
- read-only external watering detection
- best-effort current-watering observation
- reauthentication and refresh health

### v0.4.1 — Canonical controller model and observation reliability

**Status: Complete**

- persisted provider-neutral controller identities
- permanent numbered slots through detected controller capacity
- explicit replaceable vendor bindings
- v0.4.0 entity, device, and landscape-profile migration
- timestamped observations with freshness and source quality
- endpoint-specific partial failures and unknown-versus-idle semantics
- provider-factory runtime composition
- dynamic additions and safe missing-hardware behavior

### v0.4.2 — Real-time Rachio observation

**Status: Complete**

- unique local Home Assistant webhook per config entry
- optional active-subscription cloudhook with standard external HTTPS fallback
- idempotent entry-scoped Rachio notification subscriptions
- signed event validation, authorization checks, and duplicate suppression
- immediate canonical snapshot refresh after accepted status events
- dynamic subscription reconciliation for added and removed controllers
- five-minute reconciliation polling when push delivery is unavailable or incomplete
- redacted realtime health and delivery diagnostics

### v0.5.0 — Observation history and ownership signals

- external/manual operation detection
- observation Flight Recorder
- current watering session and runtime observations
- controller availability and stale-data history
- restart reconciliation
- event normalization and coordinator health

This milestone remains Observation-only.

### v0.6.0 — Execution boundary and safety ownership

- canonical irrigation operation models
- command attribution and receipts
- controller ownership model
- acknowledgement and timeout handling
- restart-safe command reconciliation
- execution disabled by default behind explicit commissioning gates

**Definition of Done:** IrrigationOS can replace the built-in Rachio integration for discovery, observation, safe command delivery, and explainable ownership behavior.

## Epic 3 — Weather Intelligence

- direct Open-Meteo provider
- optional Home Assistant weather and local sensor inputs
- NOAA/NWS forecast and alert support in the United States
- observed versus forecast separation
- source confidence and disagreement handling
- rainfall history and forecast rainfall
- reference evapotranspiration
- microclimate calibration

## Epic 4 — Soil Intelligence

- USDA SSURGO location lookup
- mapped soil recommendation during setup
- confidence and native-soil disclaimer
- per-zone override and amended-soil support
- texture, available water capacity, infiltration, drainage, and runoff model
- guided homeowner calibration tests

## Epic 5 — Landscape and Plant Intelligence

- canonical zone profile
- plant categories and coefficients
- root depth and maturity
- sun, shade, exposure, mulch, and canopy
- irrigation hardware and application efficiency
- slope as a continuous property with simple user-facing categories
- optional subareas within a zone

## Epic 6 — Water Budget Engine

- virtual root-zone water reserve
- ET depletion
- effective rainfall credit
- irrigation credit
- drainage and runoff losses
- moisture debt and stress-risk thresholds
- confidence-aware recommendations

## Epic 7 — Scheduling Engine

- user-defined hard start and sunrise finish boundaries
- preferred watering window
- automatic nightly plan construction
- backward scheduling from sunrise
- priority-based deferral when demand exceeds the window
- cycle-and-soak planning
- forecast wind and noise-aware ordering
- overnight replanning

## Epic 8 — Decision Intelligence

- immutable evaluation contexts
- deterministic alternatives and ranking
- policy engine
- friendly explanations
- confidence and uncertainty reporting
- answerable “why” and “why not” questions

## Epic 9 — Simulation and Shadow Operation

- deterministic simulation
- proposed nightly plans
- shadow comparison against actual Rachio behavior
- replay from recorded observations
- golden landscape scenarios
- promotion criteria for Live mode

## Epic 10 — Autonomous Execution

- live scheduling and command delivery
- sunrise hard stop
- safety preemption
- flow and leak response where data is available
- missed-run recovery
- manual override preservation
- controlled fail-safe behavior

## Epic 11 — Operations Center

- system health and operating mode
- weather, ET, rainfall, and confidence
- per-zone water reserve and recommendations
- current and upcoming plan
- water use and savings
- maintenance signals
- Flight Recorder and diagnostic explanations

## Epic 12 — Landscape Digital Twin

**Foundation delivered early in v0.3.0.**

- persistent property model
- zone and subarea relationships
- calibration history
- learned parameters with provenance and confidence
- landscape-health estimates
- scenario planning

## Epic 13 — Multi-Controller Support

Candidate adapters:

- Hydrawise
- Rain Bird
- OpenSprinkler
- Orbit B-hyve
- ESPHome/relay controllers

All new adapters must implement the canonical controller contract without changing higher intelligence layers.

## Deferred ideas

- AI-assisted plant and soil photo interpretation
- nearby personal-weather-station weighting
- water-price and municipal-budget optimization
- fertilization and maintenance recommendations
- municipal restriction feeds
- cross-property resource coordination


## Release sequencing correction

Earlier drafts used v0.3.1 for live commissioning and v0.4.0 for an execution boundary. The shipped v0.4.0 release was the first live, read-only installation. Execution is intentionally deferred until the canonical model, reliable observation history, ownership, and safety gates are complete.


## v1.0.18 — Shadow Evaluation Foundation

Delivered immutable nightly and material-change shadow decision evidence with semantic deduplication while remaining observation-only.


## v1.0.19 — Actual-vs-Shadow Reconciliation

Delivered immutable observation-only comparison evidence between preserved shadow schedules and real watering sessions, including zone/runtime/timing agreement, skipped watering, unexpected watering, evidence completeness, and conservative confidence.

## v1.0.20 — Shadow Reporting and Commissioning Summary

Delivered aggregate operator-facing reporting across retained shadow and reconciliation evidence. The summary reports agreement, disagreements, confidence, timing/runtime deltas, skipped/unexpected watering, evidence coverage, and a review state. It deliberately does not authorize or automatically promote Live mode.


## v1.0.21 — Replay and Control-Readiness Evidence

Delivered deterministic historical replay of retained reconciliation evidence, fixed golden scenarios, replay coverage/integrity metrics, and explicit conservative promotion criteria. Meeting the criteria only produces a manual-review evidence state; it does not authorize or enable Live mode.

## v1.0.22 — Safety Manager and Execution Authorization Foundation

Delivered deterministic fail-closed authorization evidence between control-readiness and any future live execution boundary. Health, observation freshness, controller availability, pipeline state, ownership, active-watering conflicts, and runtime limits are explicit gates. Positive authorization is never persisted across restart, and live control remains disabled.

## v1.0.23 — Controller Ownership Commissioning

Delivered explicit persisted controller ownership commissioning, topology-bound invalidation, manual execution-boundary review acknowledgement, and operator confirm/revoke controls. These decisions only satisfy future safety prerequisites; live-control feature and authorization flags remain false.


## v1.0.24 — Live-Mode Safety Architecture

Delivered a separate fail-closed safety architecture that distinguishes good commissioning evidence from actual Live-mode eligibility and explicitly tracks six required execution safeguards. Live control remains disabled.

## v1.0.25 — Command Attribution and Receipt Foundation

Delivered canonical non-actuating command intent attribution, correlation IDs, immutable not-dispatched receipts, and local audit evidence. This satisfies only the attribution/receipt safeguard; all command delivery remains disabled.

## v1.0.26 — Command Acknowledgement and Timeout Foundation

Delivered deterministic synthetic acknowledgement, rejection, and timeout semantics with a bounded acknowledgement deadline and immutable local evidence. This is the second implemented Live-mode safeguard; no controller dispatch path exists, and restart-safe command reconciliation remains deferred.


## v1.0.27 — Restart-Safe Command Reconciliation

**Status: Complete**

- Replays persisted acknowledgement evidence at integration startup.
- Restores only still-valid waiting acknowledgement windows.
- Persists timeout transitions for windows that expired while Home Assistant was offline.
- Treats malformed persisted evidence as a fail-closed reconciliation failure.
- Marks restart-safe command reconciliation as Live-mode safeguard 3 of 6.
- Does not add a controller dispatch path or authorize Live mode.


## v1.0.32 — Live Commissioning Protocol & First-Live Acceptance Criteria

**Status: Complete**

- Defines an explicit non-actuating manual commissioning protocol after integrated safety review.
- Requires one canonical controller slot and one canonical area slot for a supervised first-live trial.
- Caps the requested first-live runtime at 120 seconds.
- Uses single-use operator approval that expires after ten minutes and is never persisted across restart.
- Requires a deliberately open supervised commissioning window, healthy fresh observations, and no external watering.
- Defines mandatory acceptance evidence for future start/stop acknowledgement, observed watering, runtime compliance, safety, and post-run reconciliation.
- Can produce `first_live_trial_eligible` evidence only; command dispatch and Live authorization remain disabled.


## v1.0.33 — First-Live Command Delivery Foundation

**Status: Complete**

- Adds the audited Rachio `zone/start` and `device/stop_water` physical transport primitives.
- Retains the strict 120-second first-live runtime ceiling.
- Keeps the release-level physical delivery gate hard-disabled.
- Adds no HA service, button, scheduler callback, or coordinator execution entrypoint.
- Keeps autonomous scheduling and all Live authorization flags false.
- Defers native target binding, operator execution action, approval consumption, live acknowledgement, and post-run reconciliation to the next commissioning milestone.

## v1.0.34 — Commissioned First-Live Watering Trial Executor

**Status: Complete**

- Adds one one-shot executor for an explicitly commissioned supervised trial.
- Binds approval to a canonical controller identity plus controller/area slots and runtime.
- Re-resolves native Rachio identifiers from a fresh observed snapshot immediately before dispatch.
- Requires the controller and area to remain present, enabled, correctly bound, and safe to start.
- Consumes the ephemeral approval before the single network attempt and prohibits automatic retry.
- Treats ambiguous transport outcomes as unknown rather than success.
- Adds no HA service, button, scheduler callback, or coordinator execution path.
- Keeps general Live authorization and autonomous scheduling disabled.


## v1.0.35 — Supervised First-Live Operator Interface

**Status: Complete**

- Adds an interactive Home Assistant options-flow action for one supervised physical watering trial.
- Requires one observed Rachio target, a 1–120 second runtime, and an exact typed confirmation phrase.
- Forces a fresh coordinator refresh before delegating to the v1.0.34 executor.
- Closes the ephemeral commissioning window and revokes any remaining approval after every attempt.
- Registers no irrigation command service or button and adds no scheduler/coordinator-loop dispatch path.
- Keeps general Live mode and autonomous scheduling disabled.


## v1.0.36 — First Supervised Live Trial Acceptance

**Status: Complete**

- Separates bounded supervised commissioning eligibility from long-horizon autonomous promotion evidence.
- Reduces the autonomous promotion evidence-day threshold from 14 to 10 days while retaining the remaining promotion criteria.
- Allows a supervised trial to proceed before promotion maturity only when all non-readiness execution gates, all six live-mode safeguards, and all integrated validation scenarios pass.
- Accepts the canonical Home Assistant `HEALTHY` health-state representation during supervised commissioning.
- Makes execution-boundary acknowledgement available after ownership confirmation even while autonomous readiness remains immature.
- Preserves explicit single-use approval, fresh observations, no active watering conflict, the 120-second runtime ceiling, audit-before-dispatch, no automatic retry, and disabled autonomous Live control.

## v1.0.39 — Bounded Supervised Operational Command Path

**Status: Current milestone**

- Adds one manual Home Assistant service for repeated physical validation of the exact first-live accepted target.
- Requires the accepted first-live result plus a fresh healthy fail-closed preflight on every call.
- Requires current integrated supervised-safety prerequisites before every dispatch.
- Persists separate operational audit and structured JSONL acceptance evidence.
- Keeps all autonomous execution paths disabled.
