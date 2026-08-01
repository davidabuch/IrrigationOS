# IrrigationOS Release Strategy

## Versioning

IrrigationOS uses semantic versioning during pre-1.0 development:

- Patch: documentation, tests, corrections, or backward-compatible maintenance.
- Minor: a coherent new capability or commissioning milestone.
- Major: reserved for stable 1.0 and later breaking platform changes.

Pre-1.0 releases may still evolve internal APIs, but migrations and user-facing changes must be documented.

## Release sequence

1. Define scope and acceptance criteria.
2. Implement and test.
3. Update documentation, roadmap, changelog, and release notes.
4. Validate locally.
5. Commit and push.
6. Confirm GitHub Actions.
7. Create an annotated Git tag.
8. Publish a GitHub release when distribution begins.
9. Verify HACS installation/update behavior when applicable.

## Branching

- `main` is the canonical integration branch.
- Milestone work may use short-lived branches when useful.
- Tagged releases must point to green commits on `main`.

## Definition of Done

A release is complete only when:

- acceptance criteria are satisfied;
- tests, Ruff, MyPy, repository validation, and `git diff --check` pass;
- GitHub Actions is green;
- release notes and changelog are complete;
- architecture records are updated when required;
- secrets and generated files are absent;
- installation or migration instructions are accurate;
- the final distributed ZIP has been inspected after creation.

## Release artifacts

Development handoff packages contain repository contents but exclude `.git` and `.venv`. GitHub/HACS release archives must preserve hidden metadata such as `.github` and `.gitignore` where applicable.

## Current release line

- `v0.1.0` — Standalone Rachio API foundation
- `v0.1.1` — Project governance and architecture records
- `v0.2.0` — Controller foundation
- `v0.3.0` — Landscape Digital Twin foundation
