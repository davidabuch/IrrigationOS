# IrrigationOS Foundation RC1 — Corrected replacement

This replacement corrects the earlier incomplete repository packages.

## Corrected failures

- Includes `.github/workflows/ci.yml` in the actual ZIP.
- Includes GitHub issue, pull-request, and Dependabot configuration.
- Removes `.venv`, Python caches, Finder metadata, and `__MACOSX` files.
- Preserves the existing `.git` repository history and GitHub remote.
- Uses one non-duplicated `.gitignore`.
- Keeps Observation mode as the only active operating mode.
- Adds repository tests that verify the workflow and required metadata exist.

## Current boundary

This remains a foundation release. It validates a Rachio API key and reads account/controller data, but it does not start, stop, schedule, or otherwise control irrigation.
