"""Repository-level contracts for completed HA pipeline observability."""

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
    assert "IrrigationOSScientificInputStatusSensor" in source
    assert "IrrigationOSWeatherSourceSensor" in source
    assert "IrrigationOSPipelineStageStatusSensor" in source
    assert "IrrigationOSAreaPipelineSensor" in source
    assert "for stage in PipelineStage" in source
    assert "build_pipeline_evaluation" not in source


def test_diagnostics_include_pipeline_snapshot() -> None:
    source = (INTEGRATION / "diagnostics.py").read_text(encoding="utf-8")
    assert '"pipeline_evaluation"' in source
    assert '"pipeline_summary"' in source
    assert '"output_counts"' in source
    assert "asdict(pipeline)" in source


def test_pipeline_integration_remains_non_actuating() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for directory in ("pipeline", "scientific_inputs")
        for path in (INTEGRATION / directory).rglob("*.py")
    )
    for forbidden in ("async_call(", "/zone/start", "/zone/stop"):
        assert forbidden not in source


def test_pipeline_entity_ids_are_stable_and_non_actuating() -> None:
    source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    assert 'f"irrigationos_pipeline_stage_{slug}"' in source
    assert 'f"{area.area_id}_pipeline_output"' in source
    assert 'f"zone_{area.slot_number}_pipeline_output"' in source
    for forbidden in ("async_call(", "/zone/start", "/zone/stop"):
        assert forbidden not in source
