# 将来タスク & Phase 4 残作業

> **用途**: じっくり考えたいタスクの一覧。実装判断の際にここを起点にする。
> **一次ソース**: 各仕様ファイルの「未決事項」「Phase 4 検討」欄。変更時は元ファイルも更新すること。

---

## 1. Phase 4 残作業 — コードなし、設定のみ

コードは実装済み。各 SaaS に接続情報を登録すれば本番稼働できる。

### 1-A. SaaS アカウント作成

| サービス | 用途 | 作業 |
|---|---|---|
| **Sentry** | アプリエラー収集・通知 | アカウント作成 → プロジェクト 2 件作成 (adm-backend / adm-frontend) → DSN 取得。詳細: [MONITORING_SETUP.md §2](MONITORING_SETUP.md) |
| **Better Stack** | `/healthz` 死活監視 (3分間隔/無料) | アカウント作成 → HTTP Monitor 登録 → Slack/LINE 通知連携。詳細: [MONITORING_SETUP.md §3](MONITORING_SETUP.md) |
| **Backblaze B2** | DB・ストレージのバックアップ先 | アカウント作成 → バケット `adm-backups` 作成 → App Key 発行。詳細: [BACKUP_RESTORE.md §GitHub Secrets](BACKUP_RESTORE.md) |
| **Cloudflare** | Pages (フロント配信) + R2 (ストレージ) | アカウント作成 → Pages プロジェクト `adm-pathfinder` 作成 → R2 バケット作成 → API トークン発行 |

### 1-B. GitHub Secrets 登録

GitHub リポジトリ → Settings → Secrets and variables → Actions:

| Secret 名 | 値 | 利用ワークフロー |
|---|---|---|
| `CF_API_TOKEN` | Cloudflare API トークン | deploy-frontend |
| `CF_ACCOUNT_ID` | Cloudflare アカウント ID | deploy-frontend |
| `API_BASE_URL` | 本番 API URL (`https://adm-pathfinder-api.fly.dev`) | deploy-frontend |
| `SENTRY_DSN_PUBLIC` | Sentry フロントエンドプロジェクトの DSN | deploy-frontend |
| `FLY_API_TOKEN` | Fly.io の Deploy Token | deploy-backend |
| `BACKUP_DB_URL` | pg_dump 用接続文字列 (adm_migrator ユーザ) | backup-db |
| `B2_ACCOUNT_ID` | Backblaze B2 アカウント ID | backup-db / backup-storage |
| `B2_APP_KEY` | Backblaze B2 アプリキー | backup-db / backup-storage |
| `B2_BUCKET` | B2 バケット名 (`adm-backups`) | backup-db / backup-storage |
| `R2_ACCESS_KEY_ID` | R2 アクセスキー | backup-storage |
| `R2_SECRET_ACCESS_KEY` | R2 シークレットキー | backup-storage |
| `R2_ENDPOINT_URL` | `https://<account_id>.r2.cloudflarestorage.com` | backup-storage |
| `R2_BUCKET` | R2 バケット名 | backup-storage |

### 1-C. Fly.io secrets 登録

```bash
fly secrets set \
  SENTRY_DSN="https://xxx@oXXX.ingest.sentry.io/YYYY" \
  ENVIRONMENT="production" \
  STORAGE_BACKEND="s3" \
  S3_BUCKET="adm-sounds" \
  S3_ENDPOINT_URL="https://<account_id>.r2.cloudflarestorage.com" \
  S3_ACCESS_KEY_ID="xxx" \
  S3_SECRET_ACCESS_KEY="xxx" \
  S3_REGION="auto" \
  --app adm-pathfinder-api
```

### 1-D. Sentry アラート設定

Sentry ダッシュボードで手動設定。推奨値:

| アラート | 条件 | 通知先 |
|---|---|---|
| エラー急増 | 1 時間で 10 件超 | Slack / Email |
| 新規 Issue | 未見のエラーが発生 | Slack / Email |
| P99 レイテンシ | `/api/v1/audios/stream` が 3 秒超 | Email |

---

## 2. 設計段階・低優先度タスク

### 2-A. Admin ログ拡張 (LOG_SPEC §7: L-F01〜F07)

現状の Admin ログは「集計チャート + 個人詳細展開」まで実装済み。以下は着手判断が必要な拡張。

| # | タスク | 概要 | 着手判断のポイント |
|---|---|---|---|
| **L-F01** | CSV エクスポート | Admin ログの集計データを CSV でダウンロード。外部ツール (Excel / Notion) で二次分析したい時に便利 | 「ダッシュボードで見るだけでは足りない」と感じたら |
| **L-F02** | 異常検知 | 短時間の大量 DL をフラグ立て (bot / 不正利用の早期発見)。activity_logs に閾値判定を追加 | ユーザ数が増えて不正の可能性が出てきたら |
| **L-F03** | Creator 自己分析ページ | `/creator/stats` — 自分の音源の再生数・DL 転換率・ランク指標を creator 本人が確認できる画面 | creator から「自分の数字が見たい」という声が出たら |
| **L-F04** | 週次・月次バケット切替 | 現状は 7/30/90 日の集計のみ。暦週・暦月での集計に切り替える UI | 運用が長期化して「今月の推移」を見たくなったら |
| **L-F05** | スコア重み付け調整 UI | creator スコアの計算式の重み (reaction 率・納品速度 etc.) を admin が GUI で変更できる設定画面 | creator ランク運用を本格化して、重み付けを調整したくなったら |
| **L-F06** | 未読メッセージ判定の精緻化 | 通知バッジの「未読メッセージ」を `order_view` ベースの既読時刻で判定する方式に移行 (現状は別手法)。正確性は上がるが実装コストあり | 通知の誤検知・取りこぼしが問題になったら |
| **L-F07** | 行動ログ拡張 | `activity_logs` に `audio_view` / `search` / `favorite_add` 等を追加して検索・視聴行動を分析できるようにする | 「どの音源がよく試聴されているか」等のデータが欲しくなったら |

### 2-B. WebSocket リアルタイム化

現状はポーリング (60 秒間隔) で通知・チャットを更新。WebSocket に切り替えると即時反映になるが、サーバ実装・インフラコストが増す。

| # | タスク | 概要 | 着手判断のポイント |
|---|---|---|---|
| **WS-1** | 通知リアルタイム化 (NOTIFICATION_SPEC Phase F) | 60 秒ポーリング → WebSocket で即時プッシュ。admin/creator が通知を「気づかず放置」しているという問題が出たら検討 | 「通知に気づくまで 1 分かかる」が実業務で問題になったら |
| **WS-2** | チャット「タイピング中…」表示 (ORDER_SPEC R2.3-Q4) | Commission チケットの LINE 風チャットに typing indicator を追加。相手が入力中か分かるようになる | creator ↔ admin のチャット往復が活発になり、UX 改善要望が出たら |
| **WS-3** | DM リアルタイム更新 (DM_SPEC Phase F) | admin↔creator DM のメッセージを WebSocket で即時受信 | DM の返信遅延が業務上の問題になったら |

### 2-C. DM 添付ファイル (DM_SPEC Phase E)

`direct_messages.attachment_path` カラムは設計済み (migration 0018)。ファイルアップロード UI + storage 保存のみ未実装。

| タスク | 概要 | 着手判断のポイント |
|---|---|---|
| **DM-E** | DM 添付ファイル | admin↔creator の DM にファイル (画像・PDF・参考音源) を添付できるようにする。カラムは既存なので実装コストは低め | creator から「参考素材を送りたい」という声が出たら |

### 2-D. licensee 向け将来機能

現状は設計の議論のみ。着手するには要件定義が必要。

| タスク | 概要 | 着手判断のポイント |
|---|---|---|
| licensee サポート窓口 | DM は admin↔creator 専用。licensee の問い合わせ用チャネル (メール連携 or 別チャット) | licensee からの問い合わせが増えて、個別対応が必要になったら |
| Token grant 申請 UI | licensee が token 追加付与を申請できる画面。現状は admin が手動付与 | ユーザ数が増えて admin の手動対応が追いつかなくなったら |
| lic 発行依頼 UI | 新規ユーザが lic を申請できるフロー。現状は admin が手動発行 | 同上 |

### 2-E. セキュリティ堅牢化

ローカルセキュリティ確認 (2026-06-22) で洗い出した堅牢化項目。悪用可能な脆弱性ではなく、本番公開前の防御強化。

| # | タスク | 概要 | 状態 / 着手判断のポイント |
|---|---|---|---|
| **SEC-1** | アップロード上限 (DoS 対策) | `audios.py` の upload で `shutil.copyfileobj` がサイズ無制限にディスク書き出し。`Content-Length` 検証 + ストリーミング上限を設けて超過時 413 を返す。対応する pytest (サイズ超過→413) も追加 | **調整中** (上限値・拒否方式を検討中)。認証済み creator/admin のみ起こせる availability リスク |

---

## 3. 各タスクのコスト感

| カテゴリ | 実装工数目安 | 難易度 |
|---|---|---|
| Phase 4 残作業 (設定) | 半日〜1 日 | 低 (コードなし) |
| L-F01 CSV エクスポート | 2〜4 時間 | 低 |
| L-F02 異常検知 | 4〜8 時間 | 中 (閾値設計が必要) |
| L-F03 Creator 自己分析 | 1〜2 日 | 中 (新規ページ + 集計 API) |
| L-F04 週次・月次バケット | 2〜4 時間 | 低 |
| L-F05 スコア重み UI | 4〜8 時間 | 中 |
| L-F06 未読判定精緻化 | 4〜8 時間 | 中 |
| L-F07 行動ログ拡張 | 1〜2 日 | 低〜中 (migration + 集計 UI) |
| WS-1〜3 WebSocket | 2〜4 日 | 高 (サーバ設計 + インフラ変更) |
| DM-E 添付ファイル | 4〜8 時間 | 低 (カラム既存、UI + storage のみ) |
| SEC-1 アップロード上限 | 2〜4 時間 | 低 (上限検証 + 413 + テスト) |
