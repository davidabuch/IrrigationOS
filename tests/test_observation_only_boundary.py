"""Safety tests for the v0.2.0 observation-only boundary."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "irrigationos"

FORBIDDEN_ENDPOINTS = (
    "/zone/start",
    "/zone/start_multiple",
    "/device/stop_water",
    "/device/rain_delay",
    "/schedulerule/start",
)


def test_release_contains_no_rachio_control_endpoint() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE.rglob("*.py"))
    for endpoint in FORBIDDEN_ENDPOINTS:
        assert endpoint not in combined


def test_release_contains_no_home_assistant_switch_platform() -> None:
    assert not (SOURCE / "switch.py").exists()
