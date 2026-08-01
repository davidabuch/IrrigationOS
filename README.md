# IrrigationOS

IrrigationOS is a Home Assistant-native irrigation operating system. It will connect directly to irrigation controllers, beginning with Rachio, and build explainable watering recommendations from weather, soil, plant, and zone data.

## Current milestone

**Milestone 0 — Repository Scaffold**

This milestone establishes:

- a HACS-compatible custom integration layout;
- a Home Assistant Config Flow foundation;
- a direct Rachio API client boundary;
- observation-only safety defaults;
- diagnostics with credential redaction;
- automated linting, type checks, and tests.

No automatic watering is enabled in this milestone.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python -m mypy custom_components tests
```

See [`docs/IRRIGATIONOS_ARCHITECTURE_V1.md`](docs/IRRIGATIONOS_ARCHITECTURE_V1.md) for the canonical architecture.
