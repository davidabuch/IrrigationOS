# IrrigationOS

IrrigationOS is an intelligent, explainable irrigation operating system for Home Assistant. It connects directly to irrigation controllers, beginning with Rachio, and is being designed to calculate zone-specific watering demand from weather, soil, slope, plants, and observed system behavior.

## Current release

**v0.4.1 — Canonical Controller Model and Observation Reliability**

The current release:

- accepts and validates a Rachio API key through the Home Assistant UI;
- discovers the Rachio Person ID, controllers, and zones automatically;
- polls Rachio every five minutes in read-only Observation mode;
- creates controller and zone observation entities;
- assigns persisted provider-neutral controller identities and permanent numbered slots;
- exposes timestamps, freshness, source quality, and safe partial-failure metadata;
- distinguishes confirmed idle from unavailable watering status;
- exports redacted diagnostics;
- does not start, stop, enable, disable, or reschedule irrigation.

See [`V0_4_1_RELEASE_NOTES.md`](V0_4_1_RELEASE_NOTES.md) and [`PRODUCT_PRINCIPLES.md`](PRODUCT_PRINCIPLES.md) for the current release boundary and product rules.

## API key

In the Rachio mobile app, open **Profile**, select **API Key**, and tap **Copy**. Paste the token into the IrrigationOS Config Flow when adding the integration in Home Assistant.

## Development installation

This repository is HACS-compatible. During initial commissioning, repository packages are validated locally before installation into Home Assistant.

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

Observation mode is the default and only implemented operating mode in v0.4.1. Credentials, vendor bindings, serial numbers, MAC addresses, and exact property coordinates are redacted from diagnostics and must never be committed.

## Landscape Digital Twin

IrrigationOS separates controller facts from landscape facts. Each irrigation area has a canonical profile for plants, soil, sun exposure, slope, root depth, irrigation method, application rate, and efficiency. Every value records its source and confidence.
