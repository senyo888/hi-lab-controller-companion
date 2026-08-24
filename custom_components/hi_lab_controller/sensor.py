"""Read-only status sensors for the external HI Lab controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import RUNTIME_DATA
from .coordinator import HILabStatusCoordinator
from .entity import HILabStatusEntity


@dataclass(frozen=True, kw_only=True)
class HILabSensorDescription(SensorEntityDescription):
    """Describe a bounded value copied from the signed document."""

    value_fn: Callable[[dict[str, Any]], Any]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] = lambda _: {}
    enum_options: tuple[str, ...] | None = None


def _block(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key)
    return value if isinstance(value, dict) else {}


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _attributes(
    document: dict[str, Any],
    block: str,
    keys: tuple[str, ...],
) -> dict[str, Any]:
    value = _block(document, block)
    return {key: value.get(key) for key in keys}


def _validation_attributes(document: dict[str, Any]) -> dict[str, Any]:
    value = _block(document, "last_validation")
    stage_b = value.get("stage_b")
    stage_3 = value.get("stage_3")
    stage_b = stage_b if isinstance(stage_b, dict) else {}
    stage_3 = stage_3 if isinstance(stage_3, dict) else {}
    return {
        "deployment_id": value.get("deployment_id"),
        "installed_identity": value.get("installed_identity"),
        "stage_b_verdict": stage_b.get("verdict"),
        "stage_b_passed": stage_b.get("passed"),
        "stage_b_expected": stage_b.get("expected"),
        "stage_3_verdict": stage_3.get("verdict"),
        "stage_3_passed": stage_3.get("passed"),
        "stage_3_expected": stage_3.get("expected"),
    }


SENSORS = (
    HILabSensorDescription(
        key="controller_readiness",
        device_class=SensorDeviceClass.ENUM,
        enum_options=("READY", "BLOCKED"),
        value_fn=lambda value: _block(value, "controller").get("readiness"),
        attributes_fn=lambda value: {
            "blocker_codes": _block(value, "controller").get("blocker_codes", []),
            "overflow_count": _block(value, "controller").get("overflow_count", 0),
            "state_revision": _block(value, "snapshot").get("state_revision"),
        },
    ),
    HILabSensorDescription(
        key="active_deployment",
        value_fn=lambda value: (
            _block(value, "active").get("deployment_id")
            if value.get("active") is not None
            else "none"
        ),
        attributes_fn=lambda value: _attributes(
            value,
            "active",
            ("profile", "manifest_version", "verified_at", "accepted_baseline"),
        ),
    ),
    HILabSensorDescription(
        key="pending_deployment",
        value_fn=lambda value: (
            _block(value, "pending").get("deployment_id")
            if value.get("pending") is not None
            else "none"
        ),
        attributes_fn=lambda value: _attributes(
            value,
            "pending",
            (
                "state",
                "profile",
                "manifest_version",
                "previous_deployment_id",
                "created_at",
                "updated_at",
            ),
        ),
    ),
    HILabSensorDescription(
        key="mutation_lock",
        device_class=SensorDeviceClass.ENUM,
        enum_options=("CLEAR", "HELD", "CONFLICT", "UNVERIFIED"),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: _block(value, "lock").get("state"),
        attributes_fn=lambda value: _attributes(
            value,
            "lock",
            ("deployment_id", "owner_kind", "held_at"),
        ),
    ),
    HILabSensorDescription(
        key="accepted_baseline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: (
            _block(value, "accepted_baseline").get("deployment_id")
            if value.get("accepted_baseline") is not None
            else "none"
        ),
        attributes_fn=lambda value: _attributes(
            value,
            "accepted_baseline",
            ("target_slot", "profile", "manifest_version", "accepted_at"),
        ),
    ),
    HILabSensorDescription(
        key="last_validation",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: (
            _timestamp(_block(value, "last_validation").get("completed_at"))
            if value.get("last_validation") is not None
            else None
        ),
        attributes_fn=_validation_attributes,
    ),
    HILabSensorDescription(
        key="last_outcome",
        device_class=SensorDeviceClass.ENUM,
        enum_options=(
            "ACTIVE",
            "BLOCKED",
            "DISCARDED",
            "FAILED_ACTIVATION",
            "FAILED_PRE_DEPLOY",
            "NO_CHANGE_EQUIVALENT_PACKAGE",
            "RECOVERY_REQUIRED",
            "RESTORED_PRE_ACTIVATION",
            "ROLLED_BACK",
            "unknown",
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: (
            _block(value, "last_outcome").get("state")
            if value.get("last_outcome") is not None
            else "unknown"
        ),
        attributes_fn=lambda value: _attributes(
            value,
            "last_outcome",
            ("deployment_id", "profile", "completed_at", "error_codes"),
        ),
    ),
)


class HILabControllerSensor(HILabStatusEntity, SensorEntity):
    """One bounded controller-truth sensor."""

    entity_description: HILabSensorDescription

    def __init__(
        self,
        coordinator: HILabStatusCoordinator,
        description: HILabSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.enum_options is not None:
            self._attr_options = list(description.enum_options)

    @property
    def native_value(self) -> Any:
        document = self.controller_document
        return self.entity_description.value_fn(document) if document else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        document = self.controller_document
        return self.entity_description.attributes_fn(document) if document else {}

    @property
    def available(self) -> bool:
        document = self.controller_document
        if document is None:
            return False
        blockers = _block(document, "controller").get("blocker_codes", [])
        if (
            self.entity_description.key == "active_deployment"
            and "ACTIVE_IDENTITY_UNPROVED" in blockers
        ):
            return False
        return not (
            self.entity_description.key == "pending_deployment"
            and "LOCK_IDENTITY_CONFLICT" in blockers
        )


class HILabFeedSensor(HILabStatusEntity, SensorEntity):
    """Companion-local status feed diagnostic for every handled read outcome."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = [
        "initializing",
        "fresh",
        "stale",
        "missing",
        "invalid_signature",
        "schema_mismatch",
        "clock_invalid",
    ]

    def __init__(self, coordinator: HILabStatusCoordinator) -> None:
        super().__init__(coordinator, "status_feed")

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str:
        data = self.coordinator.data
        return data.feed_state if data is not None else "initializing"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {
                "supported_schema_major": 1,
                "observed_schema_major": None,
                "error_code": None,
            }
        document = data.document or {}
        snapshot = _block(document, "snapshot")
        return {
            "supported_schema_major": 1,
            "observed_schema_major": data.observed_schema_major,
            "error_code": data.error_code,
            "controller_boot_id": snapshot.get("controller_boot_id"),
            "state_revision": snapshot.get("state_revision"),
            "generated_at": snapshot.get("generated_at"),
            "expires_at": snapshot.get("expires_at"),
        }


class HILabLastContactSensor(HILabStatusEntity, SensorEntity):
    """Historical companion contact time; never controller freshness."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HILabStatusCoordinator) -> None:
        super().__init__(coordinator, "last_contact")

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return (
            self.coordinator.last_update_success
            and data is not None
            and data.last_contact is not None
        )

    @property
    def native_value(self) -> datetime | None:
        data = self.coordinator.data
        return data.last_contact if data is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"historical_only": True}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = hass.data[RUNTIME_DATA][entry.entry_id].coordinator
    async_add_entities(
        [
            HILabFeedSensor(coordinator),
            HILabLastContactSensor(coordinator),
            *(
                HILabControllerSensor(coordinator, description)
                for description in SENSORS
            ),
        ]
    )
