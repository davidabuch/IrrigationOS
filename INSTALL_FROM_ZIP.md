# Install a Complete IrrigationOS Repository Release

Every release ZIP is a complete replacement for the repository contents. Preserve only `.git` and `.venv` in the working repository.

## Standard staging folder

`~/Documents/GitHub/11 Temp Files to move`

## Install

Move the ZIP into the staging folder, extract it there, and synchronize the included outer `IrrigationOS/` folder:

```bash
cd ~/Documents/GitHub/11\ Temp\ Files\ to\ move
unzip -q IrrigationOS_v0.4.0_First_Live_Installation.zip

rsync -av --delete \
  --exclude='.git' \
  --exclude='.venv' \
  ~/Documents/GitHub/11\ Temp\ Files\ to\ move/IrrigationOS/ \
  ~/Documents/GitHub/IrrigationOS/
```

## Validate

```bash
cd ~/Documents/GitHub/IrrigationOS
source .venv/bin/activate

python scripts/validate_repository.py
python -m pytest -q
python -m ruff check .
python -m mypy custom_components tests
git diff --check
git status --short
```
