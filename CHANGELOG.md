# Changelog

## 1.0.48 — Recorder Payload Hotfix

- Replaced the oversized aggregate quantitative-water-balance attributes with a compact summary contract.
- Preserved detailed per-zone water-balance entities and full shadow/diagnostic evidence.
- Added a regression assertion keeping the aggregate Recorder payload below 8 KiB.
- Changed no weather ingestion, controller transport, lifecycle, scheduling, or execution authority.

## 1.0.47 — Weather Evidence Ingestion

- Added Home Assistant hourly forecast normalization using the source weather entity timestamp as issuance evidence.
- Added bounded Open-Meteo Historical Forecast ingestion for estimated recent precipitation and FAO-56 ET0; model-derived history is explicitly classified as estimated rather than sensor-verified.
- Added a 30-minute Open-Meteo refresh cadence with a two-hour last-known-good ceiling and fail-closed source handling.
- Fed canonical ET0, historical precipitation, and provisional forecast precipitation into quantitative water balance without inventing missing probability or effective precipitation.
- Preserved exact non-overlapping accounting boundaries after persisted forecast-ledger carry-forward.
- Added privacy-safe weather-evidence diagnostics and retained all existing execution-safety boundaries.

## 1.0.46 — Shadow Stability Hotfix

- Fixed semantic shadow deduplication so derived calculation, validity, and sliding accounting-window times do not create duplicate scientific decisions.
- Preserved forecast windows, observed precipitation, water deficits, recommendations, and canonical targets as decision-significant evidence.
- Replaced retained full shadow payloads in commissioning reporting with aggregate counters and avoided rescanning them on every refresh.
- Avoided unchanged shadow metadata Store writes and duplicate section hashing.
- Added privacy-safe shadow-history size, write, retention, and coordinator refresh-duration diagnostics.
- Preserved every physical-operation, no-retry, runtime, confirmation, lifecycle, and authorization boundary unchanged.

## 1.0.45 — Quantitative Water Balance & Forecast Reconciliation

- Added immutable per-production-area actual water-balance contracts with scalar/range preservation.
- Kept forecast precipitation provisional: it may defer urgency but never enters historical water received before observation.
- Added deterministic realized, partially realized, and missed-forecast reconciliation with recoverable deferred deficit.
- Added a fail-closed immutable HA storage ledger for forecast deferral/reconciliation evidence; current balances are always recomputed.
- Exposed aggregate and per-area water-balance sensors only for canonical production targets.
- Fed available balance evidence into the production recommendation contract without runtime, scheduling, or execution authority.
- Preserved missing ET0, historical precipitation, unresolved Trees identity, and uncalibrated watering as explicit blockers.

## 1.0.44 — Canonical Production Recommendation Contract

- Added one immutable, deterministic recommendation contract for each configured, enabled, bound canonical production target.
- Separates scientific need from quantitative delivery readiness and withholds irrigation depth, runtime, and scheduling windows when evidence is incomplete.
- Added transient aggregate and per-zone Home Assistant sensors with `execution_authorized` permanently false.
- Consolidated production-target selection so readiness and recommendation composition use one authoritative rule.
- Fixed weather freshness to retain the source Home Assistant entity timestamp instead of pipeline evaluation time.
- Added schema-2 shadow recommendation history and schema-1-compatible actual-vs-shadow scheduling extraction.
- Added no scheduling authority, physical-operation change, retry, or autonomous irrigation path.

## 1.0.43 — First Bounded Unattended Canary

- Added separate explicit approval and one-shot execution services for one validated production target.
- Approval is exact-target, exact-runtime, ten-minute, single-use, and restart-ephemeral.
- Limits canary runtime to 15–60 seconds and consumes approval before the only transport attempt.
- Requires fresh `ready_for_unattended_canary` evidence and every existing health, ownership, topology, persistence, observation, conflict, and integrated-safety gate.
- Added privacy-safe JSONL audit history, structured terminal acceptance persistence, and Home Assistant visibility.
- Added no scheduling, recurring execution, automatic retries, multi-zone unattended watering, or general autonomous authority.

## 1.0.42 — Production Readiness Gate

- Added a deterministic, recomputed, fail-closed production-readiness engine and coordinator-owned manager.
- Defines production targets only as configured, enabled, bound canonical areas, so unused controller-capacity slots do not block readiness.
- Requires every production target to have its own durable validated-target evidence plus healthy ownership, topology, observations, connectivity, persistence, conflicts, and integrated safety prerequisites.
- Distinguishes supervised-production readiness from a future unattended canary through an explicit additional approval prerequisite.
- Added advisory readiness sensor, compact binary sensor, and privacy-safe diagnostics without persisting stale readiness authority.
- Added no actuation path, autonomous watering, scheduling, retry, target expansion, or official Home Assistant Rachio dependency.

## 1.0.41 — Multi-Zone Commissioning & Validated Target Registry

- Added a durable privacy-safe registry keyed only by canonical controller and area slots.
- Registers a target only after its exact first-live PASS is durably persisted; FAIL and INDETERMINATE outcomes add nothing.
- Backfills the latest persisted v1.0.40 PASS once, without parsing JSONL or recreating revoked evidence.
- Replaced latest-first-live-target comparison with exact validated-registry membership while preserving every other supervised-operation gate.
- Added a validated-target count sensor, redacted diagnostics, deterministic duplicate refresh, restart restoration, and internal durable revocation.
- Added no autonomous watering, scheduling, broader control authority, command retry, or official Home Assistant Rachio dependency.

## 1.0.40 — Supervised Operational State & Acceptance Visibility

- Made transient supervised-operation state coordinator-owned and restart-fail-closed.
- Added Home Assistant storage for the latest completed supervised operational acceptance while retaining append-only audit and acceptance JSONL history.
- Added a structured acceptance sensor and an in-progress binary sensor using only privacy-safe canonical state.
- Added redacted supervised-operation diagnostics and restart restoration for completed `pass`, `fail`, and `indeterminate` evidence.
- Preserved every v1.0.39 safety gate, the 120-second limit, manual-only dispatch, and the prohibition on automatic actuation retries.

## 1.0.39 — Bounded Supervised Operational Command Path

- Added one explicitly invoked Home Assistant service for bounded supervised operational watering after a persisted successful first-live acceptance.
- Restricts every command to the exact previously accepted controller and area slots, a 1–120 second runtime, and an exact typed confirmation phrase.
- Forces a fresh canonical preflight and requires healthy confirmed observations, commissioned ownership, boundary acknowledgement, an idle eligible target, and zero active watering before dispatch.
- Requires durable privacy-safe intent evidence before the single Rachio start request, prevents overlapping IrrigationOS operations, and never retries failed or ambiguous transport requests automatically.
- Observes accepted operations through canonical WATERING-to-IDLE completion and writes separate operational audit and structured acceptance JSONL evidence.
- Keeps command buttons, scheduler/coordinator-loop actuation, general Live mode, autonomous scheduling, and `live_control_authorized` disabled.

## 1.0.38 — Structured Live Trial Acceptance Record

- Added a persistent structured `pass`, `fail`, or `indeterminate` result for the latest supervised first-live trial.
- Records explicit criterion states for durable intent, operator approval, preflight target observation, start acknowledgement, observed watering, bounded requested runtime, return to idle, concurrent watering, and post-run reconciliation.
- Exposes polling-bounded observed runtime, refresh-error count, terminal detail, and criterion counts through a dedicated Home Assistant sensor and redacted diagnostics.
- Restores the latest acceptance record after Home Assistant restart.
- Preserves the one-shot supervised operator boundary with no autonomous scheduling, automatic retries, or general Live authorization.

## 1.0.37 — Supervised Live Trial Completion & Acceptance Evidence

- Added a bounded asynchronous acceptance monitor after an accepted supervised first-live start.
- Reuses canonical controller refreshes to observe the approved area enter `WATERING` and return to `IDLE`.
- Correlates dispatch, physical observation, and terminal acceptance evidence with one privacy-safe attempt ID.
- Records explicit fail-closed terminal evidence when watering or completion cannot be observed within bounded grace periods.
- Adds no automatic command retry, additional actuation path, autonomous scheduling, or general Live authorization.

## 1.0.36 — First Supervised Live Trial Acceptance

- Separated supervised commissioning eligibility from long-horizon autonomous promotion maturity.
- Reduced the autonomous evidence-day threshold from 14 to 10 days.
- Fixed supervised health evaluation to accept Home Assistant's canonical `HEALTHY` state.
- Preserved all fail-closed supervised safety gates, all six live-mode safeguards, integrated validation scenarios, and the 120-second one-shot runtime ceiling.


## 1.0.35 — Supervised First-Live Operator Interface

- Added an interactive Home Assistant options-flow path for one supervised first-live watering trial.
- Requires one currently observed Rachio target, a bounded 1–120 second runtime, and the exact typed confirmation phrase.
- Forces a fresh coordinator refresh before invoking the v1.0.34 one-shot executor and always closes the ephemeral commissioning window afterward.
- Registers no irrigation command service or button and adds no scheduler/coordinator-loop dispatch path.

## 1.0.34 — Commissioned First-Live Watering Trial Executor

- Added a one-shot supervised executor gated by current `first_live_trial_eligible` commissioning evidence.
- Bound trial approval to a canonical controller identity, controller slot, area slot, and runtime.
- Re-resolved native Rachio target identifiers from a fresh observed snapshot immediately before dispatch.
- Required a durable privacy-safe dispatch-intent audit record before actuation, consumed the single-use approval before transport, and prohibited automatic retries after ambiguous outcomes.
- Preserved the 120-second ceiling and kept HA services, buttons, scheduler callbacks, coordinator dispatch, general Live authorization, and autonomous scheduling disabled.


## 1.0.33 — First-Live Command Delivery Foundation

- Added a narrow Rachio physical transport primitive for one bounded zone start and device-wide emergency stop.
- Preserved the 120-second first-live runtime ceiling at the transport boundary.
- Added explicit release-gate evidence with `PHYSICAL_FIRST_LIVE_DELIVERY_ENABLED = False`.
- Added no Home Assistant execution service, button, scheduler callback, or coordinator dispatch path.
- Kept autonomous scheduling and all Live authorization flags disabled.
- Added unit coverage for endpoint allowlisting, payload shape, runtime rejection, transport failures, and privacy-safe diagnostics.

## 1.0.32 — Live Commissioning Protocol & First-Live Acceptance Criteria

- Added a non-actuating manual commissioning protocol after the integrated six-safeguard review.
- Defined one-controller-slot, one-area-slot first-live scope with a strict 120-second runtime ceiling.
- Added ephemeral single-use operator approval with a ten-minute expiry and intentional restart invalidation.
- Required healthy fresh observations, zero external watering, and an explicitly open supervised commissioning window.
- Defined mandatory post-trial acceptance evidence for acknowledgement, observed watering, runtime, safety, and reconciliation.
- Preserved zero controller dispatch capability and all hard-false Live-control authorization flags.

## 1.0.31 — Integrated Live Safety Review & Commissioning Validation

- Added integrated validation across all six pre-Live safeguards.
- Added deterministic review evidence that immediately blocks when safety prerequisites degrade.
- Added operator-facing integrated safety-review diagnostics and sensor evidence.
- Proved that complete safeguards can become review-eligible without automatic commissioning or authorization.
- Preserved disabled controller dispatch and all three hard-false Live-control flags.

## 1.0.30 — Manual Override Preservation

- Added deterministic fail-closed preservation of observed watering not confidently attributed to IrrigationOS.
- Preserves manual watering, provider schedules, and ambiguous external watering instead of allowing a future IrrigationOS command lifecycle to displace them.
- Added immutable 30-day preservation evidence and privacy-safe diagnostics with explicit non-dispatch semantics.
- Marked manual override preservation as the sixth implemented Live-mode safeguard.
- All six safeguards are now represented in code, but Live-mode commissioning, feature enablement, and authorization remain disabled pending integrated review.

## 1.0.29 — Sunrise Hard Stop

- Added deterministic sunrise-boundary evaluation for future synthetic command lifecycles.
- Added immutable 30-day sunrise hard-stop evidence with explicit non-dispatch semantics.
- Added fail-closed synthetic acknowledgement preemption at or after the configured sunrise boundary.
- Marked sunrise hard stop as the fifth implemented Live-mode safeguard.
- Preserved disabled controller dispatch and Live-mode authorization; manual override preservation remains unimplemented.

## 1.0.28 — Safety Preemption Path

- Added deterministic fail-closed safety preemption evaluation for future command lifecycles.
- Added a terminal synthetic acknowledgement `preempted` state and immutable 30-day preemption evidence.
- Added privacy-safe preemption diagnostics while preserving zero controller dispatch capability.
- Marked safety preemption as the fourth implemented Live-mode safeguard.
- Preserved disabled Live-mode commissioning and authorization; sunrise hard stop remains unimplemented.

## 1.0.27 — Restart-Safe Command Reconciliation

- Replays immutable acknowledgement evidence during Home Assistant startup.
- Restores only unexpired waiting acknowledgement windows.
- Converts expired waiting windows into persisted timeout evidence.
- Fails closed when persisted acknowledgement evidence is malformed.
- Marks restart-safe command reconciliation as the third implemented Live-mode safeguard.
- Keeps controller dispatch and Live-mode authorization disabled.

## 1.0.26 — Command Acknowledgement and Timeout Foundation

- Added a deterministic synthetic acknowledgement lifecycle with waiting, acknowledged, rejected, and timed-out states.
- Added a provisional 30-second acknowledgement deadline with fail-closed late-arrival handling.
- Added immutable 30-day acknowledgement transition evidence and privacy-safe diagnostics.
- Marked acknowledgement-and-timeout handling as the second implemented Live-mode safeguard.
- Preserved disabled command delivery; restart-safe command reconciliation remains unimplemented.

## 1.0.25 — Command Attribution and Receipt Foundation

- Added canonical non-actuating command intent records with attribution and stable correlation IDs.
- Added immutable local receipts that explicitly record every v1.0.25 intent as not dispatched.
- Added 30-day local command-intent/receipt audit evidence and diagnostics.
- Marked only the command-attribution-and-receipts Live-mode safeguard as implemented.
- Preserved the disabled command-delivery and Live-mode boundaries.

## 1.0.24 — Live-Mode Safety Architecture

- Added a separate fail-closed Live-mode safety architecture and explicit execution safeguard gates.
- Required command attribution/receipts, acknowledgement/timeouts, restart reconciliation, safety preemption, sunrise hard stop, and manual-override preservation before Live-mode review.
- Preserved non-actuating operation and hard-coded Live control disabled.

## 1.0.23 — Controller Ownership Commissioning

- Added explicit persisted controller ownership commissioning bound to canonical controller topology.
- Added topology-change invalidation and manual execution-boundary review acknowledgement.
- Added operator confirm/revoke controls while preserving Live control disabled.

## 1.0.22 — Safety Manager and Execution Authorization Foundation

- Added deterministic fail-closed execution authorization safety gates.
- Added health, freshness, controller availability, ownership, active-watering, pipeline, and runtime-limit prerequisites.
- Added restart-safe semantics that never persist positive authorization.
- Added an operator-facing Home Assistant execution-authorization sensor and diagnostics.
- Preserved observation/simulation-only operation; live control remains hard-coded disabled.

## 1.0.21 — Replay and Control-Readiness Evidence

- Added deterministic replay of retained actual-vs-shadow reconciliation evidence.
- Added fixed golden comparison scenarios and aggregate replay coverage/match metrics.
- Added explicit conservative readiness criteria with manual-review semantics.
- Added Home Assistant control-readiness evidence sensor and diagnostics.
- Preserved observation-only operation; live control authorization remains hard-coded false.

## 1.0.20 — Shadow Reporting and Commissioning Summary

- Added operator-facing aggregate reporting over retained shadow and reconciliation evidence.
- Added agreement, disagreement, skipped/unexpected watering, confidence, timing, and runtime metrics.
- Added a Home Assistant commissioning-summary sensor and privacy-safe diagnostics.
- Added explicit evidence states without treating evidence availability as approval for live control.
- Preserved the observation-only, non-actuating commissioning boundary.

## 1.0.19 — Actual-vs-Shadow Reconciliation

- Added immutable planned-vs-observed reconciliation evidence.
- Added canonical zone, runtime, and timing comparison with conservative confidence.
- Added skipped/unexpected watering classification with insufficient-evidence safeguards.
- Added restart-safe pending-action and idempotency persistence with 30-day JSONL evidence.
- Preserved the observation-only, non-actuating commissioning boundary.

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

## [1.0.49] - 2026-08-19

### Added

- Added Landscape Intelligence Profile v1 with a human-reviewed Zone 1 commissioning seed.
- Added immutable structured longitudinal plant-health observations and deterministic health trends.
- Added durable integration storage and diagnostics while keeping Recorder-facing summaries compact.
- Preserved unresolved landscape factors and all existing execution/live-control safety boundaries.

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
