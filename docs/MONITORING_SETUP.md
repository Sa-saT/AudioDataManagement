# 監視セットアップガイド

実装済みコードと、各外部サービスのアカウント設定手順をまとめる。

---

## 1. ツール構成と料金

```
[Cloudflare Pages: Nuxt SPA]
    ├─ @sentry/vue       → JS 例外・Vue エラー → Sentry
    └─ Cloudflare Web Analytics (CF ダッシュボードで ON するだけ / ¥0)

[Fly.io: FastAPI]
    ├─ sentry-sdk[fastapi] → Python 例外・遅いクエリ → Sentry
    ├─ python-json-logger  → JSON 構造ログ → fly logs
    └─ /healthz (DB チェック付き) → Better Stack が 30 秒ごとに確認

[Neon: PostgreSQL]
    └─ Neon Console (ビルトイン監視 / ¥0)
```

### 料金早見表

| サービス | β (〜100 人) | 1,000 人規模 | 上限 |
|---|---|---|---|
| **Sentry** | **¥0** (Free) | **¥3,500/月** (Team) | Free: 5k errors + 10k transactions/月 |
| **Better Stack** | **¥0** (Free) | **¥1,500/月** (Lite) | Free: 10 monitors, 3 分間隔 |
| **Grafana Cloud (Loki)** | **¥0** (Free) | **¥0〜¥2,000** | Free: 50GB ログ/月 |
| **Cloudflare Web Analytics** | **¥0** | **¥0** | 無制限 |
| **Neon Console** | **¥0** | **¥0** | ビルトイン |
| **合計** | **¥0/月** | **¥5,000〜¥7,000/月** | |

> **β 期は全部無料**。Sentry が 5k errors/月を超えたとき、または死活監視を 1 分間隔にしたい時に有料プランへ移行する。

---

## 2. Sentry セットアップ

### 2.1 アカウント作成

1. [sentry.io](https://sentry.io) でアカウント作成 (GitHub 連携が楽)
2. プロジェクトを 2 つ作成:
   - `adm-backend` — Platform: **Python / FastAPI**
   - `adm-frontend` — Platform: **JavaScript / Vue**
3. 各プロジェクトの **DSN** をコピーしておく

### 2.2 バックエンド (Fly.io シークレット設定)

```bash
# Fly.io のシークレットに設定 (コードには埋め込まない)
fly secrets set SENTRY_DSN="https://xxxx@oXXX.ingest.sentry.io/YYYY" \
               ENVIRONMENT="production" \
               --app adm-pathfinder-api
```

Sentry の初期化コードは `ADM_b/app/main.py` に実装済み。DSN が空なら自動的に無効になる。

### 2.3 フロントエンド (GitHub Secrets 設定)

GitHub リポジトリ → Settings → Secrets and variables → Actions:

| Secret 名 | 値 |
|---|---|
| `SENTRY_DSN_PUBLIC` | Frontend プロジェクトの DSN (`https://xxx@oXXX...`) |

Sentry の初期化コードは `ADM_f/app/plugins/sentry.client.ts` に実装済み。`NUXT_PUBLIC_SENTRY_DSN` が空なら自動的に無効になる。

### 2.4 アラート設定 (Sentry ダッシュボード)

推奨設定 (Sentry > Alerts > Create Alert):

| アラート | 条件 | 通知先 |
|---|---|---|
| エラー急増 | 1 時間で 10 件超 | Slack / Email |
| 新規 Issue | 未見のエラーが発生 | Slack / Email |
| P99 レイテンシ | `/api/v1/audios/stream` が 3 秒超 | Email |
| エラー率 | 5% 超 | Slack |

---

## 3. 死活監視 (Better Stack)

### 3.1 セットアップ

1. [betterstack.com](https://betterstack.com) でアカウント作成
2. **New Monitor** → HTTP Monitor:
   - URL: `https://adm-pathfinder-api.fly.dev/healthz`
   - 間隔: 3 分 (Free) / 1 分 (Lite)
   - 成功条件: HTTP 200 + レスポンス本文に `"status":"ok"` を含む
   - タイムアウト: 10 秒
3. **Notification Policy**: Slack / LINE / Email を連携

`/healthz` は DB 接続も確認している。DB が落ちると 503 を返し、Better Stack がアラートを発火する。

---

## 4. JSON ログ → Grafana Loki (任意 / β 後)

`ENVIRONMENT=production` の場合、FastAPI は自動的に JSON 形式でログを出力する。

```json
{"asctime": "2026-06-04T10:00:00", "name": "app.api.v1.audios", "levelname": "ERROR", "message": "..."}
```

Grafana Cloud の **Loki** に転送する場合:
```bash
# Fly.io の log shipper を設定 (fly.toml に追記)
# または Grafana の "Alloy" エージェントを使う
# β 期は fly logs コマンドで十分
fly logs --app adm-pathfinder-api
```

---

## 5. Cloudflare Web Analytics

Cloudflare ダッシュボード → Pages → adm-pathfinder → Analytics:
- コードの変更は不要 (Cloudflare Pages に自動で組み込まれる)
- PV・ユニーク訪問・デバイス分布・パフォーマンス(LCP/FID) が確認できる

---

## 6. GitHub Secrets 一覧 (監視関連)

| Secret 名 | 用途 | 設定場所 |
|---|---|---|
| `SENTRY_DSN_PUBLIC` | Nuxt SPA フロントエンド Sentry DSN | GitHub Secrets |
| `SENTRY_DSN` | ← Fly.io シークレットで設定 (`fly secrets set`) | Fly.io |
| `ENVIRONMENT` | ← Fly.io シークレットで設定 | Fly.io |

---

## 7. ローカル開発での注意

- `SENTRY_DSN` と `SENTRY_DSN_PUBLIC` を `.env` に設定しない → Sentry は無効になり、ローカルの操作がサーバに送信されない
- `ENVIRONMENT=development` (デフォルト) では JSON ログでなく通常ログが出力される
- `python-json-logger` と `sentry-sdk[fastapi]` は `requirements.txt` に追加済み。ローカルで `pip install -r requirements.txt` すれば開発環境でも利用可能 (DSN が空なら実質無害)
