"""Audio file processing: ffprobe validation, peaks extraction, storage."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import get_settings

settings = get_settings()

_PCM_CODECS = {
    "pcm_s8", "pcm_u8",
    "pcm_s16le", "pcm_s16be",
    "pcm_s24le", "pcm_s24be",
    "pcm_s32le", "pcm_s32be",
    "pcm_f32le", "pcm_f32be",
    "pcm_f64le", "pcm_f64be",
}

_CODEC_BIT_DEPTH: dict[str, int] = {
    "pcm_s8": 8, "pcm_u8": 8,
    "pcm_s16le": 16, "pcm_s16be": 16,
    "pcm_s24le": 24, "pcm_s24be": 24,
    "pcm_s32le": 32, "pcm_s32be": 32,
    "pcm_f32le": 32, "pcm_f32be": 32,
    "pcm_f64le": 64, "pcm_f64be": 64,
}


class AudioFileError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AudioMeta:
    codec_name: str
    sample_rate: int
    bit_depth: int
    channels: int
    duration_sec: int


def probe(path: Path) -> AudioMeta:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,bits_per_raw_sample,channels,duration",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise AudioFileError("PROBE_FAILED", f"ffprobe error: {result.stderr[:200]}")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise AudioFileError("NO_AUDIO_STREAM", "no audio stream found")

    s = streams[0]
    codec_name: str = s.get("codec_name", "")
    sample_rate = int(s.get("sample_rate", 0))
    channels = int(s.get("channels", 0))
    duration_sec = max(1, round(float(s.get("duration", 0))))

    raw_bits = s.get("bits_per_raw_sample")
    bit_depth = int(raw_bits) if raw_bits else _CODEC_BIT_DEPTH.get(codec_name, 0)

    # --- Validation ---
    if codec_name not in _PCM_CODECS:
        raise AudioFileError(
            "INVALID_CODEC",
            f"codec '{codec_name}' is not PCM. Only uncompressed PCM wav is accepted.",
        )
    if sample_rate > settings.MAX_SAMPLE_RATE:
        raise AudioFileError(
            "SAMPLE_RATE_TOO_HIGH",
            f"sample_rate {sample_rate} Hz exceeds limit {settings.MAX_SAMPLE_RATE} Hz.",
        )
    if bit_depth > settings.MAX_BIT_DEPTH:
        raise AudioFileError(
            "BIT_DEPTH_TOO_HIGH",
            f"bit_depth {bit_depth} bit exceeds limit {settings.MAX_BIT_DEPTH} bit.",
        )
    if channels < 1:
        raise AudioFileError("INVALID_CHANNELS", "could not detect channel count")

    return AudioMeta(
        codec_name=codec_name,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=channels,
        duration_sec=duration_sec,
    )


def compute_peaks(path: Path, *, num_points: int = 200) -> list[float]:
    """Return normalized (0..1) peak array for waveform display."""
    data, _ = sf.read(str(path), dtype="float32", always_2d=True)
    mono = np.abs(data).max(axis=1)
    chunk = max(1, len(mono) // num_points)
    peaks = [float(mono[i : i + chunk].max()) for i in range(0, len(mono), chunk)]
    peaks = peaks[:num_points]
    max_val = max(peaks) if peaks else 1.0
    if max_val > 0:
        peaks = [round(p / max_val, 4) for p in peaks]
    return peaks


def save_original(src: Path, audio_id: uuid.UUID) -> Path:
    storage = Path(settings.STORAGE_DIR)
    storage.mkdir(parents=True, exist_ok=True)
    dest = storage / f"{audio_id}.wav"
    shutil.copy2(src, dest)
    return dest
