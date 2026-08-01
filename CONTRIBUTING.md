# Contributing to IrrigationOS

IrrigationOS is developed in small, testable milestones. Live irrigation control must never be introduced without command attribution, ownership checks, safety gates, and simulation validation.

## Local checks

```bash
python -m pytest -q
python -m ruff check .
python -m mypy custom_components tests
git diff --check
```

## Pull requests

- Keep changes focused.
- Add tests for new behavior.
- Never commit API keys, addresses, exact coordinates, or diagnostic exports containing private data.
- Preserve Observation mode as the default until live control is deliberately commissioned.
