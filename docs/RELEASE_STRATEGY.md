# IrrigationOS Release Strategy

## Versioning

IrrigationOS uses semantic versioning. The internal v1.0.x implementation milestones are part of the repository's observable version history, so the first stable public release is **v1.0.15** rather than a numerically lower v1.0.0 tag. This preserves monotonic SemVer for Home Assistant, HACS, packaging, and other update-aware tooling.

The v1.0 public compatibility contract was frozen at v1.0.13 and remains binding for v1.0.15 and backward-compatible v1.0.x maintenance releases. Future backward-compatible maintenance releases increment the patch version; backward-compatible capability releases increment the minor version; intentionally breaking public contracts require a major-version change with migration guidance.

## Release sequence

1. Define scope and acceptance criteria.
2. Implement and test.
3. Update documentation, roadmap, changelog, and milestone notes.
4. Validate locally.
5. Commit and push.
6. Confirm GitHub Actions.
7. Merge only after CI is green.
8. Create a tag/release only when the milestone or distribution plan calls for one.
9. Verify HACS installation/update behavior when public distribution begins.

## Repository source of truth

- GitHub `main` is authoritative for merged history, repository files, workflows, tags/releases, and pull requests.
- A local repository ZIP is supplemental and is required only when local/uncommitted state or unavailable binary/filesystem content materially affects the work.
- Milestone implementation may reuse a verified snapshot when GitHub confirms it matches merged `main`.

## Branching

- `main` is the canonical integration branch.
- Milestone work uses short-lived feature branches.
- Release tags, when required, must point to green commits on `main`.

## Definition of Done

A milestone is complete only when:

- acceptance criteria are satisfied;
- standard tests, Ruff, MyPy, repository validation, and `git diff --check` pass;
- Home Assistant runtime/migration/lifecycle smoke tests pass for integration milestones;
- GitHub Actions is green;
- changelog and milestone documentation are complete;
- architecture/governance records are updated when required;
- secrets and generated cache files are absent;
- installation or migration instructions are accurate;
- the final delivered ZIP has been inspected after creation.

## Stable v1.0 line

Version **1.0.15** is the first stable public release and has been tagged and published. The deterministic domain pipeline is complete through Runtime Monitoring and is integrated into Home Assistant within an Observation-and-simulation-only boundary. Stable pipeline entities/diagnostics, lifecycle tests, and the frozen public API contract are complete.

Release metadata is intentionally synchronized across `pyproject.toml`, `custom_components/irrigationos/manifest.json`, `custom_components/irrigationos/const.py`, repository validation, and tests. Subsequent v1.0.x releases use the same green feature-branch, merged-main, and explicit tag/release gates.

Live command delivery, Shadow commissioning, ownership/command attribution, and autonomous recovery are not part of v1.0.15. Observation remains the only commissioned operating mode; Simulation remains non-actuating.

## v1.0.16 health observability

v1.0.16 is a backward-compatible observability milestone adding aggregate health, persistent incident history, safe daily operational logs, and Home Assistant transition events. It does not expand the commissioned operating boundary beyond Observation and non-actuating Simulation.
