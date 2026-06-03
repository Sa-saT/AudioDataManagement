"""/api/v1/audios 認可境界テスト。実ファイルを使うアップロード正常系は除外。"""
import pytest

from tests.integration.conftest import make_lic


def token_for(client, *, username: str, role: str, license_id: str | None = None) -> str:
    lic = make_lic(username=username, role=role, license_id=license_id or f"lic-{username}")
    resp = client.post("/api/v1/auth/activate", json={"lic": lic})
    assert resp.status_code == 200, f"activate failed: {resp.json()}"
    return resp.json()["access_token"]


# ─── 公開エンドポイント (認証不要) ───────────────────────────────────────────────

class TestPublicEndpoints:
    def test_list_audios_no_auth_returns_200(self, client):
        resp = client.get("/api/v1/audios")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body

    def test_list_audios_with_auth_returns_200(self, client):
        token = token_for(client, username="aud_list", role="licensee")
        resp = client.get("/api/v1/audios", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_tags_returns_200(self, client):
        resp = client.get("/api/v1/audios/tags")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_nonexistent_audio_returns_404(self, client):
        import uuid
        resp = client.get(f"/api/v1/audios/{uuid.uuid4()}")
        assert resp.status_code == 404


# ─── upload (POST /audios) 認可 ─────────────────────────────────────────────

class TestUploadAuth:
    def test_upload_no_auth_returns_401(self, client):
        resp = client.post("/api/v1/audios", data={"title": "test"})
        assert resp.status_code == 401

    def test_upload_licensee_returns_403(self, client):
        """licensee は creator/admin 専用エンドポイントに 403。"""
        token = token_for(client, username="lic_up", role="licensee", license_id="lic-licup")
        resp = client.post(
            "/api/v1/audios",
            headers={"Authorization": f"Bearer {token}"},
            data={"title": "test"},
            files={"file": ("test.wav", b"RIFF\x00\x00\x00\x00WAVE", "audio/wav")},
        )
        assert resp.status_code == 403


# ─── update / delete 認可 ────────────────────────────────────────────────────

class TestAudioMutationAuth:
    def test_update_no_auth_returns_401(self, client):
        import uuid
        resp = client.put(f"/api/v1/audios/{uuid.uuid4()}", json={"title": "x"})
        assert resp.status_code == 401

    def test_delete_no_auth_returns_401(self, client):
        import uuid
        resp = client.delete(f"/api/v1/audios/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_update_licensee_returns_403(self, client):
        import uuid
        token = token_for(client, username="lic_upd", role="licensee", license_id="lic-licupd")
        resp = client.put(
            f"/api/v1/audios/{uuid.uuid4()}",
            json={"title": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_delete_licensee_returns_403(self, client):
        import uuid
        token = token_for(client, username="lic_del", role="licensee", license_id="lic-licdel")
        resp = client.delete(
            f"/api/v1/audios/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ─── favorite 認可 ───────────────────────────────────────────────────────────

class TestFavoriteAuth:
    def test_favorite_no_auth_returns_401(self, client):
        import uuid
        resp = client.post(f"/api/v1/audios/{uuid.uuid4()}/favorite")
        assert resp.status_code == 401

    def test_favorite_licensee_returns_404_not_403(self, client):
        """licensee は favorite 操作可。存在しない ID → 404。"""
        import uuid
        token = token_for(client, username="lic_fav", role="licensee", license_id="lic-licfav")
        resp = client.post(
            f"/api/v1/audios/{uuid.uuid4()}/favorite",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


# ─── download 認可 ───────────────────────────────────────────────────────────

class TestDownloadAuth:
    def test_download_no_auth_returns_401(self, client):
        import uuid
        resp = client.post(f"/api/v1/audios/{uuid.uuid4()}/download")
        assert resp.status_code == 401

    def test_download_nonexistent_returns_404(self, client):
        import uuid
        token = token_for(client, username="lic_dl", role="licensee", license_id="lic-licdl")
        resp = client.post(
            f"/api/v1/audios/{uuid.uuid4()}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
