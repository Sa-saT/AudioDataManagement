"""Backfill audios.peaks to v2 format (max / min / RMS) by regenerating from .wav

WAVEFORM_SHADER_SPEC.md §3.4。
原本 wav が無いレコードはスキップ (peaks は v1 のままで残り、フロントは toPeaksV2 で互換ラップ)。

Revision ID: 0011_peaks_v2_backfill
Revises: 0010_global_order_serial
Create Date: 2026-05-30
"""
import json
from pathlib import Path

from alembic import op

from app.config import get_settings
from app.services.audio_file import compute_peaks_v2

revision = "0011_peaks_v2_backfill"
down_revision = "0010_global_order_serial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    settings = get_settings()
    storage = Path(settings.STORAGE_DIR)
    conn = op.get_bind()

    rows = conn.exec_driver_sql("SELECT id FROM audios").fetchall()
    updated = 0
    skipped = 0
    for (audio_id,) in rows:
        wav_path = storage / f"{audio_id}.wav"
        if not wav_path.exists():
            skipped += 1
            continue
        try:
            new_peaks = compute_peaks_v2(wav_path)
        except Exception:
            # 破損ファイル等は静かにスキップ (v1 で残る)
            skipped += 1
            continue
        conn.exec_driver_sql(
            "UPDATE audios SET peaks = %s::jsonb WHERE id = %s",
            (json.dumps(new_peaks), str(audio_id)),
        )
        updated += 1
    print(f"[0011_peaks_v2_backfill] updated={updated} skipped={skipped}")


def downgrade() -> None:
    # 復元不可 (v1 への lossy 変換になる)。意図的に no-op。
    pass
