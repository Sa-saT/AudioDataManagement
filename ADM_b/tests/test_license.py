"""security/license.py のユニットテスト。DB 不要。"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.security.license import (
    LicenseError,
    LicensePayload,
    _parse_iso8601,
    check_validity,
    compute_signature,
    parse_lic_text,
    validate_payload,
    verify_signature,
)

# ─── 共通フィクスチャ ──────────────────────────────────────────────────────────

VALID_DATA = {
    "username": "testuser",
    "role": "licensee",
    "licenseId": "lic-abc-123",
    "monthlyQuotaTokens": 3600,
    "issuedAt": "2026-01-01T00:00:00Z",
}


def _signed_data() -> dict:
    data = dict(VALID_DATA)
    data["signature"] = compute_signature(data)
    return data


# ─── parse_lic_text ────────────────────────────────────────────────────────────

class TestParseLicText:
    def test_json_format(self):
        text = json.dumps(VALID_DATA)
        result = parse_lic_text(text)
        assert result["username"] == "testuser"

    def test_kv_format(self):
        text = (
            "username=kvuser\n"
            "role=creator\n"
            "licenseId=lic-kv-001\n"
            "monthlyQuotaTokens=1800\n"
            "issuedAt=2026-01-01T00:00:00Z\n"
        )
        result = parse_lic_text(text)
        assert result["username"] == "kvuser"
        assert result["monthlyQuotaTokens"] == 1800  # int に変換済み

    def test_kv_comment_lines_ignored(self):
        text = "# comment\nusername=x\nrole=admin\nlicenseId=L1\nmonthlyQuotaTokens=100\nissuedAt=2026-01-01T00:00:00Z"
        result = parse_lic_text(text)
        assert result["username"] == "x"

    def test_empty_raises(self):
        with pytest.raises(LicenseError) as exc:
            parse_lic_text("")
        assert exc.value.code == "MALFORMED_LICENSE"

    def test_invalid_json_raises(self):
        with pytest.raises(LicenseError) as exc:
            parse_lic_text("{bad json")
        assert exc.value.code == "MALFORMED_LICENSE"

    def test_kv_invalid_line_raises(self):
        with pytest.raises(LicenseError) as exc:
            parse_lic_text("notakeyvalue")
        assert exc.value.code == "MALFORMED_LICENSE"


# ─── validate_payload ─────────────────────────────────────────────────────────

class TestValidatePayload:
    def test_valid(self):
        payload = validate_payload(dict(VALID_DATA))
        assert payload.username == "testuser"
        assert payload.role == "licensee"
        assert payload.monthly_quota_tokens == 3600
        assert payload.expires_at is None

    def test_old_role_user_renamed_to_licensee(self):
        data = {**VALID_DATA, "role": "user"}
        payload = validate_payload(data)
        assert payload.role == "licensee"

    def test_role_creator(self):
        payload = validate_payload({**VALID_DATA, "role": "creator"})
        assert payload.role == "creator"

    def test_role_admin(self):
        payload = validate_payload({**VALID_DATA, "role": "admin"})
        assert payload.role == "admin"

    def test_invalid_role_raises(self):
        with pytest.raises(LicenseError) as exc:
            validate_payload({**VALID_DATA, "role": "superuser"})
        assert exc.value.code == "MALFORMED_LICENSE"

    def test_missing_field_raises(self):
        data = dict(VALID_DATA)
        del data["monthlyQuotaTokens"]
        with pytest.raises(LicenseError) as exc:
            validate_payload(data)
        assert exc.value.code == "MALFORMED_LICENSE"

    def test_negative_quota_raises(self):
        with pytest.raises(LicenseError) as exc:
            validate_payload({**VALID_DATA, "monthlyQuotaTokens": -1})
        assert exc.value.code == "MALFORMED_LICENSE"

    def test_invalid_username_raises(self):
        with pytest.raises(LicenseError) as exc:
            validate_payload({**VALID_DATA, "username": "has space"})
        assert exc.value.code == "MALFORMED_LICENSE"

    def test_username_too_long_raises(self):
        with pytest.raises(LicenseError) as exc:
            validate_payload({**VALID_DATA, "username": "a" * 33})
        assert exc.value.code == "MALFORMED_LICENSE"

    def test_expires_at_parsed(self):
        data = {**VALID_DATA, "expiresAt": "2099-12-31T23:59:59Z"}
        payload = validate_payload(data)
        assert payload.expires_at is not None
        assert payload.expires_at.year == 2099


# ─── verify_signature ─────────────────────────────────────────────────────────

class TestVerifySignature:
    def test_correct_signature_passes(self):
        data = _signed_data()
        payload = validate_payload(data)
        verify_signature(payload)  # no raise

    def test_wrong_signature_raises(self):
        data = {**_signed_data(), "signature": "invalidsig"}
        payload = validate_payload(data)
        with pytest.raises(LicenseError) as exc:
            verify_signature(payload)
        assert exc.value.code == "INVALID_LICENSE_SIGNATURE"

    def test_missing_signature_require_true_raises(self):
        payload = validate_payload(dict(VALID_DATA))
        with pytest.raises(LicenseError) as exc:
            verify_signature(payload, require=True)
        assert exc.value.code == "INVALID_LICENSE_SIGNATURE"

    def test_missing_signature_require_false_passes(self):
        payload = validate_payload(dict(VALID_DATA))
        verify_signature(payload, require=False)  # no raise

    def test_schema_version_2_skips_hmac(self):
        """Phase B (JWE) は schemaVersion=2 で HMAC 検証をスキップする。"""
        data = {**VALID_DATA, "schemaVersion": 2}  # 署名なし
        payload = validate_payload(data)
        # schemaVersion が raw に含まれていれば verify_signature は素通り
        verify_signature(payload)  # no raise


# ─── check_validity ───────────────────────────────────────────────────────────

class TestCheckValidity:
    def _make_payload(self, expires_at=None) -> LicensePayload:
        data = dict(VALID_DATA)
        if expires_at:
            data["expiresAt"] = expires_at.isoformat()
        return validate_payload(data)

    def test_no_expiry_passes(self):
        payload = self._make_payload()
        check_validity(payload)  # no raise

    def test_future_expiry_passes(self):
        future = datetime.now(timezone.utc) + timedelta(days=365)
        payload = self._make_payload(expires_at=future)
        check_validity(payload)  # no raise

    def test_past_expiry_raises(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        payload = self._make_payload(expires_at=past)
        with pytest.raises(LicenseError) as exc:
            check_validity(payload)
        assert exc.value.code == "LICENSE_EXPIRED"

    def test_now_parameter_respected(self):
        """now= を渡すとその時刻を基準に判定する。"""
        expiry = datetime(2026, 6, 1, tzinfo=timezone.utc)
        payload = self._make_payload(expires_at=expiry)
        # expiry の前 → valid
        check_validity(payload, now=datetime(2026, 5, 31, tzinfo=timezone.utc))
        # expiry の後 → expired
        with pytest.raises(LicenseError):
            check_validity(payload, now=datetime(2026, 6, 2, tzinfo=timezone.utc))


# ─── _parse_iso8601 ───────────────────────────────────────────────────────────

class TestParseIso8601:
    def test_z_suffix(self):
        dt = _parse_iso8601("2026-01-01T00:00:00Z", "issuedAt")
        assert dt.tzinfo is not None
        assert dt.year == 2026

    def test_offset(self):
        dt = _parse_iso8601("2026-06-01T09:00:00+09:00", "issuedAt")
        assert dt.tzinfo is not None

    def test_invalid_raises(self):
        with pytest.raises(LicenseError) as exc:
            _parse_iso8601("not-a-date", "issuedAt")
        assert exc.value.code == "MALFORMED_LICENSE"
