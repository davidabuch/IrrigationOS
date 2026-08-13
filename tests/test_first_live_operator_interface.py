"""Repository safety checks for the supervised first-live operator interface."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "irrigationos"


def test_operator_interface_is_options_flow_only() -> None:
    config_flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    button = (INTEGRATION / "button.py").read_text(encoding="utf-8")
    integration_setup = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    assert "async_step_first_live_trial" in config_flow
    assert "async_run_supervised_first_live_trial" in config_flow
    assert "FirstLiveTrialExecutor" not in button
    assert "async_run_supervised_first_live_trial" not in button
    assert "async_run_supervised_first_live_trial" not in integration_setup
    assert "SERVICE_RUN_SUPERVISED_OPERATION" in integration_setup


def test_operator_interface_requires_exact_confirmation_and_bounded_runtime() -> None:
    operator = (
        INTEGRATION / "first_live_delivery" / "operator.py"
    ).read_text(encoding="utf-8")
    config_flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    assert 'FIRST_LIVE_OPERATOR_CONFIRMATION = "RUN SUPERVISED FIRST LIVE TRIAL"' in operator
    assert "vol.Range(min=1, max=120)" in config_flow
    assert "coordinator.async_request_refresh()" in operator
    assert "coordinator.live_commissioning.revoke_approval()" in operator
