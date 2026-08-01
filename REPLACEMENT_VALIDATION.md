# Replacement validation report

## Failures found in the uploaded folder

1. `.github/workflows/ci.yml` was absent, so GitHub displayed only starter templates and the repository structure test failed.
2. The prior ZIP workflow omitted hidden `.github` content during packaging/copying.
3. The uploaded archive included `.venv`, test/type/lint caches, Python bytecode, `.DS_Store`, `__MACOSX`, and AppleDouble metadata.
4. `.gitignore` contained duplicate blocks.
5. The repository was in a partially applied RC1 state with uncommitted files but no CI workflow.
6. Prior installation instructions required copying hidden files manually, which was error-prone.

## Corrections in this replacement

- Added a complete `.github` directory with CI, Dependabot, issue template, and pull-request template.
- Preserved the existing `.git` directory, branch history, and GitHub remote so the entire local folder can be replaced safely.
- Removed the virtual environment and all generated/cache/macOS metadata from the deliverable.
- Replaced `.gitignore` with one clean canonical version.
- Changed installation to a whole-folder replacement workflow; no hidden-file merging is required.
- Added VS Code defaults and retained repository validation tests.
- Kept the integration observation-only; no irrigation command path is present.

## Validation performed before packaging

- Repository metadata validator: passed.
- Pytest repository suite: 8 passed.
- Python bytecode compilation: passed.
- Git whitespace validation: passed.
- JSON files parsed successfully.
- GitHub Actions workflow parsed as YAML.
- Archive content inspected after creation to confirm `.github/workflows/ci.yml` and `.git` are present.
- Archive inspected to confirm `.venv`, caches, bytecode, `.DS_Store`, `__MACOSX`, and AppleDouble files are absent.

Ruff and MyPy had already passed against the same Python source in the user's local environment before this replacement. The replacement changes repository infrastructure and documentation only; it does not alter that checked Python source.
