"""Canonical IrrigationOS models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControllerSummary:
    """Controller identity discovered from an adapter."""

    native_id: str
    name: str
    status: str | None = None


@dataclass(frozen=True, slots=True)
class ZoneSummary:
    """Zone identity discovered from an adapter."""

    native_id: str
    controller_native_id: str
    name: str
    enabled: bool
    zone_number: int | None = None
