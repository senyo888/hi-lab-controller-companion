"""Closed, public-safe observation v2 wire contract; no HA or controller imports.

The controller ships an identical copy, verified by the interoperability check.
Authentication binds an explicitly paired instance and epoch. Feed freshness never
changes the original time of a checkpoint or a retained result.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
import re
import uuid

SCHEMA = "hilc.integration-observation.v2"
DOMAIN = b"hilc.integration-observation.v2\n"
ACK_DOMAIN = b"hilc.integration-observation.ack.v2\n"
MAX_BYTES = 16384
MAX_SEQUENCE = 9007199254740991
CHECKPOINT_UTC_TOLERANCE = 2.001  # engine wall/monotonic tolerance + millisecond projection
PROFILE_FIELDS = {"profile_id", "integration_label", "domain", "reference_label",
                  "evidence_scope", "source_identity", "baseline"}
CAMPAIGN_FIELDS = PROFILE_FIELDS | {"id", "state", "result", "completed_slots", "total_slots",
    "reasons", "started_at", "finished_at", "next_checkpoint_at", "report_id", "checkpoints"}
TOP_FIELDS = {"schema_version", "controller_instance_id", "stream_epoch", "sequence",
              "generated_at", "expires_at", "background_state", "selected_profile", "campaign"}
STATES = {"RUNNING", "STOPPING", "STOPPED", "COMPLETED", "FAILED", "INVALIDATED", "INTERRUPTED"}
TERMINAL = STATES - {"RUNNING", "STOPPING"}


class Invalid(ValueError):
    """A bounded public error code, never an input value or credential."""


def require(condition, code="INVALID_OBSERVATION"):
    if not condition:
        raise Invalid(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def closed(value, keys):
    require(type(value) is dict and set(value) == keys)


def identifier(value):
    require(type(value) is str and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value))


def uid(value):
    require(type(value) is str)
    try:
        require(str(uuid.UUID(value)) == value and uuid.UUID(value).version == 4)
    except (ValueError, AttributeError):
        raise Invalid("INVALID_OBSERVATION") from None


def timestamp(value):
    require(type(value) is str and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value))
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        require(math.isfinite(result))
        return result
    except (ValueError, OverflowError):
        raise Invalid("INVALID_OBSERVATION") from None


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def codes(values):
    require(type(values) is list and len(values) <= 16)
    require(all(type(v) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", v) for v in values))
    require(len(values) == len(set(values)))


def profile(value):
    closed(value, PROFILE_FIELDS)
    identifier(value["profile_id"])
    require(type(value["domain"]) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value["domain"]))
    for key in ("integration_label", "reference_label"):
        require(type(value[key]) is str and re.fullmatch(r"[ -~]{1,80}", value[key]))
    require(value["evidence_scope"] == "reported_health")
    require(value["source_identity"] == "EXPECTED_REFERENCE_NOT_LOADED_PROOF")
    require(value["baseline"] == "NOT_ACCEPTED")


def campaign(value, generated):
    closed(value, CAMPAIGN_FIELDS)
    profile({k: value[k] for k in PROFILE_FIELDS})
    uid(value["id"])
    require(value["report_id"] == value["id"])
    require(value["state"] in STATES)
    require(value["result"] in {"PENDING", "PASS", "FAIL", "INCOMPLETE"})
    require(type(value["total_slots"]) is int and value["total_slots"] == 9)
    require(type(value["completed_slots"]) is int and 0 <= value["completed_slots"] <= 9)
    codes(value["reasons"])
    started = timestamp(value["started_at"])
    require(started <= generated)
    if value["state"] in TERMINAL:
        require(value["finished_at"] is not None)
        require(started <= timestamp(value["finished_at"]) <= generated)
        require(value["next_checkpoint_at"] is None)
    else:
        require(value["finished_at"] is None)
        require(value["result"] == ("INCOMPLETE" if value["state"] == "STOPPING" else "PENDING"))
    if value["next_checkpoint_at"] is not None:
        require(value["state"] == "RUNNING" and timestamp(value["next_checkpoint_at"]) >= started)
    samples = value["checkpoints"]
    require(type(samples) is list and len(samples) <= 9)
    accepted = 0
    for i, sample in enumerate(samples):
        closed(sample, {"slot", "state", "due_at", "observed_at", "reasons"})
        require(type(sample["slot"]) is int and sample["slot"] == i)
        require(sample["state"] in {"CLAIMED", "HEALTHY", "UNHEALTHY", "UNAVAILABLE", "DISCARDED"})
        require(timestamp(sample["due_at"]) == started + i * 21600)
        codes(sample["reasons"])
        if sample["state"] in {"HEALTHY", "UNHEALTHY", "UNAVAILABLE"}:
            accepted += 1
            require(sample["observed_at"] is not None)
            require(timestamp(sample["observed_at"]) <= timestamp(sample["due_at"]) + 900 + CHECKPOINT_UTC_TOLERANCE)
            if value["finished_at"] is not None:
                require(timestamp(sample["observed_at"]) <= timestamp(value["finished_at"]))
        if sample["observed_at"] is not None:
            require(max(started, timestamp(sample["due_at"]) - CHECKPOINT_UTC_TOLERANCE) <= timestamp(sample["observed_at"]) <= generated)
        if sample["state"] == "CLAIMED":
            require(i == len(samples) - 1 and value["state"] in {"RUNNING", "STOPPING", "INVALIDATED"})
    require(value["completed_slots"] == accepted)
    if value["state"] == "COMPLETED":
        require(value["result"] == "PASS" and accepted == 9 and not value["reasons"])
        require(all(s["state"] == "HEALTHY" for s in samples))
    elif value["state"] == "FAILED":
        require(value["result"] == "FAIL" and accepted == 9)
        require(any(s["state"] != "HEALTHY" for s in samples))
    elif value["state"] in {"STOPPED", "INVALIDATED", "INTERRUPTED"}:
        require(value["result"] == "INCOMPLETE")


def _validate(value):
    closed(value, TOP_FIELDS)
    require(value["schema_version"] == SCHEMA, "SCHEMA_UNSUPPORTED")
    uid(value["controller_instance_id"]); uid(value["stream_epoch"])
    require(type(value["sequence"]) is int and 1 <= value["sequence"] <= MAX_SEQUENCE)
    generated = timestamp(value["generated_at"])
    require(0 < timestamp(value["expires_at"]) - generated <= 60)
    require(value["background_state"] in {"RUNNING", "PAUSED", "UNAVAILABLE"})
    if value["selected_profile"] is not None:
        profile(value["selected_profile"])
    if value["campaign"] is not None:
        campaign(value["campaign"], generated)
        if value["campaign"]["state"] in {"RUNNING", "STOPPING"}:
            require(value["background_state"] == "RUNNING")
            require(value["selected_profile"] == {k: value["campaign"][k] for k in PROFILE_FIELDS})
    require(len(canonical(value)) <= MAX_BYTES - 128)
    return deepcopy(value)


def validate(value):
    try:
        return _validate(value)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise Invalid("INVALID_OBSERVATION") from None


def secret_bytes(secret):
    require(type(secret) is str and re.fullmatch(r"[0-9a-f]{64}", secret), "PAIRING_INVALID")
    return bytes.fromhex(secret)


def pairing(instance, epoch, secret):
    uid(instance); uid(epoch); secret_bytes(secret)
    return {"controller_instance_id": instance, "stream_epoch": epoch,
            "key_digest": hashlib.sha256(secret_bytes(secret)).hexdigest()}


def parse(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES)
    def pairs(items):
        result = {}
        for key, child in items:
            require(key not in result)
            result[key] = child
        return result
    def reject(_):
        raise Invalid("INVALID_OBSERVATION")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs, parse_constant=reject)
        require(type(value) is dict and canonical(value) == raw)
        return value
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise Invalid("INVALID_OBSERVATION") from None


def sign(value, secret):
    value = validate(value)
    digest = hmac.new(secret_bytes(secret), DOMAIN + canonical(value), hashlib.sha256).hexdigest()
    return canonical({"payload": value, "signature": digest})


def verify(raw, secret, instance, epoch):
    value = parse(raw)
    closed(value, {"payload", "signature"})
    require(type(value["signature"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["signature"]))
    expected = hmac.new(secret_bytes(secret), DOMAIN + canonical(value["payload"]), hashlib.sha256).hexdigest()
    require(hmac.compare_digest(value["signature"], expected), "AUTHENTICATION_FAILED")
    payload = validate(value["payload"])
    require((payload["controller_instance_id"], payload["stream_epoch"]) == (instance, epoch), "PAIRING_MISMATCH")
    return payload


def acknowledgement(raw, payload, secret):
    value = {"schema_version": SCHEMA, "controller_instance_id": payload["controller_instance_id"],
             "stream_epoch": payload["stream_epoch"], "sequence": payload["sequence"],
             "accepted_sha256": hashlib.sha256(raw).hexdigest()}
    digest = hmac.new(secret_bytes(secret), ACK_DOMAIN + canonical(value), hashlib.sha256).hexdigest()
    return canonical({"payload": value, "signature": digest})


def verify_ack(raw, sent, payload, secret):
    require(type(raw) is bytes and len(raw) <= 1024, "ACK_INVALID")
    require(hmac.compare_digest(raw, acknowledgement(sent, payload, secret)), "ACK_INVALID")
