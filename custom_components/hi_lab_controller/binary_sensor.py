"""Fail-closed restart truth for the external HI Lab controller."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import RUNTIME_DATA
from .coordinator import HILabStatusCoordinator
from .entity import HILabStatusEntity


class HILabRestartRequiredSensor(HILabStatusEntity, BinarySensorEntity):
    """Remain unavailable until durable restart truth exists."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HILabStatusCoordinator) -> None:
        super().__init__(coordinator, "restart_required")

    @property
    def available(self) -> bool:
        document = self.controller_document
        if document is None:
            return False
        restart = document.get("restart")
        return (
            isinstance(restart, dict)
            and restart.get("state") == "AVAILABLE"
            and isinstance(restart.get("required"), bool)
        )

    @property
    def is_on(self) -> bool | None:
        document = self.controller_document
        if document is None:
            return None
        restart = document.get("restart")
        if not isinstance(restart, dict) or not isinstance(
            restart.get("required"), bool
        ):
            return None
        return restart["required"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        document = self.controller_document
        restart = document.get("restart") if document else None
        if not isinstance(restart, dict):
            return {}
        return {
            "deployment_id": restart.get("deployment_id"),
            "reason_code": restart.get("reason_code"),
            "approved": restart.get("approved"),
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = hass.data[RUNTIME_DATA][entry.entry_id].coordinator
    async_add_entities([HILabRestartRequiredSensor(coordinator)])
