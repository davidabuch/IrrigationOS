"""Safety tests for the v0.4.0 observation-only boundary."""

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


def test_control_endpoints_are_confined_to_release_gated_first_live_transport() -> None:
    allowed_transport = SOURCE / "first_live_delivery/rachio.py"
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SOURCE.rglob("*.py")
        if path != allowed_transport
    )
    for endpoint in FORBIDDEN_ENDPOINTS:
        assert endpoint not in combined

    transport_source = allowed_transport.read_text(encoding="utf-8")
    assert '"/zone/start"' in transport_source
    assert '"/device/stop_water"' in transport_source
    for endpoint in ("/zone/start_multiple", "/device/rain_delay", "/schedulerule/start"):
        assert endpoint not in transport_source


def test_release_contains_no_home_assistant_switch_platform() -> None:
    assert not (SOURCE / "switch.py").exists()
