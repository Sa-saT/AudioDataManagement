"""ストレージ抽象化レイヤー。

STORAGE_BACKEND=local  → LocalStorageBackend (ファイルシステム)
STORAGE_BACKEND=s3     → S3StorageBackend    (Cloudflare R2 / AWS S3 互換)

各エリア別ファクトリ:
  sounds_storage()    → 音源原本   (STORAGE_DIR / S3 prefix "sounds/")
  downloads_storage() → ユーザ DL コピー (DOWNLOADS_DIR / S3 prefix "downloads/")
  orders_storage()    → Commission 納品 (ORDERS_DIR / S3 prefix "orders/")

file_path / attachment_path カラムには area-relative キーを保存する:
  例) sounds:    "3f2a1b....wav"
      downloads: "{user_id}/3f2a1b....wav"
      orders:    "finals/{order_id}.wav"
               "submissions/{order_id}_v2.wav"

旧レコード (絶対パス) は LocalStorageBackend が透過的に処理する。
"""
from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings

# ─── 抽象基底クラス ───────────────────────────────────────────────────────────

class StorageBackend(ABC):
    @abstractmethod
    def put(self, key: str, src: Path) -> None:
        """src ファイルを key として保存する。"""

    @abstractmethod
    def delete(self, key: str) -> None:
        """key のファイルを削除する (存在しなければ無視)。"""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """key が存在するか確認する。"""

    @abstractmethod
    def get_stream_source(self, key: str, ttl_seconds: int = 30) -> str:
        """ffmpeg の -i に渡せる文字列を返す。
        local: ローカルパス文字列 / S3: 署名付き HTTPS URL。
        """

    @abstractmethod
    def get_download_url(self, key: str, ttl_seconds: int = 60) -> str | None:
        """ダウンロード用 URL を返す。
        local: None (呼び出し側で FileResponse を返す)
        S3:    署名付き URL (呼び出し側で RedirectResponse を返す)
        """

    @abstractmethod
    def local_path(self, key: str) -> Path | None:
        """ローカルバックエンドなら Path を返す。S3 なら None。"""

    @abstractmethod
    def copy_object(self, src_key: str, dst_key: str) -> None:
        """同一バックエンド内でファイルをコピーする (S3: CopyObject, local: shutil.copy2)。"""


# ─── LocalStorageBackend ──────────────────────────────────────────────────────

class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def _path(self, key: str) -> Path:
        p = Path(key)
        if p.is_absolute():
            # 旧レコード: DB に絶対パスが格納されている場合の後方互換
            return p
        return self._base / key

    def put(self, key: str, src: Path) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def get_stream_source(self, key: str, ttl_seconds: int = 30) -> str:
        return str(self._path(key))

    def get_download_url(self, key: str, ttl_seconds: int = 60) -> str | None:
        return None  # 呼び出し側で FileResponse を使う

    def local_path(self, key: str) -> Path | None:
        return self._path(key)

    def copy_object(self, src_key: str, dst_key: str) -> None:
        src = self._path(src_key)
        dst = self._path(dst_key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


# ─── S3StorageBackend ─────────────────────────────────────────────────────────

class S3StorageBackend(StorageBackend):
    """Cloudflare R2 / AWS S3 互換バックエンド。

    prefix を設定することで同一バケット内でエリアを分離する。
    例) sounds_storage → prefix="sounds" → キー "abc.wav" → S3 key "sounds/abc.wav"
    """

    def __init__(
        self,
        bucket: str,
        prefix: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "auto",
    ) -> None:
        import boto3
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    def _s3_key(self, key: str) -> str:
        return f"{self._prefix}/{key}" if self._prefix else key

    def put(self, key: str, src: Path) -> None:
        self._client.upload_file(str(src), self._bucket, self._s3_key(key))

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=self._s3_key(key))
        except Exception:
            pass  # 存在しないキーは無視

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._s3_key(key))
            return True
        except Exception:
            return False

    def get_stream_source(self, key: str, ttl_seconds: int = 30) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": self._s3_key(key)},
            ExpiresIn=ttl_seconds,
        )

    def get_download_url(self, key: str, ttl_seconds: int = 60) -> str | None:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": self._s3_key(key)},
            ExpiresIn=ttl_seconds,
        )

    def local_path(self, key: str) -> Path | None:
        return None

    def copy_object(self, src_key: str, dst_key: str) -> None:
        copy_src = {"Bucket": self._bucket, "Key": self._s3_key(src_key)}
        self._client.copy_object(
            CopySource=copy_src,
            Bucket=self._bucket,
            Key=self._s3_key(dst_key),
        )


# ─── ファクトリ ───────────────────────────────────────────────────────────────

_cache: dict[str, StorageBackend] = {}


def _build_backend(area: str) -> StorageBackend:
    s = get_settings()
    if s.STORAGE_BACKEND == "s3":
        return S3StorageBackend(
            bucket=s.S3_BUCKET,
            prefix=area,
            endpoint_url=s.S3_ENDPOINT_URL,
            access_key_id=s.S3_ACCESS_KEY_ID,
            secret_access_key=s.S3_SECRET_ACCESS_KEY,
            region=s.S3_REGION,
        )
    local_dirs = {
        "sounds": Path(s.STORAGE_DIR),
        "downloads": Path(s.DOWNLOADS_DIR),
        "orders": Path(s.ORDERS_DIR),
    }
    return LocalStorageBackend(local_dirs[area])


def _get(area: str) -> StorageBackend:
    if area not in _cache:
        _cache[area] = _build_backend(area)
    return _cache[area]


def sounds_storage() -> StorageBackend:
    """音源原本ストレージ。キー例: "{audio_id}.wav"。"""
    return _get("sounds")


def downloads_storage() -> StorageBackend:
    """ユーザ DL コピーストレージ。キー例: "{user_id}/{audio_id}.wav"。"""
    return _get("downloads")


def orders_storage() -> StorageBackend:
    """Commission 納品ストレージ。キー例: "submissions/{order_id}_v2.wav"。"""
    return _get("orders")


def clear_storage_cache() -> None:
    """テスト・設定変更後にバックエンドを再生成させる。"""
    _cache.clear()


def copy_between_areas(
    src: StorageBackend, src_key: str,
    dst: StorageBackend, dst_key: str,
) -> None:
    """異なるエリア間でファイルをコピーする。
    local→local/S3: src の local_path を dst.put() で転送。
    S3→S3: 同一バケット内で CopyObject (ダウンロード不要)。
    """
    src_local = src.local_path(src_key)
    if src_local is not None:
        dst.put(dst_key, src_local)
    elif isinstance(src, S3StorageBackend) and isinstance(dst, S3StorageBackend):
        copy_src = {"Bucket": src._bucket, "Key": src._s3_key(src_key)}
        dst._client.copy_object(CopySource=copy_src, Bucket=dst._bucket, Key=dst._s3_key(dst_key))
    else:
        raise ValueError("Cannot copy between incompatible backends")
