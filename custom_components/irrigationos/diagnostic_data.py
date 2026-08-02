"""Home Assistant-independent diagnostic redaction helpers."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

REDACTED = "**REDACTED**"


def redact_data(value: Any, keys: Collection[str]) -> Any:
    """Recursively redact values whose mapping key is sensitive."""
    if isinstance(value, dict):
        return {
            str(key): REDACTED if str(key) in keys else redact_data(item, keys)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_data(item, keys) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_data(item, keys) for item in value)
    return value
