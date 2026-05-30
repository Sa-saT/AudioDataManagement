"""Add submission version tracking to order_messages (改訂2.5: 9-A3)

ORDER_SPEC §9.1 9-A3: Creator 複数提出のバージョン管理。
- order_messages に submission_version (kind=submission のみ) + attachment_peaks を追加
- 既存データ: 各 order の submission メッセージを created_at 順に 1..N で番号付与
- 既存ファイル `submissions/{order_id}.wav` を `submissions/{order_id}_v{N}.wav` にリネーム
  (N = 最新 version)。古いメッセージの attachment_path は NULL に (上書き済みで実体無し)
- 最新 version の attachment_peaks は orders.submission_peaks からコピー

Revision ID: 0019_submission_versions
Revises: 0018_direct_messages
Create Date: 2026-05-31
"""
import os
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0019_submission_versions"
down_revision = "0018_direct_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. カラム追加
    op.add_column("order_messages", sa.Column("submission_version", sa.Integer, nullable=True))
    op.add_column("order_messages", sa.Column("attachment_peaks", JSONB, nullable=True))

    # 2. 既存 submission メッセージに版数を採番 (created_at 順)
    op.execute("""
        WITH numbered AS (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY created_at) AS v
            FROM order_messages
            WHERE kind = 'submission'
        )
        UPDATE order_messages
        SET submission_version = numbered.v
        FROM numbered
        WHERE order_messages.id = numbered.id
    """)

    # 3. 最新 version の attachment_peaks に orders.submission_peaks をコピー
    op.execute("""
        WITH latest AS (
            SELECT om.id, o.submission_peaks
            FROM order_messages om
            JOIN orders o ON o.id = om.order_id
            WHERE om.kind = 'submission'
              AND om.submission_version = (
                  SELECT MAX(submission_version) FROM order_messages
                  WHERE order_id = om.order_id AND kind = 'submission'
              )
        )
        UPDATE order_messages
        SET attachment_peaks = latest.submission_peaks
        FROM latest
        WHERE order_messages.id = latest.id
    """)

    # 4. 古い submission の attachment_path は NULL (上書きで物理ファイル消失)
    op.execute("""
        UPDATE order_messages
        SET attachment_path = NULL
        WHERE kind = 'submission'
          AND submission_version < (
              SELECT MAX(submission_version) FROM order_messages om2
              WHERE om2.order_id = order_messages.order_id AND om2.kind = 'submission'
          )
    """)

    # 5. ファイルシステム: submissions/{order_id}.wav → submissions/{order_id}_v{N}.wav
    #    ローカル開発のみ。ORDERS_DIR が未設定 / dir 不在の場合はスキップ
    orders_dir_env = os.environ.get("ORDERS_DIR")
    if orders_dir_env:
        sub_dir = Path(orders_dir_env) / "submissions"
        if sub_dir.is_dir():
            conn = op.get_bind()
            rows = conn.execute(sa.text("""
                SELECT om.order_id, MAX(om.submission_version) AS max_v
                FROM order_messages om
                WHERE om.kind = 'submission'
                GROUP BY om.order_id
            """)).fetchall()
            for order_id, max_v in rows:
                src = sub_dir / f"{order_id}.wav"
                dst = sub_dir / f"{order_id}_v{max_v}.wav"
                if src.exists() and not dst.exists():
                    src.rename(dst)
                    # attachment_path を新パスへ更新 (最新 version のみ)
                    conn.execute(sa.text("""
                        UPDATE order_messages
                        SET attachment_path = :new_path
                        WHERE order_id = :oid AND kind = 'submission'
                          AND submission_version = :v
                    """), {"new_path": str(dst), "oid": str(order_id), "v": max_v})


def downgrade() -> None:
    op.drop_column("order_messages", "attachment_peaks")
    op.drop_column("order_messages", "submission_version")
    # ファイルリネームの逆操作は不可逆性回避のため省略 (local-only)
