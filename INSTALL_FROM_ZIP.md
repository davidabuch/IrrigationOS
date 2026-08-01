# Complete-folder replacement installation

This release ZIP contains the complete `IrrigationOS` repository folder, including its hidden `.git` history and `.github` workflow files. It intentionally does not contain a virtual environment or generated cache files.

## Replace the current local folder

1. Close VS Code windows that have the existing IrrigationOS folder open.
2. In Finder, go to `~/Documents/GitHub`.
3. Rename the existing folder from `IrrigationOS` to `IrrigationOS_old` as a temporary backup.
4. Extract the replacement ZIP.
5. Move the extracted `IrrigationOS` folder into `~/Documents/GitHub`.
6. Open the new `IrrigationOS` folder in VS Code.
7. Do not copy files between the old and new folders.

## Recreate the local development environment

```bash
cd ~/Documents/GitHub/IrrigationOS
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Validate before committing

```bash
find .github -maxdepth 3 -type f -print
python scripts/validate_repository.py
python -m pytest -q
python -m ruff check .
python -m mypy custom_components tests
git diff --check
git status --short
```

Keep `IrrigationOS_old` until all validation is green. Then it can be deleted.
