# IrrigationOS Roadmap

## Current status

- **Installable Home Assistant release:** v1.0.8
- **Completed domain milestone:** v0.9.5 Runtime Monitoring
- **Current operating boundary:** Observation and simulation only
- **Current epic:** v1.0 architecture freeze and Home Assistant product integration
- **Next milestone:** integrate Execution simulation from proposed Scheduling and upstream evidence

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

**Status: In progress**

Completed domain layers:

- Plant Water Requirement
- Plant Stress
- Plant Health
- Recommendations
- Planning
- Scheduling
- Execution simulation
- Runtime Monitoring

Remaining release work:

- freeze public domain APIs and compatibility tests
- reconcile architecture and release documentation
- wire the complete domain pipeline into Home Assistant (current weather and plant knowledge integrated)
- expose stable observation and simulation entities and diagnostics
- validate startup, reload, persistence, migration, and entity lifecycle
- complete v1.0.0 release metadata and release notes
- deploy with live execution disabled by default

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
