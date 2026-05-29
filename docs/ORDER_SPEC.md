# Commission / Order 機能 要件仕様書

> 最終更新: 2026-05-29 (改訂2)  
> 実装状態: ローカル完了 (Phase 3 #39/40) + 仕様改訂分は **未実装**

---

## 1. 概要

**Commission (発注)** は、ユーザーがオリジナル音源の制作をクリエイターに依頼するチケット型ワークフロー機能。

Dashboard の単発 DL 販売とは独立した仕組みであり、ユーザーとクリエイターの3者 (ユーザー / クリエイター / Admin) が1つの発注チケットを通じてコミュニケーションしながら制作を進める。

### 関係者と役割

| ロール | できること |
|---|---|
| user | 発注作成・提出・キャンセル / メッセージ / 完了ファイルDL |
| creator | 候補打診への応答 / メッセージ / 音源提出 |
| admin | 上記すべて + 候補指名 / クリエイターアサイン / 承認 / 差し戻し / token_cost調整 / 機能フラグ管理 |

### 機能フラグ

`system_settings` テーブルの `commission_enabled = "true"` で機能ON/OFF。  
OFFの場合、関連API全体が `503 COMMISSION_DISABLED` を返す。  
フロントエンドはマウント時に `GET /api/v1/system/commission` で状態を取得し、OFFなら発注画面を非表示にする。  
**Admin の操作:** `/admin > 設定` タブで ON/OFF を切替可能 (実装済み)。

---

## 2. ステータス遷移

```
draft ──[submit by user]──→ open ──[nominate by admin]──→ recruiting
                                 └─────────────────────────────┘
                                         ↓ [assign by admin]
                                      assigned ──[submit-file by creator]──→ reviewing
                                                                                 │
                                                               ┌────[reject]─────┘
                                                               │                 │
                                                            assigned          done ──[DL by user]
                                                                         (token消費・payout生成)
 どのステータスからでも [cancel] → cancelled (done/cancelled からは不可)
```

### 各ステータスの意味

| ステータス | 意味 |
|---|---|
| `draft` | 作成済み・未提出。Userが編集可能な状態 |
| `open` | 提出済み。Adminが確認中 |
| `recruiting` | Admin が候補クリエイターに打診中 |
| `assigned` | クリエイター確定。制作中 |
| `reviewing` | クリエイターが音源を提出。Adminが確認中 |
| `done` | Admin承認済み・完了。Userがファイルをダウンロード可能 |
| `cancelled` | キャンセル済み (token消費なし) |

### 遷移条件まとめ

| 遷移 | 誰が | 前提ステータス | 副作用 |
|---|---|---|---|
| `submit` | user | draft | token残高チェック (消費はしない、予約のみ) |
| `nominate` | admin | open / recruiting | `order_candidate_creators` にレコード追加、status → recruiting |
| `respond` | creator | recruiting | candidate の response_status を accepted/declined に更新 |
| `assign` | admin | open / recruiting | creator確定、token_cost 調整可能 |
| `submit-file` | creator | assigned | ファイルをサーバに保存、status → reviewing |
| `reject` | admin | reviewing | status → assigned (差し戻し)、理由メッセージ記録 |
| `done` | admin | reviewing | **token消費** / **payout生成** / ファイルコピー / status → done |
| `cancel` | user / creator / admin | 全て (done, cancelled 以外) | token消費なし |

---

## 3. サウンドブリーフ (ヒアリングフロー)

発注作成時にウィザード形式でユーザーから聞き出した情報を `orders.brief` (JSONB) に格納する。

**設計思想:**  
`images/GameAudioDirectorHearingFlow.md` に基づき、「ジャンル指定より感情指定を優先」「抽象語を具体に分解」「参考曲は要素まで分解」を UI に落とし込む。

### ウィザード構成 (6ステップ)

#### Step 1: 基本情報 (必須)

| フィールド | 型 | 説明 |
|---|---|---|
| `sound_type` | `"bgm" \| "se"` | BGM か SE のいずれか (1曲ずつの発注のため両方併用は不可。改訂2で `"both"` 削除) |
| `purpose` | `"game" \| "video" \| "podcast" \| "other"` | 用途 |
| `purpose_note` | string | purpose=other 時の自由記述 |
| `length_sec` | number | **曲の長さ (秒)**。スライダー 10〜600 + 数値直接入力可。**この値が `token_cost` になる (1秒=1token)** |
| `desired_deadline` | string (ISO date) | 希望締切日。**デフォルト: 作成日 + 7日**。user が変更可能 |

**タイトル:** 入力フィールドは廃止 (改訂2)。サーバ側で自動生成:  
形式: `YYYYMMDD_<username>_Order #<per-user-serial>`  
例: `20260529_alice_Order #12`  
- `username` は `users.username` をそのまま使用
- serial はユーザごとの通し番号 (alice の #1, bob の #1 ...)
- 編集は不可

#### Step 2: シーン/機能設計 (必須)

**BGM の場合:**

| フィールド | 型 | 説明 |
|---|---|---|
| `bgm_scenes` | `string[]` | 使用シーン (複数可)。選択肢: battle / boss / explore / menu / title / event / ending / ambient / other |
| `bgm_loop` | boolean | ループ再生が必要か |
| `bgm_note` | string | シーン補足 (他シーンとの接続、展開など) |

**SE の場合:**

| フィールド | 型 | 説明 |
|---|---|---|
| `se_trigger` | string | 何をしたときに鳴るか (必須) |
| `se_functions` | `string[]` | SEの役割 (複数可)。選択肢: success / danger / ui / operation / immersion / character |

(改訂2で `"both"` 廃止のため、両セクション同時表示は無くなる)

#### Step 3: 感情設計 (必須・核心)

クリエイターが文脈を正確に把握するための最重要ステップ。「かっこいい」等の曖昧語を排し、感情ラベルで具体化する。

| フィールド | 型 | 説明 |
|---|---|---|
| `emotions_target` | `string[]` | 狙う感情 (1つ以上必須)。狙う感情として選んだものは「避ける感情」に選べない |
| `emotions_avoid` | `string[]` | 避けたい感情 (任意) |
| `memory_impression` | string | 聴後に記憶に残したいイメージ (比喩・体験・感覚で自由記述) |

**感情ラベル一覧 (15種):**

```
excitement (高揚感/興奮), tension (緊張感), fear (恐怖/不安),
relief (安らぎ/安心), loneliness (孤独感), grandeur (壮大さ/圧倒感),
speed (疾走感), sadness (哀愁/切なさ), mystery (神秘/異世界感),
achievement (達成感/充足感), heaviness (重厚感/威圧感),
comfort (心地よさ/まったり感), euphoria (爽快感),
dread (じわじわとした恐怖), wonder (驚き/発見の喜び)
```

**UX 補足:** `memory_impression` のプレースホルダー例:  
「勝てる気がしない圧倒的な巨大感」「息を呑む静寂のあと一気に解放される感じ」

#### Step 4: テクスチャ方向 (任意・スキップ可)

5つの二項対立軸で音の質感を方向付ける。各軸は `"a値" | "mid" | "b値" | ""` の3択。

| フィールド | A側 | B側 |
|---|---|---|
| `tx_organic_electronic` | 有機的 / 生楽器 | 電子的 / シンセ |
| `tx_melody_rhythm` | メロディ重視 | リズム重視 |
| `tx_warm_cold` | 温かい / 柔らかい | 冷たい / 無機質 |
| `tx_sparse_dense` | シンプル / 余白 | 重厚 / 音が多い |
| `tx_static_dynamic` | 静的 / 落ち着いた | 激しい / 展開多い |

値: `"organic"` / `"mid"` / `"electronic"` など軸ごとに固定文字列。未選択は `""`。

#### Step 5: 参考音源 (任意・スキップ可)

参考曲そのものでなく「何の要素を参考にするか」まで分解させることで、クリエイターへの指示精度を高める。

| フィールド | 型 | 説明 |
|---|---|---|
| `reference_urls` | string | 参考音源URL (1行1URL、改行区切り) |
| `reference_elements` | `string[]` | 参考にしたい要素 (複数可) |
| `reference_avoid` | string | 逆に避けたい要素・表現 (自由記述) |

**参考要素の選択肢 (8種):**

```
atmosphere (空気感/雰囲気), bass (低音/ベース感), progression (展開/構成),
tempo (テンポ/グルーヴ), timbre (音色/サウンドデザイン),
melody (メロディライン), rhythm (リズムパターン), density (音の密度/空間感)
```

#### Step 6: 技術仕様・確認 (任意 + 確認)

| フィールド | 型 | 説明 |
|---|---|---|
| `delivery_format` | `"wav48k24b" \| "wav44k16b" \| "any" \| ""` | 納品形式 |
| `note` | string | その他補足 (ゲームエンジン、禁止事項など) |

ステップ末尾に入力内容のサマリーを表示し、`token_cost` (= `length_sec`) と `desired_deadline` を確認して発注。

**改訂2 で削除:** `deadline` (Step 1 の `desired_deadline` に統合) / `budget_range` (token_cost = 曲長で確定するため不要)。

#### 一時保存 (draft)

各ステップに「**一時保存**」ボタンを配置。クリック時:
- 入力済みの内容で `status=draft` の order を作成 (既に draft なら更新)
- モーダルを閉じてもデータが残る
- 次回 `/orders` を開いたとき draft 行が表示され、続きから入力可

未保存のままモーダルを閉じる場合は確認ダイアログを出す。

---

## 4. データモデル

### `orders` テーブル

| カラム | 型 | 説明 |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users | 発注者 |
| `user_serial` | INT NOT NULL | ユーザごとの通し番号 (改訂2で追加)。`user_id` 単位で 1 から採番 |
| `title` | TEXT NOT NULL | 発注タイトル。**改訂2 で自動生成 (`YYYYMMDD_<username>_Order #<user_serial>`)** |
| `description` | TEXT | 自由記述 (レガシー。brief 導入後は主に brief を使用) |
| `brief` | JSONB | サウンドブリーフ (§3 参照) |
| `token_cost` | INT > 0 | 消費 token 数 = `brief.length_sec` (改訂2で自動算出)。Admin の手動調整は廃止 |
| `desired_deadline` | DATE | 希望締切日。デフォルト `created_at + 7日` (改訂2で追加) |
| `status` | ENUM | §2 参照 |
| `assigned_creator_id` | UUID FK → creator_profiles | アサインされたクリエイター |
| `assigned_by_admin_id` | UUID FK → users | アサインしたAdmin |
| `assigned_at` | TIMESTAMPTZ | |
| `done_by_admin_id` | UUID FK → users | 承認したAdmin |
| `done_at` | TIMESTAMPTZ | |
| `file_path` | TEXT | 最終納品ファイルのサーバパス |
| `notified_at` | TIMESTAMPTZ | done になった時刻 (通知バッジ用) |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

**改訂2 で追加するインデックス:** `UNIQUE (user_id, user_serial)`

### `order_candidate_creators` テーブル

| カラム | 型 | 説明 |
|---|---|---|
| `id` | UUID PK | |
| `order_id` | UUID FK → orders (CASCADE) | |
| `creator_id` | UUID FK → creator_profiles (CASCADE) | |
| `sent_by_admin_id` | UUID FK → users (SET NULL) | 打診したAdmin |
| `sent_at` | TIMESTAMPTZ | |
| `response_status` | ENUM | `pending / accepted / declined` |
| `response_at` | TIMESTAMPTZ | |

### `order_messages` テーブル

| カラム | 型 | 説明 |
|---|---|---|
| `id` | UUID PK | |
| `order_id` | UUID FK → orders (CASCADE) | |
| `sender_id` | UUID FK → users (SET NULL) | NULLはSystem |
| `content` | TEXT | メッセージ本文 |
| `attachment_path` | TEXT | 音源提出時のファイルパス |
| `kind` | ENUM | `comment / status_change / submission / rejection / done` |
| `created_at` | TIMESTAMPTZ | |

### `system_settings` テーブル

| key | value | 説明 |
|---|---|---|
| `commission_enabled` | `"true" \| "false"` | Commission機能フラグ |

---

## 5. APIエンドポイント

ベースパス: `/api/v1`

### 一般 (認証不要)

| Method | Path | 説明 |
|---|---|---|
| GET | `/system/commission` | `{ "enabled": bool }` を返す |

### user ロール以上

| Method | Path | 説明 |
|---|---|---|
| GET | `/orders` | 発注一覧 (role別フィルタ) |
| POST | `/orders` | 発注作成 (status=draft) |
| GET | `/orders/{id}` | 発注詳細 (アクセス制御あり) |
| POST | `/orders/{id}/submit` | draft → open。token残高チェックあり |
| POST | `/orders/{id}/cancel` | キャンセル (done/cancelled 以外から) |
| POST | `/orders/{id}/message` | コメント追加 (done/cancelled 以外) |
| GET | `/orders/{id}/file-url` | 完了ファイルのsigned URL取得 (done時・発注者のみ) |
| GET | `/orders/download-file` | signed URL でファイルDL |
| POST | `/orders/{id}/view` | チケット閲覧記録 (改訂2 追加。`activity_logs` に `order_view` 挿入) |
| PATCH | `/orders/{id}/deadline` | 希望締切日変更 (改訂2 追加。user / admin、status≠done/cancelled) |

### creator ロール以上

| Method | Path | 説明 |
|---|---|---|
| POST | `/orders/{id}/respond` | 候補打診への応答 (`accepted / declined`) |
| POST | `/orders/{id}/submit-file` | 音源提出 (multipart, assigned → reviewing) |

### admin ロール

| Method | Path | 説明 |
|---|---|---|
| POST | `/orders/{id}/nominate` | 候補クリエイター指名 (複数可) |
| POST | `/orders/{id}/assign` | クリエイター確定 (token_cost調整可) |
| POST | `/orders/{id}/reject` | 提出差し戻し (reviewing → assigned) |
| POST | `/orders/{id}/done` | 承認・完了 (token消費・payout生成) |
| GET | `/admin/settings` | system_settings 一覧取得 |
| PATCH | `/admin/settings/{key}` | system_settings 更新 |

### アクセス制御ルール

- **user**: 自分の発注のみ閲覧・操作可
- **creator**: 候補としてノミネートされたまたはアサインされた発注のみ閲覧・操作可
- **admin**: **全発注の全メッセージ・全候補・全状態を閲覧可** (実装済み)。チケットの宛先に常時含まれる扱い (= 全やりとりを監督できる)

---

## 6. ビジネスルール

### token 消費タイミング

| タイミング | 処理 |
|---|---|
| `submit` (draft → open) | token 残高チェックのみ (消費しない) |
| `done` (reviewing → done) | `token_consumptions` にレコード追加。`tokens = order.token_cost` |

**注意:** キャンセルした場合はトークン消費なし。`submit` 時点では残高確認のみで予約ではない (Admin が `assign` 時に `token_cost` を変更する場合があるため)。

### Creator payout 生成

`done` 時に `creator_payouts` にレコードを追加。

- `audio_id = NULL` (音源販売の payout と区別)
- `amount_yen = rank_price.unit_price_yen × order.token_cost`
- `status = pending` (Admin が後から `paid` に変更)

ランク単価 (1トークンあたり):

| ランク | 単価 |
|---|---|
| bronze | ¥100 |
| silver | ¥200 |
| gold | ¥400 |
| platinum | ¥800 |

**例:** gold クリエイター、token_cost=60 → payout = ¥24,000

### ファイル保存

| 種別 | パス |
|---|---|
| 提出ファイル (一時) | `{ORDERS_DIR}/submissions/{order_id}.wav` |
| 最終納品ファイル | `{ORDERS_DIR}/{order_id}.wav` |

`done` 処理時に提出ファイルを最終パスにコピーし、`orders.file_path` に記録。

完了ファイルのDLは **HMAC signed URL** 方式 (TTL 30秒)。JWT不要。

---

## 6.5 通知ルール (改訂2)

通知は2系統に分ける:

### A. 要対応通知 (action-required)

返信・決裁・作業など、**何らかの操作が必要**な通知。完了するまでバッジに残る。

| イベント | 受信側 | 解除条件 |
|---|---|---|
| 発注 submit (open) | admin | 候補ノミネート完了 |
| ノミネート送信 | 候補 creator 各人 | accept/decline 応答 |
| 「できる送信」 (accept) | admin | 1人を assign |
| assign 確定 | 選ばれた creator | 音源提出 |
| 提出 (reviewing) | admin | done / reject |
| チケット内メッセージ送信 | 自分以外の宛先 (user / creator / admin) | チケットを開く (= `activity_logs` に `order_view` 追加) |
| done | 発注 user | チケットを開く |

**バッジ表示:** 未対応件数を数値で表示 (例: Commission 行に `3`)。  
**色:** メニューバー / Commission 行が **橙 (#ffa500)** + 金 (#ffd700) ドット (実装済み)。

### B. 情報通知 (info-only)

返信不要・読むだけで完了する純情報。**自動解除あり**。

| イベント | 受信側 | 解除条件 |
|---|---|---|
| 「できる送信したのに選ばれなかった」 | 選ばれなかった候補 creator | **Commission を開く** OR **1週間経過** で自動解除 |

**バッジ表示:** 件数は出さず Commission 行の色変化のみ。

### 内部実装

- `activity_logs` (`kind=order_view`, `target_id=order_id`) を「既読」マーカーとして使う
- 各通知ロジックは:  
  「最後に `order_view` した時刻 < 通知発生時刻 (status_change / message.created_at)」を未読と判定
- 情報通知の 1週間自動解除は: `order.updated_at < now - 7days` で除外

---

## 7. フロントエンド構成

| ページ | パス | ロール |
|---|---|---|
| 発注一覧・作成 | `/orders` | user / creator / admin |
| 発注詳細・メッセージ | `/orders/[id]` | アクセス制御あり |
| Admin: 全発注管理 | `/admin` > Commissionタブ | admin |

### 発注作成ウィザード

`OrderBriefWizard.vue` コンポーネント (モーダル内)。  
6ステップウィザード。Step 1-3 は必須、Step 4-5 はスキップ可。  
Step 2 は `sound_type` (BGM/SE/both) によって表示項目が変わる。

### 発注詳細ページ (`/orders/[id].vue`)

- **ブリーフ表示**: カテゴリ別 (基本 / BGMシーン / SE設計 / 感情設計 / テクスチャ / 参考 / 技術仕様) に構造表示
  - 狙う感情: アクセントカラーチップ
  - 避ける感情: 打ち消し線チップ
  - 記憶イメージ: イタリック引用スタイル
- **メッセージスレッド**: kind 別スタイリング (status_change / submission / rejection / done)
- **操作ボタン**: role × status の組み合わせで表示/非表示

---

## 8. エラーコード一覧

| コード | HTTP | 意味 |
|---|---|---|
| `COMMISSION_DISABLED` | 503 | 機能フラグ OFF |
| `INVALID_TOKEN_COST` | 422 | token_cost ≤ 0 |
| `INSUFFICIENT_TOKENS` | 402 | token残高不足 |
| `INVALID_STATE` | 409 | 現在ステータスから遷移不可 |
| `NOT_CANDIDATE` | 403 | 候補でないクリエイターが respond を試みた |
| `FORBIDDEN` | 403 | アクセス権限なし |
| `NOT_FOUND` | 404 | 発注が存在しない |
| `NO_SUBMISSION_FILE` | 409 | done 処理時に提出ファイルが存在しない |
| `NO_LICENSE` | 403 / 422 | ライセンスなし |
| `CREATOR_NOT_FOUND` | 404 | assign 対象のクリエイターが存在しない |
| `INVALID_RESPONSE` | 422 | respond の response 値が不正 |
| `FILE_NOT_FOUND` | 404 | DL 対象ファイルがサーバ上に存在しない |

---

## 9. 未確定・今後の課題

| # | 項目 | 優先度 |
|---|---|---|
| 1 | **通知バッジ (action-required count)** TopNav 実装済み (Phase 3 #41) | ✅ 完了 |
| 2 | **メッセージ未読カウント** `activity_logs.order_view` ベースで再計算する実装 (§6.5 A) | 高 |
| 3 | **情報通知の1週間自動解除** §6.5 B の実装 | 高 |
| 4 | **Token予約**: `submit` 時点で token を soft-lock し残高保護するか (改訂2 で token_cost が固定化されたため優先度低下) | 低 |
| 5 | **Creator 複数提出**: reject → 再提出のたびに同じパスを上書きしている。バージョン管理が必要か | 中 |
| 6 | **発注編集**: draft 状態のブリーフを編集する API / UI が未実装。改訂2 で「一時保存」UI を追加するため設計が必要 | 高 |
| 7 | **ストレージ移行**: 開発はローカルストレージ。本番は S3 互換に切替が必要 | Phase 4 |
| 8 | **クリエイター側のブリーフ確認 UI**: 候補打診時にブリーフを見た上で `accept/decline` するが、現在の詳細ページはユーザー視点で設計。クリエイター向けに最適化するか | 中 |
| 9 | **SE 納品の複数ファイル対応**: SE は複数バリエーションを納品するケースが多い。現在は1ファイル (wav) のみ対応 | 要検討 |

---

## 10. 用語

| 用語 | 説明 |
|---|---|
| 発注 / Order | ユーザーが制作依頼を出すチケット1件 |
| サウンドブリーフ / Brief | 発注時にウィザードで入力した構造化ヒアリングデータ (JSONB) |
| 候補 / Candidate | Admin が打診したクリエイター。応答前は pending |
| 提出 / Submission | クリエイターが音源ファイルをアップロードするアクション |
| 差し戻し / Reject | Admin が提出を却下し、assigned に戻す操作 |
| Commission | 本機能全体の名称。単発DL販売 (Dashboard) とは独立 |

---

## 11. 改訂2 サマリ (2026-05-29)

ユーザ要望に基づく仕様変更点。**未実装** — 次回セッションでフロント/バックエンドに反映する。

### 11.1 入力仕様の変更

| # | 変更 | 影響範囲 |
|---|---|---|
| R2-01 | **発注タイトル入力廃止** → サーバ側で `YYYYMMDD_<username>_Order #<user_serial>` 自動生成 | orders スキーマ (`user_serial` 追加 / `title` 仕様変更) / CreateOrderRequest / Wizard step6 / 一覧表示 |
| R2-02 | `sound_type` から **`both` 削除** (`bgm` / `se` の二択) | OrderBriefWizard step1/step2 / OrderBrief 型 / 詳細画面の表示分岐 |
| R2-03 | **希望締切 (`desired_deadline`)** Step1 に追加 / デフォルト `created_at + 7日` / user 編集可 | orders スキーマ / Wizard step1 / 詳細画面に編集 UI |
| R2-04 | **`token_cost` 自動算出** = `length_sec`。手入力廃止 / Step1 で曲長スライダー (10〜600s) + 直接入力 | Wizard step1 / step6 / API (token_cost を body で受けない) |
| R2-05 | Step6 から `deadline` `budget_range` 削除 | Wizard step6 / OrderBrief 型 |

### 11.2 ドラフト保存 UI

| # | 変更 |
|---|---|
| R2-06 | 各 step に「**一時保存**」ボタン追加。`status=draft` で保存。再開可能 |
| R2-07 | モーダル close 時に未保存なら確認ダイアログ |
| R2-08 | 既存 draft があれば `/orders` 一覧で先頭に「[編集] 続きから入力」リンク表示 |

### 11.3 通知ルール再設計 (§6.5 参照)

| # | 変更 |
|---|---|
| R2-09 | 通知を **要対応 (action-required)** / **情報 (info-only)** に二分類 |
| R2-10 | メッセージ未読: `activity_logs.order_view` の最終時刻と比較して件数バッジ表示 |
| R2-11 | 「できる送信したのに選ばれなかった」(情報) は **開く** OR **1週間** で自動解除 |
| R2-12 | `POST /orders/{id}/view` を追加し、詳細ページ open 時に activity_logs へ記録 |

### 11.4 admin 権限の明文化

| # | 変更 |
|---|---|
| R2-13 | admin は全 user/creator のチケット全閲覧可。チケットの宛先に常時含まれる扱い (実装は現状通り) |

### 11.5 必要マイグレーション

```sql
-- 改訂2 用 alembic migration
ALTER TABLE orders ADD COLUMN user_serial INT;
ALTER TABLE orders ADD COLUMN desired_deadline DATE;
-- title はそのまま (auto-generate に切替、DB スキーマ変更なし)
CREATE UNIQUE INDEX uq_orders_user_serial ON orders (user_id, user_serial);
-- 既存 draft/open には user_id 単位で連番を埋める backfill が必要
```

### 11.6 残課題 (改訂2 で未確定)

| # | 内容 |
|---|---|
| R2-Q1 | `sound_type=both` で既に作成済みの order の扱い (data migration するか UI 表示のみ対応か) |
| R2-Q2 | `desired_deadline` を過ぎた order の扱い (アラート色 / 自動キャンセル / 何もしない) |
| R2-Q3 | 「一時保存」中の draft をユーザが放置した場合の自動削除ポリシー (例: 30日未操作で消す) |
