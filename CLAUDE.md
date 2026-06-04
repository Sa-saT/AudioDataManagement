# Audio Data Management — Project Guide

サウンドクリエイター向け音響データ管理アプリ (Pathfinder)。

**アプリの核となる UX 原則:**
> **必要 & やりたいコトを解りやすく導いてくれるアプリ。**

ユーザーが「次に何をすべきか」を考えなくても、UI 側 (通知・階層伝播・状態表現) が自然に導く。
通知 = 自分の対応業務 / 通知がない = 安心していい — を守る。
詳細は [docs/NOTIFICATION_SPEC.md](docs/NOTIFICATION_SPEC.md)。

本ファイルは Claude 向けのプロジェクトガイド。**詳細仕様は `docs/` 配下を参照** (本ファイルは概観のみ)。

## 1. 技術スタック

### Frontend (`ADM_f/`)
- Nuxt 4 (Vue 3, TypeScript)
- pnpm
- TailwindCSS (`@nuxtjs/tailwindcss`)
- Pinia (`@pinia/nuxt`)
- WebGL2 (波形描画は自前 Fragment Shader)

### Backend (`ADM_b/`)
- FastAPI
- PostgreSQL
- JWT
- venv (`source venv/bin/activate`)

## 2. ディレクトリ構成

```
AudioDataManagement/
├── ADM_f/                                Frontend (Nuxt 4)
│   ├── app/
│   │   ├── app.vue
│   │   ├── assets/css/main.css
│   │   ├── components/
│   │   │   ├── TopNav.vue / AudioCard.vue / WaveformPlayer.vue
│   │   │   ├── NumberRoller.vue / ConfirmModal.vue / AudioEditModal.vue
│   │   │   ├── ErrorPopup.vue / OrderBriefWizard.vue
│   │   │   ├── charts/                  Admin ログ用 SVG (BarChart / Heatmap / RadarChart / Sparkline / SignalDot)
│   │   │   └── waveform/                自前 Shader 波形 (peaks.ts / useWaveformGL.ts / fallback2d.ts / shaders/)
│   │   ├── composables/                 useApi / useStreamPlayer
│   │   ├── layouts/                     default.vue
│   │   ├── pages/                       index / dashboard / activate / uploads / downloads
│   │   │                                / orders / orders/[id] / admin / dm
│   │   ├── stores/                      auth / audios / system (Pinia)
│   │   ├── types/                       audio / auth
│   │   └── utils/                       errorMessageJa
│   ├── tailwind.config.ts
│   └── nuxt.config.ts
├── ADM_b/                                Backend (FastAPI)
│   ├── app/
│   │   ├── main.py                      FastAPI エントリ
│   │   ├── config.py                    pydantic-settings (.env 読込)
│   │   ├── db.py                        SQLAlchemy engine/session
│   │   ├── api/v1/                      auth / audios / me / admin / admin_logs / orders / dm
│   │   ├── models/                      ORM (user / creator / audio / payment / log / order / dm)
│   │   ├── schemas/                     Pydantic (audio / auth)
│   │   ├── security/                    deps / jwt / license / signed_url
│   │   └── services/                    audio_file / tokens
│   ├── migrations/                      Alembic (0001 〜 0019)
│   ├── scripts/init_db.sh               冪等な DB / role / 依存 / migration 一括初期化
│   ├── .env.example                     環境変数テンプレ
│   ├── alembic.ini / requirements.txt / venv/
├── docs/                                 仕様ドキュメント (§7 参照) + 本番運用ガイド
├── images/                               UI 参考画像・モックアップ
├── DESIGN.md                             UIデザイントークン
└── CLAUDE.md                             本ファイル
```

## 3. 開発コマンド

### Frontend
```bash
cd ADM_f
pnpm install
pnpm dev          # http://localhost:3000/
pnpm nuxt prepare # 型再生成
```

### Backend
```bash
cd ADM_b
./scripts/init_db.sh                  # 初回 or 再実行 (冪等)
source venv/bin/activate
uvicorn app.main:app --reload         # http://localhost:8000/
```

`init_db.sh` は: `.env` 生成 (強乱数シークレット) → `adm_migrator` / `adm_app` ロール作成 → DB 作成 → venv & 依存 → `alembic upgrade head` → app ロールに最小権限付与 → storage ディレクトリ作成。

### DB ロール (最小権限)
- `adm_migrator`: DDL 用。Alembic から接続。DB owner
- `adm_app`: DML のみ。FastAPI が常用接続 (SELECT/INSERT/UPDATE/DELETE)

## 4. ユーザロール

| ロール | 識別 | 主な権限 |
|---|---|---|
| guest | 未アクティベート | 公開音源の閲覧・視聴のみ。DL不可 |
| licensee | licファイル (role=licensee) | 視聴 / DL (token消費) / DL済み再取得 / お気に入り / Commission 発注 |
| creator | licファイル (role=creator) | 音源のアップロード / 編集 / 削除 / 公開設定 / Commission 受注 |
| admin | licファイル (role=admin) | 全リソース管理、ランク変更、lic発行、token追加付与、payout承認、Commission 仲介、ログ閲覧 |

サイト初回アクセスは guest として `/dashboard` 表示。`/activate` で `.lic` を適用するとロール・月間token量が反映される。

> **ロール命名 (2026-06-02)**: 旧 `user` → `licensee` にリネーム済み。`.lic` の概念 (licensor=creator / licensee=客) と一致させた。UI 表記ルール: バッジ等の短い識別子は英語 `licensee` / `Users` / 説明文・選択画面は「利用者」「ユーザ」(長音なし)。

詳細: [docs/REQUIREMENTS.md §4](docs/REQUIREMENTS.md)

## 5. 音源・ストレージ (要点のみ)

- 拡張子: `.wav` (PCM、非圧縮) / 上限 **48 kHz / 24 bit / stereo**
- 保存場所 (開発): 原本 `/storage/sounds/{id}.wav` / DL コピー `/storage/downloads/{user_id}/{audio_id}.wav` / Commission `/storage/orders/`
- 波形プレビュー: peaks v2 `{n, max, min, rms}` を JSONB で保持。WebGL Fragment Shader で描画
- token量 = `duration_sec` (1秒 = 1 token)

**音質ポリシー (絶対要件):** アプリ側でトランスコード・ビットレート変換禁止。視聴も DL も原本と同一の PCM `.wav` をビットパーフェクト配信。視聴は 10 秒の動的チャンク切り出し (`?start=秒`、`ffmpeg -c:a copy`)。配信 URL は HMAC + TTL 30秒の signed URL。

詳細:
- [docs/REQUIREMENTS.md §5.3](docs/REQUIREMENTS.md) (FR-STREAM-03〜09)
- [docs/API_SPEC.md](docs/API_SPEC.md) `GET /audios/{id}/stream`
- [docs/WAVEFORM_SHADER_SPEC.md](docs/WAVEFORM_SHADER_SPEC.md) (peaks v2 + Shader)

## 5.5 料金/トークン制 (要点のみ)

- **単発販売**: 各音源はシステム全体で1人にのみ DL 可。DL 後は全員の Dashboard から消える
- **sold後の権限**: Creator は編集・削除不可。Admin のみ管理可。購入者は自身の Downloads コピーを削除可 (削除後は再 DL 不可)
- **試聴/再 DL は無料** (token 消費なし、Creator 追加支払いなし)
- **月間token**: lic の `monthlyQuotaTokens`。毎月1日 (JST) リセット、繰り越しなし。使い切ったら Admin が追加付与可 (当月末まで)
- **Creator ランク単価** (1DLあたり): bronze=¥100 / silver=¥200 / gold=¥400 / platinum=¥800。支払いは pending → admin が paid 化

詳細: [docs/REQUIREMENTS.md §5.4-5.8](docs/REQUIREMENTS.md) / [docs/DATA_MODEL.md §2.4-2.9](docs/DATA_MODEL.md)

## 6. コーディング規約

### Frontend
- `<script setup lang="ts">` を使用。Composition API。
- Pinia ストアは `stores/` 配下、actions/getters を明示。
- 型は `types/` 配下。`any` は避ける。
- スタイルは Tailwind ユーティリティ優先。共通部品のみ `main.css` の `@layer components` に。
- カラー/角丸/フォントは `tailwind.config.ts` のトークンを使用。生 hex は書かない。
- インポートパスは `~/` (=`app/`) を使う。

### Backend
- パスは `/api/v1/...` プレフィックス。
- リクエスト/レスポンス型は Pydantic で定義。
- 認可は JWT のカスタムクレーム `role` でチェック (`security/deps.py:require_role`)。
- DB アクセスは SQLAlchemy + Alembic。

### 共通
- コメントは **WHY のみ** (HOW は名前で語る)。1行で済むなら 1行。
- 過剰防衛コード禁止 (内部不変を信じる、境界のみ検証)。

## 7. 仕様ドキュメント

実装前に必ず該当ドキュメントを参照すること。

- 要件定義: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
- データモデル: [docs/DATA_MODEL.md](docs/DATA_MODEL.md)
- API設計: [docs/API_SPEC.md](docs/API_SPEC.md)
- licファイル: [docs/LICENSE_FILE_SPEC.md](docs/LICENSE_FILE_SPEC.md)
- **Commission発注**: [docs/ORDER_SPEC.md](docs/ORDER_SPEC.md)
- **Admin ログ**: [docs/LOG_SPEC.md](docs/LOG_SPEC.md)
- **通知システム (横断)**: [docs/NOTIFICATION_SPEC.md](docs/NOTIFICATION_SPEC.md)
- **DM (admin↔creator)**: [docs/DM_SPEC.md](docs/DM_SPEC.md)
- **波形描画 Shader**: [docs/WAVEFORM_SHADER_SPEC.md](docs/WAVEFORM_SHADER_SPEC.md)
- **本番運用 / 副業可能性 / licファイル暗号化方針**: [docs/PRODUCTION_OPERATIONS_GUIDE.md](docs/PRODUCTION_OPERATIONS_GUIDE.md)
- **監視セットアップ (Sentry / Better Stack / 料金表)**: [docs/MONITORING_SETUP.md](docs/MONITORING_SETUP.md)
- **バックアップ & リストア手順**: [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md)
- UIデザイン: [DESIGN.md](DESIGN.md)

## 8. 進捗フェーズ

| Phase | 内容 | 状態 |
|---|---|---|
| 1 | フロント基礎 (Dashboard / Activate / Pinia / 擬似波形) | ✅ 完了 |
| 2 | FastAPI + PostgreSQL 接続、`/audios` `/auth/activate`、実 wav 配信 | ✅ 完了 |
| 3 | Creator / Admin / Commission / 通知 / ログ / Shader 波形 / エラーポップアップ | ✅ **ローカル完了** |
| 4 | 本番運用 (CDN, 監視, バックアップ, S3 互換ストレージ) | ✅ **コード実装完了** (アカウント設定 + Secrets 登録のみ残) |

### Phase 3 タスク (#31〜#52 全完了)

| # | 内容 | 完了コミット |
|---|---|---|
| 31〜38 | Admin / アップロード / Dashboard / お気に入り / タグ検索 / My Downloads | (e7000b0 までに完了) |
| 39〜40 | Commission Backend + Frontend | e7000b0 |
| 41 | Commission 通知バッジ (action-required ベース) | d2fe503 |
| 42 | Admin ログ仕様策定 (LOG_SPEC.md) | d2fe503 |
| 43 | Commission 改訂2 (タイトル自動生成 / 曲長→token / draft保存 / 通知二系統 / 全体通し番号) | c5a65b6 |
| 44 | Admin ログ機能 実装 (集計 4 API + SVG チャート 5種 + 詳細展開) | 0e2417f |
| 45 | 波形描画 Shader 化 (peaks v2 + WebGL + wavesurfer.js 撤去 / 単色 + dim + EQ ビジュアライザ) | f4cad0a / 4c69897 |
| 46 | アップロード エラーの日本語ポップアップ (`ErrorPopup.vue`) | b99834a |
| 47 | Commission 改訂2.1 — 発注後ブリーフ編集 (diff色 + bot通知 + 履歴) + admin 代理表示モーダル | 659f927 / ca99847 |
| 48 | Commission 改訂2.2 + 2.3 — REDMINE / 受け取る / アーカイブ / LINE 風チャット / token 予約 | 7ca5a28 〜 d9c2180 |
| 49 | **NOTIFICATION_SPEC 策定 + Phase B/C/D 実装** (統合通知 API / admin タブ Level 3 / 一覧 per-row dot / クローズ dim 化 / メッセージ未読精緻化 / submission peaks v2) | 995018f 〜 2d327f1 |
| 50 | **改訂2.4** — Order 内私信廃止 + Order 共有メモ (admin/creator 各1枠、左右分割、user 不可視) + admin↔creator Direct Message (DM_SPEC Phase A-D) + admin Commission メニュー統合 | 14a5fc5 〜 3889d85 |
| 51 | **9-A3 改訂2.5** — Creator 複数提出のバージョン管理 (submissions/{id}_v{n}.wav + peaks v2 per version + GET /submissions + 履歴 UI) + リテラルルート順序バグ修正 | 3d2566b |
| 52 | **9-A4** — クリエイター視点 brief UI (役割優先順序 + tx_* スライダー視覚化 + 視点切替トグル / localStorage) | 24e31d8 |
| - | **9-A7** — R2-Q1〜Q3 (期限超過アラート色 / draft 30日自動削除 / sound_type=both UI 確認) | 3f32429 |
| - | **9-A6** — R2.1-Q1〜Q3 (設計決定のみ: reviewing 中編集不可維持 / 上限なし / 自動取消なし) | 3f32429 |
| - | **9-A5** — SE 複数スロット納品 (se_slots / _vN_sM.wav / multi-file / スロットタブ / migration 0020) | 3f32429 |
| - | **9-A12** — NOTIFICATION Phase E (prev_view_at / 「ここから未読」ディバイダー / 自動スクロール) | a566998 |

### Phase 3 残スコープ → Phase 4 前に整備

詳細は **[docs/ORDER_SPEC.md §9.1](docs/ORDER_SPEC.md)** (棚卸し済) を一次ソースとする。

**低 / 要検討 (残):**
- メモ既読マーカー (9-A13)

**完了済 (2026-06-01):**
- 9-A5 SE 複数スロット納品 / 9-A6 R2.1 残課題 (設計決定) / 9-A7 R2 残課題 / 9-A12 NOTIFICATION Phase E

**本番準備 (Phase 4) — コード実装完了 (2026-06-04):**

| タスク | 内容 | コミット |
|---|---|---|
| S3 互換ストレージ切替 (9-A8) | `StorageBackend` ABC + `LocalStorageBackend` / `S3StorageBackend`。`.env` の `STORAGE_BACKEND=s3` で R2 切替 | ebb9682 |
| lic 暗号化 Phase C | AES-256-GCM バイナリ `.lic`。`parse_lic_bytes()` で JSON/binary 自動判別 | (2026-06-03) |
| CDN 設定 | Cloudflare Pages `_redirects`/`_headers`、`fly.toml`、GitHub Actions deploy workflows 2本 | 6955d1c |
| 監視設定 | Sentry (backend + frontend)、JSON 構造ログ、`/healthz` DB チェック、`docs/MONITORING_SETUP.md` | 87e1270 |
| バックアップ設定 | GitHub Actions cron 2本 (pg_dump→B2 / rclone R2→B2)、`docs/BACKUP_RESTORE.md` | 930cea9 |

**残作業 (設定のみ):**
- 各 SaaS アカウント作成 (Sentry / Better Stack / Backblaze B2)
- GitHub Secrets 登録 (詳細: `MONITORING_SETUP.md` §6、`BACKUP_RESTORE.md` §GitHub Secrets)
- Fly.io secrets 設定 (`fly secrets set SENTRY_DSN=... ENVIRONMENT=production`)

## 9. 用語 (要点)

全用語集は [docs/REQUIREMENTS.md §8](docs/REQUIREMENTS.md) を参照。本ファイルでは Claude が頻出する識別子のみ:

| 用語 | 説明 |
|---|---|
| licファイル | ユーザ/ロールを識別する `.lic` 拡張子のライセンスファイル |
| peaks | 波形プレビューデータ。**v2** = `{n, max, min, rms}` (1000ポイント、`WAVEFORM_SHADER_SPEC.md` §3) |
| アクティベート | licファイル適用で guest → licensee/creator/admin になる操作 |
| ランク | クリエイターの段位 (bronze/silver/gold/platinum) |
| Commission / 発注 | オリジナル音源の制作依頼チケット。Dashboard の単発DL とは独立 (`ORDER_SPEC.md`) |
| activity_logs | session ping / order_view を統合した活動ログテーブル (`LOG_SPEC.md` §2.1) |
