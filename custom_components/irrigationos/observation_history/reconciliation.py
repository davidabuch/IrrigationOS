"""Deterministic canonical-snapshot watering-session reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256

from ..controllers import (
    ControllerAvailability,
    ControllerRegistrySnapshot,
    IrrigationArea,
    IrrigationAreaState,
    ObservationQuality,
)
from .models import (
    AttributionEvidenceCode,
    WateringAttribution,
    WateringObservationSource,
    WateringSession,
    WateringSessionEvent,
    WateringSessionEventType,
    WateringSessionState,
    WateringTimestampPrecision,
)


@dataclass(frozen=True, slots=True)
class SessionObservationContext:
    """Safe normalized metadata describing one canonical snapshot refresh."""

    observed_at: datetime
    source: WateringObservationSource
    realtime_event_type: str | None = None
    realtime_event_subtype: str | None = None

    def __post_init__(self) -> None:
        offset = (
            self.observed_at.utcoffset()
            if isinstance(self.observed_at, datetime)
            else None
        )
        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or offset is None
            or offset.total_seconds() != 0
        ):
            raise ValueError("observed_at must be a timezone-aware UTC datetime")
        if not isinstance(self.source, WateringObservationSource):
            raise ValueError("source must be canonical")
        for name, value in (
            ("realtime_event_type", self.realtime_event_type),
            ("realtime_event_subtype", self.realtime_event_subtype),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must not be blank")


class WateringSessionReconciler:
    """Maintain independent sessions by canonical area identity."""

    def __init__(
        self,
        *,
        active_sessions: tuple[WateringSession, ...] = (),
        completed_sessions: tuple[WateringSession, ...] = (),
    ) -> None:
        if any(not session.active for session in active_sessions):
            raise ValueError("active_sessions must contain only active sessions")
        active_area_ids = tuple(session.area_id for session in active_sessions)
        if len(active_area_ids) != len(set(active_area_ids)):
            raise ValueError("active_sessions must have unique canonical area IDs")
        if any(session.active for session in completed_sessions):
            raise ValueError("completed_sessions must contain only inactive sessions")
        self._active = {session.area_id: session for session in active_sessions}
        self._completed = list(completed_sessions)

    @property
    def active_sessions(self) -> tuple[WateringSession, ...]:
        """Return active sessions in stable area-ID order."""

        return tuple(self._active[key] for key in sorted(self._active))

    @property
    def completed_sessions(self) -> tuple[WateringSession, ...]:
        """Return completed sessions newest first."""

        return tuple(
            sorted(
                self._completed,
                key=lambda item: (item.ended_at or item.started_at, item.session_id),
                reverse=True,
            )
        )

    def reconcile(
        self,
        snapshot: ControllerRegistrySnapshot,
        context: SessionObservationContext,
    ) -> tuple[WateringSessionEvent, ...]:
        """Reconcile one successful canonical snapshot without false closure."""

        events: list[WateringSessionEvent] = []
        observed_area_ids: set[str] = set()
        for controller in snapshot.controllers:
            trustworthy = (
                controller.availability is ControllerAvailability.ONLINE
                and controller.watering_observation_quality is ObservationQuality.CONFIRMED
                and snapshot.observation.quality is not ObservationQuality.UNAVAILABLE
            )
            for area in controller.areas:
                observed_area_ids.add(area.area_id)
                current = self._active.get(area.area_id)
                if trustworthy and area.state is IrrigationAreaState.WATERING:
                    if current is None:
                        current = _open_session(area, context)
                        self._active[area.area_id] = current
                        events.append(
                            WateringSessionEvent(
                                WateringSessionEventType.SESSION_STARTED,
                                current,
                                context.observed_at,
                            )
                        )
                    else:
                        event_type = (
                            WateringSessionEventType.SESSION_RECONCILED
                            if current.observation_source
                            is WateringObservationSource.RESTART_RECONCILIATION
                            else WateringSessionEventType.SESSION_UPDATED
                        )
                        current = _continue_session(current, area, context)
                        self._active[area.area_id] = current
                        events.append(
                            WateringSessionEvent(
                                event_type,
                                current,
                                context.observed_at,
                            )
                        )
                elif current is not None and trustworthy and _definitively_not_watering(area):
                    closed = _close_session(current, area, context)
                    self._active.pop(area.area_id, None)
                    self._completed.append(closed)
                    events.append(
                        WateringSessionEvent(
                            WateringSessionEventType.SESSION_CLOSED,
                            closed,
                            context.observed_at,
                        )
                    )
                elif current is not None and not trustworthy:
                    uncertain = _mark_uncertain(current, context)
                    self._active[area.area_id] = uncertain
                    if uncertain != current:
                        events.append(
                            WateringSessionEvent(
                                WateringSessionEventType.SESSION_RECONCILED,
                                uncertain,
                                context.observed_at,
                            )
                        )

        for area_id in sorted(set(self._active) - observed_area_ids):
            current = self._active[area_id]
            uncertain = _mark_uncertain(current, context)
            self._active[area_id] = uncertain
            if uncertain != current:
                events.append(
                    WateringSessionEvent(
                        WateringSessionEventType.SESSION_RECONCILED,
                        uncertain,
                        context.observed_at,
                    )
                )
        return tuple(events)


def _open_session(
    area: IrrigationArea, context: SessionObservationContext
) -> WateringSession:
    evidence = {AttributionEvidenceCode.NO_EXPLICIT_PROVIDER_EVIDENCE.value}
    if context.source is WateringObservationSource.POLLING:
        evidence.add(AttributionEvidenceCode.POLLING_BOUNDARY_INEXACT.value)
    if context.source is WateringObservationSource.REALTIME_REFRESH:
        evidence.add(
            AttributionEvidenceCode.REALTIME_EVENT_NOT_OWNERSHIP_EVIDENCE.value
        )
    return WateringSession(
        session_id=_session_id(area, context.observed_at),
        controller_id=area.controller_id,
        area_id=area.area_id,
        slot_number=area.slot_number,
        area_name=area.vendor_name or area.name,
        started_at=context.observed_at,
        ended_at=None,
        duration_seconds=None,
        state=WateringSessionState.ACTIVE,
        observation_source=context.source,
        observation_quality=ObservationQuality.CONFIRMED,
        timestamp_precision=_precision(context.source),
        attribution=WateringAttribution.EXTERNAL_UNKNOWN,
        attribution_confidence=0.0,
        attribution_evidence=tuple(sorted(evidence)),
        reconstructed_after_restart=False,
        incomplete=context.source is not WateringObservationSource.REALTIME_REFRESH,
        first_observed_at=context.observed_at,
        last_observed_at=context.observed_at,
    )


def _continue_session(
    session: WateringSession,
    area: IrrigationArea,
    context: SessionObservationContext,
) -> WateringSession:
    return replace(
        session,
        area_name=area.vendor_name or area.name,
        observation_source=_merge_source(session.observation_source, context.source),
        timestamp_precision=_merge_precision(
            session.timestamp_precision, _precision(context.source)
        ),
        last_observed_at=max(session.last_observed_at, context.observed_at),
    )


def _close_session(
    session: WateringSession,
    area: IrrigationArea,
    context: SessionObservationContext,
) -> WateringSession:
    ended_at = max(session.last_observed_at, context.observed_at)
    source = _merge_source(session.observation_source, context.source)
    precision = _merge_precision(session.timestamp_precision, _precision(context.source))
    incomplete = (
        session.incomplete
        or session.reconstructed_after_restart
        or context.source is not WateringObservationSource.REALTIME_REFRESH
    )
    return replace(
        session,
        area_name=area.vendor_name or area.name,
        ended_at=ended_at,
        duration_seconds=max(0, round((ended_at - session.started_at).total_seconds())),
        state=WateringSessionState.INACTIVE,
        observation_source=source,
        timestamp_precision=precision,
        incomplete=incomplete,
        last_observed_at=ended_at,
    )


def _mark_uncertain(
    session: WateringSession, context: SessionObservationContext
) -> WateringSession:
    evidence = tuple(
        sorted(
            {
                *session.attribution_evidence,
                AttributionEvidenceCode.OBSERVATION_GAP.value,
            }
        )
    )
    return replace(
        session,
        observation_quality=ObservationQuality.PARTIAL,
        timestamp_precision=_merge_precision(
            session.timestamp_precision, WateringTimestampPrecision.RECONSTRUCTED
        ),
        attribution_evidence=evidence,
        incomplete=True,
    )


def _definitively_not_watering(area: IrrigationArea) -> bool:
    return area.state in {
        IrrigationAreaState.IDLE,
        IrrigationAreaState.DISABLED,
        IrrigationAreaState.UNUSED,
    }


def _session_id(area: IrrigationArea, started_at: datetime) -> str:
    payload = (
        f"{area.controller_id}|{area.area_id}|{area.slot_number}|"
        f"{started_at.isoformat()}"
    )
    return f"session.{sha256(payload.encode()).hexdigest()}"


def _precision(source: WateringObservationSource) -> WateringTimestampPrecision:
    if source is WateringObservationSource.REALTIME_REFRESH:
        return WateringTimestampPrecision.EVENT_BOUNDED
    if source is WateringObservationSource.RESTART_RECONCILIATION:
        return WateringTimestampPrecision.RECONSTRUCTED
    return WateringTimestampPrecision.POLLING_WINDOW


def _merge_source(
    previous: WateringObservationSource,
    current: WateringObservationSource,
) -> WateringObservationSource:
    return previous if previous is current else WateringObservationSource.MIXED


def _merge_precision(
    previous: WateringTimestampPrecision,
    current: WateringTimestampPrecision,
) -> WateringTimestampPrecision:
    rank = {
        WateringTimestampPrecision.EVENT_BOUNDED: 0,
        WateringTimestampPrecision.POLLING_WINDOW: 1,
        WateringTimestampPrecision.RECONSTRUCTED: 2,
    }
    return max((previous, current), key=rank.__getitem__)
