# IrrigationOS

IrrigationOS is an intelligent, explainable irrigation operating system for Home Assistant. It connects directly to irrigation controllers, beginning with Rachio, and is being designed to calculate zone-specific watering demand from weather, soil, slope, plants, and observed system behavior.

## Current release

**v1.0.48 — Recorder Payload Hotfix**

The current release:

- accepts and validates a Rachio API key through the Home Assistant UI;
- discovers the Rachio Person ID, controllers, and zones automatically;
- receives authenticated Rachio status events through a unique Home Assistant webhook;
- uses an active Home Assistant Cloud cloudhook when available, but does not require a subscription;
- otherwise uses Home Assistant's standard externally reachable HTTPS webhook URL;
- preserves five-minute polling as reconciliation and no-external-URL fallback;
- creates controller and zone observation entities;
- assigns persisted provider-neutral controller identities and permanent numbered slots;
- exposes timestamps, freshness, source quality, and safe partial-failure metadata;
- normalizes the single available Home Assistant weather entity into canonical units;
- ingests that Home Assistant weather entity's hourly forecast as the preferred forecast authority;
- ingests estimated recent Open-Meteo historical precipitation and FAO-56 ET0 with bounded caching and fail-closed freshness;
- keeps the aggregate quantitative-water-balance entity Recorder-safe while preserving detailed per-zone evidence;
- resolves landscape plant identities against the curated Plant Knowledge library;
- executes the synchronized Water Requirement, Plant Stress, Plant Health, Recommendations, Planning, Scheduling, simulation-only Execution, and Runtime Monitoring pipeline;
- reconstructs canonical watering sessions across polling, realtime refreshes, controller gaps, and Home Assistant restarts;
- retains shadow evaluations and actual-vs-shadow reconciliation evidence for commissioning review;
- exposes commissioning, replay/readiness, execution-authorization, controller-ownership, Live-mode-safety, and integrated-safety-review evidence in Home Assistant;
- implements all six pre-Live safeguards: command attribution/receipts, acknowledgement/timeouts, restart-safe reconciliation, safety preemption, sunrise hard stop, and manual override preservation;
- validates those safeguards together through the integrated Live safety review;
- retains the manual commissioning protocol and structured acceptance record for supervised first-live validation;
- adds one explicit Home Assistant supervised operational command service after a successful first-live acceptance;
- limits each supervised operational command to an exact canonical target with its own durable first-live PASS and to at most 120 seconds;
- requires the exact typed confirmation phrase, healthy fresh confirmed observations, current integrated supervised-safety prerequisites, commissioned ownership and boundary review, an idle target, and zero active watering;
- requires the requested target to remain present in the durable validated-target registry before operational dispatch is eligible;
- requires a durable privacy-safe dispatch-intent audit record before any operational command is sent;
- never retries a failed or ambiguous operational transport request automatically;
- observes each accepted supervised operation through canonical refreshes and records privacy-safe terminal audit and structured JSONL acceptance evidence;
- exposes the latest supervised operational `pass`, `fail`, or `indeterminate` acceptance as a persistent Home Assistant sensor;
- exposes coordinator-owned, restart-fail-closed supervised operation progress as a privacy-safe binary sensor;
- durably registers each canonical controller/area target only after its own successful first-live acceptance;
- allows multiple independently validated targets to remain eligible and exposes their privacy-safe registry in Home Assistant;
- evaluates current production readiness from only configured, enabled, bound targets and the existing fail-closed safety evidence;
- exposes advisory supervised-production readiness while requiring a separate explicit prerequisite for any future unattended canary;
- allows one explicitly approved, ten-minute, single-use unattended canary approval for one validated production target and exact 15–60 second runtime;
- consumes approval before one non-retrying transport attempt and observes the bounded canary to structured terminal acceptance;
- restores only completed canary acceptance after restart, never approval, progress, monitoring, or execution;
- selects configured, enabled, bound production targets through one shared canonical selector used by readiness and recommendations;
- exposes one immutable, transient, privacy-safe recommendation per production target with scientific need kept separate from delivery readiness;
- records recommendation snapshots in schema-2 shadow history while treating persisted history as audit evidence only;
- deduplicates shadow history by scientific meaning rather than derived evaluation times and bounds commissioning memory use;
- separates actual ET/precipitation/irrigation accounting from provisional forecast cover and preserves forecast deferrals as immutable, non-authorizing ledger evidence;
- preserves source weather timestamps so a new pipeline evaluation cannot make unchanged weather appear fresh;
- keeps scheduler/coordinator-loop actuation, general Live mode, autonomous scheduling, and `live_control_authorized` hard-coded `false`.

See [`docs/V1_0_47_WEATHER_EVIDENCE_INGESTION.md`](docs/V1_0_47_WEATHER_EVIDENCE_INGESTION.md), [`docs/V1_0_45_QUANTITATIVE_WATER_BALANCE.md`](docs/V1_0_45_QUANTITATIVE_WATER_BALANCE.md), [`docs/V1_0_44_CANONICAL_PRODUCTION_RECOMMENDATION_CONTRACT.md`](docs/V1_0_44_CANONICAL_PRODUCTION_RECOMMENDATION_CONTRACT.md), [`docs/ROADMAP.md`](docs/ROADMAP.md), and [`PRODUCT_PRINCIPLES.md`](PRODUCT_PRINCIPLES.md) for the current release boundary and product rules.

Realtime delivery requires a public HTTPS Home Assistant URL that Rachio can reach. Home Assistant Cloud is optional. If no suitable URL is configured, IrrigationOS reports a repair warning and continues observing through polling.

## API key

In the Rachio mobile app, open **Profile**, select **API Key**, and tap **Copy**. Paste the token into the IrrigationOS Config Flow when adding the integration in Home Assistant.

## Development installation

The repository is currently private, so HACS publication and validation are deferred. During initial commissioning, install from a reviewed ZIP or copy the integration directory manually after local validation. The HACS metadata and local brand asset remain in place for future public distribution.

Key documents:

- [`docs/IRRIGATIONOS_ARCHITECTURE_V1.md`](docs/IRRIGATIONOS_ARCHITECTURE_V1.md)
- [`docs/V1_0_45_QUANTITATIVE_WATER_BALANCE.md`](docs/V1_0_45_QUANTITATIVE_WATER_BALANCE.md)
- [`docs/V1_0_44_CANONICAL_PRODUCTION_RECOMMENDATION_CONTRACT.md`](docs/V1_0_44_CANONICAL_PRODUCTION_RECOMMENDATION_CONTRACT.md)
- [`docs/V1_0_43_FIRST_BOUNDED_UNATTENDED_CANARY.md`](docs/V1_0_43_FIRST_BOUNDED_UNATTENDED_CANARY.md)
- [`docs/V1_0_42_PRODUCTION_READINESS_GATE.md`](docs/V1_0_42_PRODUCTION_READINESS_GATE.md)
- [`docs/V1_0_41_MULTI_ZONE_COMMISSIONING.md`](docs/V1_0_41_MULTI_ZONE_COMMISSIONING.md)
- [`docs/V1_0_40_SUPERVISED_OPERATIONAL_STATE_VISIBILITY.md`](docs/V1_0_40_SUPERVISED_OPERATIONAL_STATE_VISIBILITY.md)
- [`docs/V1_0_39_BOUNDED_SUPERVISED_OPERATIONAL_COMMAND_PATH.md`](docs/V1_0_39_BOUNDED_SUPERVISED_OPERATIONAL_COMMAND_PATH.md)
- [`docs/V1_0_32_LIVE_COMMISSIONING_PROTOCOL.md`](docs/V1_0_32_LIVE_COMMISSIONING_PROTOCOL.md)
- [`docs/V1_0_31_INTEGRATED_LIVE_SAFETY_REVIEW.md`](docs/V1_0_31_INTEGRATED_LIVE_SAFETY_REVIEW.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`INSTALL_FROM_ZIP.md`](INSTALL_FROM_ZIP.md)
- [`SECURITY.md`](SECURITY.md)

## Local validation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/validate_repository.py
python -m pytest -q
python -m ruff check .
python -m mypy custom_components tests
git diff --check
```

Home Assistant runtime and migration smoke tests use an isolated dependency set:

```bash
python -m pip install -r requirements-ha-test.txt
python -m pytest -q --asyncio-mode=auto tests_ha
```

## Safety

Observation remains the default commissioned operating mode in v1.0.48. Water balances and production recommendations are advisory snapshots and never authorize execution. Supervised first-live, bounded manual `irrigationos.run_supervised_operation`, and the exact single-use canary boundary remain unchanged.

Before dispatch, v1.0.41 retains the v1.0.40 requirement for aggregate health `HEALTHY`, a fresh confirmed canonical observation, current integrated supervised-safety prerequisites, commissioned controller ownership, acknowledged execution-boundary review, zero active watering, an online Rachio controller, an idle configured target, and durable privacy-safe audit intent. A second IrrigationOS-supervised operation cannot overlap an operation that is still awaiting terminal observation. Transport failures are never retried automatically. Accepted starts are observed asynchronously for `WATERING` then `IDLE`, written to separate supervised-operation audit and structured acceptance JSONL files, and exposed through restart-safe latest-result state.

No irrigation command button is registered, no scheduler or coordinator loop dispatches operational commands, no target without its own durable first-live PASS is eligible, and general Live mode, autonomous scheduling, and `live_control_authorized` remain disabled.

Credentials, webhook URLs and identifiers, signatures, vendor bindings, serial numbers, MAC addresses, and exact property coordinates are redacted from diagnostics and must never be committed.

## Landscape Digital Twin

IrrigationOS separates controller facts from landscape facts. Each irrigation area has a canonical profile for plants, soil, sun exposure, slope, root depth, irrigation method, application rate, and efficiency. Every value records its source and confidence.

## v1.0.35 supervised first-live operator interface

The Home Assistant options flow can perform an explicitly confirmed supervised first-live watering trial for each configured target. A PASS durably validates only that exact canonical target; the bounded operational service rejects all unvalidated targets. The production-readiness gate evaluates current evidence but cannot execute irrigation, and autonomous scheduling remains disabled.

### Weather evidence ingestion

IrrigationOS 1.0.47 uses the single available Home Assistant weather entity as the preferred hourly forecast source and Open-Meteo as a read-only source for recent hourly precipitation and FAO-56 reference evapotranspiration (ET0). Open-Meteo requests use Home Assistant's configured coordinates at runtime; coordinates are not persisted in IrrigationOS weather evidence or diagnostics. Missing source fields are not fabricated, and weather ingestion never grants execution authority.
