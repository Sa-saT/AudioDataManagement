"""Parsing and verification of .lic files (see docs/LICENSE_FILE_SPEC.md)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings


class LicenseError(Exception):
    code: str = "INVALID_LICENSE"

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_VALID_ROLES = {"user", "creator", "admin"}
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,32}$")


@dataclass(frozen=True)
class LicensePayload:
    username: str
    role: str
    license_code: str
    monthly_quota_tokens: int
    issued_at: datetime
    expires_at: datetime | None
    signature: str | None
    raw: dict[str, Any]


def parse_lic_text(text: str) -> dict[str, Any]:
    """Accept both JSON and KV formats."""
    stripped = text.strip()
    if not stripped:
        raise LicenseError("MALFORMED_LICENSE", "empty license body")

    # Try JSON first
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise LicenseError("MALFORMED_LICENSE", f"invalid json: {exc}") from exc
        if not isinstance(data, dict):
            raise LicenseError("MALFORMED_LICENSE", "license must be an object")
        return data

    # Fallback: KV (key=value per line)
    data: dict[str, Any] = {}
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise LicenseError("MALFORMED_LICENSE", f"invalid kv line: {line!r}")
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    if "monthlyQuotaTokens" in data:
        try:
            data["monthlyQuotaTokens"] = int(data["monthlyQuotaTokens"])
        except ValueError as exc:
            raise LicenseError("MALFORMED_LICENSE", "monthlyQuotaTokens must be integer") from exc
    return data


def _parse_iso8601(s: str, field: str) -> datetime:
    try:
        # Handle trailing Z
        normalized = s.replace("Z", "+00:00") if s.endswith("Z") else s
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise LicenseError("MALFORMED_LICENSE", f"{field}: invalid datetime {s!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_payload(data: dict[str, Any]) -> LicensePayload:
    required = ("username", "role", "licenseId", "monthlyQuotaTokens", "issuedAt")
    missing = [k for k in required if k not in data]
    if missing:
        raise LicenseError("MALFORMED_LICENSE", f"missing fields: {missing}")

    username = data["username"]
    if not isinstance(username, str) or not _USERNAME_RE.match(username):
        raise LicenseError("MALFORMED_LICENSE", "username must match ^[a-zA-Z0-9_.-]{1,32}$")

    role = data["role"]
    if role not in _VALID_ROLES:
        raise LicenseError("MALFORMED_LICENSE", f"role must be one of {_VALID_ROLES}")

    license_code = data["licenseId"]
    if not isinstance(license_code, str) or not license_code:
        raise LicenseError("MALFORMED_LICENSE", "licenseId must be non-empty string")

    quota = data["monthlyQuotaTokens"]
    if not isinstance(quota, int) or quota < 0:
        raise LicenseError("MALFORMED_LICENSE", "monthlyQuotaTokens must be non-negative integer")

    issued_at = _parse_iso8601(str(data["issuedAt"]), "issuedAt")
    expires_at = _parse_iso8601(str(data["expiresAt"]), "expiresAt") if data.get("expiresAt") else None

    sig = data.get("signature")
    if sig is not None and not isinstance(sig, str):
        raise LicenseError("MALFORMED_LICENSE", "signature must be string")

    return LicensePayload(
        username=username,
        role=role,
        license_code=license_code,
        monthly_quota_tokens=quota,
        issued_at=issued_at,
        expires_at=expires_at,
        signature=sig,
        raw=data,
    )


def _canonical_payload_bytes(data: dict[str, Any]) -> bytes:
    payload_for_sig = {k: v for k, v in data.items() if k != "signature"}
    return json.dumps(payload_for_sig, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_signature(data: dict[str, Any], *, secret: str | None = None) -> str:
    key = (secret or get_settings().LICENSE_SECRET).encode("utf-8")
    digest = hmac.new(key, _canonical_payload_bytes(data), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def verify_signature(payload: LicensePayload, *, require: bool = True) -> None:
    if not payload.signature:
        if require:
            raise LicenseError("INVALID_LICENSE_SIGNATURE", "license is unsigned")
        return
    expected = compute_signature(payload.raw)
    if not hmac.compare_digest(expected, payload.signature):
        raise LicenseError("INVALID_LICENSE_SIGNATURE", "signature mismatch")


def check_validity(payload: LicensePayload, *, now: datetime | None = None) -> None:
    current = now or datetime.now(timezone.utc)
    if payload.expires_at is not None and payload.expires_at <= current:
        raise LicenseError("LICENSE_EXPIRED", "license has expired")
