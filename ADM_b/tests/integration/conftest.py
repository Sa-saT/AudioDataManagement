"""統合テスト共通フィクスチャ。
- adm_test DB を使用 (本番 adm_dev とは別)
- 各テストをトランザクション内で実行し、終了後にロールバック → テスト間の分離を保証
- get_db を override し、テスト用セッションを FastAPI ハンドラに注入する
"""
import json
import os

# DB_NAME を adm_test に向けてから app モジュールを import する。
# conftest は pytest が最初に解釈するため、app.db の engine がこの値で初期化される。
os.environ["DB_NAME"] = "adm_test"
# unit conftest.py が ADM_LIC_ENC_KEY を設定しているが念のため統合テスト側でも保証
if "ADM_LIC_ENC_KEY" not in os.environ:
    os.environ["ADM_LIC_ENC_KEY"] = "00" * 32

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.security.license import compute_signature, issue_phase_c_license

# lru_cache をクリアして DB_NAME=adm_test を反映
get_settings.cache_clear()
_settings = get_settings()

# テスト用エンジン (adm_app ロール / adm_test DB)
_TEST_ENGINE = create_engine(
    _settings.app_database_url,
    pool_pre_ping=True,
    future=True,
)


# ─── DB フィクスチャ ──────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db_conn():
    """テスト用コネクション。外側トランザクションを貼り、終了後ロールバック。"""
    conn = _TEST_ENGINE.connect()
    conn.begin()
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture(scope="function")
def db(db_conn):
    """TestClient に注入するセッション。db_conn と同じコネクションを共有する。
    SQLAlchemy 2.x では Session(bind=conn) で外側トランザクションに参加し、
    handler 内の session.commit() はセッションをフラッシュするが
    コネクション側トランザクションはロールバックされずに残る。"""
    session = Session(bind=db_conn)
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db):
    """override_get_db 付き TestClient。"""
    from app.db import get_db
    from app.main import app

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    # TestClient を context manager で使うと lifespan が走る。
    # lifespan の _cleanup_stale_drafts_internal は SessionLocal() を直接使うが、
    # DB_NAME=adm_test なので adm_test に接続して安全。
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ─── .lic ファクトリ ──────────────────────────────────────────────────────────

def make_lic(
    *,
    username: str = "testuser",
    role: str = "licensee",
    license_id: str = "test-lic-001",
    monthly_quota_tokens: int = 3600,
    issued_at: str = "2026-01-01T00:00:00Z",
    expires_at: str | None = None,
    sign: bool = True,
) -> str:
    """テスト用 JSON .lic 文字列を生成する。sign=True で HMAC 署名を付与。"""
    data: dict = {
        "username": username,
        "role": role,
        "licenseId": license_id,
        "monthlyQuotaTokens": monthly_quota_tokens,
        "issuedAt": issued_at,
    }
    if expires_at:
        data["expiresAt"] = expires_at
    if sign:
        data["signature"] = compute_signature(data)
    return json.dumps(data)


def make_phase_c_lic(
    *,
    username: str = "testuser",
    role: str = "licensee",
    license_id: str = "test-phc-001",
    monthly_quota_tokens: int = 3600,
    issued_at: str = "2026-01-01T00:00:00Z",
    expires_at: str | None = None,
) -> bytes:
    """テスト用 Phase C バイナリ .lic を生成する。"""
    data: dict = {
        "username": username,
        "role": role,
        "licenseId": license_id,
        "monthlyQuotaTokens": monthly_quota_tokens,
        "issuedAt": issued_at,
    }
    if expires_at:
        data["expiresAt"] = expires_at
    return issue_phase_c_license(data)


@pytest.fixture
def lic_factory():
    return make_lic
