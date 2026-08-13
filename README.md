# IrrigationOS

IrrigationOS is an intelligent, explainable irrigation operating system for Home Assistant. It connects directly to irrigation controllers, beginning with Rachio, and is being designed to calculate zone-specific watering demand from weather, soil, slope, plants, and observed system behavior.

## Current release

**v1.0.37 — Supervised Live Trial Completion & Acceptance Evidence**

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
- resolves landscape plant identities against the curated Plant Knowledge library;
- executes the synchronized Water Requirement, Plant Stress, Plant Health, Recommendations, Planning, Scheduling, simulation-only Execution, and Runtime Monitoring pipeline;
- reconstructs canonical watering sessions across polling, realtime refreshes, controller gaps, and Home Assistant restarts;
- retains shadow evaluations and actual-vs-shadow reconciliation evidence for commissioning review;
- exposes commissioning, replay/readiness, execution-authorization, controller-ownership, Live-mode-safety, and integrated-safety-review evidence in Home Assistant;
- implements all six pre-Live safeguards: command attribution/receipts, acknowledgement/timeouts, restart-safe reconciliation, safety preemption, sunrise hard stop, and manual override preservation;
- validates those safeguards together through the integrated Live safety review;
- retains the manual commissioning protocol that gates one supervised first-live trial;
- limits each supervised first-live trial to one controller slot, one area slot, and at most 120 seconds;
- requires ephemeral single-use operator approval, a supervised daytime window, healthy fresh observations, and zero external watering;
- may reach `first_live_trial_eligible` only while every commissioning gate remains satisfied;
- keeps `live_mode_commissionable`, `live_control_feature_enabled`, and `live_control_authorized` hard-coded `false`;
- enables the narrowly scoped first-live transport only behind a one-shot commissioned executor that revalidates the canonical controller and zone from a fresh Rachio snapshot, requires a durable canonical audit intent before dispatch, consumes approval before dispatch, never retries automatically, and remains unreachable from Home Assistant services, buttons, schedulers, and coordinator callbacks. After an accepted start, a background acceptance monitor uses canonical refreshes to observe the selected area enter WATERING and return to IDLE, writing privacy-safe terminal acceptance evidence without adding autonomous control authority.

See [`docs/V1_0_37_SUPERVISED_LIVE_TRIAL_COMPLETION_ACCEPTANCE.md`](docs/V1_0_37_SUPERVISED_LIVE_TRIAL_COMPLETION_ACCEPTANCE.md), [`docs/V1_0_36_FIRST_SUPERVISED_LIVE_TRIAL_ACCEPTANCE.md`](docs/V1_0_36_FIRST_SUPERVISED_LIVE_TRIAL_ACCEPTANCE.md), [`docs/V1_0_35_SUPERVISED_FIRST_LIVE_OPERATOR_INTERFACE.md`](docs/V1_0_35_SUPERVISED_FIRST_LIVE_OPERATOR_INTERFACE.md), [`docs/V1_0_34_COMMISSIONED_FIRST_LIVE_WATERING_TRIAL_EXECUTOR.md`](docs/V1_0_34_COMMISSIONED_FIRST_LIVE_WATERING_TRIAL_EXECUTOR.md), [`docs/V1_0_33_FIRST_LIVE_COMMAND_DELIVERY_FOUNDATION.md`](docs/V1_0_33_FIRST_LIVE_COMMAND_DELIVERY_FOUNDATION.md), [`docs/V1_0_32_LIVE_COMMISSIONING_PROTOCOL.md`](docs/V1_0_32_LIVE_COMMISSIONING_PROTOCOL.md), [`docs/ROADMAP.md`](docs/ROADMAP.md), and [`PRODUCT_PRINCIPLES.md`](PRODUCT_PRINCIPLES.md) for the current release boundary and product rules.

Realtime delivery requires a public HTTPS Home Assistant URL that Rachio can reach. Home Assistant Cloud is optional. If no suitable URL is configured, IrrigationOS reports a repair warning and continues observing through polling.

## API key

In the Rachio mobile app, open **Profile**, select **API Key**, and tap **Copy**. Paste the token into the IrrigationOS Config Flow when adding the integration in Home Assistant.

## Development installation

The repository is currently private, so HACS publication and validation are deferred. During initial commissioning, install from a reviewed ZIP or copy the integration directory manually after local validation. The HACS metadata and local brand asset remain in place for future public distribution.

Key documents:

- [`docs/IRRIGATIONOS_ARCHITECTURE_V1.md`](docs/IRRIGATIONOS_ARCHITECTURE_V1.md)
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

Observation remains the default commissioned operating mode in v1.0.37. A deliberately narrow Home Assistant options-flow action can invoke one supervised first-live watering trial after explicit target selection, a bounded 1–120 second runtime, and an exact typed confirmation phrase. The v1.0.34 fresh commissioning preflight, durable audit intent, single-use approval consumption, confirmed-idle target checks, and no-retry handling remain authoritative. No irrigation command service or button is registered, no scheduler or coordinator loop dispatches commands, and general Live mode, autonomous scheduling, and `live_control_authorized` remain disabled.

Credentials, webhook URLs and identifiers, signatures, vendor bindings, serial numbers, MAC addresses, and exact property coordinates are redacted from diagnostics and must never be committed.

## Landscape Digital Twin

IrrigationOS separates controller facts from landscape facts. Each irrigation area has a canonical profile for plants, soil, sun exposure, slope, root depth, irrigation method, application rate, and efficiency. Every value records its source and confidence.

## v1.0.35 supervised first-live operator interface

The Home Assistant options flow can now perform one explicitly confirmed supervised first-live watering trial. No irrigation command service or button is registered, and autonomous scheduling remains disabled.
