# Audio Data Management — Project Guide

サウンドクリエイター向け音響データ管理アプリ。
本ファイルは Claude 向けのプロジェクトガイド。詳細仕様は `docs/` 配下を参照。

## 1. 技術スタック

### Frontend (`ADM_f/`)
- Nuxt 4 (Vue 3, TypeScript)
- pnpm
- TailwindCSS (`@nuxtjs/tailwindcss`)
- Pinia (`@pinia/nuxt`)
- wavesurfer.js

### Backend (`ADM_b/`)
- FastAPI
- PostgreSQL
- JWT
- venv (`source venv/bin/activate`)

## 2. ディレクトリ構成

```
AudioDataManagement/
├── ADM_f/                Frontend (Nuxt 4)
│   ├── app/
│   │   ├── app.vue
│   │   ├── assets/css/main.css
│   │   ├── components/   TopNav, AudioCard, WaveformPlayer
│   │   ├── layouts/      default.vue
│   │   ├── pages/        index / dashboard / activate
│   │   ├── stores/       auth, audios (Pinia)
│   │   ├── types/        audio, auth
│   │   └── utils/        mockTracks (ダミー)
│   ├── tailwind.config.ts
│   └── nuxt.config.ts
├── ADM_b/                Backend (FastAPI)
│   ├── app/
│   │   ├── main.py       FastAPI エントリ
│   │   ├── config.py     pydantic-settings (.env 読込)
│   │   ├── db.py         SQLAlchemy engine/session
│   │   └── models/       ORM (users / licenses / audios / payouts ...)
│   ├── migrations/       Alembic
│   ├── scripts/
│   │   └── init_db.sh    冪等な DB / role / 依存 / migration 一括初期化
│   ├── .env.example      環境変数テンプレ (init_db.sh が .env を生成)
│   ├── alembic.ini
│   ├── requirements.txt
│   └── venv/
├── docs/                 仕様ドキュメント
│   ├── REQUIREMENTS.md   要件定義書
│   ├── DATA_MODEL.md     ER / テーブル定義
│   ├── API_SPEC.md       FastAPI エンドポイント設計
│   └── LICENSE_FILE_SPEC.md  licファイル仕様
├── images/               UI参考画像
├── DESIGN.md             UIデザイントークン (Cursor風)
└── CLAUDE.md             本ファイル
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
- 本番もこの2ロール構成を踏襲。secret は環境ごとに切替

## 4. ユーザロール

| ロール | 識別 | 主な権限 |
|---|---|---|
| guest | 未アクティベート | 公開音源の閲覧・視聴のみ。DL不可 |
| user | licファイル (role=user) | 視聴 / DL (token消費) / DL済み再取得 / お気に入り |
| creator | licファイル (role=creator) | 音源のアップロード / 編集 / 削除 / 公開設定 |
| admin | licファイル (role=admin) | 全リソース管理、ユーザ/クリエイター管理、ランク変更、lic発行、token追加付与、payout承認 |

サイト初回アクセスは guest として `/dashboard` 表示。`/activate` で `.lic` を適用するとロール・月間token量が反映される。

## 5. 音源・ストレージ

- 拡張子: `.wav` (PCM、非圧縮)
- 想定スペック上限: **48 kHz / 24 bit / stereo**
- 保存場所 (開発): 原本のみ `/storage/sounds/{id}.wav` (事前生成プレビューファイルなし)
- 波形プレビュー: サーバが事前計算した `peaks` (正規化0..1配列) を JSONB で保持
- token量 = `duration_sec` (1秒 = 1 token)

### 音質ポリシー (必須要件)

クライアント / ユーザ共にプロを想定。**アプリ側で音質を劣化させない**。guest も視聴可 (営業・加入促進目的)。

- 視聴 (ストリーミング) も DL もトランスコード・ビットレート変換禁止。原本と同一の PCM `.wav` をビットパーフェクト配信。
- 視聴は **動的チャンク切り出し** (`?start=秒` で任意位置から 10 秒を `ffmpeg -c:a copy`)。JWT 不要。
- wavesurfer.js は **波形描画専用** (peaks データ使用)。再生は **Web Audio API** (fetch → decodeAudioData → AudioBufferSourceNode)。
- 配信 URL は短命 signed URL (HMAC + TTL 30 秒)。
- 詳細は `docs/REQUIREMENTS.md` §5.3 (FR-STREAM-03〜09) / `docs/API_SPEC.md` `GET /audios/{id}/stream`。

## 5.5 料金/トークン制 (重要)

- **単発販売**: 各音源はシステム全体で1人のユーザにのみ DL される。誰か1人が DL した瞬間、その音源は全員の Dashboard から消える。
- **sold後の権限**: DL完了 (sold状態) になると Creator の編集・削除権限は消滅。以降は Admin のみが管理権限を持つ。購入者は自身の Downloads ストレージ内コピーのみ管理可 (削除でストレージ解放、削除後は再DL不可)。
- **Downloadsストレージ**: DL成功時に原本コピーを `/storage/downloads/{user_id}/{audio_id}.wav` に格納。lic で設定した容量上限 (`max_download_storage_bytes`) あり。購入者はこのコピーから無制限に再DL可。
- **DL = token消費 + Creator支払い**: DL時に `audio.duration_sec` を当月の token から差し引き、同時に Creator への支払いレコードを生成する。
- **試聴は無料**: ストリーミング再生は token を消費しない。
- **再DLは無料**: My Downloads から何度でも再取得可能 (token消費なし、Creator追加支払いなし)。
- **月間token**: licファイルの `monthlyQuotaTokens` で個別付与。毎月1日 (JST) リセット、繰り越しなし。
- **追加付与**: 使い切ったら Admin が手動で追加 token を付与可能 (当月末まで有効)。
- **Creatorランク単価** (1DLあたり): bronze=100 / silver=200 / gold=400 / platinum=800 円。支払いは pending として記録され、Admin が paid にマークする。
- 詳細は `docs/REQUIREMENTS.md` §5.4-5.8、`docs/DATA_MODEL.md` §2.4-2.9 参照。

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
- 認可は JWT のカスタムクレーム `role` でチェック。
- DBアクセスは SQLAlchemy + Alembic を想定 (Phase 2 で導入)。

## 7. 仕様ドキュメント

実装前に必ず該当ドキュメントを参照すること。

- 要件定義: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
- データモデル: [docs/DATA_MODEL.md](docs/DATA_MODEL.md)
- API設計: [docs/API_SPEC.md](docs/API_SPEC.md)
- licファイル: [docs/LICENSE_FILE_SPEC.md](docs/LICENSE_FILE_SPEC.md)
- UIデザイン: [DESIGN.md](DESIGN.md)

## 8. 進捗フェーズ

| Phase | 内容 | 状態 |
|---|---|---|
| 1 | フロント基礎 (Dashboard / Activate / Pinia / 擬似波形) | ✅ 完了 |
| 2 | FastAPI + PostgreSQL 接続、`/audios` `/auth/activate`、実 wav 配信 | ✅ 完了 |
| 3 | Creator: アップロード UI / Admin: 管理画面 / 購入 / 検索 / Commission | **実装中 (ローカル完了)** |
| 4 | 本番運用 (CDN, 監視, バックアップ) | 未着手 |

### Phase 3 タスク進捗

| # | 内容 | 状態 |
|---|---|---|
| 31 | Admin 管理画面 (ユーザ一覧・ランク変更) | ✅ 完了 |
| 32 | Admin: lic 発行 / token 追加付与 / payout 承認 | ✅ 完了 |
| 33 | Creator: アップロード UI (`/uploads`) | ✅ 完了 |
| 34 | Dashboard を実 API 接続 (mockTracks 撤去・購入フロー・ページャー) | ✅ 完了 |
| 35 | お気に入り: POST `/audios/{id}/favorite` (toggle) + AudioCard UI | ✅ 完了 |
| 36 | タグ検索: GET `/audios/tags` + `?tags=` クエリ (OR) + Dashboard チップ UI | ✅ 完了 |
| 37 | My Downloads: GET `/me/downloads` + 再DL + コピー削除 + ストレージ表示 | ✅ 完了 |
| 38 | Admin: クリエイター統計 / グループ / ユーザ role フィルタ | ✅ 完了 |
| 39 | Commission バックエンド (orders API 全エンドポイント + migration) | ✅ 完了 |
| 40 | Commission フロントエンド (`/orders`, `/orders/[id]`, Admin タブ) | ✅ 完了 |

### Phase 3 残スコープ (ローカル開発終了後 → Phase 4 前に整備)

- 視聴: 波形クリック → `/stream-url?start=N` 取得 → Web Audio API で10秒再生 (wavesurfer + Web Audio 連携)
- Creator アップロード: `INVALID_CODEC` 等のエラーコードを日本語ポップアップ表示
- Commission: 発注完了通知バッジ (TopNav に未読 done 件数表示)
- 本番: S3互換ストレージ切替 / CDN / 監視 / バックアップ

## 9. 用語

| 用語 | 説明 |
|---|---|
| licファイル | ユーザ/ロールを識別する `.lic` 拡張子のライセンスファイル |
| peaks | 波形プレビュー用の正規化サンプル値配列 (0..1) |
| アクティベート | licファイルを適用して guest → user/creator/admin になる操作 |
| ランク | クリエイターの段位 (bronze/silver/gold/platinum) |
| 発注 (Commission) | ユーザがオリジナル音源の制作依頼を出すチケットベースのフロー。Dashboard の単発DLとは独立。 |
| 発注チケット | 発注1件を表す `orders` レコード。状態遷移と3者間のメッセージ履歴を持つ。 |
