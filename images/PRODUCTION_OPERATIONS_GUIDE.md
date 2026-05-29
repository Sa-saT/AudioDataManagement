# ADM 本番運用ガイド (副業運用の現実性評価)

> 作成: 2026-05-30 / 想定読者: ADM オーナー (=本人)
> 目的: 「副業で運用監視できるか」を判定するための実務情報を1ページに集約

---

## 0. 結論 (TL;DR)

| 規模 | 副業として可能? | 月額コスト | 週あたり作業時間 |
|---|---|---|---|
| ~100 user (β/PoC) | **◎ 余裕** | 1〜3万円 | **2〜4時間** |
| ~1,000 user (小規模商用) | **○ 可能** (自動化前提) | 3〜8万円 | **5〜10時間** |
| ~10,000 user (中規模) | **△ 専任化推奨** | 15〜40万円 | 20〜30時間 (週末では足りない) |
| 10,000+ user | **✗ 本業化必須** | 50万円+ | フルタイム |

**推奨方針:** Cloudflare + Fly.io + Neon + R2 + Sentry の SaaS 寄せで**運用負荷を最小化**し、副業時間を「監視」と「機能改善」に集中させる。

---

## 1. 現状アーキテクチャの確認

| レイヤ | 技術 | 本番化で要注意 |
|---|---|---|
| Frontend | Nuxt 4 (Vue 3 + TypeScript) | SSR/SSG, 静的ホスティング向き |
| Backend | FastAPI (Python 3.10) + uvicorn | CPU/メモリ要件は ffmpeg ストリーミングに依存 |
| DB | PostgreSQL (JSONB 多用 / sequence / FK 多数) | 14+ 推奨。マネージドサービス向き |
| 音源処理 | ffmpeg `-c:a copy` (10秒チャンク切り出し) | ストリーミング毎にプロセス起動 → 同時接続数で CPU 食う |
| 波形描画 | WebGL2 Shader (自前) | クライアント側 |
| 認証 | JWT + HMAC signed URL (TTL 30秒) | secret rotation 体制要 |
| ストレージ | ローカル `/storage/{sounds,downloads,orders}/` | **本番では S3 互換必須** (WAV は大きい) |
| キュー | なし (同期処理) | スケール時に Celery / RQ 検討 |

### ファイルサイズの概算
- 48k/24bit/stereo PCM: 約 16.5 MB/分
- 90秒 1曲: ~25 MB
- ユーザ 1人あたり DL ストレージ容量上限 (lic 設定): 例 1 GB = ~40曲
- **storage コストが運用コストの主因**

---

## 2. デプロイ先候補 (規模別)

### 2.1 最小構成 (β / 100 user)

```
[Cloudflare Pages] ── 静的化された Nuxt
       │
[Fly.io] ── FastAPI (uvicorn + ffmpeg バイナリ同梱)
       │
[Neon (Postgres serverless)] ─ 0.5 vCPU 共有 / 3 GB
       │
[Cloudflare R2] ── /storage/* を S3 互換で
       │
[Sentry] (free) + [Better Stack] (uptime)
```

| 項目 | 内訳 | 月額 (USD/JPY) |
|---|---|---|
| Cloudflare Pages | 無料枠 | ¥0 |
| Fly.io | shared-cpu-1x 256MB ($1.94/mo)× 2 + outbound 100GB | **¥1,500** |
| Neon | Free tier (0.5 vCPU / 3GB) | ¥0 |
| Cloudflare R2 | 100GB (audio含む) / egress 無料 | ¥250 |
| Sentry | Developer plan | ¥0 |
| Better Stack | Uptime 10サイト | ¥0 |
| **合計** | | **¥1,750/月** |

**注意:** Neon free tier は inactivity で suspend されるので、本番では Launch plan ($19/mo) 推奨。
合計 **約 4,500円/月** が現実線。

### 2.2 小規模商用 (1,000 user / プロアマ層)

```
[Cloudflare Pages]
       │
[Fly.io] ── primary: shared-cpu-2x 512MB × 3 リージョン (auto-scale)
       │
[Neon Launch plan] ($19/mo, 1GB compute, autoscaling)
       │
[Cloudflare R2] ── 500GB-1TB
       │
[Sentry Team] + [Grafana Cloud Free] + [Better Stack]
```

| 項目 | 月額 |
|---|---|
| Fly.io | ¥4,500 (CPU 上げ + マルチリージョン) |
| Neon Launch | ¥3,000 |
| R2 (500GB) | ¥1,200 |
| Sentry Team | ¥3,500 |
| Backup ストレージ (B2 cold) | ¥1,000 |
| ドメイン / 証明書 / 雑費 | ¥1,000 |
| **合計** | **約 ¥14,000/月** |

### 2.3 中規模 (10,000 user / プロ層)

- 本格的に AWS / GCP を検討
- ECS Fargate / GKE Autopilot
- RDS Aurora Serverless / Cloud SQL
- S3 + CloudFront (or R2 + Cloudflare CDN)
- ElastiCache (Redis) でセッション/レート制限
- Sentry + Datadog or Grafana Stack
- 月額 **15〜40万円**、構築/保守の専門知識必須

### 2.4 国内ホスティング (法的・心理的要件)

| サービス | 用途 | コメント |
|---|---|---|
| さくらのクラウド / ConoHa VPS | Backend + Storage | 一台運用で 5,000-15,000円/月、国内決済・サポート |
| AWS Tokyo region | 全部 | プロ向け、海外サービス連携多い |
| Cloudflare (東京 PoP) | CDN / Pages | 日本向けのレイテンシ良好 |
| Stripe Japan / PAY.JP | Creator payout (将来) | 国内振込・税務対応 |

→ クリエイター/ユーザが日本中心なら **Cloudflare + 国内 PostgreSQL (Neon Asia region)** がレイテンシ・コスト両面で有利。

---

## 3. デプロイ方法 (推奨フロー)

### 3.1 推奨スタック (副業前提)

```
[GitHub] (main push)
   │
   ├─→ [GitHub Actions]
   │      ├─ Frontend: pnpm build → Cloudflare Pages デプロイ
   │      └─ Backend: Docker build → Fly.io deploy + alembic upgrade
   │
   └─→ [Sentry release tracking] (自動 sourcemap upload)
```

### 3.2 自動化必須項目

| 自動化 | 何を | なぜ副業に必須 |
|---|---|---|
| **CI/CD** | push → 自動デプロイ | 手動デプロイは平日夜に時間取られる |
| **DB マイグレーション** | `alembic upgrade head` を deploy 時に実行 | 手作業は事故の元 |
| **DB バックアップ** | Neon は自動 / 自前なら pg_dump cron | 災害時に「何時に戻せるか」を明確化 |
| **シークレット管理** | Fly.io secrets / GitHub Actions secrets | `.env` のミスコミット事故防止 |
| **証明書更新** | Cloudflare 自動 (Let's Encrypt) | 期限切れで全停止する |
| **ログ集約** | Fly logs → Grafana Loki / Sentry | 1日1回ダッシュボード見るだけで済む |

### 3.3 環境分離

最低でも 3 つ:
- **local** (開発、`init_db.sh` で構築)
- **staging** (本番と同構成、独立 DB、 staging.example.com)
- **production** (顧客向け)

staging を「**自分の音源テスト場**」として運用し、user 影響なく検証できる体制が必須。

---

## 4. 運用監視タスク (頻度別)

> ADM は **音源 + 課金 + creator payout** が絡むので、純粋な web app より監視項目は多い。

### 4.1 日次 (5〜15分)

| 項目 | 確認場所 | 自動化レベル |
|---|---|---|
| エラー件数 | Sentry ダッシュボード (Slack 通知設定) | アラート受信のみ |
| Uptime | Better Stack | アラート受信のみ |
| 新規 user / 取引数 | Admin > ログタブ (自前) | 手動アクセス |
| 失敗した DL / payout | Admin > Payout タブ + Sentry | 異常時のみ対応 |
| ストリーミング失敗率 | Sentry → ffmpeg error | アラート受信のみ |

**所要時間:** **平日 5分 / 異常時 30分〜2時間**

### 4.2 週次 (30〜90分)

| 項目 | 作業内容 |
|---|---|
| ストレージ使用量推移 | R2 ダッシュボード、容量上限まで余裕の確認 |
| トークン消費パターン | Admin > ログ > User タブで monthly_quota の枯渇傾向確認 |
| クリエイター活動 | Admin > ログ > Creator タブで離脱兆候 (赤シグナル) 確認 |
| 未対応の Commission | Admin > Commission > open / reviewing 長期滞留チェック |
| Payout pending 残高 | Admin > Payout で未払い分を確認 (creator に振込) |
| バックアップ復元テスト | 1ヶ月に1回、staging に DB スナップショット復元 |

**所要時間:** **週 1〜2時間**

### 4.3 月次 (3〜6時間)

| 項目 | 作業内容 |
|---|---|
| 依存パッケージ更新 | `pnpm update` / `pip-compile` 、staging で動作確認 |
| OS / ランタイム patch | Fly.io image rebuild、Python マイナーバージョン |
| パフォーマンスレビュー | Sentry traces で slow query / P99 latency 上位確認 |
| コスト集計 | 各 SaaS 請求書、ストレージ増加率から半年後コスト試算 |
| セキュリティ点検 | 認証ログ異常、未承認の admin 操作、不正 DL |
| HMAC secret ローテーション | 半年〜1年に1回 (signed URL の鍵) |
| Creator payout 振込 | 銀行振込 (将来 Stripe Connect 等で自動化) |
| 法務 / 規約レビュー | 利用規約・プライバシーポリシーの整合 |

**所要時間:** **月 4〜6時間**

### 4.4 四半期 (4〜8時間)

| 項目 | 作業内容 |
|---|---|
| Disaster Recovery 演習 | 「本番 DB 全消失」想定で復旧時間計測 (RTO/RPO 確認) |
| キャパシティプランニング | 6ヶ月後の user / storage / 帯域予測、上位プラン移行検討 |
| 機能改善ロードマップ | ユーザフィードバック集約、優先度付け |
| 監視ルール見直し | アラート閾値、通知先、ノイズ削減 |
| Penetration test (簡易) | OWASP ZAP / `pip-audit` / `npm audit` |

**所要時間:** **四半期 6〜8時間**

### 4.5 年次 (1〜2日)

- 法定書類関連 (Creator 支払いの源泉徴収 / 確定申告関連の支払い証憑整理)
- アーキテクチャ全面レビュー
- 利用規約改定
- 主要ライブラリの **メジャー** バージョン更新計画

---

## 5. 監視ツール構成 (副業向け推奨)

```
┌─────────────── Cloudflare Pages ───────────────┐
│ Frontend (Vue/Nuxt)                            │
│  ├─ Sentry Browser SDK ─→ エラー / Vitals      │
│  └─ Cloudflare Web Analytics (Free)            │
└────────────────────────────────────────────────┘
                  │
                  ▼ API
┌─────────────────── Fly.io ─────────────────────┐
│ Backend (FastAPI)                              │
│  ├─ Sentry Python SDK ─→ エラー / Transactions │
│  ├─ Better Stack uptime ─→ /healthz チェック   │
│  └─ Fly logs ──→ Grafana Loki (Free 50GB)     │
└────────────────────────────────────────────────┘
                  │
                  ▼ SQL
┌─────────────────── Neon ───────────────────────┐
│ PostgreSQL                                     │
│  ├─ Neon Console ──→ slow query / connections  │
│  └─ pg_dump (自動 + 7日保持)                    │
└────────────────────────────────────────────────┘
                  │
                  ▼ object
┌──────────────── Cloudflare R2 ─────────────────┐
│ /storage/{sounds,downloads,orders}/            │
│  └─ R2 Analytics ──→ egress / 容量             │
└────────────────────────────────────────────────┘

┌─── 通知 ───┐
│ Slack /    │ ← Sentry / Better Stack / Fly health
│ LINE bot   │
└────────────┘
```

### 月額コスト 目安 (1,000 user 規模)

| ツール | プラン | 月額 |
|---|---|---|
| Sentry | Team (50k events) | ¥3,500 |
| Better Stack | Free → 必要時 Lite | ¥0〜¥2,000 |
| Grafana Cloud | Free | ¥0 |
| Cloudflare | Free + R2 | ¥1,500 |
| Slack | Free | ¥0 |

→ 監視ツールは **3,500〜7,000円/月** で揃う。

---

## 6. 副業として現実的か (workload 評価)

### 6.1 副業ベース (本業あり、週末+夜)

| 想定 user 数 | 必要工数/週 | 副業可能度 | コメント |
|---|---|---|---|
| 〜100 | 2〜4時間 | **◎** | β/趣味延長レベル、休日に趣味でも回る |
| 100〜500 | 4〜6時間 | **◎** | 平日30分 × 5 + 週末2時間で完結 |
| 500〜1,000 | 5〜10時間 | **○** | 自動化を徹底すれば可能、ノイズ削減が肝 |
| 1,000〜5,000 | 10〜20時間 | **△** | 仕事帰り後に必ず1時間確保が必要、燃え尽きリスク |
| 5,000+ | 20時間+ | **✗** | 本業化を視野に入れるべき、または共同運営者を |

### 6.2 副業を成立させる「3つの設計原則」

1. **アラート駆動運用にする**
   - 「ダッシュボードを見に行く」のは週次のみ
   - 異常時にだけ Slack/LINE 通知が来る状態を作る
   - 平日は通知が来なければ何もしない

2. **すべてを SaaS に寄せる**
   - 自前運用は学習コスト + 時間泥棒
   - 数千円の課金で数時間/週 を買う発想
   - 特にメリット大: DB (Neon), Storage (R2), Errors (Sentry)

3. **手作業を毎週レビューして即座に潰す**
   - 「先週これに30分かかった」→ 翌週までにスクリプト化
   - 月次タスクは全部 cron / Actions に
   - 自分が病気で寝込んでも 1週間は止まらない状態を目指す

### 6.3 副業者にとってのリスク

| リスク | 緩和策 |
|---|---|
| **Creator payout の遅延** = 信用毀損 | Stripe Connect / PAY.JP で自動化、最低でも月1回固定日 |
| **障害時の対応遅延** | Better Stack + Slack 通知 + 「24時間以内対応」をSLA明記 |
| **音源データ消失** | DB / R2 両方の バックアップ + 月次復元テスト |
| **不正利用 (大量DL/ボット)** | Cloudflare WAF + Rate limit + 異常検知 |
| **本人の体調不良で停止** | Runbook (本ドキュメント) を共有できる形に整備、副管理者を1人確保 |
| **法的問題 (著作権 / 個人情報)** | 利用規約整備、DMCA 対応窓口、顧問弁護士 (年契約 月1万円〜) |

### 6.4 想定スケジュール例 (副業者の1週間)

```
月曜 朝   5分  Slack 通知確認 (週末分)
火-金 夜  5分  Sentry サマリ確認 (Slack ダイジェスト)
土曜 朝  60分  週次レビュー: ストレージ / payout / Commission 滞留
土曜 午後 30分  軽い改善 (issue から1つ消化)
日曜       (休み)

→ 週 約 100分。月次 (4時間) と合わせて 月 約 11時間。
   時給換算 ¥3,000 として ¥33,000/月 の労働価値。
```

→ **売上が月 6〜10万円**を超えるあたりで副業として割に合う。

---

## 7. クリティカルパス: 「これだけは絶対やる」

優先順:

1. **DB バックアップ** (自動 + 復元テスト月1回)
2. **HMAC / JWT secret の漏洩防止** (環境変数 / シークレット管理)
3. **Uptime 監視 + 即時通知**
4. **Sentry によるエラー監視**
5. **Payout / 課金処理の整合性**
6. **証明書 (SSL/TLS) 自動更新の確認**
7. **依存ライブラリの **脆弱性** 通知購読** (Dependabot / Snyk)

これらを満たさない場合は本番運用すべきでない。

---

## 8. 副業運用 → 本業化の判断基準

| 指標 | 副業継続 | 本業化検討 |
|---|---|---|
| MRR (月額売上) | 〜30万円 | 50万円〜 |
| アクティブユーザ | 〜1,000人 | 5,000人〜 |
| 障害頻度 | 月1回以下 | 週1回以上 |
| 自分の稼働 | 週10時間以下 | 週15時間以上が常態化 |
| Creator 数 | 〜100人 | 300人〜 (信頼確保が重い) |
| サポート問い合わせ | 月10件以下 | 月50件以上 |

**意思決定:** 上記のいずれか3つ以上が「本業化」側に振れたら、専任化 or 共同運営者の確保 を真剣に検討。

---

## 9. 学習コスト (副業前提で覚えるべきこと)

| 領域 | 必要レベル | 学習目安 |
|---|---|---|
| Docker / コンテナ基礎 | 読み書き可 | 1週間 |
| Cloudflare / Fly.io / Neon | 管理画面操作 | 各1日 |
| Sentry / Better Stack | ダッシュボード読解 | 各半日 |
| PostgreSQL 運用 | バックアップ / リストア / EXPLAIN | 1週間 |
| ネットワーク / TLS | 概念理解 | 数日 |
| セキュリティ基礎 (OWASP) | チェックリスト運用 | 1週間 |

→ 既存スキルがあれば **2〜4週間で運用可能** な水準に到達できる。

---

## 10. 終わりに

本アプリは **音源データ管理 + 課金 + creator 支払い** が絡むため、純粋な Web アプリより監視項目は多いものの、SaaS を組み合わせれば **副業範囲で完全に運用可能** な設計になっている (peaks v2 / signed URL / activity_logs / Commission 状態機械が独立しているため、自動化しやすい)。

**重要:** β リリース直後の 1〜3ヶ月は user 数が少なくても**監視体制の確立**に時間を使うこと。それを乗り越えれば、その後は本ドキュメントの「日次5分 + 週末1時間」で回せる。

---

**次のアクション (本番化に向けて):**
1. このドキュメントを基に「最小構成」での staging 環境構築 → 動作確認
2. Sentry / Better Stack のアカウント作成 + 統合テスト
3. Cloudflare R2 への storage 移行 (ORDER_SPEC §9.1: 9-A8)
4. CI/CD パイプライン (GitHub Actions) の整備
5. **β リリース対象ユーザを 10〜20人に絞って** 1ヶ月運用、本ガイドの所要時間を実測

実測した値が本ガイドと乖離していたら、その時点で構成見直し。
