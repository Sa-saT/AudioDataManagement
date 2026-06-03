"""テスト共通設定。DB 不要なユニットテスト向け。
conftest は pytest が最初に読み込む — env 上書き後に lru_cache を破棄することで
app モジュールがテスト用秘密鍵を掴む。
"""
import os

os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-chars!!"
os.environ["LICENSE_SECRET"] = "test-license-secret"
os.environ["ADM_LIC_EC_PRIVATE_KEY"] = ""
os.environ["DB_APP_PASSWORD"] = "test"
os.environ["DB_MIGRATOR_PASSWORD"] = "test"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()
