"""Optional paired observation receiver; legacy status and actions stay separate."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import hashlib
import logging

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import RUNTIME_DATA
from . import observation_protocol as p
from .observation_receiver import Receiver, initial_record, read_record
from .observation_storage import VerifiedStore

ENABLED = "observation_enabled"
INSTANCE = "observation_controller_instance"
EPOCH = "observation_stream_epoch"
SECRET = "observation_secret"
OPTIONS = {ENABLED, INSTANCE, EPOCH, SECRET}
LOG = logging.getLogger(__name__)
ENDPOINT = "/api/hi_lab_controller/observation/v2"


def storage(hass, instance, epoch):
    p.uid(instance); p.uid(epoch)
    identity = hashlib.sha256((instance + ":" + epoch).encode("ascii")).hexdigest()
    return VerifiedStore(hass, "hi_lab_controller.observation_v2." + identity)


async def prepare_pairing(hass, values, previous):
    """Explicit options-flow handshake only; startup never initializes replay state."""
    p.closed(values, OPTIONS)
    p.require(type(values[ENABLED]) is bool, "PAIRING_INVALID")
    if not values[ENABLED]:
        return {**previous, ENABLED: False}
    instance, epoch, secret = values[INSTANCE], values[EPOCH], values[SECRET]
    p.pairing(instance, epoch, secret)
    store = storage(hass, instance, epoch)
    record = await store.async_load()
    if record is None:
        p.require((instance, epoch) != (previous.get(INSTANCE), previous.get(EPOCH)), "CUSTODY_MISSING")
        record = initial_record(instance, epoch, secret)
        await store.initialize(record)
        p.require(await store.async_load() == record, "CUSTODY_WRITE_FAILED")
    read_record(record, instance, epoch, secret)
    return dict(values)


class ObservationCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, LOG, config_entry=entry, name="hi_lab_controller_observation",
                         update_interval=timedelta(seconds=5), always_update=False)
        self.entry = entry
        self.receiver = None
        self.error = "NOT_PAIRED"
        self.expiry_cancel = None
        self.stopped = False

    async def initialize(self):
        options = self.entry.options
        if options.get(ENABLED) is True:
            try:
                p.closed(dict(options), OPTIONS)
                store = storage(self.hass, options[INSTANCE], options[EPOCH])
                record = await store.async_load()
                p.require(record is not None, "CUSTODY_MISSING")
                self.receiver = Receiver(options[INSTANCE], options[EPOCH], options[SECRET], record, store.async_save)
            except Exception:
                self.error = "PAIRING_CUSTODY_UNAVAILABLE"
        await self.async_config_entry_first_refresh()

    def current(self):
        if self.stopped or self.receiver is None:
            return {"feed": "unavailable", "error": "DISABLED" if self.stopped else self.error,
                    "last_rejection": None, "document": None, "terminal": None}
        return self.receiver.snapshot()

    async def _async_update_data(self):
        return self.current()

    async def receive(self, raw):
        p.require(not self.stopped and self.receiver is not None, "NOT_PAIRED")
        try:
            reply = await self.receiver.receive(raw)
        finally:
            if not self.stopped:
                self.async_set_updated_data(self.current())
        if self.expiry_cancel is not None:
            self.expiry_cancel()
        expires = dt_util.parse_datetime(self.receiver.document["expires_at"])
        def expire(_now):
            self.expiry_cancel = None
            if not self.stopped:
                self.async_set_updated_data(self.current())
        self.expiry_cancel = async_track_point_in_utc_time(self.hass, expire, expires)
        return reply

    def stop(self):
        self.stopped = True
        if self.receiver is not None:
            self.receiver.close()
        if self.expiry_cancel is not None:
            self.expiry_cancel(); self.expiry_cancel = None

    async def async_close(self):
        """Fence reception immediately and drain persistence before a successor loads."""
        self.stop()
        if self.receiver is not None:
            await self.receiver.drain()


class ObservationView(HomeAssistantView):
    url = ENDPOINT
    name = "api:hi_lab_controller:observation:v2"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass
        self.busy = False

    async def post(self, request):
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return self.json({"error": "ADMIN_REQUIRED"}, status_code=403)
        if self.busy:
            return self.json({"error": "RECEIVER_BUSY"}, status_code=409)
        runtimes = self.hass.data.get(RUNTIME_DATA, {})
        if len(runtimes) != 1:
            return self.json({"error": "NOT_PAIRED"}, status_code=503)
        coordinator = next(iter(runtimes.values())).observation
        if coordinator is None or coordinator.stopped or coordinator.receiver is None:
            return self.json({"error": "NOT_PAIRED"}, status_code=503)
        # Bound decompressed body, chunked bodies and slow sends without reading it
        # into aiohttp's unbounded request.json()/read() convenience buffer.
        self.busy = True
        try:
            if request.content_length is not None and request.content_length > p.MAX_BYTES:
                raise p.Invalid("BODY_TOO_LARGE")
            raw = bytearray()
            async with asyncio.timeout(5):
                async for chunk in request.content.iter_chunked(1024):
                    raw.extend(chunk)
                    p.require(len(raw) <= p.MAX_BYTES, "BODY_TOO_LARGE")
            reply = await coordinator.receive(bytes(raw))
            return web.Response(body=reply, content_type="application/json")
        except (p.Invalid, TimeoutError):
            # No raw payload, key, token, route or exception details leave this boundary.
            return self.json({"error": "OBSERVATION_REFUSED"}, status_code=400)
        finally:
            self.busy = False
