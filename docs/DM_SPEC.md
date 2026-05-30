# Direct Message 仕様書 (DM_SPEC)

> 最終更新: 2026-05-31
> ステータス: **策定中** (未実装)
> 関連: [ORDER_SPEC §16](ORDER_SPEC.md) (改訂2.4 で Order 内私信を廃止し、本機能に移行)

---

## 1. 目的

**admin と creator の継続的なやりとり** のための、Order に紐づかない 1対1 メッセージ機能。

- creator: 質問・相談・お知らせを admin に投げる
- admin: 連絡事項・案件相談・ランク変更通知などを creator に投げる
- **Order に紐づかない継続的な関係** を担う (Order 内のやりとりは引き続きチケットチャットを使用)

---

## 2. UX 原則 (NOTIFICATION_SPEC §1 の継承)

- DM 通知は **要対応 (action-required)** として扱う (受け取り側はチェックすべきもの)
- 開封 (DM スレッドを開く) で既読化
- アプリの「通知 = 自分のやること」原則に合致

---

## 3. データモデル

### 3.1 `direct_messages`

| カラム | 型 | 説明 |
|---|---|---|
| id | UUID PK | |
| creator_id | UUID FK users.id | 相手となる creator (admin 側は誰でもよい = チーム扱い) |
| sender_id | UUID FK users.id | 実送信者 (admin / creator どちらか) |
| sender_kind | ENUM('admin','creator') | 区別 (UI 表示用) |
| content | TEXT (≤4000 chars) | 本文 |
| attachment_path | TEXT NULL | 将来添付対応 (Phase 4) |
| created_at | TIMESTAMPTZ | |

**インデックス:**
- `(creator_id, created_at DESC)` — スレッド表示用

### 3.2 既読マーカー (NOTIFICATION_SPEC §6 と整合)

- `activity_logs.kind` に `dm_view` を追加
- `target_id`: creator_id (= スレッド単位)
- 既読判定: 「最後の `dm_view` 時刻 < 相手の最新メッセージ時刻」

---

## 4. アクセス制御

| ロール | 操作 |
|---|---|
| user | × (DM 機能自体を提供しない) |
| creator | 自分宛のスレッドのみ閲覧/送信 |
| admin (誰でも) | **全 creator** との全 DM 閲覧/送信 (admin はチーム扱い、§4.1 参照) |

### 4.1 admin チーム扱いの理由

複数 admin がいる場合、別 admin の応答を見られないと一貫対応ができないため、**admin は全 DM を共有** する。
- creator から見れば「admin」という単一の相手
- admin 同士は誰が応答してもよい
- 送信者は `sender_id` で識別 (UI で「Admin (山田)」のように表示)

---

## 5. API 設計

### 5.1 admin → creator 視点

```
GET  /api/v1/admin/dm/creators              # creator 一覧 (DM スレッドが存在する/しない両方)
GET  /api/v1/admin/dm/creators/{creator_id} # 特定 creator との全 DM
POST /api/v1/admin/dm/creators/{creator_id} # 送信 (body: {content})
POST /api/v1/admin/dm/creators/{creator_id}/view  # 既読化
```

### 5.2 creator → admin 視点

```
GET  /api/v1/me/dm/admin       # 自分の admin DM 全件
POST /api/v1/me/dm/admin       # 送信 (body: {content})
POST /api/v1/me/dm/admin/view  # 既読化
```

creator 視点ではスレッドは1本 (admin チーム宛) なので、`creator_id` パラメータは不要。

### 5.3 通知統合 API への追加

[NOTIFICATION_SPEC §5.2](NOTIFICATION_SPEC.md) の `areas` map に `creator_dm` area を追加:

```json
{
  "areas": {
    "creator_dm": {
      "action_count": 2,
      "has_info": false,
      "breakdown": { "unread_threads": 2 }
    },
    ...
  }
}
```

- admin の場合: 未読 DM スレッド数 (= 相手 creator 別の未読)
- creator の場合: 未読 DM 数 (admin との単一スレッドが未読なら 1、既読なら 0)

---

## 6. UI 構成

### 6.1 admin 側

- **エントリ**: `/admin > ユーザ管理 タブ > creator 行 > [DM] ボタン**
- **モーダル or 専用ページ**: クリックでスレッドモーダルが開く (Order チャットと類似の LINE 風 UI)
- **一覧**: `/admin > DM タブ` (将来) で creator 全員 + 未読スレッドを集約表示

### 6.2 creator 側

- **エントリ**: TopNav に **`DM ToAdmin`** メニュー項目を追加
- **専用ページ**: `/dm` で admin との全履歴を表示
- 未読時は TopNav 項目に金ドット + 件数 (Commission と同じパターン)

### 6.3 階層伝播 (NOTIFICATION_SPEC §3)

```
Level 1 (TopNav root)  — totals (DM + Commission 合算)
Level 2 (creator: DM ToAdmin)  — creator_dm 単体
Level 2 (admin: Admin メニュー)  — creator_dm を含む admin 領域合算
Level 3 (admin > DM タブ)  — creator_dm
Level 4 (admin > DM タブ > creator 行)  — その creator との未読あり
```

---

## 7. 実装フェーズ

| Phase | 範囲 | 状態 |
|---|---|---|
| **A** | データモデル + 基本 API (送受信 + 既読) | 未着手 |
| **B** | admin Users タブの [DM] ボタン + モーダル | 未着手 |
| **C** | creator 用 `/dm` ページ + TopNav `DM ToAdmin` | 未着手 |
| **D** | NOTIFICATION 統合 (`creator_dm` area 追加) | 未着手 |
| **E** | 添付ファイル対応 | Phase 4 |
| **F** | WebSocket リアルタイム更新 | Phase 4 |

---

## 8. アンチパターン

| 反例 | 理由 |
|---|---|
| user に DM 機能を提供する | DM は admin↔creator の業務連絡用。user の問い合わせは別チャネル (将来) |
| Order 内に DM を組み込む | Order は3者参加のチケット。DM は admin↔creator の継続関係 (役割が違う) |
| admin ごとに別スレッドを切る | 一貫対応の妨げになる (§4.1) |
| DM を「お知らせ」として乱用 | NOTIFICATION_SPEC §10 の禁則。要対応のみ |

---

## 9. 関連ドキュメント

- [ORDER_SPEC §16](ORDER_SPEC.md) — Order 内私信の廃止経緯
- [NOTIFICATION_SPEC](NOTIFICATION_SPEC.md) — 通知統合 (areas マップに `creator_dm` を追加)
- [LOG_SPEC](LOG_SPEC.md) — `activity_logs.dm_view` の運用
- [DATA_MODEL.md](DATA_MODEL.md) — DB スキーマ全体

---

## 10. 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-31 | 初版策定 (ORDER_SPEC 改訂2.4 と同時) |
