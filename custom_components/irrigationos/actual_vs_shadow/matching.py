"""Pure deterministic matching helpers for actual-vs-shadow reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

MATCH_GRACE = timedelta(hours=2)


def parse_time(value: object) -> datetime:
    """Parse timezone-aware ISO text to UTC."""
    if not isinstance(value, str):
        raise ValueError("timestamp must be ISO text")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def extract_scheduled_irrigation_actions(record: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Extract only executable irrigation schedule evidence from one shadow record."""
    evaluation_id = str(record.get("evaluation_id", ""))
    payload = record.get("payload", {})
    if not evaluation_id or not isinstance(payload, dict):
        return ()
    scheduling = payload.get("scheduling")
    actions = _scheduling_actions(scheduling)
    found: list[dict[str, Any]] = []
    for raw in actions:
        if not isinstance(raw, dict) or raw.get("disposition") != "scheduled":
            continue
        source = raw.get("source_action")
        if not isinstance(source, dict) or source.get("action_type") != "irrigate":
            continue
        values = (
            raw.get("target_id"),
            raw.get("starts_at"),
            raw.get("ends_at"),
            raw.get("scheduled_action_id"),
        )
        if not all(isinstance(value, str) and value for value in values):
            continue
        start = parse_time(values[1])
        end = parse_time(values[2])
        cycle_starts = raw.get("cycle_starts_at", [])
        cycle_runtime = raw.get("cycle_runtime_seconds")
        runtime = source.get("runtime_seconds")
        if isinstance(cycle_starts, list) and isinstance(cycle_runtime, int) and cycle_runtime > 0:
            runtime_seconds = len(cycle_starts) * cycle_runtime
        elif isinstance(runtime, int) and runtime > 0:
            runtime_seconds = runtime
        else:
            runtime_seconds = max(1, round((end - start).total_seconds()))
        found.append({
            "evaluation_id": evaluation_id,
            "scheduled_action_id": values[3],
            "target_id": values[0],
            "starts_at": start,
            "ends_at": end,
            "runtime_seconds": runtime_seconds,
        })
    return tuple(
        sorted(
            found,
            key=lambda item: (item["evaluation_id"], item["scheduled_action_id"]),
        )
    )


def _scheduling_actions(scheduling: object) -> list[object]:
    """Read legacy schema-1 lists and coherent schema-2 scheduling envelopes."""

    if isinstance(scheduling, list):
        area_evaluations = scheduling
    elif isinstance(scheduling, dict):
        direct = scheduling.get("actions")
        if isinstance(direct, list):
            return list(direct)
        nested = scheduling.get("area_evaluations")
        if not isinstance(nested, list):
            return []
        area_evaluations = nested
    else:
        return []

    actions: list[object] = []
    for evaluation in area_evaluations:
        if not isinstance(evaluation, dict):
            continue
        schedule = evaluation.get("schedule")
        if not isinstance(schedule, dict):
            continue
        nested_actions = schedule.get("actions")
        if isinstance(nested_actions, list):
            actions.extend(nested_actions)
    return actions


def classify_match(
    *,
    planned_start: datetime,
    planned_runtime_seconds: int,
    observed_start: datetime,
    observed_runtime_seconds: int | None,
    incomplete: bool,
    observation_quality: str,
    timestamp_precision: str,
) -> dict[str, Any]:
    """Classify one zone/runtime/timing comparison conservatively."""
    start_delta = round((observed_start - planned_start).total_seconds())
    runtime_delta = (
        None
        if observed_runtime_seconds is None
        else observed_runtime_seconds - planned_runtime_seconds
    )
    reasons = ["planned_zone_observed"]
    outcome = "agreement"
    if abs(start_delta) > 15 * 60:
        reasons.append("start_timing_difference")
        outcome = "partial"
    if runtime_delta is not None and abs(runtime_delta) > max(60, planned_runtime_seconds * 0.1):
        reasons.append("runtime_difference")
        outcome = "partial"
    if incomplete or observation_quality == "partial":
        reasons.append("observation_incomplete")
        confidence = "low"
    elif timestamp_precision == "event_bounded":
        confidence = "high"
    else:
        confidence = "medium"
    return {
        "outcome": outcome,
        "confidence": confidence,
        "reason_codes": tuple(sorted(set(reasons))),
        "start_delta_seconds": start_delta,
        "runtime_delta_seconds": runtime_delta,
    }
