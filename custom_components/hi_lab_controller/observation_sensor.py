"""Independent reporting sensors, never a substitute for legacy deployment truth."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import MATCH_ALL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class ObservationSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "controller")},
            entry_type=DeviceEntryType.SERVICE, name="HI Lab Controller",
            manufacturer="Senyo", model="External HA Lab controller")

    @property
    def available(self):
        data = self.coordinator.current()  # recheck original deadline even between polls
        if self.key == "observation_feed":
            return not self.coordinator.stopped
        if self.key == "observation_last_result":
            return data["terminal"] is not None
        return data["document"] is not None

    @property
    def native_value(self):
        data = self.coordinator.current()
        if self.key == "observation_feed":
            return data["feed"]
        if self.key == "observation_last_result":
            return data["terminal"]["campaign"]["result"] if data["terminal"] else None
        document = data["document"]
        if document is None:
            return None
        if self.key == "observation_integration":
            return document["selected_profile"]["integration_label"]
        campaign = document["campaign"]
        return campaign["state"] if campaign is not None else "IDLE"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.current()
        if self.key == "observation_feed":
            document = data["document"] or {}
            return {"error_code": data["error"], "last_rejection": data["last_rejection"],
                    "generated_at": document.get("generated_at"), "expires_at": document.get("expires_at"),
                    "schema": "hilc.integration-observation.v2"}
        if self.key == "observation_last_result":
            return {"historical_only": True, "campaign": data["terminal"]["campaign"] if data["terminal"] else None}
        document = data["document"]
        if document is None:
            return {}
        if self.key == "observation_integration":
            return dict(document["selected_profile"])
        return {"background_state": document["background_state"],
                "campaign": document["campaign"], "evidence_scope": "reported_health",
                "idle_means_healthy": False}


def entities(coordinator):
    return [ObservationSensor(coordinator, key) for key in (
        "observation_feed", "observation_integration", "observation_campaign", "observation_last_result")]
