"""Diagnostic buttons for IrrigationOS."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IrrigationOSCoordinator
from .entity import IrrigationOSEntity
from .health import IrrigationOSHealthState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IrrigationOSCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the non-actuating health incident reset button."""

    del hass
    coordinator = entry.runtime_data
    async_add_entities(
        [
            IrrigationOSResetHealthIncidentButton(coordinator),
            IrrigationOSConfirmControllerOwnershipButton(coordinator),
            IrrigationOSAcknowledgeExecutionBoundaryReviewButton(coordinator),
            IrrigationOSRevokeControllerOwnershipButton(coordinator),
        ]
    )


class IrrigationOSResetHealthIncidentButton(IrrigationOSEntity, ButtonEntity):
    """Acknowledge recovered health history without touching irrigation equipment."""

    _attr_name = "Reset health incident"
    _attr_unique_id = "irrigationos_reset_health_incident"
    entity_id = "button.irrigationos_reset_health_incident"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:restore-alert"

    def __init__(self, coordinator: IrrigationOSCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        """Allow acknowledgement only while current health is fully healthy."""

        return self.coordinator.health_assessment.state is IrrigationOSHealthState.HEALTHY

    async def async_press(self) -> None:
        """Reset the diagnostic latch only."""

        await self.coordinator.reset_health_incident_latch()


class IrrigationOSConfirmControllerOwnershipButton(IrrigationOSEntity, ButtonEntity):
    """Explicitly commission ownership without enabling live control."""

    _attr_name = "Confirm controller ownership"
    _attr_unique_id = "irrigationos_confirm_controller_ownership"
    entity_id = "button.irrigationos_confirm_controller_ownership"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:account-check-outline"

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data.controllers)

    async def async_press(self) -> None:
        await self.coordinator.confirm_controller_ownership()


class IrrigationOSAcknowledgeExecutionBoundaryReviewButton(
    IrrigationOSEntity, ButtonEntity
):
    """Acknowledge manual execution-boundary review without authorizing commands."""

    _attr_name = "Acknowledge execution boundary review"
    _attr_unique_id = "irrigationos_acknowledge_execution_boundary_review"
    entity_id = "button.irrigationos_acknowledge_execution_boundary_review"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clipboard-check-outline"

    @property
    def available(self) -> bool:
        summary = self.coordinator.execution_authorization.summary
        return summary.blocker_codes == ("execution_boundary_review_acknowledged",)

    async def async_press(self) -> None:
        await self.coordinator.acknowledge_execution_boundary_review()


class IrrigationOSRevokeControllerOwnershipButton(IrrigationOSEntity, ButtonEntity):
    """Revoke ownership commissioning and fail closed."""

    _attr_name = "Revoke controller ownership"
    _attr_unique_id = "irrigationos_revoke_controller_ownership"
    entity_id = "button.irrigationos_revoke_controller_ownership"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:shield-off-outline"

    @property
    def available(self) -> bool:
        return self.coordinator.ownership_commissioning.summary.ownership_confirmed

    async def async_press(self) -> None:
        await self.coordinator.revoke_controller_ownership()
