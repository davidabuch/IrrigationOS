"""Deterministic controller ownership commissioning state derivation."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from .models import OwnershipCommissioningStatus, OwnershipCommissioningSummary


def controller_topology_fingerprint(controller_ids: Iterable[str]) -> str:
    """Return stable fingerprint for canonical controller membership."""

    canonical = tuple(sorted(set(str(value) for value in controller_ids if str(value))))
    return hashlib.sha256("\n".join(canonical).encode()).hexdigest()


def build_ownership_commissioning_summary(
    *,
    controller_ids: Iterable[str],
    stored: Mapping[str, Any] | None,
) -> OwnershipCommissioningSummary:
    """Derive effective commissioning state; topology changes always fail closed."""

    current_ids = tuple(sorted(set(str(value) for value in controller_ids if str(value))))
    stored = stored if isinstance(stored, Mapping) else {}
    state = str(stored.get("state", "uncommissioned"))
    commissioned_ids = _identifiers(stored.get("controller_ids"))
    topology_matches = bool(current_ids) and commissioned_ids == current_ids
    confirmed_at = _timestamp(stored.get("confirmed_at"))
    reviewed_at = _timestamp(stored.get("boundary_reviewed_at"))
    revoked_at = _timestamp(stored.get("revoked_at"))
    revision = _nonnegative_int(stored.get("commissioning_revision"))

    ownership_confirmed = state == "confirmed" and topology_matches and confirmed_at is not None
    review_acknowledged = ownership_confirmed and reviewed_at is not None

    if state == "revoked":
        status = OwnershipCommissioningStatus.REVOKED
    elif state == "confirmed" and not topology_matches:
        status = OwnershipCommissioningStatus.STALE_TOPOLOGY
    elif review_acknowledged:
        status = OwnershipCommissioningStatus.BOUNDARY_REVIEW_ACKNOWLEDGED
    elif ownership_confirmed:
        status = OwnershipCommissioningStatus.OWNERSHIP_CONFIRMED
    else:
        status = OwnershipCommissioningStatus.UNCOMMISSIONED

    return OwnershipCommissioningSummary(
        status=status,
        controller_count=len(current_ids),
        commissioned_controller_count=len(commissioned_ids),
        topology_matches=topology_matches,
        ownership_confirmed=ownership_confirmed,
        boundary_review_acknowledged=review_acknowledged,
        confirmed_at=confirmed_at,
        boundary_reviewed_at=reviewed_at,
        revoked_at=revoked_at,
        commissioning_revision=revision,
    )


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    return result if result.tzinfo is not None and result.utcoffset() is not None else None


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _identifiers(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(sorted(set(str(item) for item in value if isinstance(item, str) and item)))
