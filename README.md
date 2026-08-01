# IrrigationOS

IrrigationOS is an intelligent, explainable irrigation operating system for Home Assistant. It is being designed to connect directly to irrigation controllers, beginning with Rachio, and eventually calculate zone-specific watering demand from weather, soil, slope, plants, and observed system behavior.

## Current status

**Foundation RC1 / pre-release development**

The current code is observation-only. It contains the Home Assistant custom-integration scaffold, direct Rachio API authentication foundation, repository tooling, and safety architecture. It does not autonomously start irrigation.

## Installation during development

Development packages are copied into a cloned GitHub repository and validated locally. HACS installation will be commissioned after the standalone Rachio foundation is validated.

See:

- [`FOUNDATION_RC1_RELEASE_NOTES.md`](FOUNDATION_RC1_RELEASE_NOTES.md)
- [`docs/IRRIGATIONOS_ARCHITECTURE_V1.md`](docs/IRRIGATIONOS_ARCHITECTURE_V1.md)
- [`INSTALL_FROM_ZIP.md`](INSTALL_FROM_ZIP.md)

## Local validation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python -m mypy custom_components tests
python scripts/validate_repository.py
git diff --check
```

## Safety

Observation mode is the default and live autonomous irrigation is outside the current release boundary. Credentials and exact property information must never be committed or included in public diagnostics.
