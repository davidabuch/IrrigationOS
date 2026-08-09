# IrrigationOS Release Strategy

## Versioning

IrrigationOS uses semantic versioning. The `v1.0.x` integration milestones are release-candidate implementation checkpoints leading to the final stable `v1.0.0` release designation defined by this project. Each milestone must remain backward-compatible with the frozen v1.0 public contract unless a documented migration is provided.

After the stable v1.0.0 release:

- Patch: backward-compatible fixes and maintenance.
- Minor: backward-compatible capabilities.
- Major: intentionally breaking public contracts with migration guidance.

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

## Current v1.0 release-candidate line

The domain pipeline is complete through Runtime Monitoring and is integrated into Home Assistant in an Observation-and-simulation-only boundary. Stable pipeline entities/diagnostics, lifecycle tests, and the public API compatibility freeze are complete through v1.0.14.

Remaining before the first stable public release:

1. Resolve the final public semantic version. Internal milestones already use `1.0.13` and `1.0.14`, so publishing `1.0.0` afterward would be a version downgrade for SemVer-aware tooling. The roadmap shorthand “v1.0.0” must therefore be reconciled before tagging or distribution.
2. Reconcile all release metadata, including the historical `pyproject.toml` project version, manifest/constant versions, release notes, and tag/release naming.
3. Run final release-candidate validation against the frozen API and Home Assistant lifecycle contracts.
4. Deploy/distribute with live execution disabled by default.

Live command delivery, Shadow commissioning, ownership/command attribution, and autonomous recovery remain post-release commissioning work unless explicitly promoted into a separately reviewed milestone.
