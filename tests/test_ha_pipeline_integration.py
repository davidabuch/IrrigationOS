"""Repository-level contracts for v1.0.1 HA pipeline integration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "irrigationos"


def test_coordinator_builds_one_cached_pipeline_evaluation() -> None:
    source = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
    assert "self.pipeline_evaluation" in source
    assert "build_pipeline_evaluation(" in source


def test_pipeline_entities_only_read_cached_evaluation() -> None:
    source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    assert "IrrigationOSPipelineStatusSensor" in source
    assert "IrrigationOSPipelineStageSensor" in source
    assert "IrrigationOSPipelineVersionSensor" in source
    assert "IrrigationOSPipelineLastEvaluationSensor" in source
    assert "build_pipeline_evaluation" not in source


def test_diagnostics_include_pipeline_snapshot() -> None:
    source = (INTEGRATION / "diagnostics.py").read_text(encoding="utf-8")
    assert '"pipeline_evaluation"' in source
    assert "asdict(pipeline)" in source


def test_pipeline_integration_remains_non_actuating() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (INTEGRATION / "pipeline").rglob("*.py")
    )
    for forbidden in ("async_call", "start_area", "stop_area", "/zone/start"):
        assert forbidden not in source
