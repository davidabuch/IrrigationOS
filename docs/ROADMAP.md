# IrrigationOS Roadmap

## Current status

- **Installable Home Assistant release:** v1.0.24
- **Completed domain milestone:** v0.9.5 Runtime Monitoring
- **Current operating boundary:** Observation and simulation only
- **Current epic:** v1.0 architecture freeze and Home Assistant product integration
- **Next milestone:** accumulate real-world shadow/replay evidence while implementing the required execution safeguards behind the still-disabled Live-mode boundary; live control remains deferred

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

Defined a separate fail-closed architecture gate between commissioning evidence and any future Live-mode enablement. Existing readiness, ownership, and authorization evidence remain prerequisites only. Command attribution/receipts, acknowledgement/timeouts, restart-safe reconciliation, safety preemption, sunrise hard stop, and manual override preservation are explicit required safeguards and remain unimplemented. Live control remains disabled.
