# ADM 本番運用ガイド

> **目的**: 副業で運用監視できるかを判定し、本番化までの道筋を 1 ページにまとめる
> **対象**: ADM オーナー (= 本人)
> **lic 暗号化の詳細は別ファイル**: [LIC_ENCRYPTION_DEEP_DIVE.md](LIC_ENCRYPTION_DEEP_DIVE.md)

---

## 0. TL;DR

| 規模 | 副業可能性 | 月額コスト | 週あたり工数 |
|---|---|---|---|
| ~100 ユーザ (β/PoC) | **◎ 余裕** | ¥1,500〜¥4,500 | 2〜4 時間 |
| ~1,000 ユーザ (小規模商用) | **○ 可能** (自動化前提) | ¥14,000 | 5〜10 時間 |
| ~10,000 ユーザ (中規模) | **△ 専任化推奨** | ¥150,000〜¥400,000 | 20〜30 時間 |
| 10,000+ | **✗ 本業化必須** | ¥500,000+ | フルタイム |

**推奨スタック**: Cloudflare Pages + Fly.io + Neon + Cloudflare R2 + Sentry
**設計思想**: 運用負荷を SaaS に寄せて、副業時間を「監視」と「機能改善」に集中させる

---

## 1. 前提となるアーキテクチャ

### 1.1 技術スタック

| レイヤ | 技術 | 本番化での注意 |
|---|---|---|
| Frontend | Nuxt 4 (Vue 3 + TypeScript) | 静的ホスティング向き |
| Backend | FastAPI (Python 3.10) + uvicorn | ffmpeg ストリーミング常駐 → CPU 食う |
| DB | PostgreSQL 14+ | JSONB / sequence / FK 多用、マネージド推奨 |
| 音源処理 | ffmpeg `-c:a copy` (10 秒チャンク) | 同時接続が増えるとプロセス数で詰まる |
| 認証 | JWT + HMAC signed URL (TTL 30 秒) | secret rotation の体制要 |
| ストレージ | ローカル `/storage/{sounds,downloads,orders}/` | **本番では S3 互換必須** ← 抽象化実装済 (2026-06-04)。`.env` で `STORAGE_BACKEND=s3` + R2 認証情報を設定するだけ |
| キュー | なし (同期処理) | スケール時に Celery / RQ 検討 |

### 1.2 ADM 固有の制約 — ファイルサイズ

- 48k/24bit/stereo PCM: **約 16.5 MB/分**
- 90 秒 1 曲: **約 25 MB**
- ユーザ 1 人あたり DL 上限 (lic 設定): 例 1 GB = ~40 曲

**結果として storage コストが運用コストの主因**になる。これが選定の前提。

---

## 2. デプロイ構成

### 2.1 サービスの用途 — 各 SaaS は「何の代わりか」

> 複雑なデプロイが初めての場合、各サービスを「自前運用したら何時間消えるか」の視点で理解すると判断が早い。

#### A. アプリ本体

| サービス | 一言で | ADM での用途 | 自前運用なら |
|---|---|---|---|
| **Cloudflare Pages** | 静的サイトを CDN で配る無料ホスト | Nuxt ビルド成果物の配信 | nginx + Let's Encrypt + CDN |
| **Fly.io** | Docker を世界各地に立てる軽量 PaaS | FastAPI + ffmpeg を動かす本体 | EC2 / VPS + Docker 自前管理 |
| **Neon** | PostgreSQL のサーバレス版 | DB 本体 (ローカルからそのまま移す) | RDS / VPS の Postgres 自前 |
| **Cloudflare R2** | S3 互換、**egress 無料** | wav ファイルの保管 + 配信 | EC2 にディスクをアタッチ |

> **ADM 特有のポイント**: wav (1 曲 25 MB) を多数配信するため、egress 無料の R2 が AWS S3 (¥10〜15/GB) より圧倒的に安い。R2 が無ければこの規模で副業運用は厳しい。

#### B. 監視・通知

| サービス | 一言で | 無いと困る瞬間 |
|---|---|---|
| **Sentry** | アプリ内のエラー収集 + 通知 | ユーザが DM するまで気づけない |
| **Better Stack** | URL 死活監視 | Fly.io 自体が落ちたら Sentry も通知不能 |
| **Grafana Cloud (Loki)** | ログ集約と検索 | 障害調査で「あの時何が起きた?」が追えない |

#### C. CI/CD・開発周辺

| サービス | 用途 |
|---|---|
| **GitHub** | source of truth、Issue/PR 運用 |
| **GitHub Actions** | push → 自動デプロイ + alembic migration |

#### D. 必要になったら追加

| サービス | 必要になる時期 |
|---|---|
| **Stripe / PAY.JP** | Creator payout を自動化したい時 (現状は手動振込) |
| **Cloudflare WAF** | 1,000 ユーザ超え or 攻撃を観測した時 |

#### 選定の原則

1. **すべて managed service** — OS パッチ・ログローテ・SSL 更新を自分でやらない
2. **Free tier から始められる** — β は月 ¥0 で立ち上げ可能
3. **段階的スケール** — Free → 有料の移行が GUI で完結
4. **標準連携** — Fly.io ↔ Sentry, GitHub Actions ↔ Fly.io はワンクリック

**避けるべき構成**: 生 EC2 / VPS 1 台運用 (OS 管理が時間泥棒) / AWS フルセット (IAM だけで週末消える) / Vercel + Lambda (ffmpeg 同梱が手間)。

#### 学習順序 (4 週間プラン)

```
1週目: GitHub Actions  (CI 自動化に慣れる)
2週目: Fly.io          (`fly deploy` を体験)
3週目: Cloudflare Pages + R2
4週目: Neon            (DB の本番化)
最後 : Sentry + Better Stack  (監視は仕組みが固まってから)
```

最初から全部やろうとせず、staging に 1 サービスずつ繋ぐのが結果的に早い。

---

### 2.2 規模別の推奨構成

#### β / 100 ユーザ — 最小構成 (約 ¥4,500/月)

```
Cloudflare Pages ── Fly.io ── Neon ── Cloudflare R2
                            └─ Sentry + Better Stack
```

| 項目 | プラン | 月額 |
|---|---|---|
| Cloudflare Pages | Free | ¥0 |
| Fly.io | shared-cpu-1x 256MB × 2 + outbound 100GB | ¥1,500 |
| Neon | **Launch ($19/mo)** — Free tier は suspend するので本番は不可 | ¥3,000 |
| Cloudflare R2 | 100GB | ¥250 |
| Sentry / Better Stack | Free | ¥0 |
| **合計** | | **約 ¥4,500/月** |

#### 1,000 ユーザ — 小規模商用 (約 ¥14,000/月)

```
Cloudflare Pages ── Fly.io (multi-region, auto-scale)
                       │
                    Neon Launch + R2 500GB-1TB
                       │
                    Sentry Team + Grafana Cloud Free
```

| 項目 | 月額 |
|---|---|
| Fly.io (CPU 2x × 3 リージョン) | ¥4,500 |
| Neon Launch | ¥3,000 |
| R2 (500GB) | ¥1,200 |
| Sentry Team | ¥3,500 |
| Backup ストレージ (B2 cold) | ¥1,000 |
| ドメイン / 雑費 | ¥1,000 |
| **合計** | **約 ¥14,000/月** |

#### 10,000 ユーザ — 中規模 (¥150k〜¥400k/月)

副業の範囲外。本格的に検討する場合:

- ECS Fargate / GKE Autopilot
- RDS Aurora Serverless / Cloud SQL
- S3 + CloudFront (or R2 + Cloudflare CDN)
- ElastiCache (Redis) でセッション・レート制限
- Datadog or Grafana Stack

### 2.3 国内ホスティング (法的・心理的要件)

| サービス | 用途 | コメント |
|---|---|---|
| さくらのクラウド / ConoHa VPS | Backend + Storage | 1 台運用で ¥5,000〜¥15,000/月、国内サポート |
| AWS Tokyo region | 全部 | プロ向け、海外サービス連携多い |
| Cloudflare (東京 PoP) | CDN / Pages | 日本向けレイテンシ良好 |
| Stripe Japan / PAY.JP | Creator payout (将来) | 国内振込・税務対応 |

ユーザが日本中心なら **Cloudflare + Neon Asia region** がレイテンシ・コスト両面で有利。

---

## 3. デプロイ運用

### 3.1 CI/CD パイプライン

```
GitHub (main push)
   ├─ GitHub Actions
   │     ├─ Frontend: pnpm build → Cloudflare Pages
   │     └─ Backend:  Docker build → Fly.io deploy + alembic upgrade
   └─ Sentry release tracking (sourcemap 自動 upload)
```

### 3.2 GitHub Actions — Workflow / Job 詳細

`.github/workflows/` に 5 本のワークフローがある。

#### Workflow 一覧

| ファイル | Workflow 名 | トリガー | 用途 |
|---|---|---|---|
| `deploy-frontend.yml` | Deploy Frontend (Cloudflare Pages) | `main` push (`ADM_f/` 変更時) | Nuxt の静的ビルド → Cloudflare Pages へデプロイ |
| `deploy-backend.yml` | Deploy Backend (Fly.io) | `main` push (`ADM_b/` 変更時) | FastAPI を Docker ビルド → Fly.io へデプロイ + DB マイグレーション自動実行 |
| `backup-db.yml` | Backup Database (Daily) | 毎日 JST 03:00 (cron) / 手動 | PostgreSQL を `pg_dump` → gzip → B2 に保存 (7 日分保持) |
| `backup-storage.yml` | Backup Storage (Daily) | 毎日 JST 04:00 (cron) / 手動 | Cloudflare R2 の wav ファイル群を rclone で B2 に差分コピー |
| `deploy-moc.yml` | Deploy mock to Pages | `main` push (`moc/` 変更時) / 手動 | クライアント提案用の静的モック (`moc/`) を GitHub Pages へ配信 |

#### 各 Workflow の Job と Step

**`deploy-frontend.yml` — Job: `Build & Deploy Nuxt SPA`**

| Step | 内容 |
|---|---|
| checkout | ソースを取得 |
| pnpm setup / node setup | pnpm + Node 20 をセットアップ、依存をキャッシュ |
| Install dependencies | `pnpm install --frozen-lockfile` |
| Generate static site | `pnpm generate` で静的 HTML/JS 生成 (env: `API_BASE_URL` / `SENTRY_DSN_PUBLIC`) |
| Deploy to Cloudflare Pages | `ADM_f/.output/public/` を Cloudflare Pages へアップロード |

**`deploy-backend.yml` — Job: `Build & Deploy FastAPI`**

| Step | 内容 |
|---|---|
| checkout | ソースを取得 |
| flyctl setup | Fly.io CLI をセットアップ |
| Deploy to Fly.io | `flyctl deploy --remote-only` — `fly.toml` の `release_command` で `alembic upgrade head` が**デプロイ直前に自動実行**される |

**`backup-db.yml` — Job: `pg_dump → B2`**

| Step | 内容 |
|---|---|
| Install rclone | rclone CLI をインストール |
| Configure rclone (B2) | B2 の認証情報を `~/.config/rclone/rclone.conf` に書き込む |
| pg_dump → gzip | `BACKUP_DB_URL` (Neon の接続文字列) から `pg_dump` → `adm_db_YYYYMMDD.sql.gz` |
| Upload to B2 | `b2:<bucket>/db/` へアップロード |
| Delete dumps older than 7 days | 8 日以上前のダンプを B2 から削除 (7 日保持) |
| Verify upload | B2 の `db/` 直下の最新 5 件を表示して確認 |

**`backup-storage.yml` — Job: `R2 → B2 (rclone copy)`**

| Step | 内容 |
|---|---|
| Install rclone | rclone CLI をインストール |
| Configure rclone (R2 + B2) | R2 (S3 互換) と B2 の両認証情報を設定 |
| Copy R2 → B2 (差分のみ) | `rclone copy` で R2 の全 wav ファイルを `b2:<bucket>/storage/` へ差分コピー (削除はしない) |
| Show B2 storage summary | B2 上のストレージ使用量を JSON で出力 |

**`deploy-moc.yml` — Job: `deploy`**

| Step | 内容 |
|---|---|
| checkout | ソースを取得 |
| configure-pages | `actions/configure-pages@v5` (`enablement: true` で Pages を未設定でも自動有効化) |
| Upload moc/ as Pages artifact | `moc/` ディレクトリを Pages アーティファクトとしてアップロード |
| deploy | `actions/deploy-pages@v4` で GitHub Pages へデプロイ |

> ビルド不要の静的ファイル (HTML/CSS/JS)。Secrets は不要で、既定の `GITHUB_TOKEN` (`pages: write` / `id-token: write`) のみで動く。初回は **Settings → Pages → Source = "GitHub Actions"** を有効化する (または Workflow permissions を Read and write にして `enablement: true` に任せる)。公開 URL: `https://sa-sat.github.io/AudioDataManagement/`

#### 必要な GitHub Secrets

| Secret 名 | 使用 Workflow | 内容 |
|---|---|---|
| `FLY_API_TOKEN` | deploy-backend | Fly.io のデプロイ用トークン |
| `CF_API_TOKEN` | deploy-frontend | Cloudflare Pages デプロイ用トークン |
| `CF_ACCOUNT_ID` | deploy-frontend | Cloudflare アカウント ID |
| `API_BASE_URL` | deploy-frontend | 本番 API URL (例: `https://adm-pathfinder-api.fly.dev`) |
| `SENTRY_DSN_PUBLIC` | deploy-frontend | Sentry の公開 DSN (フロント用) |
| `BACKUP_DB_URL` | backup-db | Neon 接続文字列 (`postgresql://...`) |
| `B2_ACCOUNT_ID` | backup-db / backup-storage | Backblaze B2 アカウント ID |
| `B2_APP_KEY` | backup-db / backup-storage | Backblaze B2 アプリケーションキー |
| `B2_BUCKET` | backup-db / backup-storage | B2 バケット名 |
| `R2_ACCESS_KEY_ID` | backup-storage | Cloudflare R2 アクセスキー |
| `R2_SECRET_ACCESS_KEY` | backup-storage | Cloudflare R2 シークレットキー |
| `R2_ENDPOINT_URL` | backup-storage | R2 エンドポイント URL |
| `R2_BUCKET` | backup-storage | R2 バケット名 |

詳細: [MONITORING_SETUP.md](MONITORING_SETUP.md) §6 / [BACKUP_RESTORE.md](BACKUP_RESTORE.md)

---

### 3.3 Workflow の有効化 / 無効化

公開を一時停止する場合や Secrets 未設定のまま cron が走るのを防ぐために、Workflow を無効化できる。

#### 無効化 (Disable)

1. GitHub → リポジトリ → **Actions** タブ
2. 左サイドバーで対象 Workflow を選択
3. 右上の **`...`** メニュー → **Disable workflow**

> **本番系 4 本すべて無効化する手順**: `Backup Database (Daily)` → `Backup Storage (Daily)` → `Deploy Backend (Fly.io)` → `Deploy Frontend (Cloudflare Pages)` の順に繰り返す。
>
> `Deploy mock to Pages` (`deploy-moc.yml`) は提案用デモの配信で本番アプリとは独立。停止したい場合は同様に Disable する。

#### 有効化 (Enable) — 公開再開時

1. GitHub → **Actions** タブ
2. 左サイドバーで対象 Workflow を選択
3. 黄色バナー **"This workflow is disabled"** の右の **Enable workflow** をクリック

> **再開時の推奨順序**:
> 1. `Deploy Backend (Fly.io)` を Enable → `ADM_b/` に空コミット or 手動 Run で動作確認
> 2. `Deploy Frontend (Cloudflare Pages)` を Enable → 同様に確認
> 3. `Backup Database (Daily)` を Enable
> 4. `Backup Storage (Daily)` を Enable

#### 手動実行 (動作確認用)

Workflow 画面の **Run workflow** ボタン (`workflow_dispatch` トリガー対応) で即時実行できる。
バックアップ系 2 本 + `Deploy mock to Pages` が対応 (本番デプロイ系 2 本は push トリガーのみ)。

### 3.4 環境分離 (最低 3 つ)

- **local** — 開発、`init_db.sh` で構築
- **staging** — 本番と同構成、独立 DB、自分の音源テスト場
- **production** — 顧客向け

> staging で常時検証する体制が無いと、本番デプロイのたびに緊張する。これは副業時間を一番削る。

### 3.5 自動化必須項目

| 自動化 | 内容 | 副業に必須な理由 |
|---|---|---|
| CI/CD | push → 自動デプロイ | 手動デプロイは平日夜を吸う |
| DB マイグレーション | deploy 時に `alembic upgrade head` | 手作業は事故の元 |
| DB バックアップ | Neon は自動 / 自前なら pg_dump cron | 「何時に戻せるか」を明確化 |
| シークレット管理 | Fly.io secrets / GitHub Actions secrets | `.env` ミスコミット防止 |
| 証明書更新 | Cloudflare 自動 (Let's Encrypt) | 期限切れで全停止する |
| ログ集約 | Fly logs → Grafana Loki / Sentry | 1 日 1 回ダッシュボード見るだけで済む |

---

## 4. 運用監視

### 4.1 監視ツール構成

```
[Cloudflare Pages: Nuxt]
    ├─ Sentry Browser SDK ─→ JS エラー / Vitals
    └─ Cloudflare Web Analytics

[Fly.io: FastAPI]
    ├─ Sentry Python SDK ─→ 例外 / Transactions
    ├─ Better Stack ─→ /healthz チェック
    └─ Fly logs ─→ Grafana Loki

[Neon: Postgres]
    ├─ Neon Console ─→ slow query / connections
    └─ pg_dump (自動 + 7 日保持)

[Cloudflare R2]
    └─ R2 Analytics ─→ egress / 容量

通知: Sentry / Better Stack / Fly health ─→ Slack or LINE bot
```

**ツール料金 (1,000 ユーザ規模)**: ¥3,500〜¥7,000/月 (Sentry Team + Better Stack Lite + Grafana Free + Cloudflare Free/R2)

### 4.2 頻度別タスク

#### 日次 (平日 5 分 / 異常時 30 分〜2 時間)

| 項目 | 確認場所 |
|---|---|
| エラー件数 | Sentry (Slack 通知) |
| Uptime | Better Stack |
| 新規ユーザ / 取引 | Admin > ログタブ |
| 失敗 DL / payout | Admin > Payout + Sentry |
| ストリーミング失敗率 | Sentry → ffmpeg error |

#### 週次 (1〜2 時間)

| 項目 | 内容 |
|---|---|
| ストレージ使用量推移 | R2 ダッシュボード、上限の余裕確認 |
| トークン消費パターン | Admin > ログ > User タブで枯渇傾向 |
| クリエイター活動 | Admin > ログ > Creator タブで赤シグナル |
| 未対応 Commission | open / reviewing 長期滞留 |
| Payout pending 残高 | 未払い分を確認 (creator に振込) |
| バックアップ復元テスト | 月 1 回、staging に DB スナップショット復元 |

#### 月次 (4〜6 時間)

| 項目 | 内容 |
|---|---|
| 依存パッケージ更新 | `pnpm update` / `pip-compile`、staging 検証 |
| OS / ランタイム patch | Fly.io image rebuild |
| パフォーマンスレビュー | Sentry traces で slow query / P99 |
| コスト集計 | SaaS 請求書、ストレージ増加率 |
| セキュリティ点検 | 認証ログ異常、不正 DL |
| HMAC secret ローテーション | 半年〜1 年に 1 回 |
| Creator payout 振込 | 銀行振込 (将来 Stripe Connect 自動化) |
| 法務 / 規約レビュー | 利用規約・プラポリ整合 |

#### 四半期 (6〜8 時間)

| 項目 | 内容 |
|---|---|
| Disaster Recovery 演習 | 「DB 全消失」想定で RTO/RPO 計測 |
| キャパシティプランニング | 6 ヶ月後の ユーザ / storage / 帯域予測 |
| 機能改善ロードマップ | ユーザフィードバック集約 |
| 監視ルール見直し | 閾値・通知先・ノイズ削減 |
| 簡易 Penetration test | OWASP ZAP / `pip-audit` / `npm audit` |

#### 年次 (1〜2 日)

- 法定書類 (Creator 支払いの源泉徴収 / 確定申告関連)
- アーキテクチャ全面レビュー
- 利用規約改定
- 主要ライブラリのメジャーバージョン更新計画

### 4.3 クリティカルパス (絶対やる項目)

> これらを満たさない場合は本番運用すべきでない。

1. **DB バックアップ** (自動 + 月 1 回復元テスト)
2. **HMAC / JWT secret の漏洩防止** (環境変数 / シークレット管理)
3. **Uptime 監視 + 即時通知**
4. **Sentry によるエラー監視**
5. **Payout / 課金処理の整合性チェック**
6. **証明書自動更新の確認**
7. **依存ライブラリの脆弱性通知購読** (Dependabot / Snyk)

---

## 5. 副業として現実的か

### 5.1 副業を成立させる 3 原則

1. **アラート駆動運用**
   - ダッシュボード巡回は週次のみ
   - 異常時にのみ Slack/LINE 通知が来る状態を作る
   - 平日は通知が来なければ何もしない

2. **すべて SaaS に寄せる**
   - 自前運用は学習コスト + 時間泥棒
   - 数千円の課金で数時間/週 を買う発想
   - 特にメリット大: DB (Neon), Storage (R2), Errors (Sentry)

3. **手作業を毎週レビューして即座に潰す**
   - 「先週これに 30 分かかった」→ 翌週までにスクリプト化
   - 月次タスクは全部 cron / Actions に
   - 自分が寝込んでも 1 週間止まらない状態を目指す

### 5.2 想定スケジュール (1 週間)

```
月曜 朝    5 分  Slack 通知確認 (週末分)
火-金 夜  5 分  Sentry サマリ (Slack ダイジェスト)
土曜 朝   60 分 週次レビュー: ストレージ / payout / Commission 滞留
土曜 午後 30 分 軽い改善 (issue 1 つ消化)
日曜      休み

→ 週 約 100 分。月次 (4 時間) を加えて月 約 11 時間。
→ 売上が月 ¥60,000〜¥100,000 を超えるあたりで副業として割に合う。
```

### 5.3 主要リスクと緩和策

| リスク | 緩和策 |
|---|---|
| Creator payout の遅延 = 信用毀損 | Stripe Connect / PAY.JP で自動化、最低でも月 1 回固定日 |
| 障害時の対応遅延 | Better Stack + Slack 通知 + 「24 時間以内対応」を SLA 明記 |
| 音源データ消失 | DB / R2 両方のバックアップ + 月次復元テスト |
| 不正利用 (大量 DL / ボット) | Cloudflare WAF + Rate limit + 異常検知 |
| 本人の体調不良で停止 | Runbook (本ドキュメント) 共有可能化、副管理者 1 人確保 |
| 法的問題 (著作権 / 個人情報) | 利用規約整備、DMCA 対応窓口、顧問弁護士 (年契約 月 ¥10,000〜) |

---

## 6. 副業 → 本業化の判断基準

| 指標 | 副業継続 | 本業化検討 |
|---|---|---|
| MRR (月額売上) | 〜30 万円 | 50 万円〜 |
| アクティブユーザ | 〜1,000 人 | 5,000 人〜 |
| 障害頻度 | 月 1 回以下 | 週 1 回以上 |
| 自分の稼働 | 週 10 時間以下 | 週 15 時間以上が常態化 |
| Creator 数 | 〜100 人 | 300 人〜 (信頼確保が重い) |
| サポート問い合わせ | 月 10 件以下 | 月 50 件以上 |

**意思決定**: 上記のうち **3 つ以上が本業化側に振れたら**、専任化 or 共同運営者の確保を真剣に検討。

---

## 7. 学習コスト + 次のアクション

### 7.1 必要な学習領域

| 領域 | 必要レベル | 学習目安 |
|---|---|---|
| Docker / コンテナ基礎 | 読み書き可 | 1 週間 |
| Cloudflare / Fly.io / Neon | 管理画面操作 | 各 1 日 |
| Sentry / Better Stack | ダッシュボード読解 | 各半日 |
| PostgreSQL 運用 | バックアップ / リストア / EXPLAIN | 1 週間 |
| ネットワーク / TLS | 概念理解 | 数日 |
| セキュリティ基礎 (OWASP) | チェックリスト運用 | 1 週間 |

→ 既存スキルがあれば **2〜4 週間で運用可能** な水準に到達できる。

### 7.2 本番化に向けた次のアクション

1. このドキュメントを基に「最小構成」での staging 環境構築 → 動作確認
2. Sentry / Better Stack のアカウント作成 + 統合テスト
3. ~~Cloudflare R2 への storage 移行~~ **✅ 完了 (2026-06-04, ebb9682)** — `.env` に R2 認証情報を設定するだけで切替可
4. ~~CI/CD パイプライン (GitHub Actions) の整備~~ **✅ 完了 (2026-06-04, 6955d1c)** — `.github/workflows/` に deploy-frontend / deploy-backend 追加済み
5. ~~Sentry + Better Stack のアカウント作成 + 統合テスト~~ **✅ コード実装完了 (2026-06-04)** — アカウント作成 + シークレット設定のみ残 (詳細: [MONITORING_SETUP.md](MONITORING_SETUP.md))
6. ~~DB / ストレージバックアップ自動化~~ **✅ 完了 (2026-06-04)** — GitHub Actions cron 2本 (backup-db / backup-storage)。R2→B2 rclone copy + pg_dump 7日保持 (詳細: [BACKUP_RESTORE.md](BACKUP_RESTORE.md))
7. **β リリース対象を 10〜20 人に絞って** 1 ヶ月運用、本ガイドの所要時間を実測

> **重要**: β リリース直後の 1〜3 ヶ月は ユーザ数が少なくても**監視体制の確立**に時間を使う。それを越えれば日次 5 分 + 週末 1 時間で回せるようになる。

実測値が本ガイドと乖離していたら、その時点で構成見直し。

---

## 付録: 関連ドキュメント

- **lic ファイル暗号化の仕組みと実装**: [LIC_ENCRYPTION_DEEP_DIVE.md](LIC_ENCRYPTION_DEEP_DIVE.md)
- **lic ファイル仕様**: [LICENSE_FILE_SPEC.md](LICENSE_FILE_SPEC.md)
- **storage 移行 (9-A8 完了)**: [ORDER_SPEC.md](ORDER_SPEC.md) §9.2 / `ADM_b/app/services/storage.py`
- **監視セットアップ**: [MONITORING_SETUP.md](MONITORING_SETUP.md) (Sentry / Better Stack / JSON ログ / 料金表)
- **バックアップ & リストア**: [BACKUP_RESTORE.md](BACKUP_RESTORE.md) (pg_dump / rclone R2→B2 / 復元手順)
- **将来タスク & Phase 4 残作業**: [FUTURE_TASKS.md](FUTURE_TASKS.md) (設定手順 / 低優先度タスク一覧 / 工数目安)
- **データモデル**: [DATA_MODEL.md](DATA_MODEL.md)
- **要件定義**: [REQUIREMENTS.md](REQUIREMENTS.md)
