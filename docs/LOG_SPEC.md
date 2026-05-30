# Admin Activity Log 仕様

管理者がクリエイター・ユーザの活動状況を可視化する機能。
目的は **admin の意思決定負荷を下げる**ことに特化:
- **User**: 満足度を見て、離脱兆候 / アップセル候補を発見する
- **Creator**: 作業頻度・対応品質を見て、ランク昇給/降格の手動判断を支援する

---

## 1. 概要

| 項目 | 内容 |
|---|---|
| 対象ロール | admin のみ |
| 配置 | Admin ページ「ログ」タブ |
| データソース | 既存テーブル + 新規 `activity_logs` 1 つ |
| チャート | 自前 SVG (BarChart / Sparkline / Heatmap / Radar) |
| 期間選択 | 7 / 30 / 90 日 |
| 個別詳細 | 一覧行クリックで縦に展開 |

---

## 2. データソース

### 2.1 新規テーブル

統合した活動ログ。**個別テーブルを分けず1つに集約**して複雑さを避ける。

```sql
activity_logs
  id          uuid PRIMARY KEY
  user_id     uuid NOT NULL REFERENCES users(id)
  kind        enum NOT NULL  -- 'session' | 'order_view' | 'dm_view' | (将来追加)
  target_id   uuid NULL      -- 'order_view': orders.id / 'dm_view': creator.user_id
  created_at  timestamptz NOT NULL DEFAULT now()
  INDEX (user_id, kind, created_at DESC)
  INDEX (target_id, kind, created_at DESC)
```

**記録タイミング:**

| kind | トリガー | 重複排除 |
|---|---|---|
| `session` | `POST /me/session/ping` (フロントが主要ページに到達した時) | 直近30分以内の同ユーザ記録があればスキップ |
| `order_view` | `/orders/[id]` ページ open 時に upsert (`POST /orders/{id}/view`) | しない (履歴を残す) |
| `dm_view` | DM スレッド open 時 (`POST /admin/dm/creators/{id}/view` / `POST /me/dm/admin/view`)。改訂2.4 で追加 | しない |

将来追加候補: `audio_view` / `search` / `favorite_add` など。

### 2.2 既存テーブル (引き続き活用)

| テーブル | 活用 |
|---|---|
| `download_logs` | DL/再DL/拒否ログ |
| `audios` | UL日時、売却日時 |
| `orders` | Commission 状態遷移、納品リードタイム |
| `order_messages` | メッセージ送信数、status_change 履歴 |
| `creator_payouts` | 支払い実績 |
| `token_consumptions` | token 消費 |
| `favorites` | お気に入り |

---

## 3. 指標設計

### 3.1 User 満足度指標

| 指標 | 計算式 | 示唆 |
|---|---|---|
| アクティブ度 | 過去30日の起動日数 / 30 | 0.3未満 = 離脱兆候 |
| DL転換率 | downloads / sessions | 「来ても買わない」検出 |
| ♡→DL転換 | downloads / favorites | 検討→購入の効率 |
| Token消化率 | tokens_used / monthlyQuota | 100% = アップセル候補 / 10%未満 = 過剰ランク |
| Commission活用 | orders 件数 (90日) | ヘビーユーザの兆候 |
| 平均利用間隔 | 連続するsession間の中央値 | 利用習慣の安定性 |

### 3.2 User 総合スコア (0-100)

各指標を 0-1 に正規化して重み付き線形結合:

```
score = 100 * (
  0.30 * アクティブ度
  + 0.25 * min(Token消化率, 1.0)
  + 0.15 * min(DL転換率 * 5, 1.0)
  + 0.10 * min(♡→DL転換 * 3, 1.0)
  + 0.20 * min(Commission活用 / 5, 1.0)
)
```

**シグナル色:**
- 緑 (good): score ≥ 60
- 黄 (watch): 30 ≤ score < 60
- 赤 (alert): score < 30

### 3.3 Creator 作業頻度指標

| 指標 | 計算式 | 昇給判断ヒント |
|---|---|---|
| アクセス頻度 | 30日起動日数 | 高頻度ほど積極的 |
| UL頻度 | UL数 / 30日 | 制作ペース |
| 販売率 | sold / uploaded | 「売れる音」を作れているか |
| 既読時間中央値 | last_viewed_at - notified_at の中央値 | 対応の早さ |
| 納品リードタイム中央値 | submitted_at - assigned_at の中央値 | 仕事の早さ |
| 承認率 | done / submitted | 一発OK率 |
| メッセージ送信数 | order_messages 数 (30日) | コミュニケーション量 |

### 3.4 Creator 総合スコア (0-100)

```
score = 100 * (
  0.20 * アクセス頻度
  + 0.20 * min(UL頻度 / 月3本, 1.0)
  + 0.20 * 販売率
  + 0.15 * (1 - min(既読時間中央値 / 24h, 1.0))
  + 0.15 * (1 - min(納品リードタイム中央値 / 7日, 1.0))
  + 0.10 * 承認率
)
```

**シグナル色:**
- 緑 (active): score ≥ 60
- 黄 (steady): 30 ≤ score < 60
- 赤 (inactive): score < 30

**ランク昇給ヒント (admin 手動判断):**
レーダーチャートで現ランク中央値を点線で重ね、超えた軸が多いほど昇給候補。自動フラグは行わない。

---

## 4. Backend API

### 4.1 セッション記録 (公開)

```
POST /api/v1/me/session/ping
Authorization: Bearer <token>
```

直近30分以内に同ユーザの `kind=session` 記録があれば 204、なければ INSERT して 201。

### 4.2 発注既読記録 (公開)

```
POST /api/v1/orders/{id}/view
Authorization: Bearer <token>
```

`kind=order_view, target_id={id}` を INSERT。

### 4.3 User ログ (admin)

```
GET /api/v1/admin/logs/users?days=30
```

**Response:**
```json
[
  {
    "user_id": "uuid",
    "username": "string",
    "role": "user",
    "score": 72,
    "signal": "green",
    "metrics": {
      "active_rate": 0.43,
      "dl_conversion": 0.18,
      "fav_to_dl": 0.22,
      "token_usage_rate": 0.85,
      "commission_count": 2,
      "median_interval_hours": 38
    },
    "last_active_at": "ISO8601"
  }
]
```

```
GET /api/v1/admin/logs/users/{user_id}/detail?days=30
```

**Response:**
```json
{
  "user_id": "uuid",
  "username": "string",
  "score": 72,
  "metrics": { /* 上と同じ */ },
  "heatmap": [
    { "weekday": 0, "hour": 9, "count": 3 }
  ],
  "sparkline": {
    "downloads": [/* 日次 30要素 */],
    "sessions":  [/* 日次 30要素 */],
    "tokens":    [/* 日次 30要素 */]
  },
  "token_quota": { "used": 340, "quota": 500 },
  "events": [
    { "ts": "ISO8601", "kind": "download", "detail": "曲名" }
  ]
}
```

### 4.4 Creator ログ (admin)

```
GET /api/v1/admin/logs/creators?days=30
```

**Response:**
```json
[
  {
    "creator_id": "uuid",
    "creator_name": "string",
    "rank": "gold",
    "score": 68,
    "signal": "green",
    "metrics": {
      "access_days": 22,
      "upload_per_month": 4.0,
      "sell_rate": 0.5,
      "median_read_hours": 6,
      "median_lead_days": 2.5,
      "approval_rate": 0.9,
      "message_count": 14
    },
    "earnings_pending": 2400,
    "earnings_paid": 8000,
    "last_active_at": "ISO8601"
  }
]
```

```
GET /api/v1/admin/logs/creators/{creator_id}/detail?days=30
```

**Response:**
```json
{
  "creator_id": "uuid",
  "creator_name": "string",
  "rank": "gold",
  "score": 68,
  "metrics": { /* 上と同じ */ },
  "rank_median": { /* gold ランクの中央値 */
    "access_days": 18,
    "upload_per_month": 3.0,
    "sell_rate": 0.4,
    "median_read_hours": 8,
    "median_lead_days": 3.0,
    "approval_rate": 0.85
  },
  "heatmap": [
    { "weekday": 0, "hour": 21, "count": 2 }
  ],
  "sparkline": {
    "uploads":  [/* 日次 30要素 */],
    "sold":     [/* 日次 30要素 */],
    "earnings": [/* 日次 30要素 */]
  },
  "events": [
    { "ts": "ISO8601", "kind": "upload", "detail": "曲名" }
  ]
}
```

---

## 5. Frontend

### 5.1 配置

Admin ページに「ログ」タブを追加:

```
users | payouts | tokens | licenses | orders | settings | ログ
```

### 5.2 ログタブ画面構成

```
┌─ サブタブ ──────────────────────────────┐
│  [User]  [Creator]                          │
├─ 期間切替 ──────────────────────────────┤
│  [7日] [30日] [90日]                        │
├─ KPI カード ────────────────────────────┤
│  ┌──────┬──────┬──────┬──────┐               │
│  │ DAU  │ MAU  │ 平均 │ 平均 │               │
│  │  42  │ 180  │ DL   │ Score│               │
│  └──────┴──────┴──────┴──────┘               │
├─ 一覧 (シグナル色付き) ─────────────────┤
│  ● 緑  alice    score 82  ▮▮▮▮▮ [▶]         │
│  ● 黄  bob      score 45  ▮▮▮   [▶]         │
│  ● 赤  charlie  score 18  ▮     [▶]         │
│                                              │
│  [▶] クリックで詳細展開:                     │
│  ┌─────────────────────────────────────────┐ │
│  │ Heatmap (曜日×時間)                      │ │
│  │ Sparkline: DL / 起動 / Token            │ │
│  │ Token残量バー                            │ │
│  │ 直近イベントタイムライン (30件)          │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

### 5.3 新規コンポーネント

| ファイル | 役割 |
|---|---|
| `components/charts/BarChart.vue` | SVG 縦棒 (期間別バーチャート) |
| `components/charts/Sparkline.vue` | SVG 細い折れ線 (一覧行・詳細用) |
| `components/charts/Heatmap.vue` | SVG 曜日×時間グリッド (アクセスパターン) |
| `components/charts/RadarChart.vue` | SVG レーダー (Creator 詳細・rank median 重ね) |
| `components/charts/SignalDot.vue` | 緑/黄/赤シグナル丸 |

全て自前 SVG、外部ライブラリ不要。

### 5.4 一覧行の見え方

```html
<!-- User 一覧の1行 -->
<div class="row">
  <SignalDot :signal="user.signal" />
  <span>{{ user.username }}</span>
  <span>score {{ user.score }}</span>
  <Sparkline :data="user.sessions_30d" />
  <button @click="expand(user.user_id)">▶</button>
</div>
```

### 5.5 詳細展開パネル

展開時に `/admin/logs/users/{id}/detail` を遅延フェッチして表示。スクロール位置は維持。複数同時展開可。

---

## 6. 実装スコープ

| # | 内容 | 優先度 |
|---|---|---|
| L-01 | DB migration: `activity_logs` テーブル追加 | 高 |
| L-02 | Backend: `POST /me/session/ping` | 高 |
| L-03 | Backend: `POST /orders/{id}/view` | 中 |
| L-04 | Frontend: 主要ページに session ping を仕込む | 高 |
| L-05 | Frontend: 発注詳細 mount 時に view ping | 中 |
| L-06 | Backend: `/admin/logs/users` (サマリ + スコア) | 高 |
| L-07 | Backend: `/admin/logs/creators` (サマリ + スコア) | 高 |
| L-08 | Backend: `/admin/logs/users/{id}/detail` | 中 |
| L-09 | Backend: `/admin/logs/creators/{id}/detail` | 中 |
| L-10 | Frontend: charts/ コンポーネント5種 | 高 |
| L-11 | Frontend: Admin「ログ」タブ + サブタブ + 一覧 | 高 |
| L-12 | Frontend: 詳細展開パネル | 中 |
| L-13 | Frontend: KPI カード | 低 |

---

## 7. 未決事項 / 将来拡張

| # | 内容 |
|---|---|
| L-F01 | CSV エクスポート (admin の手動分析) |
| L-F02 | 異常検知: 短時間の大量DLをフラグ |
| L-F03 | Creator 向け自己分析ページ (`/creator/stats`) |
| L-F04 | 週次・月次バケット切替 |
| L-F05 | スコア重み付けの admin 調整 UI |
| L-F06 | 通知バッジの「未読メッセージ」判定を order_view ベースに移行 |
| L-F07 | activity_logs に `audio_view` `search` 等を追加し検索ログ分析 |
