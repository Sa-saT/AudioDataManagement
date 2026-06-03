"""/api/v1/auth/activate + 単一セッション制 (B案) の統合テスト。"""
import json

import pytest

from tests.integration.conftest import make_lic, make_phase_c_lic


# ─── ヘルパー ────────────────────────────────────────────────────────────────

def activate(client, lic_text: str) -> tuple[int, dict]:
    """JSON body {"lic": "<lic_text>"} 形式で /activate を呼ぶ。"""
    resp = client.post(
        "/api/v1/auth/activate",
        json={"lic": lic_text},
    )
    return resp.status_code, resp.json()


def ping(client, token: str) -> int:
    """session/ping でトークンの有効性を確認する。201/204 = 有効、401 = 無効。"""
    resp = client.post(
        "/api/v1/me/session/ping",
        headers={"Authorization": f"Bearer {token}"},
    )
    # ping は新規記録時 201, dedup 時 204, 認証失敗時 401
    return 200 if resp.status_code in (201, 204) else resp.status_code


# ─── 正常系: 各ロール ─────────────────────────────────────────────────────────

class TestActivateSuccess:
    def test_licensee(self, client):
        status, body = activate(client, make_lic(username="lic01", role="licensee"))
        assert status == 200
        assert body["user"]["role"] == "licensee"
        assert body["user"]["username"] == "lic01"
        assert "access_token" in body

    def test_creator(self, client):
        status, body = activate(client, make_lic(username="cr01", role="creator", license_id="lic-cr-01"))
        assert status == 200
        assert body["user"]["role"] == "creator"

    def test_admin(self, client):
        status, body = activate(client, make_lic(username="adm01", role="admin", license_id="lic-adm-01"))
        assert status == 200
        assert body["user"]["role"] == "admin"

    def test_old_role_user_accepted_as_licensee(self, client):
        """旧 role='user' は licensee として受け入れる (後方互換)。"""
        lic = make_lic(username="olduser", role="user", license_id="lic-old-01")
        status, body = activate(client, lic)
        assert status == 200
        assert body["user"]["role"] == "licensee"

    def test_no_expiry_lic(self, client):
        lic = make_lic(username="noexp", license_id="lic-noexp", expires_at=None)
        status, body = activate(client, lic)
        assert status == 200

    def test_future_expiry_lic(self, client):
        lic = make_lic(username="futexp", license_id="lic-fut", expires_at="2099-12-31T23:59:59Z")
        status, body = activate(client, lic)
        assert status == 200

    def test_activate_returns_monthly_quota(self, client):
        lic = make_lic(username="quota01", license_id="lic-quota", monthly_quota_tokens=7200)
        status, body = activate(client, lic)
        assert status == 200
        assert body["user"]["monthly_quota_tokens"] == 7200

    def test_second_activate_same_lic_returns_same_user_id(self, client):
        """同一 .lic で 2 回 activate → ユーザ ID は同じ / トークンは別。"""
        lic = make_lic(username="reactivate", license_id="lic-rea")
        s1, b1 = activate(client, lic)
        s2, b2 = activate(client, lic)
        assert s1 == 200
        assert s2 == 200
        assert b1["user"]["id"] == b2["user"]["id"]
        assert b1["access_token"] != b2["access_token"]


# ─── 異常系: ライセンス検証 ───────────────────────────────────────────────────

class TestActivateFailure:
    def test_expired_lic_returns_401(self, client):
        lic = make_lic(username="expu", license_id="lic-exp", expires_at="2020-01-01T00:00:00Z")
        status, body = activate(client, lic)
        assert status == 401
        assert body["detail"]["code"] == "LICENSE_EXPIRED"

    def test_invalid_signature_returns_401(self, client):
        data = {
            "username": "badsig",
            "role": "licensee",
            "licenseId": "lic-badsig",
            "monthlyQuotaTokens": 100,
            "issuedAt": "2026-01-01T00:00:00Z",
            "signature": "invalidsignature",
        }
        status, body = activate(client, json.dumps(data))
        assert status == 401
        assert body["detail"]["code"] == "INVALID_LICENSE_SIGNATURE"

    def test_unsigned_lic_returns_401(self, client):
        """署名なし (require=True) → INVALID_LICENSE_SIGNATURE → 401。"""
        lic = make_lic(username="nosig", license_id="lic-nosig", sign=False)
        status, body = activate(client, lic)
        assert status == 401
        assert body["detail"]["code"] == "INVALID_LICENSE_SIGNATURE"

    def test_missing_required_field_returns_400(self, client):
        """必須フィールド欠如 → MALFORMED_LICENSE → 400。"""
        status, body = activate(client, json.dumps({"username": "nofields"}))
        assert status == 400
        assert body["detail"]["code"] == "MALFORMED_LICENSE"

    def test_empty_lic_returns_400(self, client):
        status, body = activate(client, "")
        assert status == 400

    def test_no_body_returns_4xx(self, client):
        """body なし → Content-Type 不一致で独自 400 エラー。"""
        resp = client.post("/api/v1/auth/activate")
        assert resp.status_code in (400, 422)


# ─── 単一セッション制 (B案) ──────────────────────────────────────────────────

class TestSingleSession:
    def test_old_token_invalidated_after_reactivate(self, client):
        """同じ .lic で 2 台目が activate → 1 台目のトークンは SESSION_INVALIDATED になる。"""
        lic = make_lic(username="session_test", license_id="lic-ses")

        # 1 台目: activate
        _, b1 = activate(client, lic)
        token1 = b1["access_token"]

        # 2 台目: 同じ .lic で再 activate → DB の current_session_id が更新される
        activate(client, lic)

        # 1 台目トークンで ping → SESSION_INVALIDATED
        resp = client.post(
            "/api/v1/me/session/ping",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "SESSION_INVALIDATED"

    def test_new_token_valid_after_reactivate(self, client):
        """2 台目のトークンは 2 台目 activate 後も有効。"""
        lic = make_lic(username="session_ok", license_id="lic-sesok")
        activate(client, lic)
        _, b2 = activate(client, lic)
        token2 = b2["access_token"]
        assert ping(client, token2) == 200

    def test_token_valid_before_reactivate(self, client):
        """最初の activate 直後はトークンが有効。"""
        lic = make_lic(username="tok_valid", license_id="lic-tv")
        _, body = activate(client, lic)
        assert ping(client, body["access_token"]) == 200

    def test_no_token_returns_401(self, client):
        """認証不要エンドポイント以外はトークンなしで 401。"""
        resp = client.post("/api/v1/me/session/ping")
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "NOT_AUTHENTICATED"


# ─── Phase C バイナリ .lic ────────────────────────────────────────────────────

class TestPhaseCActivate:
    def test_phase_c_lic_via_file_upload(self, client):
        """Phase C バイナリ .lic をマルチパートでアップロード → 200 & 正しいユーザ情報。"""
        raw = make_phase_c_lic(username="phc01", license_id="lic-phc-01", monthly_quota_tokens=5000)
        resp = client.post(
            "/api/v1/auth/activate",
            files={"file": ("phc01.lic", raw, "application/octet-stream")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user"]["username"] == "phc01"
        assert body["user"]["role"] == "licensee"
        assert body["user"]["monthly_quota_tokens"] == 5000
        assert "access_token" in body

    def test_phase_c_creator_role(self, client):
        raw = make_phase_c_lic(username="phc_cr", role="creator", license_id="lic-phc-cr")
        resp = client.post(
            "/api/v1/auth/activate",
            files={"file": ("phc_cr.lic", raw, "application/octet-stream")},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "creator"

    def test_phase_c_tampered_returns_401(self, client):
        """改ざんされた Phase C .lic → GCM tag 不一致 → 401 INVALID_LICENSE_SIGNATURE。"""
        raw = make_phase_c_lic(username="phc_bad", license_id="lic-phc-bad")
        tampered = bytearray(raw)
        tampered[20] ^= 0xFF  # 暗号文先頭バイトを反転
        resp = client.post(
            "/api/v1/auth/activate",
            files={"file": ("bad.lic", bytes(tampered), "application/octet-stream")},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "INVALID_LICENSE_SIGNATURE"

    def test_phase_c_expired_returns_401(self, client):
        """期限切れ Phase C .lic → 401 LICENSE_EXPIRED。"""
        raw = make_phase_c_lic(
            username="phc_exp", license_id="lic-phc-exp", expires_at="2020-01-01T00:00:00Z"
        )
        resp = client.post(
            "/api/v1/auth/activate",
            files={"file": ("exp.lic", raw, "application/octet-stream")},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "LICENSE_EXPIRED"
