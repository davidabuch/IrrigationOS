# v1.0.15 Stable Release Candidate

## Purpose

This milestone resolves the final v1.0 public-versioning issue, synchronizes active release metadata, adds stable release notes, and establishes final validation gates for the first stable public IrrigationOS release candidate.

## Version decision

The final stable candidate is **1.0.15**.

Internal implementation milestones already used observable versions 1.0.1 through 1.0.14. Publishing a later 1.0.0 would therefore be a semantic-version downgrade for update-aware tooling. Version 1.0.15 preserves monotonic ordering without inventing a second version namespace.

## Metadata synchronization

The following active version sources must agree at 1.0.15:

- `pyproject.toml`
- `custom_components/irrigationos/manifest.json`
- `custom_components/irrigationos/const.py`
- repository validation
- repository tests
- README, roadmap, changelog, and release documentation

Repository validation now checks the Python project version against the Home Assistant manifest version so this class of drift cannot silently recur.

## Compatibility

The machine-readable v1.0 public API contract remains frozen at the v1.0.13 compatibility milestone. That freeze point is historical metadata and is not rewritten to 1.0.15.

## Safety boundary

No controller, Rachio, Home Assistant service, valve, switch, retry, recovery, or autonomous command path is added by this milestone.

Observation remains the only commissioned operating mode. Simulation remains non-actuating. Live and Shadow commissioning remain future separately reviewed work.

## Release gate

The v1.0.15 tag/release may be created only after:

1. local standard tests pass;
2. Home Assistant smoke/lifecycle tests pass;
3. Ruff and MyPy pass;
4. repository validation and `git diff --check` pass;
5. the feature branch is merged to `main`;
6. GitHub Actions are green on the merged commit;
7. public distribution is explicitly approved.
