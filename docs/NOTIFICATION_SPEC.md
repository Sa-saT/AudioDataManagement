# 通知システム仕様書 (NOTIFICATION_SPEC)

> 最終更新: 2026-05-31
> ステータス: **Phase A-E 実装済** (Phase F は Phase 4 検討)
> 適用範囲: **アプリ全体** (Commission に限らず admin 業務全般を含む)

---

## 1. 目的・UX 原則

### 1.1 核となる原則

> **通知 = 自分の対応業務**

- 通知があれば → どこかに自分の対応業務がある
- 通知がなければ → 今、自分はやることがない (= 安心していい)
- 通知を辿れば → 必ず操作可能な画面に着く (= 迷子にならない)

この原則を守ることで、ユーザーが **「次に何をすべきか」を考えずに UI に導かれる** アプリを実現する。
([CLAUDE.md](../CLAUDE.md) 冒頭「必要 & やりたいコトを解りやすく導いてくれるアプリ」の実装手段)

### 1.2 守るべき約束

| 約束 | 意味 |
|---|---|
| **通知は嘘をつかない** | 通知が立っている = ユーザーは何か対応しなければならない |
| **通知は迷子にしない** | 通知を辿れば必ず操作可能な画面に着く |
| **通知は読ませない** | 件数・色・位置だけで意味が分かる (テキストを読む必要なし) |
| **通知は永続しない** | 自動解除条件のない通知は作らない |

---

## 2. 通知の3分類

| 種別 | 意味 | 視覚 | 解除条件 |
|---|---|---|---|
| **action-required (要対応)** | 自分の操作で次のステップに進む | 橙 `#ffa500` + 件数バッジ + 金ドット `#ffd700` (左上) | 当該操作の完了 |
| **info-only (情報)** | 状況変化を知らせるだけ。読んだら消える | 青 `#3b82f6` + 小ドット (件数なし) | 対象画面を開く OR **1週間経過** |
| **dim (クローズ済み)** | ※通知ではなく **視覚状態**。詳細は §8 | opacity 50% + muted ラベル | 解除しない (永続) |

**注:** `dim` は「通知」ではない。終了した項目を視覚的に「過去のもの」として示す仕組み。
通知 (action / info) とは独立して機能する (§8 参照)。

---

## 3. 階層伝播モデル

### 3.1 階層レベル定義

```
Level 1: メニューバー本体 (root)
   ↓ 集約
Level 2: メニュー項目 (Dashboard / Admin / Commission / Uploads / DL List)
   ↓ 集約
Level 3: ページ内タブ (admin の8タブ等)
   ↓ 集約
Level 4: 一覧の各行 (order / payout / user / lic 等)
   ↓ (詳細を開けば current)
Level 5: 詳細ページ内セクション (オプション、必要に応じて)
```

### 3.2 伝播ルール

| ルール | 内容 |
|---|---|
| **子→親への昇り** | 子のどこかに通知があれば、親の全階層にも必ず表示される |
| **親は最強通知を表示** | action-required > info-only。子に action があれば親は橙、子が info のみなら親は青 |
| **件数の集約** | Level 2-3 では子の件数を合算 (例: Commission 行に `5`) |
| **dim は伝播しない** | dim は Level 4 (行) 固有の視覚状態。親階層には影響しない |

### 3.3 視覚例 (admin で Payout 3件・Commission 2件の場合)

```
┌─────────────────────────────────────────────────────┐
│ [ロゴ]  Dashboard           [● Admin ▼]            │ ← Level 1: 橙テキスト + 金ドット
└─────────────────────────────────────────────────────┘
                              ↓ メニュー展開
                    ┌──────────────────────┐
                    │ ● Admin           [5] │ ← Level 2 (admin 合算): 橙 + 件数5
                    │ ● Commission      [2] │ ← Level 2 (commission 単体): 橙 + 件数2
                    │   Uploads             │
                    │   DL List             │
                    └──────────────────────┘
                              ↓ Admin をクリック
        ┌──────────────────────────────────────────────────┐
        │ Users  ●Payout(3)  Token  lic  ●Commission(2)    │ ← Level 3: タブごとに集約
        └──────────────────────────────────────────────────┘
                              ↓ Payout タブ選択
        ┌─────────────────────────────────┐
        │ ● [Pending]  creator-A  ¥12,000  │ ← Level 4: 行ごとに自分の出番
        │   [Paid]     creator-B  ¥8,000   │
        │ ● [Pending]  creator-C  ¥3,200   │
        └─────────────────────────────────┘
```

---

## 4. ロール別の通知源

### 4.1 user

| 通知源 | 種別 | 解除条件 |
|---|---|---|
| 自分の発注が `done` になり、creator から提出された | action | 受け取り (`close`) |
| 自分の発注チャットに新メッセージ | action | チケットを開く |

### 4.2 creator

| 通知源 | 種別 | 解除条件 |
|---|---|---|
| 自分が候補にノミネートされた | action | accept / decline 応答 |
| 自分が assigned された | action | 音源提出 |
| 自分のチケットに新メッセージ | action | チケットを開く |
| 候補だった発注が他 creator にアサインされた | info | チケットを開く OR 1週間 |
| **admin からの新着 DM** | action | DM ToAdmin を開く ([DM_SPEC](DM_SPEC.md)) |
| ※ 自分が user として発注している場合は user の通知源も合算 |  |  |

### 4.3 admin

| 通知源 | 種別 | 解除条件 |
|---|---|---|
| **Commission**: 全 user/creator の action 全般 (nominate / assign / done 決裁待ち) | action | 当該操作完了 |
| **Commission**: 全 user/creator のチャットメッセージ (監督枠) | action | チケットを開く |
| **Payout**: 承認待ち creator 支払い | action | paid 化 |
| **Creator DM**: creator からの新着 DM | action | DM スレッドを開く ([DM_SPEC](DM_SPEC.md)) |
| **Token grant 申請** (将来) | action | 付与 / 却下 |
| **lic 発行依頼** (将来) | action | lic 発行 / 却下 |
| ※ 自分が user/creator として参加していれば各通知源も合算 |  |  |

### 4.4 通知源の追加ルール

新しい admin 業務 / ユーザー業務を追加する際は、本仕様の §5 (API) に新しい `area` enum 値を追加するだけで、UI 層は自動的に対応する。新しい spec を書く必要はない。

---

## 5. API 設計

### 5.1 設計思想: 領域非依存 (Area-Agnostic)

通知 API は **領域 (area) 非依存** で設計する。Commission / Payout / Token grant / lic 等を個別エンドポイントにせず、汎用の `area` enum で受ける。

これにより:
- 新領域追加 = enum 値追加のみ (DB スキーマ・API シグネチャ不変)
- フロントは map で回しているので新領域追加時に UI 改修不要

### 5.2 統合エンドポイント

```
GET /api/v1/me/notifications
Authorization: Bearer <token>
```

**レスポンス:**

```json
{
  "areas": {
    "commission": {
      "action_count": 2,
      "has_info": true,
      "breakdown": {
        "action_required": 1,
        "message_unread": 1,
        "info_only": 1
      }
    },
    "payouts": {
      "action_count": 3,
      "has_info": false,
      "breakdown": { "action_required": 3 }
    },
    "token_grants": {
      "action_count": 0,
      "has_info": false,
      "breakdown": {}
    },
    "lic_requests": {
      "action_count": 0,
      "has_info": false,
      "breakdown": {}
    },
    "creator_dm": {
      "action_count": 2,
      "has_info": false,
      "breakdown": { "unread_threads": 2 }
    }
  },
  "totals": {
    "action_count": 5,
    "has_info": true
  }
}
```

- `areas.{name}` は **そのユーザーのロールで利用可能な領域のみ** を返す (user に payouts は返さない)
- `totals` は Level 1 (root) 表示用の集約
- `breakdown` は領域固有の内訳。汎用キー (`action_required`, `message_unread`, `info_only`) + 領域固有キーを許可

### 5.3 既存エンドポイントとの関係

- 既存の `GET /api/v1/me/commission/unread` は **本エンドポイントに統合** し廃止予定 (移行期間中は併存可)
- 一覧エンドポイント (`GET /orders`, `GET /admin/payouts`, etc.) は **各行に `action_required: boolean` フィールドを追加** (Level 4 表示用)

### 5.4 既読化エンドポイント

```
POST /api/v1/me/{area}/view
Body: { "target_id": "<uuid>" }
```

詳細ページ open 時に呼び、`activity_logs` に `kind={area}_view` を記録する。
既存の `POST /api/v1/orders/{id}/view` は本仕様に従い、他領域も同パターンで実装。

### 5.5 ポーリング頻度

- フロント: TopNav マウント時 + 60秒ごと
- ページ遷移時 (Nuxt の `route` watch) にも再取得
- WebSocket 対応は Phase 4 検討事項

---

## 6. 既読判定 (activity_logs ベース)

### 6.1 仕組み

「既読」マーカーは `activity_logs` テーブルに `kind=*_view` で記録。
未読判定 = **「最後に view した時刻 < 通知発生時刻」**。

### 6.2 kind 命名規則

| 領域 | kind |
|---|---|
| Commission | `order_view` |
| Payout | `payout_view` |
| Creator DM | `dm_view` ([DM_SPEC §3.2](DM_SPEC.md)) |
| Token grant 申請 (将来) | `token_grant_view` |
| lic 発行依頼 (将来) | `lic_request_view` |

### 6.3 詳細

[LOG_SPEC.md](LOG_SPEC.md) §2.1 を参照。

---

## 7. デザイントークン

| 種別 | 色 | 用途 |
|---|---|---|
| 要対応 (action) ベース | `#ffa500` (橙) | テキスト・バッジ背景・アイコン stroke |
| 要対応 (action) ドット | `#ffd700` (金) | 左上の「!」相当ドット |
| 情報 (info) ベース | `#3b82f6` (blue-500、暫定) | テキスト・小ドット |
| dim opacity | `0.5` | カード全体の透過度 |
| dim text | `text-muted` (washi muted) | ラベル文言 |

**配色詳細・トークン整合**は [DESIGN.md](../DESIGN.md) と整合させる。info 色は実装時に最終確定。

---

## 8. dim の運用ルール

### 8.1 dim とは

**dim = 「終わったもの」を読まずに判別させる視覚状態**。
通知ではなく、永続的な視覚マーカー。

### 8.2 必要性

| 理由 | 詳細 |
|---|---|
| **読まずに分かる** | 一覧で「これは過去」を一瞬で識別。認知負荷を下げる |
| **悲壮感の回避** | 「選ばれませんでした」等の拒絶表現を使わずに済む。状態で語る |
| **通知 TTL と独立** | 青ドット (info) は1週間で消える。dim は永続。役割が違うため両立 |
| **履歴の一覧表示** | アーカイブに飛ばさず、その場で過去/現在を視覚分離 |

### 8.3 視覚仕様

| 要素 | 通常 | dim |
|---|---|---|
| カード全体 opacity | `1.0` | **`0.5`** |
| テキスト色 | `text-ink` | `text-muted` |
| ステータスラベル | 通常色 | **muted グレー** + 文言「**クローズ**」 |
| 枠線 | `border-hairline` | `border-hairline-soft` |
| hover lift / shadow | あり | **なし** (完全に過去) |
| クリック可否 | 可 | **可** (履歴として開ける) |

### 8.4 dim を適用する場面

| シーン | dim ? |
|---|---|
| 他 creator にアサインされ自分の候補が終わった | ✅ |
| 自分が `declined` したチケット | ✅ |
| `done` になった自分の発注 (受け取り前) | ❌ (受け取りが action) |
| 受け取り完了 (`close` 後) | ✅ |
| `cancelled` チケット | ✅ |

### 8.5 通知との時系列

```
[● 候補中] (橙、通常)
        ↓ 他 creator にアサイン
[  クローズ] (グレー、dim) + 青ドット (info-only)
        ↓ チケットを開く OR 1週間経過
[  クローズ] (グレー、dim のまま) ← 青ドット消える
        ↓ 永続
[  クローズ] (グレー、dim のまま) ← 履歴として残る
```

---

## 9. 実装フェーズ

| Phase | 範囲 | 状態 |
|---|---|---|
| **A** | Commission の Level 1-2 (TopNav バッジ + メニュー Commission 行) | ✅ 実装済 (#41, #43) |
| **B** | 統合 API `/api/v1/me/notifications` + admin タブ Level 3 (Payout/Commission/将来領域) | ✅ 実装済 (3d2f4c1) |
| **C** | 一覧 Level 4 per-row dot (orders / payouts / lic / etc.) | ✅ 実装済 (2d327f1) |
| **D** | Commission クローズ後の **dim 化** (creator 候補だった発注) | ✅ 実装済 (1352576、= ORDER_SPEC 9-A2) |
| **E** | 詳細セクション Level 5 (任意、メッセージスレッド内未読位置等) | ✅ 実装済 (9-A12) |
| **F** | WebSocket リアルタイム通知 | Phase 4 検討 |

---

## 10. 反例・禁則 (これは通知にしない)

| 反例 | 理由 |
|---|---|
| 「キャンペーン中！」「新機能リリース！」等の宣伝 | 自分の対応業務ではない |
| 「ログインしました」「保存しました」等の操作直後の確認 | 操作のフィードバックは別 UI (トースト等) |
| 「他のユーザーがいいねしました」等の他人事 | 自分が何かする必要がない |
| 「現在◯◯人がオンライン」等のシステム状態表示 | 行動を促さない情報は通知にしない |
| 自分が見るだけで意思決定がない情報 | ダッシュボード・一覧で十分 |

---

## 11. 関連ドキュメント

- [REQUIREMENTS.md](REQUIREMENTS.md) — 全体要件
- [ORDER_SPEC.md §6.5](ORDER_SPEC.md) — Commission への適用 (本仕様の特殊化)
- [LOG_SPEC.md](LOG_SPEC.md) — activity_logs データ層
- [DESIGN.md](../DESIGN.md) — カラートークン
- [CLAUDE.md](../CLAUDE.md) — UX 原則の出典

---

## 12. 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-05-30 | 初版策定 (Phase A 実装済を spec 化、Phase B-F を未実装課題として登録) |
| 2026-05-31 | Phase B/C/D 実装完了 (統合 API + admin タブ Level 3 + 一覧 per-row dot + Commission dim 化)。creator_dm area を追加 ([DM_SPEC](DM_SPEC.md) と統合) |
