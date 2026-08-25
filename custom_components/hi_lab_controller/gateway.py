"""Signed filesystem-mailbox client for the external HA Lab controller."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path

from .const import MAILBOX_ROOT


class GatewayError(RuntimeError):
    def __init__(self, code: str, summary: str) -> None:
        self.code = code
        self.summary = summary
        super().__init__(f"{code}: {summary}")


class GatewayClient:
    def __init__(self, shared_secret: str, timeout: int = 600) -> None:
        self.secret = shared_secret.encode("ascii")
        self.timeout = timeout
        self.root = Path(MAILBOX_ROOT)

    @staticmethod
    def _body(value: dict) -> bytes:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")

    def _signature(
        self,
        *,
        path: str,
        timestamp: str,
        request_id: str,
        body: bytes,
    ) -> str:
        canonical = "\n".join(
            ["POST", path, timestamp, request_id, hashlib.sha256(body).hexdigest()]
        ).encode("ascii")
        return hmac.new(self.secret, canonical, hashlib.sha256).hexdigest()

    def _validate_directories(self) -> tuple[Path, Path]:
        incoming = self.root / "incoming"
        outgoing = self.root / "outgoing"
        for path in (self.root, incoming, outgoing):
            if not path.is_dir() or path.is_symlink():
                raise GatewayError("MAILBOX_UNAVAILABLE", "controller mailbox is unavailable")
        return incoming, outgoing

    def _post(self, path: str, value: dict) -> dict:
        incoming, outgoing = self._validate_directories()
        request_id = str(uuid.uuid4())
        timestamp = str(int(time.time()))
        body = self._body(value)
        envelope = {
            "schema_version": 1,
            "path": path,
            "timestamp": timestamp,
            "request_id": request_id,
            "body": value,
            "signature": self._signature(
                path=path,
                timestamp=timestamp,
                request_id=request_id,
                body=body,
            ),
        }
        payload = self._body(envelope) + b"\n"
        temporary = incoming / f".{request_id}.{os.getpid()}.tmp"
        final = incoming / f"{request_id}.json"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, final)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

        response_path = outgoing / f"{request_id}.json"
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if response_path.is_file() and not response_path.is_symlink():
                raw = response_path.read_bytes()
                if len(raw) > 4 * 1024 * 1024:
                    raise GatewayError("CONTROLLER_INVALID_RESPONSE", "controller response is too large")
                try:
                    envelope = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError) as err:
                    raise GatewayError(
                        "CONTROLLER_INVALID_RESPONSE",
                        "controller returned invalid JSON",
                    ) from err
                response_body = envelope.get("body") if isinstance(envelope, dict) else None
                response_route = f"{path}/response"
                if (
                    not isinstance(envelope, dict)
                    or envelope.get("schema_version") != 1
                    or envelope.get("request_id") != request_id
                    or envelope.get("path") != response_route
                    or not isinstance(response_body, dict)
                ):
                    raise GatewayError(
                        "CONTROLLER_INVALID_RESPONSE",
                        "controller response identity differs",
                    )
                response_timestamp = str(envelope.get("timestamp") or "")
                try:
                    if abs(int(time.time()) - int(response_timestamp)) > 300:
                        raise ValueError
                except ValueError as err:
                    raise GatewayError(
                        "CONTROLLER_INVALID_RESPONSE",
                        "controller response timestamp is invalid",
                    ) from err
                expected = self._signature(
                    path=response_route,
                    timestamp=response_timestamp,
                    request_id=request_id,
                    body=self._body(response_body),
                )
                if not hmac.compare_digest(str(envelope.get("signature") or ""), expected):
                    raise GatewayError(
                        "CONTROLLER_INVALID_RESPONSE",
                        "controller response signature differs",
                    )
                response_path.unlink()
                if response_body.get("ok") is not True:
                    raise GatewayError(
                        str(response_body.get("error") or "CONTROLLER_REQUEST_FAILED"),
                        str(response_body.get("summary") or "controller rejected the request"),
                    )
                return response_body["result"]
            time.sleep(0.25)
        raise GatewayError("CONTROLLER_TIMEOUT", "external controller did not answer in time")

    def check(self, user_id: str) -> dict:
        return self._post("/v1/check", {"user_id": user_id})

    def _nonce(self, action: str, user_id: str) -> str:
        result = self._post("/v1/nonce", {"action": action, "user_id": user_id})
        return str(result["nonce"])

    def prepare(self, profile: str, request_key: str, user_id: str) -> dict:
        nonce = self._nonce("prepare", user_id)
        return self._post(
            "/v1/prepare",
            {
                "nonce": nonce,
                "profile": profile,
                "request_key": request_key,
                "user_id": user_id,
            },
        )

    def activate(self, deployment_id: str, user_id: str) -> dict:
        nonce = self._nonce("activate", user_id)
        return self._post(
            "/v1/activate",
            {"deployment_id": deployment_id, "nonce": nonce, "user_id": user_id},
        )

    def queue_prepare(self, profile: str, request_key: str, user_id: str) -> dict:
        nonce = self._nonce("queue_prepare", user_id)
        return self._post(
            "/v1/queue-prepare",
            {
                "nonce": nonce,
                "profile": profile,
                "request_key": request_key,
                "user_id": user_id,
            },
        )

    def cancel_queued_prepare(self, queue_id: str, user_id: str) -> dict:
        nonce = self._nonce("cancel_queued_prepare", user_id)
        return self._post(
            "/v1/cancel-queued-prepare",
            {"queue_id": queue_id, "nonce": nonce, "user_id": user_id},
        )

    def rollback(self, deployment_id: str, user_id: str) -> dict:
        nonce = self._nonce("rollback", user_id)
        return self._post(
            "/v1/rollback",
            {"deployment_id": deployment_id, "nonce": nonce, "user_id": user_id},
        )

    def discard(self, deployment_id: str, user_id: str) -> dict:
        nonce = self._nonce("discard", user_id)
        return self._post(
            "/v1/discard",
            {"deployment_id": deployment_id, "nonce": nonce, "user_id": user_id},
        )

    def status(self, deployment_id: str, user_id: str) -> dict:
        return self._post(
            "/v1/status",
            {"deployment_id": deployment_id, "user_id": user_id},
        )

    def health(self, user_id: str) -> dict:
        return self._post("/v1/health", {"user_id": user_id})
