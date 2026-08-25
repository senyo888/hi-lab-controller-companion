"""Private Home Assistant action gateway for the external HA Lab controller."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_SHARED_SECRET,
    DOMAIN,
    NOTIFICATION_ID,
    PLATFORMS,
    RUNTIME_DATA,
    STATUS_PATH,
)
from .coordinator import HILabStatusCoordinator
from .gateway import GatewayClient, GatewayError
from .status_reader import StatusSnapshotReader

PROFILE_SCHEMA = vol.Schema(
    {vol.Required("profile"): vol.In(("public_patch_1", "public_main"))}
)
DEPLOYMENT_SCHEMA = vol.Schema({vol.Required("deployment_id"): cv.string})
QUEUE_SCHEMA = vol.Schema({vol.Required("queue_id"): cv.string})


@dataclass(frozen=True)
class HILabRuntimeData:
    """Config-entry runtime state."""

    client: GatewayClient
    coordinator: HILabStatusCoordinator


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions even when the controller config entry is unavailable."""

    async def _admin_client(call: ServiceCall) -> tuple[GatewayClient, str]:
        user_id = call.context.user_id
        if not user_id:
            raise HomeAssistantError(
                "HI Lab Controller actions require an authenticated user"
            )
        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            raise HomeAssistantError(
                "HI Lab Controller actions require an administrator"
            )
        clients = hass.data.get(DOMAIN, {})
        if len(clients) != 1:
            raise HomeAssistantError(
                "HI Lab Controller has no unique configured gateway"
            )
        return next(iter(clients.values())), user_id

    async def _notify(message: str) -> None:
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "notification_id": NOTIFICATION_ID,
                "title": "HI Lab Controller",
                "message": message,
            },
            blocking=True,
        )

    async def _refresh_status() -> None:
        runtimes = hass.data.get(RUNTIME_DATA, {})
        if len(runtimes) == 1:
            runtime = next(iter(runtimes.values()))
            await runtime.coordinator.async_request_refresh()

    async def _restart_after_response() -> None:
        await asyncio.sleep(3)
        await hass.services.async_call("homeassistant", "restart", {}, blocking=False)

    async def prepare(call: ServiceCall) -> ServiceResponse | None:
        gateway, user_id = await _admin_client(call)
        try:
            result = await asyncio.to_thread(
                gateway.prepare,
                call.data["profile"],
                f"ha-action-{uuid.uuid4()}",
                user_id,
            )
        except GatewayError as err:
            raise HomeAssistantError(f"{err.code}: {err.summary}") from err
        finally:
            await _refresh_status()
        await _notify(
            f"Deployment `{result['deployment_id']}` is `{result['state']}`. "
            "Activation remains a separate administrator action."
        )
        return result if call.return_response else None

    async def activate(call: ServiceCall) -> ServiceResponse | None:
        gateway, user_id = await _admin_client(call)
        try:
            result = await asyncio.to_thread(
                gateway.activate,
                call.data["deployment_id"],
                user_id,
            )
        except GatewayError as err:
            raise HomeAssistantError(f"{err.code}: {err.summary}") from err
        finally:
            await _refresh_status()
        activation = result.get("activation_result") or {}
        if activation.get("restart_approved") is not True:
            raise HomeAssistantError("controller did not approve this exact restart")
        await _notify(
            f"Activation accepted for `{result['deployment_id']}`. "
            "Home Assistant will restart; controller verification remains authoritative."
        )
        hass.async_create_task(_restart_after_response())
        return result if call.return_response else None

    async def queue_prepare(call: ServiceCall) -> ServiceResponse | None:
        gateway, user_id = await _admin_client(call)
        try:
            result = await asyncio.to_thread(
                gateway.queue_prepare,
                call.data["profile"],
                f"ha-queue-{uuid.uuid4()}",
                user_id,
            )
        except GatewayError as err:
            raise HomeAssistantError(f"{err.code}: {err.summary}") from err
        finally:
            await _refresh_status()
        await _notify(
            f"Prepare request `{result['queue_id']}` is `{result['state']}`. "
            "It remains bounded and may be cancelled before claim."
        )
        return result if call.return_response else None

    async def cancel_queued_prepare(call: ServiceCall) -> ServiceResponse | None:
        gateway, user_id = await _admin_client(call)
        try:
            result = await asyncio.to_thread(
                gateway.cancel_queued_prepare,
                call.data["queue_id"],
                user_id,
            )
        except GatewayError as err:
            raise HomeAssistantError(f"{err.code}: {err.summary}") from err
        finally:
            await _refresh_status()
        return result if call.return_response else None

    async def status(call: ServiceCall) -> ServiceResponse | None:
        gateway, user_id = await _admin_client(call)
        try:
            result = await asyncio.to_thread(
                gateway.status,
                call.data["deployment_id"],
                user_id,
            )
            return result if call.return_response else None
        except GatewayError as err:
            raise HomeAssistantError(f"{err.code}: {err.summary}") from err
        finally:
            await _refresh_status()

    async def health(call: ServiceCall) -> ServiceResponse | None:
        gateway, user_id = await _admin_client(call)
        try:
            result = await asyncio.to_thread(gateway.health, user_id)
            return result if call.return_response else None
        except GatewayError as err:
            raise HomeAssistantError(f"{err.code}: {err.summary}") from err
        finally:
            await _refresh_status()

    async def discard(call: ServiceCall) -> ServiceResponse | None:
        gateway, user_id = await _admin_client(call)
        try:
            result = await asyncio.to_thread(
                gateway.discard,
                call.data["deployment_id"],
                user_id,
            )
        except GatewayError as err:
            raise HomeAssistantError(f"{err.code}: {err.summary}") from err
        finally:
            await _refresh_status()
        await _notify(
            f"Prepared deployment `{result['deployment_id']}` is `{result['state']}`. "
            "The verified previous package was restored without restarting Home Assistant."
        )
        return result if call.return_response else None

    async def rollback(call: ServiceCall) -> ServiceResponse | None:
        gateway, user_id = await _admin_client(call)
        try:
            result = await asyncio.to_thread(
                gateway.rollback,
                call.data["deployment_id"],
                user_id,
            )
        except GatewayError as err:
            raise HomeAssistantError(f"{err.code}: {err.summary}") from err
        finally:
            await _refresh_status()
        activation = result.get("activation_result") or {}
        if activation.get("restart_approved") is not True:
            raise HomeAssistantError(
                "controller did not approve this exact rollback restart"
            )
        await _notify(
            f"Rollback accepted for `{result['deployment_id']}`. "
            "Home Assistant will restart; controller verification remains authoritative."
        )
        hass.async_create_task(_restart_after_response())
        return result if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        "prepare_version",
        prepare,
        schema=PROFILE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "activate_prepared_version",
        activate,
        schema=DEPLOYMENT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "queue_prepare_version",
        queue_prepare,
        schema=PROFILE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "cancel_queued_prepare",
        cancel_queued_prepare,
        schema=QUEUE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "deployment_status",
        status,
        schema=DEPLOYMENT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "controller_health",
        health,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "discard_prepared_version",
        discard,
        schema=DEPLOYMENT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "rollback_deployment",
        rollback,
        schema=DEPLOYMENT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = GatewayClient(
        entry.data[CONF_SHARED_SECRET],
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    reader = StatusSnapshotReader(
        STATUS_PATH,
        entry.data[CONF_SHARED_SECRET],
    )
    coordinator = HILabStatusCoordinator(hass, entry, reader)
    await coordinator.async_config_entry_first_refresh()
    runtime = HILabRuntimeData(client=client, coordinator=coordinator)
    hass.data.setdefault(RUNTIME_DATA, {})[entry.entry_id] = runtime
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    hass.data.get(RUNTIME_DATA, {}).pop(entry.entry_id, None)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
