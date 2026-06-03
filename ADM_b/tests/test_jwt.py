"""security/jwt.py のユニットテスト。DB 不要。"""
import uuid
from datetime import datetime, timezone

import pytest

from app.security.jwt import TokenError, create_access_token, decode_token


def _ids():
    return uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


class TestJwtRoundtrip:
    def test_encode_decode(self):
        uid, lid, sid = _ids()
        token, expires = create_access_token(
            user_id=uid, role="licensee", license_id=lid, session_id=sid
        )
        assert isinstance(token, str)
        assert isinstance(expires, datetime)

        payload = decode_token(token)
        assert payload["sub"] == str(uid)
        assert payload["role"] == "licensee"
        assert payload["license_id"] == str(lid)
        assert payload["sid"] == str(sid)

    def test_roles(self):
        for role in ("licensee", "creator", "admin"):
            uid, lid, sid = _ids()
            token, _ = create_access_token(user_id=uid, role=role, license_id=lid, session_id=sid)
            payload = decode_token(token)
            assert payload["role"] == role

    def test_exp_claim_present(self):
        uid, lid, sid = _ids()
        token, expires = create_access_token(
            user_id=uid, role="admin", license_id=lid, session_id=sid
        )
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload
        # expires は UTC で今より未来
        assert expires > datetime.now(timezone.utc)

    def test_invalid_token_raises(self):
        with pytest.raises(TokenError):
            decode_token("not.a.valid.jwt.token")

    def test_tampered_token_raises(self):
        uid, lid, sid = _ids()
        token, _ = create_access_token(
            user_id=uid, role="licensee", license_id=lid, session_id=sid
        )
        # 末尾 1 文字を改変
        tampered = token[:-1] + ("X" if token[-1] != "X" else "Y")
        with pytest.raises(TokenError):
            decode_token(tampered)

    def test_wrong_secret_raises(self, monkeypatch):
        """別の秘密鍵で署名されたトークンは検証失敗する。"""
        uid, lid, sid = _ids()
        token, _ = create_access_token(
            user_id=uid, role="licensee", license_id=lid, session_id=sid
        )
        # 秘密鍵を差し替えて decode → 署名不一致
        from app.security import jwt as jwt_mod
        original_secret = jwt_mod.settings.JWT_SECRET
        object.__setattr__(jwt_mod.settings, "JWT_SECRET", "different-secret-32chars!!!!!!")
        try:
            with pytest.raises(TokenError):
                decode_token(token)
        finally:
            object.__setattr__(jwt_mod.settings, "JWT_SECRET", original_secret)
