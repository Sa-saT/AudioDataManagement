# 要件定義書 — Audio Data Management (ADM)

## 1. 概要

サウンドクリエイター向けの音響データ管理アプリ。
クリエイターが制作した音源 (`.wav`) を登録・公開し、ユーザがブラウザ上で視聴・ダウンロードできるWebアプリケーション。

- フロントエンド: Nuxt 4 (Vue 3, TypeScript, TailwindCSS, Pinia, wavesurfer.js)
- バックエンド: FastAPI + PostgreSQL + JWT
- 音源ストレージ: 開発環境では `/storage/sounds/`

## 2. 目的・背景

- クリエイターと利用者を直接つなぐ音響データ供給プラットフォームを提供する。
- ライセンスファイル (`.lic`) を介した固有識別により、利用者/作家を一意に紐づける。
- **単発販売モデル**: 各音源はシステム全体で1人のユーザにのみダウンロードされる (1音源 = 1販売)。Creator収入は Admin から支払われる買い切り型。
- **トークン定額制**: ユーザは月間 token (= 音源の秒数) でダウンロード可能量を消費する。

## 3. スコープ

| フェーズ | 内容 | 状態 |
|---|---|---|
| Phase 1 | フロント画面の基礎 (Dashboard / Activate)、Piniaストア、wavesurfer.js プレビュー、ダミー音源 | 完了 |
| Phase 2 | FastAPI + PostgreSQL 接続、`/auth/activate` `/audios` `/audios/{id}/download`、token消費・lic検証、実 `.wav` 配信 | 未着手 |
| Phase 3 | Creator向けアップロード/編集、Admin管理画面 (lic発行/token手動付与/payout承認/ランク変更)、My Downloads、検索/タグ | 未着手 |
| Phase 4 | 本番運用 (CDN, バックアップ, ロギング, 監視) | 未着手 |

非対象: モバイルネイティブアプリ、リアルタイム共同編集、DAW的な編集機能、ユーザ間個別決済。

## 4. ユーザロール

| ロール | 識別方法 | 主な権限 |
|---|---|---|
| **guest** | 未アクティベート | 公開音源の閲覧・視聴 (ストリーミング再生) のみ。ダウンロード不可 |
| **licensee** | `.lic` ファイル (role=licensee) | 視聴 / ダウンロード (token消費) / ダウンロード済み再取得 / お気に入り |
| **creator** | `.lic` ファイル (role=creator) | 音源アップロード / 編集 / 削除 / 公開設定。**自身がアップロードした音源のみ DL可能 (token消費なし、sold遷移なし)**。他の Creator 音源は DL 不可。**sold 状態の音源に対する編集・削除権限を失う。** |
| **admin** | `.lic` ファイル (role=admin) | 全リソース管理、ユーザ/クリエイター管理、ランク変更、システム設定、lic発行、token手動付与、Creator支払い承認。**全音源 DL可能 (token消費なし、sold遷移なし)**。sold状態の音源も含め編集・削除が可能。 |

> サイト初回アクセス時は guest として Dashboard が表示される。`/activate` で `.lic` を適用するとユーザ名・ロール・月間token量が反映される。

## 5. 機能要件

### 5.1 認証 / アクティベート

- FR-AUTH-01: 初回アクセス時、ユーザは guest として Dashboard に遷移する。
- FR-AUTH-02: `/activate` 画面で `.lic` ファイルをアップロードできる。
- FR-AUTH-03: licファイルのパース成功で、ユーザ名・ロール・月間token量が反映される。
- FR-AUTH-04: licファイルは localStorage に永続化される (Phase 2 では JWT に置換)。
- FR-AUTH-05: TopNav の「解除」ボタンで guest 状態に戻せる。

### 5.2 Dashboard (販売中音源一覧)

- FR-DASH-01: 音源を一覧表示する。1件は波形 / タイトル / クリエイター名 / token量 (=秒数) / 操作ボタンを含む。
- FR-DASH-02: 並び順は「オススメ順 / 新着順」から選択可能。
- FR-DASH-03: 1ページあたりの表示件数を 25 / 50 / 100 / 200 から選択可能。
- FR-DASH-04: ページャーで前後ページに移動できる。
- FR-DASH-05: 各カードに wavesurfer.js による波形プレビュー + 再生/一時停止ボタンを表示。
- FR-DASH-06: **既にダウンロード済み (= 売却済み) の音源は表示しない** (誰か1人がDL → 全員に非表示)。
- FR-DASH-07: 非アクティベート時に DL ボタンを押すと注意メッセージを表示。

### 5.3 視聴 / ストリーミング

クライアント / ユーザ共にサウンドのプロを想定しており、**視聴時にもアプリ側の音質劣化を発生させない**ことを必須要件とする。
未アクティベートの guest にも音源の良さを体験させ、営業・加入促進に活用できる設計とする。

- FR-STREAM-01: 視聴は **JWT 不要。guest を含め全ロール可能**。
- FR-STREAM-02: 視聴は token を消費しない (何回でも無料)。
- FR-STREAM-03: 視聴用音源は**原本と同一の非圧縮 PCM `.wav`** を配信する。サーバ側でのトランスコード・ビットレート変換・ダウンミックスを行わない (ビットパーフェクト)。
- FR-STREAM-04: 視聴は**動的チャンク切り出し**方式。クライアントが `?start=秒` を指定し、サーバが原本から `start` 〜 `start+10 秒` の PCM wav をリアルタイムで切り出して返す。事前生成ファイルは持たない。
- FR-STREAM-05: 1リクエストあたりのチャンク長は **10 秒固定** (サーバ設定 `PREVIEW_DURATION_SEC`)。`start` は `0` 〜 `duration_sec - 1` の範囲で任意指定可能。範囲外は 400。
- FR-STREAM-06: 想定する音源スペックの上限は **48 kHz / 24 bit PCM** (スタジオ品質)。これを超えるファイルはアップロード時に拒否する。
- FR-STREAM-07: フロントの波形描画は `audios.peaks` (正規化済み配列) のみで行い、音声デコード結果に依存しない。wavesurfer.js は波形表示専用として使用する。
- FR-STREAM-08: 音声再生は **Web Audio API (AudioContext)**。`fetch` でチャンク取得 → `decodeAudioData` → `AudioBufferSourceNode.start`。波形クリック時に `start` を算出して10秒チャンクを取得・再生する。
- FR-STREAM-09: 視聴 URL は短命 signed URL (HMAC-SHA256 + 有効期限 30 秒)。直リンクの長期再利用・一括ダウンローダー対策。

### 5.4 ダウンロード / トークン消費

- FR-DL-01: ダウンロードは アクティベート済みユーザのみ。
- FR-DL-02: ダウンロード時、`audio.duration_sec` と同値の token を当月分から消費する。
- FR-DL-03: 残 token が不足する場合は DL 不可。「今月の token を使い切りました」メッセージを表示。
- FR-DL-04: DL成功時、音源の `downloaded_by_user_id` にユーザID、`downloaded_at` に現在時刻が記録される。
- FR-DL-05: DL成功と同時に Creator に対する支払いレコード (`creator_payouts`) が生成される。
- FR-DL-06: DL対象ファイルは `.wav` 形式。
- FR-DL-07: DL成功時、原本のコピーが購入者の Downloads ストレージ (`/storage/downloads/{user_id}/{audio_id}.wav`) に保存される。以降、購入者は signed URL 経由でこのコピーから再DLできる (FR-MYDL-03)。
- FR-DL-08: 購入者の Downloads ストレージには licファイルで設定した容量上限 (`max_download_storage_bytes`) がある。DL後のコピー格納でこの上限を超える場合は DL 不可とし、「ストレージ容量が不足しています」を表示する。
- FR-DL-09: **sold状態に遷移した音源に対して、アップロード元 Creator の編集・削除権限は即座に消滅する。** その後の管理権限は Admin のみが持つ。購入者 (DL licensee) は自身の Downloads ストレージ内のコピーのみ管理できる (削除してストレージを解放可能)。
- FR-DL-10: **Creator は自身がアップロードした音源のみ DL可能。** token消費なし。DL しても音源は sold 状態に遷移しない (`downloaded_by_user_id` は変更されない)。他の Creator の音源はDL不可 (`CREATOR_CANNOT_DOWNLOAD`)。ログには `admin_preview` として記録する。
- FR-DL-11: **Admin は全音源を DL可能。** token消費なし。DL しても音源は sold 状態に遷移しない。ログには `admin_preview` として記録する。

### 5.5 My Downloads (ダウンロード済み一覧)

- FR-MYDL-01: メニューから「ダウンロード済み」画面に遷移できる。
- FR-MYDL-02: 自身が DL した全音源を一覧表示する。
- FR-MYDL-03: 一覧から音源を再ダウンロードできる (token消費なし、Creator支払いも発生しない)。再DL元は `/storage/downloads/{user_id}/{audio_id}.wav` のコピー。
- FR-MYDL-04: 再DL回数はログ (`download_logs`) に記録されるが課金対象外。
- FR-MYDL-05: Downloads ストレージの使用量 / 上限 (`max_download_storage_bytes`) を画面上で確認できる。
- FR-MYDL-06: 一覧からファイルを削除できる。削除するとストレージのコピーが破棄され、容量が解放される。**削除後は再DL不可**。元の音源は sold 状態のため Dashboard にも表示されない。

### 5.6 月間トークン管理

- FR-TKN-01: ユーザの月間 token 量は licファイルの `monthlyQuotaTokens` で個別に付与される。
- FR-TKN-02: 残 token は毎月 1日 00:00 (JST) にリセットされる。**繰り越しなし**。
- FR-TKN-03: 月途中にアクティベートした場合も、その月は満額付与される。
- FR-TKN-04: ユーザは Dashboard ヘッダや専用画面で「当月の残 token / 付与 token」を確認できる。
- FR-TKN-05: 残 token を使い切ったあと、Admin が手動で追加 token を付与できる (FR-ADM-04 参照)。
- FR-TKN-06: 追加付与された token も当月末で失効する。

### 5.7 Creator機能 (Phase 3)

- FR-CRT-01: `.wav` ファイルをアップロードできる (タイトル / 公開設定)。ユーザ側に価格設定は存在しない。
- FR-CRT-02: 自身がアップロードした音源を編集・削除できる。**ただし `sold` 状態 (`downloaded_by_user_id` が設定済み) の音源は編集・削除不可。** sold後はその音源への一切の書き込み権限を失う (FR-DL-09)。
- FR-CRT-03: 音源の公開/非公開を切り替えられる (未売却音源のみ)。
- FR-CRT-04: 自身の累計 DL 数 / Creator 支払い予定額 / 確定額を確認できる。

### 5.8 Creator支払い (Phase 3)

- FR-PAY-01: 音源が DL されると、その時点の Creator ランクに応じた固定単価が支払い対象となる。
- FR-PAY-02: ランク × 単価 (1DLあたり、円):
  - bronze = 100
  - silver = 200
  - gold = 400
  - platinum = 800
- FR-PAY-03: 各音源について支払いは生涯1回のみ (単発販売モデル)。
- FR-PAY-04: 支払いレコードは Admin が「支払済」に手動でマークする (実送金は外部)。

### 5.10 発注機能 — Commission (Phase 3)

ユーザがオリジナル音源の制作を依頼するチケットベースの仕組み。Dashboard の DL フローとは独立しており、発注音源は Dashboard に登録されない。

#### チケットの状態遷移

```
draft (ユーザが下書き中)
  └─ open (ユーザが送信 → Admin 受信)
       └─ recruiting (Admin が Creator を指名・送信。Creator の返信待ち)
            └─ assigned (Admin が受注 Creator を確定)
                 └─ reviewing (Creator が音源を添付・提出 → Admin 確認待ち)
                      ├─ done (Admin が [Done] → User 通知 + 音源格納) ← 終端
                      └─ assigned (差し戻し → Creator が再提出)
cancelled (任意の段階でキャンセル可)
```

#### 機能フラグ

- FR-ORD-00: 発注機能は **デフォルト無効**。Admin 画面のシステム設定から ON/OFF を切り替えられる (`system_settings.commission_enabled`)。
  - OFF 時: ユーザ・Creator メニューに「発注」を表示しない。API も 503 を返す。
  - ON 時: 全機能が有効になる。

#### 機能要件

- FR-ORD-01: アクティベート済みユーザはメニューの「発注」から発注チケットを作成できる。
- FR-ORD-02: チケットには「タイトル」「依頼内容 (詳細説明)」「消費 token 量 (カスタム指定)」を記入する。token 量は admin が確認・調整できる。
- FR-ORD-03: チケット送信時に指定 token 量分の残高を確認する。残高不足の場合は送信不可。token の実消費は Done 時点。キャンセル時は消費なし。
- FR-ORD-04: Admin はメニューの「発注管理」から発注一覧を確認し、任意の Creator を個別指名してチケットを送信 (push) できる。同一チケットに複数の候補 Creator へ送信可 (返信を見て受注者を選ぶため)。
- FR-ORD-05: 指名を受けた Creator は「発注」メニューでチケットを確認し、チケット内でメッセージ (受諾・辞退・提案) を返信できる。
- FR-ORD-06: Admin は Creator からの返信を確認し、受注 Creator を1名に確定する。確定されなかった他の候補への通知は Admin が手動で行う (Phase 3 はシンプル実装)。
- FR-ORD-07: 受注確定後、Creator はチケット内に `.wav` ファイルを添付して提出できる。差し戻し後の再提出も可。
- FR-ORD-08: Admin は提出音源を確認し、[Done] または [差し戻し] を選択できる。差し戻し時はメッセージを付与。
- FR-ORD-09: Admin が [Done] をマークすると次が同時実行される:
  - 指定 token 量を購入者の当月 token から消費する
  - Creator への支払いレコード (`creator_payouts`) を生成 (ランク単価ベース、token_cost × ランク単価)
  - 音源ファイルを `/storage/orders/{order_id}.wav` に確定保存
  - User に通知 (フロント側のバッジ・通知リスト)
- FR-ORD-10: 発注音源は Dashboard に登録されない。通常 `audios` テーブルとは別の独立管理 (`orders` テーブル)。
- FR-ORD-11: User はメニューの「発注」からチケット一覧 + 状態 + メッセージ履歴を閲覧できる。
- FR-ORD-12: Done 済みの発注音源は「発注」セクションから何度でも再DL可能 (token 消費なし)。
- FR-ORD-13: Creator の発注支払いはランク単価ベース。ただし token_cost が duration_sec 相当でない場合は token_cost そのものを換算基準とする (Admin の裁量で調整可)。

### 5.9 Admin機能 (Phase 3)

- FR-ADM-01: 全ユーザ・全クリエイターを一覧/編集/削除できる。
- FR-ADM-02: クリエイターのランクを変更できる。
- FR-ADM-03: licファイルを発行できる (username / role / monthlyQuotaTokens / expiresAt 指定)。
- FR-ADM-04: 特定ユーザに当月分の追加 token を手動付与できる (FR-TKN-05 連動)。
- FR-ADM-05: Creator 支払いレコードを一覧表示、`pending → paid` にマークできる。
- FR-ADM-06: ランク単価テーブル (FR-PAY-02) を編集できる (将来運用での調整用)。
- FR-ADM-07: システム設定 (`system_settings`) を変更できる。発注機能の ON/OFF スイッチを含む。

## 6. 画面一覧

| ID | 画面名 | パス | 主な対象 | 内容 |
|---|---|---|---|---|
| SC-001 | Dashboard | `/dashboard` | 全ロール | 販売中音源一覧、ソート/件数/ページャー、残token表示 |
| SC-002 | Activate | `/activate` | guest | licファイル選択、現在のアクティベート状況 |
| SC-003 | My Downloads | `/me/downloads` | licensee/creator/admin | 自身がDLした音源一覧、再DLボタン |
| SC-004 | My Quota | `/me/quota` | licensee/creator/admin | 当月の付与/消費/残量と履歴 |
| SC-101 | 音源詳細 | `/audios/:id` | 全ロール | 大きな波形、メタ、token量、DLボタン |
| SC-201 | Creator: 音源管理 | `/creator/audios` | creator | 自身の音源一覧 (販売中/売却済) (Phase 3) |
| SC-202 | Creator: アップロード | `/creator/upload` | creator | `.wav` アップロード (Phase 3) |
| SC-203 | Creator: 売上 | `/creator/payouts` | creator | 自身の支払い予定/確定一覧 (Phase 3) |
| SC-401 | 発注一覧 (Licensee) | `/orders` | licensee/creator/admin | 自身の発注チケット一覧・状態確認 (Phase 3) |
| SC-402 | 発注詳細 | `/orders/:id` | licensee/creator/admin | チケット本文・メッセージ履歴・提出音源 (Phase 3) |
| SC-403 | 発注管理 (Admin) | `/admin/orders` | admin | 全発注チケット管理・Creator 指名・Done処理 (Phase 3) |
| SC-301 | Admin: ユーザ管理 | `/admin/users` | admin | (Phase 3) |
| SC-302 | Admin: クリエイター管理 | `/admin/creators` | admin | ランク変更含む (Phase 3) |
| SC-303 | Admin: 音源管理 | `/admin/audios` | admin | (Phase 3) |
| SC-304 | Admin: ライセンス発行 | `/admin/licenses` | admin | lic生成 / 失効 (Phase 3) |
| SC-305 | Admin: Creator支払い | `/admin/payouts` | admin | pending→paid マーク (Phase 3) |
| SC-306 | Admin: 追加token付与 | `/admin/token-grants` | admin | ユーザへの追加token手動付与 (Phase 3) |

## 7. 非機能要件

| カテゴリ | 内容 |
|---|---|
| 性能 | Dashboard 初回表示 < 2秒 (50件想定)。波形描画は擬似peaks経由でクライアント計算ゼロ。 |
| 可用性 | 開発環境は手元、本番は単一リージョン (将来見直し)。 |
| 同時性 | 単発販売モデルのため、同一音源への DL リクエストは DBレベルで排他制御 (トランザクション + `audios.downloaded_by_user_id IS NULL` の条件付き UPDATE) する。 |
| セキュリティ | licファイルは Phase 2 で HMAC 署名検証。JWT は短期 (1h) + リフレッシュトークン (Phase 2)。ダウンロードURLは署名付き (Phase 2)。 |
| 監査 | アクティベート / DL / 再DL / アップロード / token付与 / payout承認 をログ。 |
| ジョブ | 月初リセットは「当月分は使えない」というクエリ条件 (`period_yyyymm`) で表現するため、定期ジョブの実体は不要。 |
| 国際化 | 初期は日本語のみ。将来 i18n 対応の余地を残す。 |
| ブラウザ | Chrome / Edge / Safari の最新2バージョン。 |
| ストレージ | 開発: ローカル `/storage/sounds/`。本番: S3互換 (将来)。 |

## 8. 用語集

| 用語 | 説明 |
|---|---|
| licファイル | ロール・ユーザ名・月間token量を含むライセンスファイル (`.lic`) |
| token | ダウンロード可能量の単位。**1秒 = 1 token** (音源の `duration_sec` と同値) |
| 月間token量 | licファイルで個別に付与される、毎月リセットされるユーザの DL 許容量 |
| 単発販売 | 1音源 = 1ユーザにしか売れない、唯一在庫モデル |
| ランク | クリエイターの段位 (bronze/silver/gold/platinum)。1DLあたりの支払い単価が決まる |
| ランク単価 | bronze=100 / silver=200 / gold=400 / platinum=800 円 (FR-PAY-02) |
| peaks | 波形描画用の正規化サンプル値 (0..1)。サーバが事前計算してDB保存 |

## 9. 関連ドキュメント

- [データモデル](./DATA_MODEL.md)
- [API仕様](./API_SPEC.md)
- [licファイル仕様](./LICENSE_FILE_SPEC.md)
- [UIデザイントークン](../DESIGN.md)
