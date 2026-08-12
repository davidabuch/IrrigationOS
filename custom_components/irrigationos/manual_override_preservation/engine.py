"""Deterministic manual override preservation without controller dispatch."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

from ..observation_history.models import WateringAttribution
from .models import ManualOverridePreservationEvent


def evaluate_preservation_reasons(
    active_attributions: Iterable[WateringAttribution | str],
) -> tuple[str, ...]:
    """Return fail-closed reasons requiring existing watering preservation."""

    reasons: set[str] = set()
    for raw_attribution in active_attributions:
        try:
            attribution = (
                raw_attribution
                if isinstance(raw_attribution, WateringAttribution)
                else WateringAttribution(str(raw_attribution))
            )
        except ValueError:
            reasons.add("unknown_attribution_preserved")
            continue

        if attribution is WateringAttribution.IRRIGATIONOS:
            continue
        if attribution is WateringAttribution.MANUAL:
            reasons.add("manual_watering_preserved")
        elif attribution is WateringAttribution.PROVIDER_SCHEDULE:
            reasons.add("provider_schedule_preserved")
        else:
            reasons.add("ambiguous_external_watering_preserved")

    return tuple(sorted(reasons))


def preservation_required(
    active_attributions: Iterable[WateringAttribution | str],
) -> bool:
    """Return whether a future IrrigationOS command must yield to observed watering."""

    return bool(evaluate_preservation_reasons(active_attributions))


def build_manual_override_preservation_event(
    *,
    command_id: str,
    evaluated_at: datetime,
    active_attributions: Iterable[WateringAttribution | str],
) -> ManualOverridePreservationEvent:
    """Build immutable evidence that an external/manual watering state was preserved."""

    command_id = command_id.strip()
    if not command_id:
        raise ValueError("command_id_required")
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at_timezone_required")

    attribution_values = tuple(
        value.value if isinstance(value, WateringAttribution) else str(value)
        for value in active_attributions
    )
    reasons = evaluate_preservation_reasons(attribution_values)
    if not reasons:
        raise ValueError("manual_override_preservation_not_required")

    evaluated_at_utc = evaluated_at.astimezone(UTC)
    protected_count = sum(
        1
        for value in attribution_values
        if value != WateringAttribution.IRRIGATIONOS.value
    )
    ambiguous = any(
        value not in {
            WateringAttribution.IRRIGATIONOS.value,
            WateringAttribution.MANUAL.value,
            WateringAttribution.PROVIDER_SCHEDULE.value,
        }
        for value in attribution_values
    )
    seed = "|".join(
        (
            command_id,
            evaluated_at_utc.isoformat(),
            ",".join(sorted(attribution_values)),
            ",".join(reasons),
        )
    )
    return ManualOverridePreservationEvent(
        event_id=hashlib.sha256(seed.encode()).hexdigest(),
        command_id=command_id,
        evaluated_at_utc=evaluated_at_utc,
        reason_codes=reasons,
        active_session_count=len(attribution_values),
        protected_session_count=protected_count,
        ambiguous_attribution_present=ambiguous,
    )
