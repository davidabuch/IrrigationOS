# Changelog

## 1.0.18 — Shadow Evaluation Foundation

- Added immutable point-in-time shadow evaluation evidence.
- Added authoritative nightly evaluation at 8:00 PM Home Assistant local time.
- Added material-change reevaluation with semantic decision deduplication.
- Added 30-day local JSONL shadow evidence and safe diagnostics.
- Preserved the observation-only, non-actuating commissioning boundary.

## 1.0.17 - Observation History and Watering Session Recorder

- Add immutable provider-neutral watering-session evidence with canonical controller, area, and permanent-slot identity.
- Reconcile independent sessions from canonical polling and realtime-triggered snapshots without duplicate creation or false closure during partial/offline observations.
- Persist active and recent completed sessions with Home Assistant Store and conservatively reconcile them after restart.
- Add a separate 30-day local-day JSONL watering-session evidence stream without vendor-native identifiers or credentials.
- Add compact current-session, last-completed-session, and sessions-today Home Assistant sensors plus safe diagnostics summaries.
- Keep all naturally observed watering attribution at `external_unknown` because the current adapter exposes no explicit schedule/manual ownership evidence.
- Preserve the Observation-and-simulation-only boundary; no controller command or scheduling behavior is added.

## 1.0.16 - Health Monitoring and Incident Diagnostics

- Add aggregate `INITIALIZING`, `HEALTHY`, `DEGRADED`, and `UNHEALTHY` operational health with a six-minute startup/reload grace period.
- Treat realtime failure with successful polling fallback as degraded redundancy rather than a full outage.
- Escalate stale observations after twelve minutes and sustained all-controller unavailability after ten minutes to unhealthy.
- Persist and latch genuine unhealthy incidents across Home Assistant restarts, with a non-actuating reset button available only after recovery.
- Emit one-shot Home Assistant unhealthy and recovery events suitable for phone-notification automations while keeping degraded states notification-free by default.
- Add 30-day daily JSONL operational logs under `/config/irrigationos_logs/` using local-day filenames plus local and UTC timestamps.
- Preserve the Observation-and-simulation-only safety boundary; no irrigation decision or controller actuation behavior changes.

## 1.0.15 - Stable Release Candidate

- Resolve the first stable public semantic version as 1.0.15, preserving monotonic version ordering after the internal v1.0.x milestone line.
- Synchronize `pyproject.toml`, Home Assistant manifest, runtime version constant, repository validation, and tests at 1.0.15.
- Add machine-enforced validation that the Python project version and Home Assistant manifest version remain synchronized.
- Add stable v1.0.15 release notes and final release-candidate documentation.
- Preserve the frozen v1.0 public API compatibility contract established at v1.0.13.
- Preserve the Observation-and-simulation-only boundary; live irrigation execution remains disabled.

## 1.0.14 - Architecture and Release Documentation Reconciliation

- Reconcile the v1.0 architecture audit with the completed Home Assistant pipeline, entity/diagnostics, lifecycle, and public-API milestones.
- Distinguish current observation/simulation behavior from future Shadow and Live control architecture across canonical architecture and operating-mode documents.
- Update release strategy and roadmap language to match the v1.0 release-candidate state and remaining release work.
- Preserve the frozen v1.0 public API contract and the Observation-and-simulation-only safety boundary.
- Make no runtime, domain-engine, Home Assistant entity, or controller behavior changes.

## 1.0.13 - Public API and Compatibility Freeze

- Freeze exact public exports for all completed v1.0 domain layers and the synchronized Home Assistant pipeline.
- Add a machine-readable v1.0 API contract covering schema and algorithm versions, enum names/values, and dataclass field ordering.
- Convert compatibility tests from minimum-symbol checks to exact contract checks so silent breaking changes fail CI.
- Document public-versus-internal compatibility expectations for future refactors and schema evolution.
- Preserve the Observation-and-simulation-only boundary; no runtime behavior or controller command path changes are introduced.

## 1.0.12 - Home Assistant Lifecycle Validation

- Validate cold startup of the completed Home Assistant pipeline from persisted config-entry data and options.
- Validate unload/setup and config-entry reload without changing or duplicating pipeline entity IDs and unique IDs.
- Validate canonical identity and landscape-profile persistence across lifecycle transitions.
- Validate legacy migration followed by a real Home Assistant startup with canonical per-zone pipeline entities.
- Preserve the Observation-and-simulation-only boundary; this milestone adds lifecycle validation and no live command path.

## 1.0.11 - Pipeline Entities and Diagnostics

- Add one stable diagnostic sensor for every synchronized pipeline stage.
- Add one compact per-zone pipeline-output sensor exposing Water Requirement, Plant Stress, Plant Health, Recommendations, Planning, Scheduling, Execution simulation, and Runtime Monitoring statuses without recomputation.
- Preserve canonical provenance identifiers and blocker codes as read-only entity attributes.
- Add a compact pipeline diagnostics summary alongside the fully redacted immutable pipeline snapshot.
- Preserve the Observation-and-simulation-only boundary; no controller, Rachio, Home Assistant service, valve, switch, retry, or recovery command path is introduced.

## 1.0.10 - Runtime Monitoring Pipeline Integration

- Adapt the existing deterministic Runtime Monitoring engine into the synchronized Home Assistant pipeline.
- Consume canonical simulation-only Execution plans without recomputing execution, scheduling, or upstream scientific logic.
- Preserve execution-plan provenance and report truthful no-execution/blocked states without fabricating command acknowledgements, failures, or interruptions.
- Keep runnable simulated commands unmonitored until real command-result and interruption observations are integrated.
- Preserve the Observation-and-simulation-only boundary; no retry, recovery, controller, or Home Assistant command path is introduced.

## 1.0.9 - Execution Simulation Pipeline Integration

- Adapt the existing deterministic Execution engine into the synchronized Home Assistant pipeline.
- Consume canonical proposed Scheduling outputs without recomputing scheduling or upstream scientific logic.
- Preserve schedule-to-execution-plan and scheduled-action provenance with deterministic simulated command models.
- Keep the execution path simulation-only: no controller adapter, Rachio API, Home Assistant service, valve, or switch calls are introduced.
- Keep Runtime Monitoring blocked until its dedicated integration milestone.

## 1.0.8 - Scheduling Pipeline Integration

- Adapt the existing deterministic Scheduling engine into the synchronized Home Assistant pipeline.
- Consume canonical machine-readable Planning outputs without recomputing planning or upstream scientific logic.
- Preserve plan-to-schedule provenance and manual-only dispositions.
- Do not fabricate permitted watering windows; runnable actions remain unscheduled until an explicit window source is configured.
- Keep Execution and Runtime Monitoring blocked until their dedicated integration milestones.

## 1.0.7 - Planning Pipeline Integration

- Adapt the existing deterministic Planning engine into the synchronized Home Assistant pipeline.
- Consume canonical Recommendation assessments without recomputing recommendation or upstream scientific logic.
- Create machine-readable plans without inventing irrigation quantities, runtime, targets, or scheduling directives.
- Preserve recommendation provenance and `NO_AUTOMATIC_EXECUTION` as manual-only planning dispositions.
- Keep Scheduling, Execution, and Runtime Monitoring blocked until their dedicated integration milestones.

## 1.0.6 - Recommendation Pipeline Integration

- Adapt the existing deterministic Recommendation engine into the synchronized Home Assistant pipeline.
- Consume accepted Water Requirement, Plant Stress, and Plant Health assessments without recomputing upstream science.
- Preserve assessment provenance, unresolved evidence, and advisory-only/no-automatic-execution safety flags.
- Allow conservative inspection guidance when direct Plant Health evidence is insufficient.
- Keep Planning, Scheduling, Execution, and Runtime Monitoring blocked until their dedicated integration milestones.

## 1.0.5 - Plant Health Pipeline Integration

- Execute the canonical Plant Health engine for every area with aggregate Plant Stress context.
- Preserve the direct-evidence boundary: stress is context and is never treated as a health diagnosis.
- Return explicit insufficient-direct-evidence assessments until manual, sensor, or visual observations exist.
- Store immutable per-area Plant Health results in the synchronized Home Assistant pipeline.
- Keep Recommendations and downstream stages blocked until their dedicated integration milestones.

## 1.0.4 - Plant Stress Pipeline Integration

- Build conservative Environmental Intelligence from normalized current Home Assistant weather.
- Execute water-deficit, heat, and freeze stress engines per eligible irrigation area.
- Aggregate independent stress dimensions without recomputing upstream Water Requirement science.
- Preserve explicit partial and blocked states when current weather lacks drying or forecast evidence.
- Keep Plant Health and all downstream stages non-actuating and blocked until their dedicated integration milestones.

## 1.0.3 - Water Requirement Pipeline Integration

- Add per-area plant establishment stage to the Landscape Digital Twin.
- Derive season from Home Assistant location hemisphere without persisting coordinates.
- Carry resolved Plant Knowledge forward without recomputing upstream science.
- Execute evidence-backed Plant Water Requirement assessments in the HA pipeline.
- Preserve explicit partial/blocking results when context or evidence is incomplete.
- Update GitHub Actions to Node 24-compatible action generations.

## 1.0.2 - Scientific Input Integration

- Normalize the single available Home Assistant weather entity into canonical units.
- Resolve landscape plant identities against the curated Plant Knowledge library.
- Expose scientific-input readiness and weather-source sensors.
- Preserve explicit blockers for ambiguous weather sources and unresolved plant identity.
- Keep Water Requirement and all downstream stages non-actuating and blocked until their remaining context is configured.

## 1.0.1 - Home Assistant pipeline integration

- Added one immutable `PipelineEvaluation` snapshot per coordinator refresh.
- Added pipeline status, stage, version, and last-evaluation sensors.
- Added pipeline readiness and blocker details to diagnostics.
- Preserved observation-only behavior; no hardware commands are issued.

## v1.0 Architecture Freeze Audit

- Audited the completed deterministic domain pipeline through Runtime Monitoring.
- Confirmed that no release-blocking engine redesign is required.
- Documented stale release metadata and incomplete Home Assistant pipeline wiring.
- Added explicit public-API compatibility contracts for the frozen v1.0 domain layers.
- Updated the roadmap to distinguish the v0.4.2 installable runtime from the v0.9.5 domain baseline.

## v0.9.4 - Execution Engine

- Added immutable simulation-only execution contracts.
- Added deterministic controller start/stop command generation.
- Added stable idempotency keys and IrrigationOS command attribution.
- Added acknowledgement, retry, timeout, rejection, and safety-block modeling.
- Preserved complete schedule provenance without hardware or Home Assistant writes.

## 0.4.2

- Added a unique authenticated Home Assistant webhook per config entry.
- Added optional cloudhook selection for active Home Assistant Cloud subscriptions and standard external HTTPS webhook fallback without a paid subscription.
- Added idempotent, entry-scoped Rachio subscriptions for controller, zone, schedule, rain-delay, and rain-sensor status events.
- Matched RachioPy legacy discovery headers and added safe structured event-discovery failure diagnostics.
- Added HMAC signature and entry authorization validation, bounded event deduplication, and immediate canonical snapshot refreshes.
- Added dynamic remote subscription reconciliation for controllers discovered or removed after startup.
- Added nonfatal setup warnings and diagnostics for URL source, registration health, event counts, last event, and polling fallback.
- Expanded redaction to webhook URLs, identifiers, authorization values, and signatures.
- Preserved five-minute polling and the Observation-only safety boundary.

## 0.4.1

- Added persisted canonical controller identities and permanent controller slots.
- Separated replaceable Rachio bindings from IrrigationOS identity.
- Added observation timestamps, freshness, quality, and endpoint-specific partial failures.
- Added provider-factory composition and dynamic entity reconciliation.
- Added v0.4.0 registry and landscape-profile migration.
- Added behavioral coverage and ADR-009/ADR-010.
- Added Home Assistant runtime, registry-migration, and diagnostics smoke tests to CI.
- Added HACS-ready packaging metadata and a local brand icon; HACS validation remains deferred while the repository is private.
- Preserved the Observation-only safety boundary.

## 0.4.0

- Added first live Home Assistant installation flow and discovery review.
- Added reauthentication and live refresh diagnostics.
- Added best-effort current-watering observation.
- Preserved the Observation-only safety boundary.

All notable changes to IrrigationOS will be documented here.

## [0.3.0] - 2026-08-01

### Added

- Canonical Landscape Digital Twin and per-area landscape profiles.
- Provenance and confidence for landscape values.
- Conservative controller-derived defaults and user override support.
- Home Assistant landscape profile sensors and options-flow foundation.
- ADR-007 for the landscape/controller separation boundary.

## [0.2.0] - 2026-08-01

### Added

- Controller adapter protocol and runtime registry.
- Canonical controller and irrigation-area domain models.
- Rachio translation boundary and generic Home Assistant entities.
- ADR-006 documenting the controller domain model.

## [0.1.1] - 2026-08-01

### Added

- Product vision, master roadmap, and high-level architecture.
- Formal Observation, Simulation, Shadow, and Live operating-mode boundaries.
- Engineering and release standards.
- ADR-001 through ADR-005 covering controller adapters, staged execution, weather providers, soil modeling, and decision transparency.
- Governance-document repository validation and tests.

## [0.1.0] - 2026-08-01

### Added

- Standalone Rachio API-key authentication and account discovery.
- Typed controller and zone observation models.
- Read-only polling coordinator and Home Assistant observation entities.
- Redacted diagnostics and explicit API error handling.
- Expanded tests for API behavior and payload normalization.

## [Unreleased]

### Added

- Added the deterministic v0.9.3 Scheduling Engine.
- Added immutable scheduling windows, policies, requests, actions, and schedules.
- Added permitted-window placement, cycle-and-soak timing, external blocking constraints, and typed unschedulable outcomes.
- Preserved the no-hardware-control boundary and complete Planning provenance.

## [0.0.1] - 2026-08-01

### Added

- HACS-compatible Home Assistant custom integration scaffold
- Direct Rachio API-key config-flow foundation
- Observation-only coordinator and entities
- Repository quality tooling with pytest, Ruff, and MyPy
- GitHub Actions CI and repository metadata validation
- Architecture specification and contribution/security guidance
