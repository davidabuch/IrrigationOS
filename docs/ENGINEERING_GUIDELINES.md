# IrrigationOS Engineering Guidelines

## Quality gates

Every delivered milestone must pass:

```bash
python scripts/validate_repository.py
python -m pytest -q
python -m ruff check .
python -m mypy custom_components tests
git diff --check
```

GitHub Actions must also be green before a milestone is complete.

## Python standards

- Use Python 3.13-compatible typed code.
- Keep strict MyPy enabled for project-owned modules.
- Prefer immutable dataclasses or frozen domain models.
- Avoid untyped dictionaries beyond vendor/API parsing boundaries.
- Normalize vendor payloads once, at the adapter boundary.
- Use UTC-aware timestamps internally and preserve local context for user-facing schedules.
- Never block the Home Assistant event loop.

## Architecture standards

- Domain logic must not call Rachio or Home Assistant services directly.
- Vendor-specific behavior belongs in adapters.
- Entity IDs are presentation bindings, not domain identities.
- Decision outputs are plans, not side effects.
- Every execution path requires attribution, safety review, and a delivery receipt.
- Restart recovery must observe and reconcile before acting.

## Testing standards

- Every defect fix receives a regression test.
- Tests must be deterministic and independent of live internet services.
- Vendor responses are represented by minimal sanitized fixtures.
- Safety-boundary tests prove forbidden control paths are absent or gated.
- Golden scenarios are added for supervisory behavior once decision engines exist.
- Time-dependent tests use injected clocks rather than wall-clock sleeps.

## Documentation standards

- Update `CHANGELOG.md` for user-visible changes.
- Add release notes for every tagged version.
- Update `ROADMAP.md` when scope or status changes.
- Create or supersede an ADR for material architecture decisions.
- Preserve terminology across code, entities, diagnostics, and docs.

## Secrets and privacy

- Never commit API keys, addresses, precise coordinates, account payloads, or live diagnostics.
- Redact tokens in exceptions and diagnostics.
- Test fixtures must use synthetic identifiers.
- Flight Recorder events must not contain credentials.

## Delivery workflow

1. Start from a clean tagged or committed baseline.
2. Build one cohesive milestone.
3. Perform technical review.
4. Perform omission, safety, and maintainability review.
5. Run all local quality gates.
6. Inspect the final ZIP contents after packaging.
7. User installs the complete package using Finder.
8. User runs the exact validation block.
9. Commit and push only after green local validation.
10. Confirm GitHub Actions before tagging.

## Repository hygiene

Generated files must remain excluded:

- `.venv`
- `__pycache__`
- `*.pyc`
- `.pytest_cache`
- `.mypy_cache`
- `.ruff_cache`
- `.DS_Store`
- `__MACOSX`
