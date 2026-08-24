"""Pure signed-status reader for the private HA Lab companion."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .const import STATUS_MAX_BYTES, STATUS_TTL_SECONDS

CONTRACT_NAME = "hi-lab-status"
SUPPORTED_SCHEMA_MAJOR = 1
SIGNATURE_ALGORITHM = "hmac-sha256-status-v1"
SIGNATURE_DOMAIN = b"hi-lab-status-v1\n"
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
INSTANCE_ID = re.compile(r"^[0-9a-f]{24}$")
UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
DEPLOYMENT_ID = re.compile(r"^HIL-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
PUBLIC_PROFILES = {"public_main", "public_patch_1"}
PENDING_STATES = {
    "WAITING_FOR_RESTART",
    "ACTIVATING",
    "VERIFYING",
    "DISCARDING",
    "ROLLBACK_REQUIRED",
    "ROLLING_BACK",
    "ROLLBACK_WAITING_FOR_RESTART",
    "ROLLBACK_VERIFYING",
    "RECOVERY_REQUIRED",
}
TERMINAL_STATES = {
    "ACTIVE",
    "BLOCKED",
    "DISCARDED",
    "FAILED_ACTIVATION",
    "FAILED_PRE_DEPLOY",
    "NO_CHANGE_EQUIVALENT_PACKAGE",
    "RECOVERY_REQUIRED",
    "RESTORED_PRE_ACTIVATION",
    "ROLLED_BACK",
}
FEED_STATES = {
    "initializing",
    "fresh",
    "stale",
    "missing",
    "invalid_signature",
    "schema_mismatch",
    "clock_invalid",
}
REQUIRED_TOP_LEVEL = {
    "contract",
    "snapshot",
    "capabilities",
    "controller",
    "active",
    "pending",
    "accepted_baseline",
    "lock",
    "restart",
    "last_validation",
    "last_outcome",
    "action_eligibility",
    "queue",
    "signature",
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _parse_timestamp(value: Any) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError
    return parsed.astimezone(dt.UTC)


def _id_or_none(value: Any) -> bool:
    return value is None or (
        isinstance(value, str) and DEPLOYMENT_ID.fullmatch(value) is not None
    )


def _exact_keys(value: dict[str, Any], keys: set[str]) -> bool:
    return set(value) == keys


def _text(value: Any, *, maximum: int = 64) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= maximum


def _timestamp_or_none(value: Any, *, nullable: bool = False) -> bool:
    if value is None:
        return nullable
    if not isinstance(value, str):
        return False
    try:
        _parse_timestamp(value)
    except (TypeError, ValueError):
        return False
    return True


def _deployment_block(
    value: Any,
    *,
    expected_keys: set[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not _exact_keys(value, expected_keys):
        return None
    if (
        not _id_or_none(value.get("deployment_id"))
        or value.get("deployment_id") is None
    ):
        return None
    return value


def _validation_stage(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and _exact_keys(value, {"verdict", "passed", "expected"})
        and value.get("verdict") in {"PASS", "FAIL"}
        and type(value.get("passed")) is int
        and 0 <= value["passed"] <= 512
        and type(value.get("expected")) is int
        and 0 <= value["expected"] <= 512
    )


@dataclass(frozen=True)
class StatusData:
    """One coordinator result, including fail-closed feed diagnostics."""

    feed_state: str
    document: dict[str, Any] | None
    last_contact: dt.datetime | None
    error_code: str | None
    observed_schema_major: int | None

    @property
    def truth_available(self) -> bool:
        return self.feed_state == "fresh" and self.document is not None


class StatusSnapshotReader:
    """Read and validate one fixed, signed, bounded status snapshot."""

    def __init__(
        self,
        path: Path,
        shared_secret: str,
        *,
        now: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self.path = path
        self.secret = shared_secret.encode("ascii")
        self._now = now or (lambda: dt.datetime.now(dt.UTC))
        self._last_contact: dt.datetime | None = None
        self._last_instance_id: str | None = None
        self._last_boot_id: str | None = None
        self._last_revision: int | None = None
        self._last_semantic: bytes | None = None
        self._last_generated: dt.datetime | None = None
        self._last_payload_digest: bytes | None = None

    def _result(
        self,
        feed_state: str,
        *,
        document: dict[str, Any] | None = None,
        error_code: str | None = None,
        observed_schema_major: int | None = None,
    ) -> StatusData:
        if feed_state not in FEED_STATES:
            raise ValueError("unsupported local feed state")
        return StatusData(
            feed_state=feed_state,
            document=document,
            last_contact=self._last_contact,
            error_code=error_code,
            observed_schema_major=observed_schema_major,
        )

    def _read_bytes(self) -> bytes:
        parent = self.path.parent
        if not parent.exists():
            raise FileNotFoundError(self.path)
        if not parent.is_dir() or parent.is_symlink():
            raise OSError("status directory is unavailable or unsafe")
        # A special file must not be able to pin the coordinator before fstat()
        # can reject it. O_NONBLOCK is inert for regular files and makes FIFO or
        # device substitution return promptly to the fail-closed path below.
        flags = os.O_RDONLY | os.O_NONBLOCK
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise OSError("status snapshot is not a regular file")
            if metadata.st_mode & 0o077:
                raise OSError("status snapshot permissions are not private")
            if metadata.st_size <= 0 or metadata.st_size > STATUS_MAX_BYTES:
                raise OSError("status snapshot size is outside policy")
            chunks: list[bytes] = []
            remaining = STATUS_MAX_BYTES + 1
            while remaining:
                chunk = os.read(descriptor, min(8192, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            if len(raw) > STATUS_MAX_BYTES:
                raise OSError("status snapshot exceeds policy")
            return raw
        finally:
            os.close(descriptor)

    @staticmethod
    def _validate_shape(document: dict[str, Any]) -> None:
        if not REQUIRED_TOP_LEVEL.issubset(document):
            raise ValueError("required status block is missing")
        contract = document.get("contract")
        snapshot = document.get("snapshot")
        controller = document.get("controller")
        lock = document.get("lock")
        restart = document.get("restart")
        queue = document.get("queue")
        capabilities = document.get("capabilities")
        if not all(
            isinstance(value, dict)
            for value in (
                contract,
                snapshot,
                capabilities,
                controller,
                lock,
                restart,
                queue,
            )
        ):
            raise ValueError("status block has an invalid type")
        if not _exact_keys(contract, {"name", "schema_major", "schema_minor"}):
            raise ValueError("status contract fields differ")
        if contract.get("name") != CONTRACT_NAME:
            raise ValueError("status contract name differs")
        if type(contract.get("schema_major")) is not int:
            raise ValueError("schema major is invalid")
        if type(contract.get("schema_minor")) is not int:
            raise ValueError("schema minor is invalid")
        if not _exact_keys(
            snapshot,
            {
                "controller_instance_id",
                "controller_boot_id",
                "state_revision",
                "generated_at",
                "expires_at",
            },
        ):
            raise ValueError("snapshot fields differ")
        if (
            not isinstance(snapshot.get("controller_instance_id"), str)
            or INSTANCE_ID.fullmatch(snapshot["controller_instance_id"]) is None
            or not isinstance(snapshot.get("controller_boot_id"), str)
            or UUID.fullmatch(snapshot["controller_boot_id"]) is None
            or type(snapshot.get("state_revision")) is not int
            or snapshot["state_revision"] < 1
        ):
            raise ValueError("snapshot identity is invalid")
        if not _timestamp_or_none(
            snapshot.get("generated_at")
        ) or not _timestamp_or_none(snapshot.get("expires_at")):
            raise ValueError("snapshot timestamps are invalid")
        if not _exact_keys(
            capabilities,
            {
                "status_entities",
                "dashboard",
                "known_good_prepare",
                "queue",
                "ci_artifact_cache",
            },
        ) or capabilities != {
            "status_entities": True,
            "dashboard": False,
            "known_good_prepare": False,
            "queue": False,
            "ci_artifact_cache": False,
        }:
            raise ValueError("status capabilities differ from schema 1.0")
        if not _exact_keys(
            controller,
            {"readiness", "blocker_codes", "overflow_count"},
        ):
            raise ValueError("controller fields differ")
        if controller.get("readiness") not in {"READY", "BLOCKED"}:
            raise ValueError("controller readiness is invalid")
        blockers = controller.get("blocker_codes")
        if (
            not isinstance(blockers, list)
            or len(blockers) > 8
            or len(blockers) != len(set(blockers))
            or not all(
                isinstance(code, str) and SAFE_CODE.fullmatch(code) for code in blockers
            )
            or type(controller.get("overflow_count")) is not int
            or not 0 <= controller["overflow_count"] <= 999
        ):
            raise ValueError("controller blockers are invalid")
        if (
            controller["readiness"] == "READY"
            and (blockers or controller["overflow_count"])
        ) or (
            controller["readiness"] == "BLOCKED"
            and not blockers
            and controller["overflow_count"] == 0
        ):
            raise ValueError("controller readiness and blockers disagree")
        active = document.get("active")
        if active is not None:
            active = _deployment_block(
                active,
                expected_keys={
                    "deployment_id",
                    "profile",
                    "manifest_version",
                    "verified_at",
                    "accepted_baseline",
                },
            )
            if (
                active is None
                or active.get("profile") not in PUBLIC_PROFILES
                or not _text(active.get("manifest_version"))
                or not _timestamp_or_none(active.get("verified_at"))
                or not isinstance(active.get("accepted_baseline"), bool)
            ):
                raise ValueError("active deployment is invalid")
        pending = document.get("pending")
        if pending is not None:
            pending = _deployment_block(
                pending,
                expected_keys={
                    "deployment_id",
                    "state",
                    "profile",
                    "manifest_version",
                    "previous_deployment_id",
                    "created_at",
                    "updated_at",
                },
            )
            if (
                pending is None
                or pending.get("state") not in PENDING_STATES
                or pending.get("profile") not in PUBLIC_PROFILES
                or not _text(pending.get("manifest_version"))
                or not _id_or_none(pending.get("previous_deployment_id"))
                or not _timestamp_or_none(pending.get("created_at"))
                or not _timestamp_or_none(pending.get("updated_at"))
            ):
                raise ValueError("pending deployment is invalid")
        baseline = document.get("accepted_baseline")
        if baseline is not None:
            baseline = _deployment_block(
                baseline,
                expected_keys={
                    "deployment_id",
                    "target_slot",
                    "profile",
                    "manifest_version",
                    "accepted_at",
                },
            )
            if (
                baseline is None
                or baseline.get("target_slot") != "lab_v20"
                or baseline.get("profile") not in PUBLIC_PROFILES
                or not _text(baseline.get("manifest_version"))
                or not _timestamp_or_none(baseline.get("accepted_at"))
            ):
                raise ValueError("accepted baseline is invalid")
        if not _exact_keys(lock, {"state", "deployment_id", "owner_kind", "held_at"}):
            raise ValueError("lock fields differ")
        if lock.get("state") not in {"CLEAR", "HELD", "CONFLICT", "UNVERIFIED"}:
            raise ValueError("lock state is invalid")
        if not _id_or_none(lock.get("deployment_id")):
            raise ValueError("lock deployment ID is invalid")
        if lock.get("owner_kind") is not None and (
            not _text(lock.get("owner_kind"))
            or SAFE_CODE.fullmatch(lock["owner_kind"]) is None
        ):
            raise ValueError("lock owner kind is invalid")
        if not _timestamp_or_none(lock.get("held_at"), nullable=True):
            raise ValueError("lock held time is invalid")
        if pending is not None and (
            lock.get("state") != "HELD"
            or lock.get("deployment_id") != pending.get("deployment_id")
        ):
            raise ValueError("pending deployment and lock disagree")
        if (
            pending is None
            and lock.get("state") == "HELD"
            and lock.get("deployment_id") is not None
        ):
            raise ValueError("bound lock lacks pending deployment")
        if active is not None:
            baseline_is_active = baseline is not None and baseline.get(
                "deployment_id"
            ) == active.get("deployment_id")
            if active.get("accepted_baseline") is not baseline_is_active:
                raise ValueError("active deployment and baseline disagree")
        if not _exact_keys(
            restart,
            {"state", "required", "approved", "deployment_id", "reason_code"},
        ):
            raise ValueError("restart fields differ")
        if restart.get("state") not in {"AVAILABLE", "UNAVAILABLE"}:
            raise ValueError("restart state is invalid")
        if restart.get("required") not in {True, False, None}:
            raise ValueError("restart required truth is invalid")
        if restart.get("approved") not in {True, False, None}:
            raise ValueError("restart approval truth is invalid")
        if not _id_or_none(restart.get("deployment_id")):
            raise ValueError("restart deployment ID is invalid")
        reason_code = restart.get("reason_code")
        if reason_code is not None and (
            not _text(reason_code) or SAFE_CODE.fullmatch(reason_code) is None
        ):
            raise ValueError("restart reason is invalid")
        validation = document.get("last_validation")
        if validation is not None:
            validation = _deployment_block(
                validation,
                expected_keys={
                    "deployment_id",
                    "completed_at",
                    "installed_identity",
                    "stage_b",
                    "stage_3",
                },
            )
            if (
                validation is None
                or not _timestamp_or_none(validation.get("completed_at"))
                or validation.get("installed_identity")
                not in {"PASS", "FAIL", "UNKNOWN"}
                or not _validation_stage(validation.get("stage_b"))
                or not _validation_stage(validation.get("stage_3"))
            ):
                raise ValueError("last validation is invalid")
            if active is None or validation.get("deployment_id") != active.get(
                "deployment_id"
            ):
                raise ValueError("last validation does not cover active deployment")
        outcome = document.get("last_outcome")
        if outcome is not None:
            outcome = _deployment_block(
                outcome,
                expected_keys={
                    "deployment_id",
                    "profile",
                    "state",
                    "completed_at",
                    "error_codes",
                },
            )
            error_codes = outcome.get("error_codes") if outcome else None
            if (
                outcome is None
                or outcome.get("profile") not in PUBLIC_PROFILES
                or outcome.get("state") not in TERMINAL_STATES
                or not _timestamp_or_none(outcome.get("completed_at"))
                or not isinstance(error_codes, list)
                or len(error_codes) > 3
                or len(error_codes) != len(set(error_codes))
                or not all(
                    isinstance(code, str) and SAFE_CODE.fullmatch(code)
                    for code in error_codes
                )
            ):
                raise ValueError("last outcome is invalid")
        if document.get("action_eligibility") != {}:
            raise ValueError("action eligibility must remain disabled in schema 1.0")
        if not _exact_keys(queue, {"enabled", "depth", "max_depth", "entries"}):
            raise ValueError("queue fields differ")
        if (
            queue.get("enabled") is not False
            or queue.get("depth") != 0
            or queue.get("max_depth") != 0
            or queue.get("entries") != []
        ):
            raise ValueError("queue must remain explicitly disabled in schema 1.0")

    def read(self) -> StatusData:
        try:
            raw = self._read_bytes()
        except FileNotFoundError:
            return self._result("missing", error_code="STATUS_FILE_MISSING")
        except OSError:
            return self._result("schema_mismatch", error_code="STATUS_FILE_UNSAFE")

        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._result("schema_mismatch", error_code="STATUS_JSON_INVALID")
        if not isinstance(document, dict):
            return self._result("schema_mismatch", error_code="STATUS_SHAPE_INVALID")

        contract = document.get("contract")
        observed_major = (
            contract.get("schema_major")
            if isinstance(contract, dict)
            and isinstance(contract.get("schema_major"), int)
            else None
        )
        if observed_major != SUPPORTED_SCHEMA_MAJOR:
            return self._result(
                "schema_mismatch",
                error_code="STATUS_SCHEMA_UNSUPPORTED",
                observed_schema_major=observed_major,
            )
        try:
            self._validate_shape(document)
        except (KeyError, TypeError, ValueError):
            return self._result(
                "schema_mismatch",
                error_code="STATUS_SHAPE_INVALID",
                observed_schema_major=observed_major,
            )

        signature = document.get("signature")
        if not isinstance(signature, dict) or not _exact_keys(
            signature,
            {"algorithm", "value"},
        ):
            return self._result(
                "invalid_signature",
                error_code="STATUS_SIGNATURE_MISSING",
                observed_schema_major=observed_major,
            )
        signature_value = signature.get("value")
        if (
            signature.get("algorithm") != SIGNATURE_ALGORITHM
            or not isinstance(signature_value, str)
            or HEX_64.fullmatch(signature_value) is None
        ):
            return self._result(
                "invalid_signature",
                error_code="STATUS_SIGNATURE_INVALID",
                observed_schema_major=observed_major,
            )
        unsigned = dict(document)
        unsigned.pop("signature", None)
        expected = hmac.new(
            self.secret,
            SIGNATURE_DOMAIN + _canonical_json(unsigned),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature_value, expected):
            return self._result(
                "invalid_signature",
                error_code="STATUS_SIGNATURE_INVALID",
                observed_schema_major=observed_major,
            )

        snapshot = document["snapshot"]
        try:
            generated = _parse_timestamp(snapshot["generated_at"])
            expires = _parse_timestamp(snapshot["expires_at"])
        except (KeyError, TypeError, ValueError):
            return self._result(
                "clock_invalid",
                error_code="STATUS_TIME_INVALID",
                observed_schema_major=observed_major,
            )
        now = self._now().astimezone(dt.UTC)
        ttl = (expires - generated).total_seconds()
        if ttl != STATUS_TTL_SECONDS or generated > now + dt.timedelta(seconds=30):
            return self._result(
                "clock_invalid",
                error_code="STATUS_TIME_INVALID",
                observed_schema_major=observed_major,
            )
        if now > expires:
            return self._result(
                "stale",
                error_code="STATUS_EXPIRED",
                observed_schema_major=observed_major,
            )

        instance_id = str(snapshot["controller_instance_id"])
        boot_id = str(snapshot["controller_boot_id"])
        revision = int(snapshot["state_revision"])
        if self._last_instance_id is not None and instance_id != self._last_instance_id:
            return self._result(
                "schema_mismatch",
                error_code="STATUS_INSTANCE_CHANGED",
                observed_schema_major=observed_major,
            )
        if self._last_generated is not None and generated < self._last_generated:
            return self._result(
                "clock_invalid",
                error_code="STATUS_TIME_REGRESSION",
                observed_schema_major=observed_major,
            )
        semantic = {
            key: value
            for key, value in document.items()
            if key not in {"contract", "snapshot", "signature"}
        }
        semantic_bytes = _canonical_json(semantic)
        if self._last_boot_id == boot_id and self._last_revision is not None:
            if revision < self._last_revision:
                return self._result(
                    "schema_mismatch",
                    error_code="STATUS_REVISION_REGRESSION",
                    observed_schema_major=observed_major,
                )
            if (
                revision == self._last_revision
                and semantic_bytes != self._last_semantic
            ):
                return self._result(
                    "schema_mismatch",
                    error_code="STATUS_REVISION_CONFLICT",
                    observed_schema_major=observed_major,
                )
            if revision > self._last_revision and semantic_bytes == self._last_semantic:
                return self._result(
                    "schema_mismatch",
                    error_code="STATUS_REVISION_CONFLICT",
                    observed_schema_major=observed_major,
                )

        payload_digest = hashlib.sha256(raw).digest()
        if payload_digest != self._last_payload_digest:
            self._last_contact = now
            self._last_payload_digest = payload_digest
        self._last_instance_id = instance_id
        self._last_boot_id = boot_id
        self._last_revision = revision
        self._last_semantic = semantic_bytes
        self._last_generated = generated
        return self._result(
            "fresh",
            document=document,
            observed_schema_major=observed_major,
        )
