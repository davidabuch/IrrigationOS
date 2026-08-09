# IrrigationOS

IrrigationOS is an intelligent, explainable irrigation operating system for Home Assistant. It connects directly to irrigation controllers, beginning with Rachio, and is being designed to calculate zone-specific watering demand from weather, soil, slope, plants, and observed system behavior.

## Current release

**v1.0.16 — Health Monitoring and Incident Diagnostics**

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
- distinguishes confirmed idle from unavailable watering status;
- normalizes the single available Home Assistant weather entity into canonical units;
- resolves landscape plant identities against the curated Plant Knowledge library;
- executes evidence-backed Plant Water Requirement, aggregate Plant Stress, Plant Health, advisory Recommendations, machine-readable Planning, conservative proposed Scheduling, and simulation-only Execution and conservative Runtime Monitoring in the synchronized pipeline;
- exposes stable per-stage and per-zone pipeline output sensors plus redacted pipeline diagnostics;
- freezes the v1.0 domain and pipeline public API contracts with machine-readable compatibility tests;
- synchronizes Python package and Home Assistant integration release metadata at v1.0.16;
- reconciles the architecture, operating-mode, release-strategy, and v1.0 audit documents with the shipped observation/simulation runtime;
- exposes aggregate HEALTHY / DEGRADED / UNHEALTHY operational health;
- persistently latches genuine unhealthy incidents with a non-actuating reset button;
- writes 30 days of safe daily JSONL operational evidence under `/config/irrigationos_logs/`;
- exports redacted diagnostics;
- does not start, stop, enable, disable, or reschedule irrigation.

See [`docs/V1_0_16_HEALTH_MONITORING.md`](docs/V1_0_16_HEALTH_MONITORING.md), [`docs/V1_0_14_ARCHITECTURE_RELEASE_DOCUMENTATION.md`](docs/V1_0_14_ARCHITECTURE_RELEASE_DOCUMENTATION.md), [`docs/V1_0_ARCHITECTURE_AUDIT.md`](docs/V1_0_ARCHITECTURE_AUDIT.md), and [`PRODUCT_PRINCIPLES.md`](PRODUCT_PRINCIPLES.md) for the current release boundary and product rules.

Realtime delivery requires a public HTTPS Home Assistant URL that Rachio can reach. Home Assistant Cloud is optional. If no suitable URL is configured, IrrigationOS reports a repair warning and continues observing through polling.

## API key

In the Rachio mobile app, open **Profile**, select **API Key**, and tap **Copy**. Paste the token into the IrrigationOS Config Flow when adding the integration in Home Assistant.

## Development installation

The repository is currently private, so HACS publication and validation are deferred. During initial commissioning, install from a reviewed ZIP or copy the integration directory manually after local validation. The HACS metadata and local brand asset remain in place for future public distribution.

Key documents:

- [`docs/IRRIGATIONOS_ARCHITECTURE_V1.md`](docs/IRRIGATIONOS_ARCHITECTURE_V1.md)
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

Observation mode remains the default and only commissioned operating mode in v1.0.16; startup, unload/setup, config-entry reload, migration, persistence, and pipeline entity identity are regression-tested while live execution remains disabled. Credentials, webhook URLs and identifiers, signatures, vendor bindings, serial numbers, MAC addresses, and exact property coordinates are redacted from diagnostics and must never be committed.

## Landscape Digital Twin

IrrigationOS separates controller facts from landscape facts. Each irrigation area has a canonical profile for plants, soil, sun exposure, slope, root depth, irrigation method, application rate, and efficiency. Every value records its source and confidence.
