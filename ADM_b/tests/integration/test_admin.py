"""/api/v1/admin/* エンドポイントのロール制御・基本動作テスト。"""
import pytest

from tests.integration.conftest import make_lic


def activate(client, lic_text: str) -> tuple[int, dict]:
    resp = client.post("/api/v1/auth/activate", json={"lic": lic_text})
    return resp.status_code, resp.json()


def token_for(client, *, username: str, role: str, license_id: str | None = None) -> str:
    lic = make_lic(username=username, role=role, license_id=license_id or f"lic-{username}")
    status, body = activate(client, lic)
    assert status == 200, f"activate failed: {body}"
    return body["access_token"]


def user_id_for(client, *, username: str, role: str, license_id: str | None = None) -> tuple[str, str]:
    """(user_id, access_token) を返す。"""
    lic = make_lic(username=username, role=role, license_id=license_id or f"lic-{username}")
    status, body = activate(client, lic)
    assert status == 200
    return body["user"]["id"], body["access_token"]


# ─── GET /admin/users ─────────────────────────────────────────────────────────

class TestAdminListUsers:
    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == 401

    def test_licensee_returns_403(self, client):
        token = token_for(client, username="adm_lic", role="licensee", license_id="lic-admlic")
        resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_creator_returns_403(self, client):
        token = token_for(client, username="adm_cr", role="creator", license_id="lic-admcr")
        resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_admin_returns_200_list(self, client):
        """admin は全ユーザ一覧を取得できる。"""
        token = token_for(client, username="adm_ok", role="admin", license_id="lic-admok")
        resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_admin_list_includes_activated_user(self, client):
        """activate した licensee が一覧に含まれる。"""
        adm_token = token_for(client, username="adm_list", role="admin", license_id="lic-admlist")
        # 別ユーザを activate
        token_for(client, username="target_user", role="licensee", license_id="lic-target")

        resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {adm_token}"})
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "target_user" in usernames


# ─── PATCH /admin/users/{id}/group ───────────────────────────────────────────

class TestAdminUpdateGroup:
    def test_licensee_returns_403(self, client):
        import uuid
        token = token_for(client, username="grp_lic", role="licensee", license_id="lic-grplic")
        resp = client.patch(
            f"/api/v1/admin/users/{uuid.uuid4()}/group",
            json={"group_name": "teamA"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_admin_can_update_group(self, client):
        adm_token = token_for(client, username="grp_adm", role="admin", license_id="lic-grpadm")
        uid, _ = user_id_for(client, username="grp_target", role="licensee", license_id="lic-grptgt")

        resp = client.patch(
            f"/api/v1/admin/users/{uid}/group",
            json={"group_name": "teamB"},
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["group_name"] == "teamB"

    def test_admin_can_clear_group(self, client):
        adm_token = token_for(client, username="grp_clr", role="admin", license_id="lic-grpclr")
        uid, _ = user_id_for(client, username="grp_clrt", role="licensee", license_id="lic-grpclrt")

        client.patch(
            f"/api/v1/admin/users/{uid}/group",
            json={"group_name": "initial"},
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        resp = client.patch(
            f"/api/v1/admin/users/{uid}/group",
            json={"group_name": None},
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["group_name"] is None


# ─── PATCH /admin/creators/{id}/rank ─────────────────────────────────────────

class TestAdminUpdateRank:
    def test_licensee_returns_403(self, client):
        import uuid
        token = token_for(client, username="rnk_lic", role="licensee", license_id="lic-rnklic")
        resp = client.patch(
            f"/api/v1/admin/creators/{uuid.uuid4()}/rank",
            json={"rank": "silver"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_admin_rank_nonexistent_creator_returns_404(self, client):
        import uuid
        token = token_for(client, username="rnk_adm", role="admin", license_id="lic-rnkadm")
        resp = client.patch(
            f"/api/v1/admin/creators/{uuid.uuid4()}/rank",
            json={"rank": "silver"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


# ─── POST /admin/token-grants ─────────────────────────────────────────────────

class TestAdminTokenGrants:
    def test_creator_returns_403(self, client):
        token = token_for(client, username="tkg_cr", role="creator", license_id="lic-tkgcr")
        resp = client.post(
            "/api/v1/admin/token-grants",
            json={"user_id": "00000000-0000-0000-0000-000000000000", "tokens": 100},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_admin_nonexistent_user_returns_404(self, client):
        import uuid
        token = token_for(client, username="tkg_adm", role="admin", license_id="lic-tkgadm")
        resp = client.post(
            "/api/v1/admin/token-grants",
            json={"user_id": str(uuid.uuid4()), "tokens": 100},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_admin_can_grant_tokens(self, client):
        adm_token = token_for(client, username="tkg_adm2", role="admin", license_id="lic-tkgadm2")
        uid, _ = user_id_for(client, username="tkg_target", role="licensee", license_id="lic-tkgtgt")

        resp = client.post(
            "/api/v1/admin/token-grants",
            json={"user_id": uid, "tokens": 500},
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["tokens"] == 500


# ─── POST /admin/licenses ─────────────────────────────────────────────────────

class TestAdminIssueLicense:
    def test_licensee_returns_403(self, client):
        token = token_for(client, username="iss_lic", role="licensee", license_id="lic-isslic")
        resp = client.post(
            "/api/v1/admin/licenses",
            json={"username": "newuser", "role": "licensee", "monthly_quota_tokens": 3600},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_admin_issues_lic_file(self, client):
        """admin は .lic ファイルをダウンロードできる。"""
        token = token_for(client, username="iss_adm", role="admin", license_id="lic-issadm")
        resp = client.post(
            "/api/v1/admin/licenses",
            json={"username": "newuser", "role": "licensee", "monthly_quota_tokens": 3600},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Response() を直接返す場合 decorator の status_code=201 より Response のデフォルト 200 が優先される
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/octet-stream"
        assert "newuser.lic" in resp.headers.get("content-disposition", "")
        assert len(resp.content) > 0

    def test_admin_invalid_role_returns_400(self, client):
        token = token_for(client, username="iss_adm2", role="admin", license_id="lic-issadm2")
        resp = client.post(
            "/api/v1/admin/licenses",
            json={"username": "x", "role": "superuser", "monthly_quota_tokens": 100},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (400, 422)
