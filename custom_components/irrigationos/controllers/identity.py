"""Persistent canonical identity allocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ControllerIdentityRegistry:
    """Allocate and persist provider-neutral controller identifiers."""

    controllers: dict[str, str] = field(default_factory=dict)
    _changed: bool = False

    @classmethod
    def from_dict(cls, value: object) -> ControllerIdentityRegistry:
        """Load an identity registry from config-entry data."""
        if not isinstance(value, dict):
            return cls()
        controllers = value.get("controllers", {})
        if not isinstance(controllers, dict):
            return cls()
        return cls(
            controllers={
                str(key): str(item)
                for key, item in controllers.items()
                if isinstance(item, str) and item
            }
        )

    @property
    def changed(self) -> bool:
        """Return whether a new identity has been allocated."""
        return self._changed

    def controller_id_for(self, provider: str, native_id: str) -> str:
        """Return a stable persisted identity for a provider controller."""
        binding_key = self.binding_key(provider, native_id)
        existing = self.controllers.get(binding_key)
        if existing is not None:
            return existing
        controller_id = f"controller_{uuid4().hex}"
        self.controllers[binding_key] = controller_id
        self._changed = True
        return controller_id

    @staticmethod
    def area_id_for(controller_id: str, slot_number: int) -> str:
        """Return the canonical identity of a permanent controller slot."""
        if slot_number < 1:
            raise ValueError("Controller slot numbers start at 1")
        return f"{controller_id}:slot:{slot_number}"

    @staticmethod
    def binding_key(provider: str, native_id: str) -> str:
        """Return a storage key for a replaceable provider binding."""
        return f"{provider.strip().lower()}:{native_id.strip()}"

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-serializable config-entry data."""
        return {"controllers": dict(sorted(self.controllers.items()))}

    def mark_saved(self) -> None:
        """Record that the current mapping has been persisted."""
        self._changed = False
