"""/api/v1/me/* エンドポイントの認可・レスポンス形式テスト。"""
import pytest

from tests.integration.conftest import make_lic


def token_for(client, *, username: str, role: str, license_id: str | None = None) -> str:
    lic = make_lic(username=username, role=role, license_id=license_id or f"lic-{username}")
    resp = client.post("/api/v1/auth/activate", json={"lic": lic})
    assert resp.status_code == 200, f"activate failed: {resp.json()}"
    return resp.json()["access_token"]


# ─── notifications ────────────────────────────────────────────────────────────

class TestNotifications:
    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/v1/me/notifications")
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "NOT_AUTHENTICATED"

    def test_licensee_returns_200(self, client):
        token = token_for(client, username="notif_lic", role="licensee", license_id="lic-notif")
        resp = client.get("/api/v1/me/notifications", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert "areas" in body
        assert "totals" in body
        assert "action_count" in body["totals"]
        assert "has_info" in body["totals"]

    def test_creator_returns_200(self, client):
        token = token_for(client, username="notif_cr", role="creator", license_id="lic-notif-cr")
        resp = client.get("/api/v1/me/notifications", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_admin_returns_200(self, client):
        token = token_for(client, username="notif_adm", role="admin", license_id="lic-notif-adm")
        resp = client.get("/api/v1/me/notifications", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_fresh_user_has_zero_action_count(self, client):
        """新規ユーザはアクション要対応なし。"""
        token = token_for(client, username="notif_zero", role="licensee", license_id="lic-nz")
        resp = client.get("/api/v1/me/notifications", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["totals"]["action_count"] == 0


# ─── downloads ────────────────────────────────────────────────────────────────

class TestMyDownloads:
    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/v1/me/downloads")
        assert resp.status_code == 401

    def test_licensee_returns_200_empty(self, client):
        """DL 実績なし licensee → 空リスト。"""
        token = token_for(client, username="dl_lic", role="licensee", license_id="lic-dl")
        resp = client.get("/api/v1/me/downloads", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert body["items"] == []
        assert body["storage_used_bytes"] == 0

    def test_creator_returns_200(self, client):
        token = token_for(client, username="dl_cr", role="creator", license_id="lic-dl-cr")
        resp = client.get("/api/v1/me/downloads", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_delete_nonexistent_returns_404(self, client):
        """存在しない DL の削除 → 404。"""
        import uuid
        token = token_for(client, username="dl_del", role="licensee", license_id="lic-dldel")
        resp = client.delete(
            f"/api/v1/me/downloads/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_delete_no_auth_returns_401(self, client):
        import uuid
        resp = client.delete(f"/api/v1/me/downloads/{uuid.uuid4()}")
        assert resp.status_code == 401


# ─── session/ping (already covered in test_auth.py; 最小確認のみ) ─────────────

class TestSessionPingBasic:
    def test_ping_no_auth_returns_401(self, client):
        resp = client.post("/api/v1/me/session/ping")
        assert resp.status_code == 401

    def test_ping_with_valid_token(self, client):
        token = token_for(client, username="ping_me", role="licensee", license_id="lic-ping")
        resp = client.post(
            "/api/v1/me/session/ping",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (201, 204)
