# データモデル — Audio Data Management

PostgreSQL を想定。主キーはすべて UUID v7 (時系列ソート可)。タイムスタンプは `TIMESTAMPTZ`、金額は `INTEGER` (円)、トークン量は `INTEGER` (秒数と同じスケール)。

## 1. ER 概要

```mermaid
erDiagram
  USERS ||--o| LICENSES        : "1対0..1"
  USERS ||--o| CREATOR_PROFILES: "1対0..1 (role=creatorのみ)"
  CREATOR_PROFILES ||--o{ AUDIOS : "投稿"
  USERS ||--o| AUDIOS          : "downloaded_by (0..1ユーザ × 1音源)"
  USERS ||--o{ FAVORITES       : "お気に入り"
  AUDIOS ||--o{ FAVORITES      : "お気に入り対象"
  AUDIOS ||--o{ AUDIO_TAGS     : "タグ付け"
  TAGS   ||--o{ AUDIO_TAGS     : "タグ"
  AUDIOS ||--o{ DOWNLOAD_LOGS  : "DL/再DL履歴"
  USERS  ||--o{ DOWNLOAD_LOGS  : "実行者"
  USERS  ||--o{ TOKEN_CONSUMPTIONS : "消費"
  AUDIOS ||--o| TOKEN_CONSUMPTIONS : "対象"
  USERS  ||--o{ TOKEN_GRANTS   : "受領"
  USERS  ||--o{ TOKEN_GRANTS   : "Admin発行"
  AUDIOS ||--o| CREATOR_PAYOUTS    : "支払い対象 (1対0..1)"
  CREATOR_PROFILES ||--o{ CREATOR_PAYOUTS : "受領"
  CREATOR_RANK_PRICES ||--o{ CREATOR_PAYOUTS : "ランク単価"
  USERS  ||--o{ ORDERS         : "発注者"
  ORDERS ||--o{ ORDER_CANDIDATE_CREATORS : "候補Creator"
  CREATOR_PROFILES ||--o{ ORDER_CANDIDATE_CREATORS : "候補"
  ORDERS ||--o{ ORDER_MESSAGES : "メッセージ履歴"
  USERS  ||--o{ ORDER_MESSAGES : "送信者"
  ORDERS ||--o| CREATOR_PAYOUTS : "発注支払い (Done時)"
```

## 2. エンティティ定義

### 2.1 `users`

サイト利用者の基本情報。`role` で権限を分岐。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `username` | TEXT | UNIQUE, NOT NULL | 表示名 |
| `email` | TEXT | UNIQUE | 任意 (Phase 2) |
| `role` | ENUM(`user`,`creator`,`admin`) | NOT NULL, DEFAULT `user` | |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

### 2.2 `licenses`

`.lic` ファイル発行管理。1ユーザにつき有効なライセンスは原則1件。`monthly_quota_tokens` がユーザの月間DL許容量を決める。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, UNIQUE | |
| `license_code` | TEXT | UNIQUE, NOT NULL | 公開ID (例: `LIC-2026-0001`) |
| `role` | ENUM | NOT NULL | licファイル内の role |
| `monthly_quota_tokens` | INTEGER | NOT NULL, CHECK (>=0) | 毎月リセットされる月間DL token量 |
| `signature` | TEXT |  | HMAC署名 (Phase 2) |
| `max_download_storage_bytes` | BIGINT | NOT NULL, DEFAULT 0 | Downloads ストレージの容量上限 (0=制限なし)。FR-DL-08 |
| `issued_at` | TIMESTAMPTZ | NOT NULL | |
| `expires_at` | TIMESTAMPTZ |  | NULL = 無期限 |
| `revoked_at` | TIMESTAMPTZ |  | 失効日時 |

### 2.3 `creator_profiles`

creator ロール限定の追加情報。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `user_id` | UUID | PK, FK→users.id | |
| `display_name` | TEXT | NOT NULL | |
| `bio` | TEXT |  | |
| `rank` | ENUM(`bronze`,`silver`,`gold`,`platinum`) | NOT NULL, DEFAULT `bronze` | FR-PAY-02 のキー |
| `payout_method` | JSONB |  | 振込先 (Phase 3) |

### 2.4 `audios`

音源本体。原本は `/storage/sounds/{id}.wav`。
`duration_sec` がそのままDL時のtoken消費量となる (1秒=1token)。
`downloaded_by_user_id` が NULL でない音源は **sold (売却済み)** で、Dashboard 一覧から除外する。

**sold後の権限:** アップロード元 Creator の編集・削除権限は消滅する。Admin のみ全権を持つ。購入者 (DL user) は自身の Downloads ストレージ内のコピーのみ管理できる (FR-DL-09)。

視聴は **動的チャンク切り出し** (ffmpeg -ss start -t 10 -c:a copy)。事前生成プレビューファイルは持たない。DL は原本ファイルを signed URL で配信。
DL成功時は購入者の Downloads ストレージ (`/storage/downloads/{user_id}/{id}.wav`) にコピーを保存する (FR-DL-07)。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `creator_id` | UUID | FK→creator_profiles.user_id, NOT NULL | |
| `title` | TEXT | NOT NULL | |
| `description` | TEXT |  | |
| `file_path` | TEXT | NOT NULL | 原本 `.wav` のパス。例: `/storage/sounds/{id}.wav`。DL・視聴チャンク切り出しの対象 |
| `duration_sec` | INTEGER | NOT NULL, CHECK (>0) | 原本長 = token消費量 |
| `sample_rate` | INTEGER | NOT NULL | Hz。例: 44100, 48000。上限 48000 (FR-STREAM-06) |
| `bit_depth` | SMALLINT | NOT NULL | bit。例: 16, 24。上限 24 (FR-STREAM-06) |
| `channels` | SMALLINT | NOT NULL, DEFAULT 2 | 1=mono / 2=stereo |
| `peaks` | JSONB | NOT NULL | 波形プレビュー用 (0..1 配列)。音声デコードに依存しない波形描画用 |
| `is_public` | BOOLEAN | NOT NULL, DEFAULT false | |
| `youtube_safe` | BOOLEAN | NOT NULL, DEFAULT true | YT利用可否 |
| `recommend_score` | NUMERIC(6,2) | NOT NULL, DEFAULT 0 | オススメ順ソート用 |
| `published_at` | TIMESTAMPTZ |  | 公開日時 |
| `file_size_bytes` | BIGINT | NOT NULL | 原本ファイルサイズ。Downloads ストレージの残量計算に使用 (FR-DL-08) |
| `downloaded_by_user_id` | UUID | FK→users.id, UNIQUE, NULLABLE | 売却済みなら買い手のID |
| `downloaded_at` | TIMESTAMPTZ |  | 売却日時 |
| `download_file_exists` | BOOLEAN | NOT NULL, DEFAULT false | 購入者の Downloads ストレージにコピーが存在するか。購入者が削除すると false になる (FR-MYDL-06) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

> インデックス: `idx_audios_published_at`, `idx_audios_recommend_score`, `idx_audios_creator_id`, `idx_audios_available` (`WHERE downloaded_by_user_id IS NULL`)。
>
> 単発販売の排他制御: DLは `UPDATE audios SET downloaded_by_user_id=$1, downloaded_at=now() WHERE id=$2 AND downloaded_by_user_id IS NULL RETURNING *` 形式で必ず実施。0件返却なら売り切れ。

### 2.5 `tags` / `audio_tags`

| 列 (tags) | 型 | 制約 |
|---|---|---|
| `id` | UUID | PK |
| `name` | TEXT | UNIQUE NOT NULL |

| 列 (audio_tags) | 型 | 制約 |
|---|---|---|
| `audio_id` | UUID | FK→audios.id |
| `tag_id` | UUID | FK→tags.id |
| PK | (audio_id, tag_id) | |

### 2.6 `creator_rank_prices`

ランクごとの「1DLあたり支払い単価」テーブル。Admin が編集可能。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `rank` | ENUM | PK | bronze / silver / gold / platinum |
| `unit_price_yen` | INTEGER | NOT NULL, CHECK (>=0) | 1DLあたりの円 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

初期データ:
```
bronze   = 100
silver   = 200
gold     = 400
platinum = 800
```

### 2.7 `creator_payouts`

音源の DL に対する Creator 支払いレコード。FR-PAY-03 により音源1件につき1行。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `audio_id` | UUID | FK→audios.id, UNIQUE, NOT NULL | 1音源 = 1支払い |
| `creator_id` | UUID | FK→creator_profiles.user_id, NOT NULL | |
| `rank_at_payout` | ENUM | NOT NULL | DL時点のランクをスナップショット |
| `unit_price_yen` | INTEGER | NOT NULL | DL時点の単価をスナップショット |
| `amount_yen` | INTEGER | NOT NULL | = unit_price_yen × 1 |
| `status` | ENUM(`pending`,`paid`,`cancelled`) | NOT NULL, DEFAULT `pending` | |
| `paid_at` | TIMESTAMPTZ |  | |
| `paid_by_admin_id` | UUID | FK→users.id |  |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | DL成立と同時に作成 |

### 2.8 `token_consumptions`

DL時の token 消費履歴。再DLは記録しない (`download_logs` に残す)。
`period_yyyymm` 列により当月消費量の集計が定数時間で可能。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, NOT NULL | |
| `audio_id` | UUID | FK→audios.id, NOT NULL | |
| `license_id` | UUID | FK→licenses.id, NOT NULL | DL時に有効だったlic |
| `tokens` | INTEGER | NOT NULL, CHECK (>0) | = audio.duration_sec |
| `period_yyyymm` | INTEGER | NOT NULL | DL時刻(JST)の YYYYMM (例: 202605) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

> インデックス: `idx_tc_user_period (user_id, period_yyyymm)` で残量計算が高速。

### 2.9 `token_grants`

Admin による追加 token 付与。当月分のみ有効 (FR-TKN-06)。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, NOT NULL | 受領者 |
| `granted_by_admin_id` | UUID | FK→users.id, NOT NULL | 付与した admin |
| `tokens` | INTEGER | NOT NULL, CHECK (>0) | 追加付与量 |
| `period_yyyymm` | INTEGER | NOT NULL | 付与対象月 |
| `reason` | TEXT |  | |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

> 当月残量計算:
> `remaining = (lic.monthly_quota_tokens + SUM(grants当月)) - SUM(consumptions当月)`

### 2.10 `favorites`

| 列 | 型 | 制約 |
|---|---|---|
| `user_id` | UUID | FK→users.id |
| `audio_id` | UUID | FK→audios.id |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| PK | (user_id, audio_id) |  |

### 2.11 `system_settings` (システム設定 / 機能フラグ)

Admin が管理画面から変更できるシステム全体の設定テーブル。key-value 形式で将来のフラグ追加にも対応。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `key` | TEXT | PK | 設定キー。例: `commission_enabled` |
| `value` | TEXT | NOT NULL | JSON 互換文字列。boolean は `"true"` / `"false"` |
| `description` | TEXT |  | Admin UI に表示する説明文 |
| `updated_by_admin_id` | UUID | FK→users.id, NULLABLE | 最後に変更した Admin |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

初期データ:
```
key                   value    description
commission_enabled    "false"  発注 (Commission) 機能の有効/無効
```

> 追加予定フラグの例: `maintenance_mode`, `new_registration_enabled` など。

### 2.12 `orders` (発注チケット)

ユーザが発注するカスタム制作依頼の本体。Dashboard の `audios` とは独立した管理。
音源ファイルは Done 確定後に `/storage/orders/{id}.wav` に保存。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, NOT NULL | 依頼者 (user/creator) |
| `title` | TEXT | NOT NULL | 依頼タイトル |
| `description` | TEXT |  | 詳細説明・希望条件 |
| `token_cost` | INTEGER | NOT NULL, CHECK (>0) | カスタム指定の消費 token 量 |
| `status` | ENUM(`draft`,`open`,`recruiting`,`assigned`,`reviewing`,`done`,`cancelled`) | NOT NULL, DEFAULT `draft` | |
| `assigned_creator_id` | UUID | FK→creator_profiles.user_id, NULLABLE | 確定した受注 Creator |
| `assigned_by_admin_id` | UUID | FK→users.id, NULLABLE | 受注確定を行った Admin |
| `assigned_at` | TIMESTAMPTZ |  | 受注確定日時 |
| `done_by_admin_id` | UUID | FK→users.id, NULLABLE | Done 処理を行った Admin |
| `done_at` | TIMESTAMPTZ |  | Done 日時 |
| `file_path` | TEXT |  | Done確定後の音源パス (`/storage/orders/{id}.wav`) |
| `notified_at` | TIMESTAMPTZ |  | User への通知日時 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

> 状態遷移: `draft → open → recruiting → assigned → reviewing → done`。差し戻し: `reviewing → assigned`。どの段階でも `cancelled` へ移行可。

### 2.13 `order_candidate_creators` (発注候補Creator)

Admin が一つの発注チケットに対して複数 Creator に打診できる中間テーブル。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `order_id` | UUID | FK→orders.id, NOT NULL | |
| `creator_id` | UUID | FK→creator_profiles.user_id, NOT NULL | 指名された Creator |
| `sent_by_admin_id` | UUID | FK→users.id, NOT NULL | 指名した Admin |
| `sent_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| `response_status` | ENUM(`pending`,`accepted`,`declined`) | NOT NULL, DEFAULT `pending` | Creator の返信状況 |
| `response_at` | TIMESTAMPTZ |  | |
| UNIQUE | (order_id, creator_id) |  | 同一チケットへの重複指名防止 |

### 2.14 `order_messages` (チケット内メッセージ)

Redmine のジャーナル相当。User / Admin / Creator の3者がチケット内でやり取りするメッセージ履歴。Creator の音源提出も添付として本テーブルで管理。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `order_id` | UUID | FK→orders.id, NOT NULL | |
| `sender_id` | UUID | FK→users.id, NOT NULL | 送信者 (user/admin/creator いずれも) |
| `content` | TEXT |  | メッセージ本文 |
| `attachment_path` | TEXT |  | Creator 提出音源のパス (添付がある場合) |
| `kind` | ENUM(`comment`,`status_change`,`submission`,`rejection`,`done`) | NOT NULL, DEFAULT `comment` | メッセージ種別 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

### 2.15 `download_logs`

監査・利用統計用。初回DL/再DL/失敗試行を全て記録。

| 列 | 型 | 制約 | 説明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | FK→users.id, NULLABLE | |
| `audio_id` | UUID | FK→audios.id, NOT NULL | |
| `kind` | ENUM(`initial`,`redownload`,`denied_no_token`,`denied_sold`) | NOT NULL | |
| `ip` | INET |  | |
| `user_agent` | TEXT |  | |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

## 3. 状態遷移

### Audio
```
draft
  └─ published (is_public=true, published_at=now)
       ├─ unpublished (is_public=false, downloaded_by_user_id=NULL)
       └─ sold (downloaded_by_user_id 設定済) ← 終端
              ├─ creator_payouts に1行生成 (status=pending)
              ├─ Creator の編集・削除権限消滅 (Admin のみ管理可)
              ├─ download_file_exists=true (購入者の Downloads ストレージにコピー格納)
              └─ 購入者がコピー削除 → download_file_exists=false (再DL不可)
```

### CreatorPayout
```
pending → paid (Admin手動)
       → cancelled (Admin手動、例: 不正DL扱い)
```

### Order (発注チケット)
```
draft (ユーザ下書き)
  └─ open (ユーザ送信 → Admin 受信)
       └─ recruiting (Admin が Creator を指名・送信。候補Creator 返信待ち)
            └─ assigned (Admin が受注 Creator 1名を確定)
                 └─ reviewing (Creator が .wav を添付提出 → Admin 確認待ち)
                      ├─ done (Admin [Done] → token消費 + payout生成 + User通知) ← 終端
                      └─ assigned (差し戻し → Creator 再提出)
cancelled (任意の段階で Admin/User がキャンセル可)
```

### License
```
issued → revoked
       → expired (expires_at 経過)
```

## 4. 残量計算 (リファレンス SQL)

```sql
WITH g AS (
  SELECT COALESCE(SUM(tokens),0) AS granted
  FROM token_grants
  WHERE user_id = $1 AND period_yyyymm = $2
), c AS (
  SELECT COALESCE(SUM(tokens),0) AS consumed
  FROM token_consumptions
  WHERE user_id = $1 AND period_yyyymm = $2
), q AS (
  SELECT monthly_quota_tokens FROM licenses WHERE user_id = $1
)
SELECT (q.monthly_quota_tokens + g.granted) AS total_granted,
       c.consumed                            AS used,
       (q.monthly_quota_tokens + g.granted - c.consumed) AS remaining
FROM q, g, c;
```

## 5. 命名規約

- テーブル名: 複数形・スネークケース (`audios`, `download_logs`)
- 列名: スネークケース、boolean は `is_*` / `has_*` 接頭辞
- FK列名: `{table_singular}_id`
- timestamp: `*_at`
- 期間集計キー: `period_yyyymm` (INTEGER, JST基準)
