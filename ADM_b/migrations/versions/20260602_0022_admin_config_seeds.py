"""Seed system_settings: image_tag_presets / commission_item_visibility

Admin が管理する 2 つの設定を system_settings に追加:
- image_tag_presets: アップロード時の画像タグプリセット (JSON 文字列)
- commission_item_visibility: Commission ブリーフ各項目の表示可否 (JSON 文字列)

両方ともデフォルト値を seed。既存値があればスキップ (冪等)。

Revision ID: 0022_admin_config_seeds
Revises: 0021_role_user_to_licensee
Create Date: 2026-06-02
"""
import json

from alembic import op

revision = "0022_admin_config_seeds"
down_revision = "0021_role_user_to_licensee"
branch_labels = None
depends_on = None


DEFAULT_IMAGE_TAGS = [
    "warm", "ambient", "nature", "cinematic",
    "dark", "bright", "acoustic", "electronic",
    "energetic", "peaceful", "dramatic", "mysterious",
]

# OrderBriefWizard の全項目 (sound_type/purpose/length_sec/desired_deadline は
# バリデーション必須のため UI 上は admin が hide しても server 強制チェックは継続)
DEFAULT_ITEM_VISIBILITY = {
    "sound_type": True,
    "purpose": True,
    "length_sec": True,
    "desired_deadline": True,
    "bgm_scenes": True,
    "bgm_loop": True,
    "bgm_note": True,
    "se_trigger": True,
    "se_functions": True,
    "se_slots": True,
    "emotions_target": True,
    "emotions_avoid": True,
    "memory_impression": True,
    "tx_organic_electronic": True,
    "tx_melody_rhythm": True,
    "tx_warm_cold": True,
    "tx_sparse_dense": True,
    "tx_static_dynamic": True,
    "reference_urls": True,
    "reference_elements": True,
    "reference_avoid": True,
    "delivery_format": True,
    "note": True,
}


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO system_settings (key, value, description)
        VALUES (
          'image_tag_presets',
          '{json.dumps(DEFAULT_IMAGE_TAGS)}',
          'アップロード画面で creator が選択できるイメージタグ (JSON array)'
        )
        ON CONFLICT (key) DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO system_settings (key, value, description)
        VALUES (
          'commission_item_visibility',
          '{json.dumps(DEFAULT_ITEM_VISIBILITY)}',
          'Commission ブリーフの各項目の表示可否 (JSON object)'
        )
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM system_settings WHERE key IN ('image_tag_presets', 'commission_item_visibility')"
    )
