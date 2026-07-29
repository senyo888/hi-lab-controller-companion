"""Config flow for the private HA Lab controller companion."""

from __future__ import annotations

import asyncio

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_SHARED_SECRET, DOMAIN
from .gateway import GatewayClient, GatewayError


class HILabControllerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            client = GatewayClient(
                user_input[CONF_SHARED_SECRET],
                timeout=180,
            )
            try:
                await asyncio.to_thread(client.check, "config-flow")
            except GatewayError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="HI Lab Controller",
                    data=user_input,
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_SHARED_SECRET): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD,
                        autocomplete="new-password",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
