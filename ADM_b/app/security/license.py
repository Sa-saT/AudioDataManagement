"""Parsing and verification of .lic files (see docs/LICENSE_FILE_SPEC.md)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import struct
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


_VALID_ROLES = {"licensee", "creator", "admin"}
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


# ─── Phase B: JWE (ECDH-ES + A256GCM) ───────────────────────────────────────

def _b64url_enc(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _concat_kdf(z: bytes, alg: str, key_len_bits: int) -> bytes:
    """One-pass Concat KDF (SHA-256) per RFC 7518 §4.6.2."""
    alg_bytes = alg.encode("ascii")
    other_info = (
        struct.pack(">I", len(alg_bytes)) + alg_bytes
        + struct.pack(">I", 0)  # empty apu
        + struct.pack(">I", 0)  # empty apv
        + struct.pack(">I", key_len_bits)
    )
    h = hashlib.sha256()
    h.update(struct.pack(">I", 1))
    h.update(z)
    h.update(other_info)
    return h.digest()[: key_len_bits // 8]


def _is_jwe_token(s: str) -> bool:
    """JWE compact = 5 base64url parts separated by dots."""
    parts = s.split(".")
    return len(parts) == 5 and parts[0].startswith("eyJ")


def _load_ec_private_key():
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    pem = get_settings().ADM_LIC_EC_PRIVATE_KEY
    if not pem:
        raise LicenseError("INVALID_LICENSE_FORMAT", "ADM_LIC_EC_PRIVATE_KEY not configured")
    # Support both literal \n (env var string) and actual newlines
    pem = pem.replace("\\n", "\n")
    return load_pem_private_key(pem.encode(), password=None)


def issue_jwe_license(data: dict[str, Any], *, kid: str = "adm-v1") -> str:
    """Return a JWE compact token for the given payload (Phase B).
    Adds schemaVersion=2 so the verifier skips HMAC."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.ec import ECDH
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    recipient_pub = _load_ec_private_key().public_key()
    ephem_priv = ec.generate_private_key(ec.SECP256R1())
    ephem_pub = ephem_priv.public_key()
    epk_nums = ephem_pub.public_numbers()

    shared = ephem_priv.exchange(ECDH(), recipient_pub)
    cek = _concat_kdf(shared, "A256GCM", 256)

    epk_jwk = {
        "kty": "EC", "crv": "P-256",
        "x": _b64url_enc(epk_nums.x.to_bytes(32, "big")),
        "y": _b64url_enc(epk_nums.y.to_bytes(32, "big")),
    }
    header = {"alg": "ECDH-ES", "enc": "A256GCM", "epk": epk_jwk, "kid": kid}
    header_b64 = _b64url_enc(json.dumps(header, separators=(",", ":")).encode())

    iv = os.urandom(12)
    plaintext = json.dumps({**data, "schemaVersion": 2}, separators=(",", ":")).encode()
    ct_tag = AESGCM(cek).encrypt(iv, plaintext, header_b64.encode("ascii"))
    ct, tag = ct_tag[:-16], ct_tag[-16:]

    return f"{header_b64}..{_b64url_enc(iv)}.{_b64url_enc(ct)}.{_b64url_enc(tag)}"


def parse_jwe_lic_text(text: str) -> dict[str, Any]:
    """Decrypt a Phase B JWE compact token and return the payload dict."""
    from cryptography.hazmat.primitives.asymmetric.ec import (
        ECDH, EllipticCurvePublicNumbers, SECP256R1,
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    parts = text.strip().split(".")
    if len(parts) != 5:
        raise LicenseError("MALFORMED_LICENSE", "invalid JWE compact format")

    header_b64, _enc_key, iv_b64, ct_b64, tag_b64 = parts
    try:
        header = json.loads(_b64url_dec(header_b64))
    except Exception as exc:
        raise LicenseError("MALFORMED_LICENSE", f"JWE header decode failed: {exc}") from exc

    if header.get("alg") != "ECDH-ES" or header.get("enc") != "A256GCM":
        raise LicenseError(
            "INVALID_LICENSE_FORMAT",
            f"unsupported JWE alg/enc: {header.get('alg')}/{header.get('enc')}",
        )

    try:
        private_key = _load_ec_private_key()
        epk = header["epk"]
        ephem_pub = EllipticCurvePublicNumbers(
            int.from_bytes(_b64url_dec(epk["x"]), "big"),
            int.from_bytes(_b64url_dec(epk["y"]), "big"),
            SECP256R1(),
        ).public_key()
        shared = private_key.exchange(ECDH(), ephem_pub)
        cek = _concat_kdf(shared, "A256GCM", 256)
        iv = _b64url_dec(iv_b64)
        ct_tag = _b64url_dec(ct_b64) + _b64url_dec(tag_b64)
        plaintext = AESGCM(cek).decrypt(iv, ct_tag, header_b64.encode("ascii"))
    except LicenseError:
        raise
    except Exception as exc:
        raise LicenseError("INVALID_LICENSE_SIGNATURE", f"JWE decryption failed: {exc}") from exc

    try:
        data = json.loads(plaintext)
    except json.JSONDecodeError as exc:
        raise LicenseError("MALFORMED_LICENSE", f"JWE payload not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LicenseError("MALFORMED_LICENSE", "JWE payload must be a JSON object")
    return data


# ─── Format detection + unified entry ────────────────────────────────────────

def parse_lic_text(text: str) -> dict[str, Any]:
    """Accept JWE (Phase B), JSON (Phase A), and KV formats."""
    stripped = text.strip()
    if not stripped:
        raise LicenseError("MALFORMED_LICENSE", "empty license body")

    if _is_jwe_token(stripped):
        return parse_jwe_lic_text(stripped)

    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise LicenseError("MALFORMED_LICENSE", f"invalid json: {exc}") from exc
        if not isinstance(data, dict):
            raise LicenseError("MALFORMED_LICENSE", "license must be an object")
        # schemaVersion>=2 は AEAD 復号を通った証。平文で自称されても信用しない
        # (さもないと HMAC 検証を素通りさせ、任意ロールを偽造できてしまう)。
        # pop で除去 → HMAC 署名の canonical bytes を変えないため正規の署名済み lic に無影響。
        data.pop("schemaVersion", None)
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
    data.pop("schemaVersion", None)
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
    if role == "user":  # 旧 role 名の後方互換 (2026-06-02 リネーム)
        role = "licensee"
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
    # Phase B+: GCM authentication tag already verified at decrypt time
    if payload.raw.get("schemaVersion", 1) >= 2:
        return
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


# ─── Phase C: AES-256-GCM バイナリ ───────────────────────────────────────────
# フォーマット: magic(8B) + nonce(12B) + GCM ciphertext+tag(N+16B)
# magic を AAD として用いるため、magic 改変も tag 検証で検出できる。

_PHASE_C_MAGIC = b"ADMLIC\x01\x00"  # 8 bytes


def _load_phase_c_key() -> bytes:
    key_hex = get_settings().ADM_LIC_ENC_KEY
    if not key_hex:
        raise LicenseError("INVALID_LICENSE_FORMAT", "ADM_LIC_ENC_KEY not configured")
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise LicenseError("INVALID_LICENSE_FORMAT", f"ADM_LIC_ENC_KEY must be hex: {exc}") from exc
    if len(key) != 32:
        raise LicenseError("INVALID_LICENSE_FORMAT", "ADM_LIC_ENC_KEY must be 64 hex chars (256 bit)")
    return key


def issue_phase_c_license(data: dict[str, Any]) -> bytes:
    """JSON ペイロードを AES-256-GCM で暗号化して Phase C バイナリを返す。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _load_phase_c_key()
    nonce = os.urandom(12)
    plaintext = json.dumps({**data, "schemaVersion": 3}, separators=(",", ":")).encode()
    ct_tag = AESGCM(key).encrypt(nonce, plaintext, _PHASE_C_MAGIC)
    return _PHASE_C_MAGIC + nonce + ct_tag


def _parse_phase_c(raw: bytes) -> dict[str, Any]:
    """Phase C バイナリを復号してペイロード dict を返す。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(raw) < len(_PHASE_C_MAGIC) + 12 + 16:
        raise LicenseError("MALFORMED_LICENSE", "Phase C data too short")
    nonce = raw[8:20]
    ct_tag = raw[20:]
    key = _load_phase_c_key()
    try:
        plaintext = AESGCM(key).decrypt(nonce, ct_tag, _PHASE_C_MAGIC)
    except Exception as exc:
        raise LicenseError("INVALID_LICENSE_SIGNATURE", f"Phase C decryption failed: {exc}") from exc
    try:
        result = json.loads(plaintext)
    except json.JSONDecodeError as exc:
        raise LicenseError("MALFORMED_LICENSE", f"Phase C payload not valid JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise LicenseError("MALFORMED_LICENSE", "Phase C payload must be JSON object")
    return result


def parse_lic_bytes(raw: bytes) -> dict[str, Any]:
    """フォーマット統一エントリ: Phase C バイナリ / Phase B JWE / Phase A JSON・KV。"""
    if raw[:8] == _PHASE_C_MAGIC:
        return _parse_phase_c(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LicenseError(
            "INVALID_LICENSE_FORMAT",
            f"not UTF-8 and not Phase C binary: {exc}",
        ) from exc
    return parse_lic_text(text)
