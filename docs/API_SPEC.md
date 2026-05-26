# API仕様 — Audio Data Management

FastAPI で実装する HTTP API のエンドポイント設計。Phase 2 以降の実装対象。

## 0. 共通事項

- ベースURL: `http://localhost:8000/api/v1` (開発)
- 認証: `Authorization: Bearer <JWT>` (アクティベート時に発行)
- 受信形式: JSON (`Content-Type: application/json`)、アップロード時のみ `multipart/form-data`
- 日時: ISO 8601 (UTC)。期間集計は JST 基準 (`period_yyyymm`)
- 金額: 整数 (円)
- token: 整数 (秒数と同値、1秒=1token)
- ページング: クエリ `?page=1&per_page=50&sort=recommended|newest`
- エラー形式:
  ```json
  { "error": { "code": "INSUFFICIENT_TOKENS", "message": "..." } }
  ```

### 共通HTTPステータス
| 状況 | コード |
|---|---|
| 成功 (取得) | 200 |
| 成功 (生成) | 201 |
| 成功 (本文なし) | 204 |
| 入力不正 | 400 |
| 未認証 | 401 |
| 権限不足 | 403 |
| 不在 | 404 |
| 競合 (売り切れ等) | 409 |
| クォータ不足 | 402 (Payment Required を流用) |
| サーバエラー | 500 |

## 1. 認証

### POST `/auth/activate`
licファイルの内容を送信し、JWTを受け取る。

Request (multipart):
```
file: <.licファイル>
```
または JSON:
```json
{ "lic": "<lic文字列>" }
```

Response 200:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "username": "saaaaa",
    "role": "user",
    "monthly_quota_tokens": 18000
  }
}
```

Errors: 400 `INVALID_LICENSE_FORMAT` / 401 `INVALID_LICENSE_SIGNATURE` / 401 `LICENSE_REVOKED` / 401 `LICENSE_EXPIRED`

### GET `/me`
現在のユーザ情報を返す (要 JWT)。

Response 200:
```json
{
  "id": "uuid",
  "username": "saaaaa",
  "role": "user",
  "activated_at": "...",
  "monthly_quota_tokens": 18000
}
```

## 2. 音源 (公開API)

### GET `/audios`
**販売中** (= `downloaded_by_user_id IS NULL` AND `is_public=true`) の音源を一覧取得。guest でも閲覧可。

クエリ:
| 名前 | 型 | 既定 | 説明 |
|---|---|---|---|
| `sort` | `recommended`/`newest` | `recommended` | |
| `page` | int | 1 | |
| `per_page` | 25/50/100/200 | 50 | |
| `q` | string |  | 全文検索 (Phase 3) |
| `tag` | string |  | タグID (Phase 3) |

Response 200:
```json
{
  "total": 4446,
  "page": 1,
  "per_page": 50,
  "items": [
    {
      "id": "trk_0001",
      "title": "ロック感ある王道的フュージョン",
      "creator": { "id": "crt_1", "display_name": "モくろろ" },
      "duration_sec": 354,
      "token_cost": 354,
      "peaks": [0.12, 0.34, "..."],
      "youtube_safe": true,
      "published_at": "2026-05-20T00:00:00Z"
    }
  ]
}
```

### GET `/audios/{id}`
詳細取得 (販売中・売却済み問わず、メタのみ。売却済みは「sold」フラグ付き)。

### GET `/audios/{id}/stream`

プレビュー再生用ストリーミング (公開、token消費なし)。

クライアント / ユーザ共にプロを想定するため、**アプリ側で音質劣化を発生させない**。トランスコード・ビットレート変換は行わず、原本と同一の PCM `.wav` をビットパーフェクトで配信する。

**配信仕様**
- 配信対象: 先頭 60 秒を切り出した `*_preview.wav` (`audios.preview_path`)。フォーマットは原本と同一 (最大 48 kHz / 24 bit PCM)。
- プロトコル: HTTP Range Request (RFC 7233)。`Accept-Ranges: bytes` を必ず返し、`Range: bytes=START-END` を受けて `206 Partial Content` でチャンク返却。Range なし要求は `200` で全体返却。
- `Content-Type: audio/wav`、`Content-Length` / `Content-Range` 必須。
- 認可: `?sig=...&exp=...` 形式の短命 signed URL (HMAC-SHA256、TTL 数分)。`exp` 失効時は `403 EXPIRED_SIGNATURE`。
- キャッシュ: `Cache-Control: private, max-age=60`。

**ステップ**
1. クライアントが `GET /audios/{id}/stream-url` (別エンドポイント) または `/audios/{id}` 詳細 で短命 signed URL を取得。
2. `<audio>` / wavesurfer.js (MediaElement バックエンド) がその URL に対し Range 付きで GET を発行、ブラウザ標準のチャンク取得で再生。

Errors: 403 `EXPIRED_SIGNATURE` / 403 `INVALID_SIGNATURE` / 404 / 416 `Range Not Satisfiable`

> 原本 (`audios.file_path`) はこのエンドポイントからは配信しない。原本取得は `/audios/{id}/download` 経路のみ。

### POST `/audios/{id}/download`
原本 `.wav` のダウンロード。要 JWT + アクティベート済み。

サーバ側処理 (1トランザクション内):
1. `audios` を `WHERE id=? AND downloaded_by_user_id IS NULL FOR UPDATE` で取得 — 0件なら 409 `ALREADY_SOLD`
2. 当月残 token を計算 — 不足なら 402 `INSUFFICIENT_TOKENS`
3. `audios.downloaded_by_user_id` `downloaded_at` を更新
4. `token_consumptions` 行を作成 (`period_yyyymm` は JST now)
5. `creator_payouts` 行を作成 (`rank_at_payout` / `unit_price_yen` を当時の `creator_rank_prices` からスナップショット、`status=pending`)
6. `download_logs` に `kind=initial` を記録
7. ファイル本体を返す (本番は presigned URL を JSON で返す方針)

Response 200 (JSON 経路):
```json
{
  "download_url": "https://.../trk_0001.wav?sig=...&exp=...",
  "remaining_tokens": 17646
}
```

Errors: 401 / 402 `INSUFFICIENT_TOKENS` / 403 `NOT_ACTIVATED` / 409 `ALREADY_SOLD`

### GET `/me/downloads`
自身が DL した音源一覧 (My Downloads)。

Response 200:
```json
{
  "items": [
    {
      "id": "trk_0001",
      "title": "...",
      "downloaded_at": "2026-05-21T03:12:00Z",
      "tokens_consumed": 354
    }
  ]
}
```

### GET `/me/downloads/{audio_id}/file`
再ダウンロード。token消費なし、payout生成なし、`download_logs.kind=redownload` を記録。要 JWT、自身が買い手のとき 200、そうでなければ 403。

### GET `/me/quota`
当月のクォータ情報。

Response 200:
```json
{
  "period_yyyymm": 202605,
  "monthly_quota_tokens": 18000,
  "granted_extra": 1200,
  "consumed": 354,
  "remaining": 18846,
  "history": [
    { "audio_id": "trk_0001", "tokens": 354, "consumed_at": "2026-05-21T03:12:00Z" }
  ]
}
```

## 3. お気に入り

### POST `/me/favorites/{audio_id}`
追加。

### DELETE `/me/favorites/{audio_id}`
削除。

### GET `/me/favorites`
自身のお気に入り一覧。売却済みは含む (タイトル等メタは見える)。

## 4. Creator API (role=creator 必須)

### POST `/creator/audios`
`.wav` アップロード (multipart)。サーバが波形 (peaks) と `duration_sec` を解析して保存。

Request:
```
file: <.wav>
title: string
is_public: bool
```

Response 201: 作成された audio オブジェクト。価格パラメータは存在しない。

### PATCH `/creator/audios/{id}`
タイトル / 公開状態の更新。売却済みは `is_public` のみ変更可。

### DELETE `/creator/audios/{id}`
論理削除。売却済みは削除不可 (400)。

### GET `/creator/audios`
自身の音源一覧 (非公開・売却済み含む)。

### GET `/creator/payouts`
自身に紐づく `creator_payouts` 一覧 (pending / paid)。

Response 200:
```json
{
  "summary": { "pending_yen": 1200, "paid_yen": 5600 },
  "items": [
    {
      "id": "po_001",
      "audio_id": "trk_0001",
      "audio_title": "...",
      "rank_at_payout": "silver",
      "amount_yen": 200,
      "status": "pending",
      "created_at": "2026-05-21T03:12:00Z"
    }
  ]
}
```

## 5. Admin API (role=admin 必須)

### GET `/admin/users` / `/admin/users/{id}`
ユーザ一覧 / 詳細。

### PATCH `/admin/users/{id}`
ロール変更 / 凍結。

### PATCH `/admin/creators/{id}/rank`
ランク変更。Body: `{ "rank": "gold" }`。以後の DL から新ランク単価が適用される (既存 payout は不変)。

### GET `/admin/audios`
全音源 (非公開・売却済み含む)。

### DELETE `/admin/audios/{id}`
強制削除。

### GET `/admin/licenses` / POST `/admin/licenses` / POST `/admin/licenses/{id}/revoke`
ライセンス発行履歴 / 新規発行 (`.lic` バイナリ返却) / 失効。
`POST /admin/licenses` Body:
```json
{
  "username": "saaaaa",
  "role": "user",
  "monthly_quota_tokens": 18000,
  "expires_at": "2027-05-26T00:00:00Z"
}
```

### POST `/admin/users/{id}/token-grants`
当月の追加 token を手動付与 (FR-TKN-05 / FR-ADM-04)。

Request:
```json
{ "tokens": 3600, "reason": "キャンペーン補填" }
```

Response 201:
```json
{ "id": "tg_001", "tokens": 3600, "period_yyyymm": 202605 }
```

### GET `/admin/creator-payouts`
payout 一覧。クエリ: `status=pending|paid|cancelled`、`creator_id=...`、`from=YYYY-MM` `to=YYYY-MM`。

### PATCH `/admin/creator-payouts/{id}`
`{ "status": "paid" }` でマーク (FR-PAY-04 / FR-ADM-05)。`paid_at`, `paid_by_admin_id` が記録される。

### GET `/admin/rank-prices` / PATCH `/admin/rank-prices/{rank}`
ランク単価テーブルの参照・編集 (FR-ADM-06)。

## 6. ヘルスチェック / メタ

### GET `/health`
`{ "status": "ok" }`

### GET `/version`
`{ "version": "0.1.0", "git": "abc123" }`
