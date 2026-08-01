# v0.1.0 Package Validation

The delivered ZIP is a complete repository-content replacement package. It intentionally excludes `.git`, `.venv`, generated caches, Finder metadata, and compiled Python files.

Validation gates:

- Repository metadata validator
- Pytest
- Ruff
- MyPy
- Python bytecode compilation
- JSON parsing
- ZIP inventory inspection
- Forbidden-artifact inspection
