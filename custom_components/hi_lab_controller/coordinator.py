"""Shared local-file coordinator for all HI Lab controller status entities."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, STATUS_SCAN_SECONDS
from .status_reader import StatusData, StatusSnapshotReader

LOGGER = logging.getLogger(__name__)


class HILabStatusCoordinator(DataUpdateCoordinator[StatusData]):
    """Read one local signed snapshot for every entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        reader: StatusSnapshotReader,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_status",
            update_interval=timedelta(seconds=STATUS_SCAN_SECONDS),
            always_update=False,
        )
        self.reader = reader

    async def _async_update_data(self) -> StatusData:
        return await self.hass.async_add_executor_job(self.reader.read)
