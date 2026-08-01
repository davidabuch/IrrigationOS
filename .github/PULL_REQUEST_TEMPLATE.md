## Summary

Describe the change and its purpose.

## Safety

- [ ] Observation-only behavior remains the default.
- [ ] No credentials or exact property information are included.
- [ ] Any future command path has explicit attribution and safety checks.

## Validation

- [ ] `python -m pytest -q`
- [ ] `python -m ruff check .`
- [ ] `python -m mypy custom_components tests`
- [ ] `python scripts/validate_repository.py`
- [ ] `git diff --check`
