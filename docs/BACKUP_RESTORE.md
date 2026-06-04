# バックアップ & リストア手順

## 構成概要

```
【毎日自動実行】

DB (Neon/PostgreSQL)
  JST 03:00  pg_dump → gzip → Backblaze B2
             b2:adm-backups/db/adm_db_YYYYMMDD.sql.gz
             7日分保持、8日目以降は自動削除

Storage (Cloudflare R2)
  JST 04:00  rclone copy R2 → B2 (差分のみ追加、削除しない)
             b2:adm-backups/storage/sounds/
             b2:adm-backups/storage/downloads/
             b2:adm-backups/storage/orders/
```

---

## GitHub Secrets 設定 (バックアップ用)

GitHub リポジトリ → Settings → Secrets and variables → Actions:

| Secret 名 | 値の例 | 説明 |
|---|---|---|
| `BACKUP_DB_URL` | `postgres://adm_migrator:pass@...neon.tech/adm` | pg_dump 接続文字列 |
| `B2_ACCOUNT_ID` | `001abc...` | Backblaze B2 アカウント ID |
| `B2_APP_KEY` | `K001abc...` | Backblaze B2 アプリケーションキー |
| `B2_BUCKET` | `adm-backups` | B2 バケット名 |
| `R2_ACCESS_KEY_ID` | — | Fly.io の `S3_ACCESS_KEY_ID` と同値 |
| `R2_SECRET_ACCESS_KEY` | — | Fly.io の `S3_SECRET_ACCESS_KEY` と同値 |
| `R2_ENDPOINT_URL` | `https://xxx.r2.cloudflarestorage.com` | R2 エンドポイント |
| `R2_BUCKET` | `adm-sounds` | R2 バケット名 |

---

## DB リストア手順

### ケース 1: 特定日付に戻したい

```bash
# 1. B2 からダンプをダウンロード (rclone が手元にある場合)
rclone copy b2:adm-backups/db/adm_db_20260601.sql.gz /tmp/

# または B2 Web コンソールからダウンロード

# 2. 展開して psql でリストア
gunzip /tmp/adm_db_20260601.sql.gz

# 新規 DB を作成してリストア (本番 DB を上書きしない!)
createdb adm_restore
psql adm_restore < /tmp/adm_db_20260601.sql

# 3. 内容確認後、本番に反映するかどうか判断する
```

### ケース 2: 完全消失 — 本番 DB を最新バックアップで復元

```bash
# 1. 最新のダンプを取得
rclone ls b2:adm-backups/db/ | sort | tail -1
# → adm_db_20260604.sql.gz

rclone copy b2:adm-backups/db/adm_db_20260604.sql.gz /tmp/
gunzip /tmp/adm_db_20260604.sql.gz

# 2. Neon の場合: コンソールで新規 DB を作成 or 既存をリセット
# Neon Console > Branches > Create branch (point-in-time restore も使える)

# 3. psql でリストア
psql "$BACKUP_DB_URL" < /tmp/adm_db_20260604.sql

# 4. Alembic でマイグレーション状態を確認
alembic current
```

### 復元後の確認チェックリスト

- [ ] `SELECT COUNT(*) FROM users;` — ユーザ数が妥当か
- [ ] `SELECT COUNT(*) FROM audios;` — 音源数が妥当か
- [ ] `SELECT COUNT(*) FROM orders;` — Commission 数が妥当か
- [ ] 直近の `admin_logs` が存在するか
- [ ] `/healthz` が HTTP 200 を返すか

---

## ストレージ リストア手順

### ケース 1: 特定ファイルを取り出す

```bash
# B2 から1ファイルだけ取り出す
rclone copy \
  "b2:adm-backups/storage/sounds/abc123.wav" \
  /tmp/restore/

# R2 に戻す
rclone copy \
  /tmp/restore/abc123.wav \
  "r2:adm-sounds/sounds/"
```

### ケース 2: R2 全消失 — B2 から R2 へ全リストア

```bash
# R2 → B2 の逆方向コピー (時間がかかる)
rclone copy \
  "b2:adm-backups/storage/" \
  "r2:adm-sounds/" \
  --transfers 4 \
  --stats 60s

# 完了後、ファイル数を比較して確認
rclone size "b2:adm-backups/storage/"
rclone size "r2:adm-sounds/"
```

### ケース 3: 特定ディレクトリだけ復元 (例: orders のみ)

```bash
rclone copy \
  "b2:adm-backups/storage/orders/" \
  "r2:adm-sounds/orders/" \
  --transfers 4
```

---

## 月次リストアテスト (推奨)

月に 1 回、staging 環境で復元できることを確認する:

```bash
# 1. staging DB に最新ダンプをリストア
psql "$STAGING_DB_URL" < /tmp/adm_db_YYYYMMDD.sql

# 2. staging の /healthz を確認
curl https://adm-pathfinder-api-staging.fly.dev/healthz

# 3. 音源が 1 件ストリーミングできるか確認
# (streaming は signed URL が必要なため、ブラウザで staging にアクセス)
```

---

## rclone ローカルセットアップ (手動操作時)

```bash
# インストール
curl https://rclone.org/install.sh | sudo bash

# 設定ファイル作成
mkdir -p ~/.config/rclone
cat >> ~/.config/rclone/rclone.conf << 'EOF'
[r2]
type = s3
provider = Cloudflare
access_key_id = YOUR_R2_ACCESS_KEY_ID
secret_access_key = YOUR_R2_SECRET_ACCESS_KEY
endpoint = https://xxx.r2.cloudflarestorage.com
acl = private

[b2]
type = b2
account = YOUR_B2_ACCOUNT_ID
key = YOUR_B2_APP_KEY
EOF

# 動作確認
rclone ls r2:adm-sounds/ | head -5
rclone ls b2:adm-backups/ | head -5
```
