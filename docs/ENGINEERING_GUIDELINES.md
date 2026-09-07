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

Home Assistant integration milestones must also pass:

```bash
python -m pytest -q --asyncio-mode=auto tests_ha
```

GitHub Actions, Hassfest, and HACS validation must be green before a release candidate is complete.

## Python standards

- Use Python 3.14-compatible typed code.
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

1. Start from a clean committed `main` baseline.
2. Create a short-lived feature branch.
3. Build one cohesive milestone.
4. Perform technical review.
5. Perform omission, safety, and maintainability review.
6. Run all local quality gates, including Home Assistant smoke tests when applicable.
7. Inspect the final diff.
8. Commit and push only after green local validation.
9. Open a pull request and require CI, Hassfest, and HACS validation to pass.
10. Merge only after the pull request is reviewed and green.
11. For an approved installable release, verify synchronized version metadata, create the matching immutable tag, and publish the GitHub Release.
12. Install or update through HACS, run `ha core check`, then restart only after configuration validation succeeds.
13. Perform focused post-restart validation and inspect relevant logs.

A deterministic ZIP built from an exact approved commit may be retained for forensic comparison,
rollback, or exceptional manual recovery, but HACS is the normal production distribution path once
release publication is active. See `docs/HACS_RELEASE_WORKFLOW.md`.

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
