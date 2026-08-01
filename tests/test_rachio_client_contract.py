"""Static contract tests for the initial Rachio client."""

from __future__ import annotations

import ast
from pathlib import Path

API_FILE = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "irrigationos"
    / "adapters"
    / "rachio"
    / "api.py"
)


def test_api_module_parses() -> None:
    ast.parse(API_FILE.read_text(encoding="utf-8"))


def test_api_key_is_not_in_error_text() -> None:
    source = API_FILE.read_text(encoding="utf-8")
    assert "self._api_key" not in source.split("raise RachioApiError", maxsplit=1)[-1]
