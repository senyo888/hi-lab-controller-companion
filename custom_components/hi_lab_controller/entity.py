"""Shared entity support for the HI Lab controller status device."""

from __future__ import annotations

from homeassistant.const import MATCH_ALL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HILabStatusCoordinator


class HILabStatusEntity(CoordinatorEntity[HILabStatusCoordinator]):
    """Base class that never restores controller truth."""

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(
        self,
        coordinator: HILabStatusCoordinator,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "controller")},
            entry_type=DeviceEntryType.SERVICE,
            name="HI Lab Controller",
            manufacturer="Senyo",
            model="External HA Lab controller",
        )

    @property
    def controller_document(self) -> dict | None:
        if not self.coordinator.last_update_success:
            return None
        data = self.coordinator.data
        if data is None or not data.truth_available:
            return None
        return data.document

    @property
    def available(self) -> bool:
        return self.controller_document is not None
