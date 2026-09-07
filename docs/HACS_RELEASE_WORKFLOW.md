# IrrigationOS HACS Release Workflow

IrrigationOS is distributed from the public GitHub repository through GitHub Releases and HACS.
Development, release publication, and Home Assistant deployment remain separate gates.

## Compatibility floor

The minimum supported Home Assistant Core version is **2026.8.0**.

This floor is required by the Home Assistant 2026.8 device-registry API used by IrrigationOS,
including `via_device_id` and `async_get_device_id_by_identifier()`.

## Required validation before merge

Every release candidate must pass:

- repository validation;
- full unit tests;
- Ruff;
- MyPy;
- Home Assistant smoke tests;
- Hassfest;
- HACS validation;
- `git diff --check` during local validation.

A green pull request is necessary but does not itself authorize a release or deployment.

## Release sequence

1. Develop on a feature branch from current `main`.
2. Run focused tests while editing.
3. Run the complete local validation stack.
4. Review the final diff.
5. Push the reviewed branch and open a pull request.
6. Require all GitHub checks to pass.
7. Merge the approved pull request.
8. Verify the exact merged `main` commit and version metadata.
9. Create the matching immutable Git tag and GitHub Release only after explicit release approval.
10. Install or update IrrigationOS through HACS from that published release.
11. Run `ha core check` before restarting Home Assistant.
12. Restart only after successful configuration validation.
13. Perform focused post-restart integration, entity, safety, and log checks.

## Version contract

For an installable release, these values must agree:

- `custom_components/irrigationos/manifest.json` version;
- `custom_components/irrigationos/const.py` `VERSION`;
- `pyproject.toml` project version;
- Git tag;
- GitHub Release tag.

Do not publish a tag or release from a dirty or unreviewed tree.

## ZIP artifacts

A deterministic ZIP built from an exact approved commit remains useful for forensic comparison,
rollback, or exceptional manual recovery. It is not the normal production update path once HACS
release distribution is active.

## Safety boundary

Release mechanics never authorize irrigation execution. Existing fail-closed command,
confirmation, ownership, freshness, and Live-mode safety boundaries remain unchanged.
