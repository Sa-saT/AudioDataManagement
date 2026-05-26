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
| **user** | `.lic` ファイル (role=user) | 視聴 / ダウンロード (token消費) / ダウンロード済み再取得 / お気に入り |
| **creator** | `.lic` ファイル (role=creator) | user権限に加え、音源アップロード / 編集 / 削除 / 公開設定 |
| **admin** | `.lic` ファイル (role=admin) | 全リソース管理、ユーザ/クリエイター管理、ランク変更、システム設定、lic発行、token手動付与、Creator支払い承認 |

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

- FR-STREAM-01: 視聴は guest を含め全ロール可能。
- FR-STREAM-02: 視聴 (ストリーミング) は token を消費しない (何回でも無料)。
- FR-STREAM-03: 視聴用音源は**原本と同一の非圧縮 PCM `.wav`** を配信する。サーバ側でのトランスコード・ビットレート変換・ダウンミックスを行わない (ビットパーフェクト)。
- FR-STREAM-04: 配信は **HTTP Range Request (RFC 7233, `206 Partial Content`) によるチャンク単位**で行う。`Accept-Ranges: bytes` を必ず返し、シーク・先読みに対応する。
- FR-STREAM-05: 視聴可能な区間は**先頭から最大 60 秒のプレビュー**に限定する。サーバはこの区間を切り出した `*_preview.wav` を事前生成し、ストリーミング配信対象とする。原本へのアクセスは DL 経路でのみ可能とする。
- FR-STREAM-06: 想定する音源スペックの上限は **48 kHz / 24 bit PCM** (スタジオ品質)。これを超えるファイル (96kHz / 32bit float 等) はアップロード時に弾くか、視聴用プレビューのみ 48/24 に dither なしでサンプル単位カットする (Phase 3 で検討)。
- FR-STREAM-07: フロントの波形プレビュー描画は `audios.peaks` (正規化済み配列) を使い、音声本体のデコード結果には依存しない。
- FR-STREAM-08: wavesurfer.js は MediaElement バックエンドで動作させ、`<audio>` の Range 配信を活用する (WebAudio バックエンドの一括 decode は使わない)。
- FR-STREAM-09: ストリーミング URL は短命の signed URL (HMAC + 有効期限) を都度発行する。直リンク貼り付けによる長期再利用を防ぐ。

### 5.4 ダウンロード / トークン消費

- FR-DL-01: ダウンロードは アクティベート済みユーザのみ。
- FR-DL-02: ダウンロード時、`audio.duration_sec` と同値の token を当月分から消費する。
- FR-DL-03: 残 token が不足する場合は DL 不可。「今月の token を使い切りました」メッセージを表示。
- FR-DL-04: DL成功時、音源の `downloaded_by_user_id` にユーザID、`downloaded_at` に現在時刻が記録される。
- FR-DL-05: DL成功と同時に Creator に対する支払いレコード (`creator_payouts`) が生成される。
- FR-DL-06: DL対象ファイルは `.wav` 形式。

### 5.5 My Downloads (ダウンロード済み一覧)

- FR-MYDL-01: メニューから「ダウンロード済み」画面に遷移できる。
- FR-MYDL-02: 自身が DL した全音源を一覧表示する。
- FR-MYDL-03: 一覧から音源を再ダウンロードできる (token消費なし、Creator支払いも発生しない)。
- FR-MYDL-04: 再DL回数はログ (`download_logs`) に記録されるが課金対象外。

### 5.6 月間トークン管理

- FR-TKN-01: ユーザの月間 token 量は licファイルの `monthlyQuotaTokens` で個別に付与される。
- FR-TKN-02: 残 token は毎月 1日 00:00 (JST) にリセットされる。**繰り越しなし**。
- FR-TKN-03: 月途中にアクティベートした場合も、その月は満額付与される。
- FR-TKN-04: ユーザは Dashboard ヘッダや専用画面で「当月の残 token / 付与 token」を確認できる。
- FR-TKN-05: 残 token を使い切ったあと、Admin が手動で追加 token を付与できる (FR-ADM-04 参照)。
- FR-TKN-06: 追加付与された token も当月末で失効する。

### 5.7 Creator機能 (Phase 3)

- FR-CRT-01: `.wav` ファイルをアップロードできる (タイトル / 公開設定)。ユーザ側に価格設定は存在しない。
- FR-CRT-02: 自身がアップロードした音源を編集・削除できる (未売却分のみ削除可)。
- FR-CRT-03: 音源の公開/非公開を切り替えられる。
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

### 5.9 Admin機能 (Phase 3)

- FR-ADM-01: 全ユーザ・全クリエイターを一覧/編集/削除できる。
- FR-ADM-02: クリエイターのランクを変更できる。
- FR-ADM-03: licファイルを発行できる (username / role / monthlyQuotaTokens / expiresAt 指定)。
- FR-ADM-04: 特定ユーザに当月分の追加 token を手動付与できる (FR-TKN-05 連動)。
- FR-ADM-05: Creator 支払いレコードを一覧表示、`pending → paid` にマークできる。
- FR-ADM-06: ランク単価テーブル (FR-PAY-02) を編集できる (将来運用での調整用)。
- FR-ADM-07: システム設定を変更できる。

## 6. 画面一覧

| ID | 画面名 | パス | 主な対象 | 内容 |
|---|---|---|---|---|
| SC-001 | Dashboard | `/dashboard` | 全ロール | 販売中音源一覧、ソート/件数/ページャー、残token表示 |
| SC-002 | Activate | `/activate` | guest | licファイル選択、現在のアクティベート状況 |
| SC-003 | My Downloads | `/me/downloads` | user/creator/admin | 自身がDLした音源一覧、再DLボタン |
| SC-004 | My Quota | `/me/quota` | user/creator/admin | 当月の付与/消費/残量と履歴 |
| SC-101 | 音源詳細 | `/audios/:id` | 全ロール | 大きな波形、メタ、token量、DLボタン |
| SC-201 | Creator: 音源管理 | `/creator/audios` | creator | 自身の音源一覧 (販売中/売却済) (Phase 3) |
| SC-202 | Creator: アップロード | `/creator/upload` | creator | `.wav` アップロード (Phase 3) |
| SC-203 | Creator: 売上 | `/creator/payouts` | creator | 自身の支払い予定/確定一覧 (Phase 3) |
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
