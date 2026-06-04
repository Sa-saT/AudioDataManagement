"""Unit tests for the storage abstraction layer (LocalStorageBackend)."""
import uuid
from pathlib import Path

import pytest

from app.services.storage import (
    LocalStorageBackend,
    clear_storage_cache,
    copy_between_areas,
    downloads_storage,
    sounds_storage,
)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_storage_cache()
    yield
    clear_storage_cache()


@pytest.fixture()
def sounds_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sounds"
    d.mkdir()
    return d


@pytest.fixture()
def downloads_dir(tmp_path: Path) -> Path:
    d = tmp_path / "downloads"
    d.mkdir()
    return d


@pytest.fixture()
def wav(tmp_path: Path) -> Path:
    p = tmp_path / "src.wav"
    p.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")
    return p


class TestLocalStorageBackend:
    def test_put_and_exists(self, sounds_dir: Path, wav: Path):
        b = LocalStorageBackend(sounds_dir)
        key = "test.wav"
        assert not b.exists(key)
        b.put(key, wav)
        assert b.exists(key)
        assert (sounds_dir / key).read_bytes() == wav.read_bytes()

    def test_delete(self, sounds_dir: Path, wav: Path):
        b = LocalStorageBackend(sounds_dir)
        b.put("del.wav", wav)
        assert b.exists("del.wav")
        b.delete("del.wav")
        assert not b.exists("del.wav")

    def test_delete_nonexistent_does_not_raise(self, sounds_dir: Path):
        b = LocalStorageBackend(sounds_dir)
        b.delete("ghost.wav")  # should not raise

    def test_get_stream_source_returns_string_path(self, sounds_dir: Path, wav: Path):
        b = LocalStorageBackend(sounds_dir)
        b.put("a.wav", wav)
        src = b.get_stream_source("a.wav")
        assert isinstance(src, str)
        assert Path(src).exists()

    def test_get_download_url_returns_none(self, sounds_dir: Path):
        b = LocalStorageBackend(sounds_dir)
        assert b.get_download_url("any.wav") is None

    def test_local_path_returns_path(self, sounds_dir: Path):
        b = LocalStorageBackend(sounds_dir)
        p = b.local_path("x.wav")
        assert isinstance(p, Path)
        assert p == sounds_dir / "x.wav"

    def test_copy_object(self, sounds_dir: Path, wav: Path):
        b = LocalStorageBackend(sounds_dir)
        b.put("orig.wav", wav)
        b.copy_object("orig.wav", "copy.wav")
        assert b.exists("copy.wav")
        assert b.local_path("copy.wav").read_bytes() == wav.read_bytes()

    def test_nested_key_creates_parent_dir(self, sounds_dir: Path, wav: Path):
        b = LocalStorageBackend(sounds_dir)
        b.put("sub/dir/nested.wav", wav)
        assert (sounds_dir / "sub" / "dir" / "nested.wav").exists()

    def test_absolute_key_backward_compat(self, sounds_dir: Path, wav: Path):
        """旧レコード: DB に絶対パスが入っていても正しく解決できる。"""
        b = LocalStorageBackend(sounds_dir)
        b.put("new.wav", wav)
        abs_key = str(sounds_dir / "new.wav")
        assert b.exists(abs_key)
        assert b.get_stream_source(abs_key) == abs_key


class TestCopyBetweenAreas:
    def test_local_to_local(self, sounds_dir: Path, downloads_dir: Path, wav: Path):
        src = LocalStorageBackend(sounds_dir)
        dst = LocalStorageBackend(downloads_dir)
        src.put("audio.wav", wav)
        copy_between_areas(src, "audio.wav", dst, "user/audio.wav")
        assert dst.exists("user/audio.wav")

    def test_content_preserved(self, sounds_dir: Path, downloads_dir: Path, wav: Path):
        src = LocalStorageBackend(sounds_dir)
        dst = LocalStorageBackend(downloads_dir)
        src.put("a.wav", wav)
        copy_between_areas(src, "a.wav", dst, "copy.wav")
        assert dst.local_path("copy.wav").read_bytes() == wav.read_bytes()


class TestStorageFactories:
    def test_sounds_storage_cached(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "sounds"))
        monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "downloads"))
        monkeypatch.setenv("ORDERS_DIR", str(tmp_path / "orders"))
        clear_storage_cache()
        s1 = sounds_storage()
        s2 = sounds_storage()
        assert s1 is s2

    def test_clear_cache_rebuilds_backend(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "sounds"))
        monkeypatch.setenv("DOWNLOADS_DIR", str(tmp_path / "downloads"))
        monkeypatch.setenv("ORDERS_DIR", str(tmp_path / "orders"))
        clear_storage_cache()
        s1 = sounds_storage()
        clear_storage_cache()
        s2 = sounds_storage()
        assert s1 is not s2
