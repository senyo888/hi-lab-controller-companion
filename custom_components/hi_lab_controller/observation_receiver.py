"""Serialized authenticated observation acceptance with durable replay custody.

Persistence is injected by the HA adapter and must complete before acknowledgement.
Restored custody protects ordering but never restores current availability.
"""
from copy import deepcopy
import asyncio
import hashlib
import hmac
import math
import time

from . import observation_protocol as p

RECORD_DOMAIN = b"hilc.integration-observation.receiver-custody.v2\n"


async def await_physical(future):
    """Cancellation cannot abandon an executor write or its ownership fence."""
    cancelled = False
    while not future.done():
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError:
            cancelled = True
    result = future.result()
    if cancelled:
        raise asyncio.CancelledError
    return result


def seal_record(value, secret):
    digest = hmac.new(p.secret_bytes(secret), RECORD_DOMAIN + p.canonical(value), hashlib.sha256).hexdigest()
    return {"value": deepcopy(value), "signature": digest}


def initial_record(instance, epoch, secret):
    return seal_record({**p.pairing(instance, epoch, secret), "sequence": 0,
                        "generated_at": None, "accepted_sha256": None,
                        "terminal": None}, secret)


def read_record(record, instance, epoch, secret):
    p.closed(record, {"value", "signature"})
    p.require(type(record["signature"]) is str, "CUSTODY_INVALID")
    p.require(hmac.compare_digest(p.canonical(record), p.canonical(seal_record(record["value"], secret))), "CUSTODY_INVALID")
    value = record["value"]
    p.closed(value, {"controller_instance_id", "stream_epoch", "key_digest", "sequence",
                     "generated_at", "accepted_sha256", "terminal"})
    pair = p.pairing(instance, epoch, secret)
    p.require(all(value[k] == v for k, v in pair.items()), "PAIRING_MISMATCH")
    p.require(type(value["sequence"]) is int and 0 <= value["sequence"] <= p.MAX_SEQUENCE)
    if value["sequence"] == 0:
        p.require(value["generated_at"] is None and value["accepted_sha256"] is None and value["terminal"] is None)
    else:
        p.timestamp(value["generated_at"])
        p.require(type(value["accepted_sha256"]) is str and len(value["accepted_sha256"]) == 64)
    if value["terminal"] is not None:
        terminal = p.validate(value["terminal"])
        p.require(terminal["campaign"] is not None and terminal["campaign"]["state"] in p.TERMINAL)
        p.require(terminal["sequence"] <= value["sequence"])
    return deepcopy(value)


class Receiver:
    def __init__(self, instance, epoch, secret, record, persist,
                 *, wall=time.time, monotonic=time.monotonic):
        self.instance, self.epoch, self.secret = instance, epoch, secret
        self.value = read_record(record, instance, epoch, secret)
        self.persist = persist
        self.wall, self.monotonic = wall, monotonic
        self.lock = asyncio.Lock()
        self.document = None
        self.deadline = None
        self.anchor = (wall(), monotonic())
        self.previous = self.anchor
        self.poison = None
        self.closed = False
        self.rejection = None

    def _clock(self):
        now, mono = self.wall(), self.monotonic()
        wall_delta, mono_delta = now - self.anchor[0], mono - self.anchor[1]
        if (not all(math.isfinite(x) for x in (now, mono)) or now < self.previous[0]
                or mono < self.previous[1] or wall_delta < 0 or mono_delta < 0
                or abs(wall_delta - mono_delta) > 5):
            self.poison = "CLOCK_DISCONTINUITY"
        p.require(not self.poison, self.poison or "CLOCK_DISCONTINUITY")
        self.previous = (now, mono)
        return now, mono

    def snapshot(self):
        error = self.poison
        document = None
        try:
            now, mono = self._clock()
            if self.closed:
                error = "DISABLED"
            elif self.document is None:
                error = "AWAITING_NEW_SEQUENCE"
            elif now >= p.timestamp(self.document["expires_at"]) or mono >= self.deadline:
                error = "OBSERVATION_EXPIRED"
            elif self.document["selected_profile"] is None:
                error = "SELECTION_UNAVAILABLE"
            elif self.document["background_state"] == "UNAVAILABLE":
                error = "SOURCE_UNAVAILABLE"
            else:
                document = deepcopy(self.document)
        except p.Invalid as exc:
            error = str(exc)
        terminal = deepcopy(self.value["terminal"])
        return {"feed": "fresh" if document is not None else
                       "stale" if error == "OBSERVATION_EXPIRED" else "unavailable",
                "error": error, "last_rejection": self.rejection,
                "document": document, "terminal": terminal}

    async def receive(self, raw):
        # One accepted frame at a time; concurrent requests are refused, not queued.
        p.require(not self.lock.locked(), "RECEIVER_BUSY")
        async with self.lock:
            p.require(not self.closed and not self.poison, self.poison or "DISABLED")
            try:
                payload = p.verify(raw, self.secret, self.instance, self.epoch)
                now, mono = self._clock()
                generated, expires = p.timestamp(payload["generated_at"]), p.timestamp(payload["expires_at"])
                p.require(generated <= now + 5 and now < expires, "OBSERVATION_EXPIRED")
                p.require(payload["sequence"] > self.value["sequence"], "SEQUENCE_REPLAY")
                if self.value["generated_at"] is not None:
                    p.require(generated >= p.timestamp(self.value["generated_at"]), "CLOCK_DISCONTINUITY")
                updated = {**p.pairing(self.instance, self.epoch, self.secret),
                    "sequence": payload["sequence"], "generated_at": payload["generated_at"],
                    "accepted_sha256": hashlib.sha256(raw).hexdigest(),
                    "terminal": deepcopy(self.value["terminal"])}
                if payload["campaign"] is not None and payload["campaign"]["state"] in p.TERMINAL:
                    updated["terminal"] = deepcopy(payload)
                try:
                    await self.persist(seal_record(updated, self.secret))
                except BaseException:
                    # Persistence may have completed despite cancellation or failure.
                    # Poison this receiver; a reload must reconcile durable custody.
                    self.poison = "CUSTODY_WRITE_FAILED"
                    self.document = None
                    raise p.Invalid("CUSTODY_WRITE_FAILED") from None
                self.value = updated
                end, end_mono = self._clock()
                p.require(not self.closed, "DISABLED")
                p.require(end < expires and end_mono < mono + (expires - now), "OBSERVATION_EXPIRED")
                self.document = payload
                self.deadline = mono + (expires - now)
                self.rejection = None
                return p.acknowledgement(raw, payload, self.secret)
            except p.Invalid as exc:
                self.rejection = str(exc)
                raise

    def close(self):
        self.closed = True
        self.document = None

    async def drain(self):
        self.close()
        async def fence():
            async with self.lock:
                pass
        await await_physical(asyncio.create_task(fence()))
