# Install a Complete IrrigationOS Release ZIP

Every release ZIP is a complete replacement for repository content. Preserve only the existing `.git` and `.venv` directories.

## Standard staging folder

Move the downloaded ZIP to:

```text
~/Documents/GitHub/11 Temp Files to move
```

Extract it there. The extracted repository root must be:

```text
~/Documents/GitHub/11 Temp Files to move/IrrigationOS
```

## Synchronize the release

```bash
rsync -av --delete \
  --exclude='.git' \
  --exclude='.venv' \
  ~/Documents/GitHub/11\ Temp\ Files\ to\ move/IrrigationOS/ \
  ~/Documents/GitHub/IrrigationOS/
```

This copies hidden files, removes obsolete repository content, and preserves local Git history and the virtual environment.

## Validate

```bash
cd ~/Documents/GitHub/IrrigationOS
source .venv/bin/activate

python -m pip install -r requirements-dev.txt
python scripts/validate_repository.py
python -m pytest -q
python -m ruff check .
python -m mypy custom_components tests
git diff --check
git status --short
```

Do not commit until all checks are green. Do not empty the staging folder until the commit is pushed and GitHub Actions is green.
