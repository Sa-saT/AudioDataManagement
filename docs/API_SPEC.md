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
| `q` | string |  | 全文検索 (Phase 4) |
| `tags` | string[] |  | タグ名 OR フィルタ。`?tags=jazz&tags=piano` で 1つ以上マッチする音源を返す |

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
      "tags": ["jazz", "fusion"],
      "youtube_safe": true,
      "published_at": "2026-05-20T00:00:00Z",
      "favorite_count": 12,
      "is_favorited": false
    }
  ]
}
```

### GET `/audios/tags`
販売中の音源に付けられているタグ一覧をカウント降順で返す。認証不要。

Response 200:
```json
[
  { "name": "jazz", "count": 24 },
  { "name": "piano", "count": 18 }
]
```

### POST `/audios/{id}/favorite`
お気に入りをトグル。JWT 必須 (アクティベート済み)。

Response 200:
```json
{ "is_favorited": true, "favorite_count": 13 }
```

### GET `/audios/{id}`
詳細取得 (販売中・売却済み問わず、メタのみ。売却済みは「sold」フラグ付き)。

### GET `/audios/{id}/stream-url`

視聴用 signed URL を発行する (公開、JWT 不要、token 消費なし)。

Query:
| 名前 | 型 | 既定 | 説明 |
|---|---|---|---|
| `start` | int | 0 | 再生開始位置 (秒)。0 〜 duration_sec-1 |

Response 200:
```json
{ "url": "http://localhost:8000/api/v1/audios/{id}/stream?start=0&sig=xxx&exp=1234567890" }
```

- signed URL の TTL は 30 秒 (`SIGNED_URL_TTL_SECONDS`)。
- 署名対象: `{audio_id}:{start}:{exp}` を HMAC-SHA256。

Errors: 400 `INVALID_START` / 404

---

### GET `/audios/{id}/stream`

10 秒チャンクの PCM wav を返す (公開、JWT 不要)。

Query: `start`, `sig`, `exp` (stream-url が発行した signed URL そのまま使用)

**配信仕様**
- 認可: `sig` + `exp` を HMAC で検証。失効・改竄は 403。
- ffmpeg で原本の `start` 秒から `PREVIEW_DURATION_SEC` (= 10) 秒を `-c:a copy` で切り出し、PCM wav として返却 (トランスコードなし、ビットパーフェクト)。
- `start + 10 > duration_sec` の場合は残り秒数まで返す (無音パディングしない)。
- `Content-Type: audio/wav`、`Content-Length` 付与。
- `Cache-Control: no-store` (signed URL 再利用を防ぐ)。

**フロント利用フロー**
1. 波形クリック → クリック位置から `start` 秒を算出
2. `GET /stream-url?start={N}` → signed URL 取得
3. `fetch(signed_url)` → `AudioContext.decodeAudioData` → `AudioBufferSourceNode.start`
4. 10 秒再生完了後に次チャンクが必要な場合は 2 に戻る

Errors: 400 `INVALID_START` / 403 `EXPIRED_SIGNATURE` / 403 `INVALID_SIGNATURE` / 404

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
  "storage_used_bytes": 52428800,
  "items": [
    {
      "id": "trk_0001",
      "title": "...",
      "creator": { "id": "...", "display_name": "..." },
      "duration_sec": 354,
      "token_cost": 354,
      "tags": ["jazz"],
      "peaks": [...],
      "downloaded_at": "2026-05-21T03:12:00Z",
      "tokens_consumed": 354,
      "file_size_bytes": 26214400,
      "copy_exists": true
    }
  ]
}
```

### GET `/me/downloads/{audio_id}/copy-url`
再ダウンロード用 signed URL を発行 (token 消費なし)。コピーが存在しない場合は原本にフォールバック。

Response 200: `{ "url": "/api/v1/me/downloads/copy-file?audio_id=...&sig=...&exp=..." }`

### GET `/me/downloads/copy-file`
signed URL で保護されたファイル配信 (Range 対応)。

### DELETE `/me/downloads/{audio_id}`
ダウンロードコピー (`/storage/downloads/{user_id}/{audio_id}.wav`) を削除。削除後は再DL不可。

Response 204

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

## 5. Commission (発注) API

発注機能は `system_settings.commission_enabled = "true"` のときのみ有効。無効時は 503 `COMMISSION_DISABLED`。

### GET `/system/commission`
機能フラグ確認。認証不要。

Response 200: `{ "enabled": true }`

### GET `/orders`
ロールに応じた発注一覧。
- user: 自分が作成した発注
- creator: 自分が候補または受注者の発注
- admin: 全発注

Response 200: `OrderListItem[]`

```json
[
  {
    "id": "uuid",
    "title": "ゲーム用 SE 3種",
    "token_cost": 300,
    "status": "assigned",
    "user_name": "alice",
    "assigned_creator_name": "モくろろ",
    "notified_at": null,
    "created_at": "...",
    "updated_at": "..."
  }
]
```

### POST `/orders`
下書き作成 (user/creator/admin)。JWT 必須。

Request: `{ "title": "...", "description": "...", "token_cost": 300 }`

Response 201: `OrderOut` (詳細オブジェクト、candidates/messages 含む)

### GET `/orders/{order_id}`
チケット詳細。アクセス権確認あり。

Response 200: `OrderOut`

### POST `/orders/{order_id}/submit`
draft → open。ユーザが送信。残 token 確認 (不足で 402)。

### POST `/orders/{order_id}/cancel`
任意ステータス → cancelled (done/cancelled からは不可)。

### POST `/orders/{order_id}/message`
コメント追加。Request: `{ "content": "..." }`

> 改訂2.4: `private` フィールドは廃止 (admin↔creator 私信機能ごと撤去)。

### POST `/orders/{order_id}/view` (改訂2)
チケット閲覧記録。`activity_logs` に `kind=order_view, target_id=order_id` を挿入。通知の既読判定に使う ([NOTIFICATION_SPEC §6](NOTIFICATION_SPEC.md))。Response 201.

### PATCH `/orders/{order_id}/deadline` (改訂2)
希望締切日変更。user / admin のみ。status≠done/cancelled。
Request: `{ "desired_deadline": "YYYY-MM-DD" }`

### PATCH `/orders/{order_id}/brief-after-submit` (改訂2.1)
発注後ブリーフ編集。`order_brief_edits` に差分記録 + bot メッセージ自動投稿。
Request: `{ "brief": {...} }`

### GET `/orders/{order_id}/brief-edits` (改訂2.1)
ブリーフ編集履歴を取得 (1 field 1 行)。

### POST `/orders/{order_id}/close` (改訂2.2)
done → close。user が「受け取る」を押したとき。token 消費 + creator_payouts 確定 + closed_at 設定 + アーカイブ移動。

### GET `/orders/{order_id}/submission-stream-url` (改訂2.2)
提出済み音源プレビュー用 signed URL を返す (reviewing / done で全参加者視聴可)。
Response 200: `{ "url": "..." }`

### GET `/orders/submission-stream` (改訂2.2)
signed URL で保護された提出音源のストリーム配信。

### GET `/orders/{order_id}/memos` (改訂2.4)
Order 共有メモを取得。admin / assigned creator のみアクセス可 (user は 403)。詳細は [ORDER_SPEC §16.2](ORDER_SPEC.md)。

Response 200:
```json
{
  "admin":   { "author_kind":"admin",   "content":"...", "author_name":"root", "updated_at":"..." },
  "creator": { "author_kind":"creator", "content":"...", "author_name":"demo_creator", "updated_at":"..." },
  "can_edit_admin":   true,
  "can_edit_creator": false
}
```

### PUT `/orders/{order_id}/memo` (改訂2.4)
自身の枠 (admin / creator どちらか) を upsert。role から自動判定。
Request: `{ "content": "..." }` (≤ 2000 chars)
エラー: `MEMO_TOO_LONG` (422) / `INVALID_STATE` (409: close/cancel 後) / `FORBIDDEN` (403)

### POST `/orders/{order_id}/respond`
Creator が候補返信 (recruiting 状態のみ)。

Request: `{ "response": "accepted" | "declined", "content": "..." }`

### POST `/orders/{order_id}/submit-file`
Creator が .wav を提出 → assigned → reviewing。multipart: `file` + `note`。
改訂2.5 (9-A3): 各提出は自動採番で `submissions/{order_id}_v{n}.wav` に保存される。
peaks v2 は version ごとに OrderMessage.attachment_peaks に格納。

### GET `/orders/{order_id}/submissions` (改訂2.5 / 9-A3)
提出履歴 (version 一覧 + rejection 情報) を時系列順 (古い順) で返す。

Response 200:
```json
[
  { "version": 1, "message_id": "...", "sender_name": "demo_creator", "note": "初回提出",
    "file_available": true, "peaks": { "n": 1000, "max": [...], "min": [...], "rms": [...] },
    "rejected": true, "rejection_reason": "テンポ早すぎ", "created_at": "..." },
  { "version": 2, ..., "rejected": false, "rejection_reason": null }
]
```

### GET `/orders/{order_id}/submission-stream-url`
チケット参加者向けの 10 秒チャンク signed URL を発行。
クエリ: `start=N`(秒, default 0) / `version=N`(default 0 = latest、改訂2.5)。

### GET `/orders/{order_id}/file-url`
Done 済み音源の signed URL 発行 (user/admin のみ)。

Response 200: `{ "url": "/api/v1/orders/download-file?order_id=...&sig=...&exp=..." }`

### GET `/orders/download-file`
signed URL で保護されたファイル配信 (静的パス、`/{order_id}` より前に定義)。

### POST `/orders/{order_id}/nominate` (admin のみ)
Creator 候補追加。open/recruiting 状態のみ。

Request: `{ "creator_ids": ["uuid", ...] }`

### POST `/orders/{order_id}/assign` (admin のみ)
受注 Creator 確定 → assigned。

Request: `{ "creator_id": "uuid", "token_cost": 300 }`  ※ `token_cost` は任意 (変更時のみ)

### POST `/orders/{order_id}/reject` (admin のみ)
差し戻し reviewing → assigned。

Request: `{ "reason": "..." }`

### POST `/orders/{order_id}/done` (admin のみ)
reviewing → done。同時実行:
1. 提出 .wav を `/storage/orders/{id}.wav` にコピー
2. token_cost 分を user の当月 token から消費
3. Creator への `creator_payouts` 行を生成 (rank_at_payout × token_cost)
4. `notified_at` を設定

### GET `/me/notifications` (改訂2.4 / NOTIFICATION_SPEC §5)
領域非依存の統合通知 API。アプリ全体の「自分が対応すべきもの」を集約。詳細は [NOTIFICATION_SPEC §5](NOTIFICATION_SPEC.md)。

Response 200:
```json
{
  "areas": {
    "commission":   { "action_count": 2, "has_info": true,  "breakdown": {"action_required":1,"message_unread":1,"info_only":1} },
    "payouts":      { "action_count": 3, "has_info": false, "breakdown": {"pending_approval":3} },
    "creator_dm":   { "action_count": 1, "has_info": false, "breakdown": {"unread_threads":1} },
    "token_grants": { "action_count": 0, "has_info": false, "breakdown": {} },
    "lic_requests": { "action_count": 0, "has_info": false, "breakdown": {} }
  },
  "totals": { "action_count": 6, "has_info": true }
}
```

ロール別に表示する area が異なる:
- user: `commission` のみ
- creator: `commission`, `creator_dm`
- admin: 全 area

### GET `/me/commission/unread` (deprecated)
Commission 単体の旧エンドポイント。後方互換のため残置。新規実装は `/me/notifications.areas.commission` を参照すること。

### GET `/admin/dm/creators` (admin のみ、改訂2.4 / DM_SPEC)
DM 履歴のある creator スレッド一覧 (新しい順)。`unread` フラグ付き。

Response 200:
```json
[
  { "creator_id":"...", "creator_name":"...", "creator_display_name":"...",
    "last_message_at":"...", "last_message_preview":"先頭60文字...", "unread": true }
]
```

### GET `/admin/dm/creators/{creator_id}` (admin のみ)
特定 creator との DM 全件 (古い順)。

### POST `/admin/dm/creators/{creator_id}` (admin のみ)
admin → creator DM 送信。Request: `{ "content": "..." }` (≤ 4000 chars)
エラー: `EMPTY_CONTENT` / `CONTENT_TOO_LONG` (422)

### POST `/admin/dm/creators/{creator_id}/view` (admin のみ)
DM スレッド既読化。`activity_logs.dm_view` を記録。

### GET `/me/dm/admin` (creator のみ、改訂2.4)
自分の admin チーム宛 DM 全件 (古い順)。

### POST `/me/dm/admin` (creator のみ)
creator → admin DM 送信。Request: `{ "content": "..." }`

### POST `/me/dm/admin/view` (creator のみ)
DM スレッド既読化。

### GET `/admin/settings` (admin のみ)
`system_settings` 全件取得。

Response 200: `[{ "key": "commission_enabled", "value": "false", "description": "..." }]`

### PATCH `/admin/settings/{key}` (admin のみ)
値を更新。Request: `{ "value": "true" }`

## 6. Admin API (role=admin 必須)

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
