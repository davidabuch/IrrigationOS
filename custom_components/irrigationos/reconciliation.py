"""Dynamic entity inventory reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Changes between the previous and current discovery inventory."""

    added: frozenset[str]
    missing: frozenset[str]


@dataclass(slots=True)
class EntityInventory:
    """Track entities already registered with Home Assistant."""

    known: set[str] = field(default_factory=set)

    def reconcile(self, current: set[str]) -> ReconciliationResult:
        """Return additions and currently missing keys without forgetting identity."""
        added = current - self.known
        missing = self.known - current
        self.known.update(added)
        return ReconciliationResult(frozenset(added), frozenset(missing))
