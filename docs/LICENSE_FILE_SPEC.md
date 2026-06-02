# licファイル仕様 — Audio Data Management

`.lic` ファイルは licensee / creator / admin を識別するためのライセンスファイル。
Admin が発行し、利用者は `/activate` 画面でアップロードしてアクティベートする。

> **ロール命名 (2026-06-02 確定)**: 旧 `user` ロールは `licensee` にリネーム。`.lic` の概念 (licensor=creator / licensee=客) と一致させる目的。旧 `role=user` の lic は `validate_payload()` 内で `licensee` に正規化する互換シムあり。

## 1. 拡張子・MIME

- 拡張子: `.lic`
- 想定MIME: `application/octet-stream` / `text/plain` / `application/json` (どれでも可)
- エンコーディング: UTF-8 / 改行コード LF または CRLF

## 2. フォーマット

### 2.1 JSON形式 (推奨)

```json
{
  "username": "saaaaa",
  "role": "licensee",
  "licenseId": "LIC-2026-0001",
  "monthlyQuotaTokens": 18000,
  "issuedAt": "2026-05-26T00:00:00Z",
  "expiresAt": "2027-05-26T00:00:00Z",
  "signature": "base64(HMAC-SHA256(payload, secret))"
}
```

### 2.2 KV形式 (互換)

```
username=saaaaa
role=licensee
licenseId=LIC-2026-0001
monthlyQuotaTokens=18000
issuedAt=2026-05-26T00:00:00Z
```

JSON / KV のいずれもフロントの `useAuthStore.activateFromText()` でパース可能。

## 3. フィールド定義

| 名前 | 型 | 必須 | 説明 |
|---|---|---|---|
| `username` | string | ✓ | 表示名。`^[a-zA-Z0-9_.-]{1,32}$` を推奨 |
| `role` | `licensee`/`creator`/`admin` | ✓ | (旧 `user` は `licensee` に自動正規化) |
| `licenseId` | string | ✓ | 一意ID。例: `LIC-{年}-{連番}` |
| `monthlyQuotaTokens` | integer | ✓ | 月間ダウンロード許容token量 (1秒=1token)。例: 18000 = 5時間相当。0は実質guest扱い |
| `issuedAt` | ISO 8601 datetime | ✓ | 発行日時 (UTC) |
| `expiresAt` | ISO 8601 datetime |  | 失効日時。省略時は無期限 |
| `signature` | string |  | HMAC署名 (Phase 2 で必須化予定) |

> creator / admin ロールにも `monthlyQuotaTokens` は必須 (creator/admin 自身もユーザとして DL したい場合がある)。利用しない運用なら 0 を指定。

## 4. 署名 (Phase 2 で導入)

### 4.1 計算手順

1. `signature` を除いたフィールドをアルファベット順に並べて JSON 化 (canonical JSON)。
2. サーバ管理の秘密鍵 (環境変数 `ADM_LIC_SIGNING_KEY`) を使い HMAC-SHA256 を計算。
3. base64url エンコードした値を `signature` に格納。

```python
import hmac, hashlib, json, base64

payload_for_sig = {k: v for k, v in lic.items() if k != "signature"}
canon = json.dumps(payload_for_sig, sort_keys=True, separators=(",", ":")).encode()
sig = hmac.new(key, canon, hashlib.sha256).digest()
lic["signature"] = base64.urlsafe_b64encode(sig).decode().rstrip("=")
```

### 4.2 検証

- サーバ側 `/auth/activate` で同じ計算を行い、一致しなければ 401 `INVALID_LICENSE_SIGNATURE`。
- 失効/期限切れの場合は 401 `LICENSE_REVOKED` / `LICENSE_EXPIRED`。

## 5. 発行・配布フロー

```
Admin (発行画面)
  └─ POST /admin/licenses { username, role, monthlyQuotaTokens, expiresAt? }
       └─ サーバが licenseId 採番 + 署名計算
            └─ .lic ファイルをレスポンス (Content-Disposition: attachment)
                 └─ Admin がユーザに配布 (メール / 別チャネル)
                      └─ ユーザが /activate でアップロード
```

`monthlyQuotaTokens` を運用中に変更する場合は新しい lic を再発行し、旧 lic は `/admin/licenses/{id}/revoke` で失効する。

## 6. セキュリティ留意点

- licファイルは秘密ではないが、改ざんは署名で検知する (Phase 2)。
- `revoked_at` を持つレコードを DB 側に保持し、サーバ検証時に必ず参照する。
- 失効済み licファイルが手元に残っていてもサーバ拒否で安全。
- localStorage 保存は Phase 1 限定。Phase 2 以降は JWT に置き換える (lic は再アクティベート時のみ送信)。
- admin 用 lic は短期失効 (90日) を必須化することを推奨。

### 6.1 単一セッション制 (B案 / Spotify モデル / 2026-06-02 実装)

`.lic` ファイルが第三者にコピーされた場合の対策。

**仕組み:**

- `licenses.current_session_id` (UUID) を持つ
- `/auth/activate` 毎にサーバが新 UUID を発行し、DB に上書き保存
- JWT の `sid` claim にも同 UUID を埋め込み
- 認証必須リクエストで `JWT.sid == licenses.current_session_id` を毎回照合
- 不一致なら `401 SESSION_INVALIDATED` で拒否

**挙動:**

```
Alice  /activate ─→ DB.sid = S1, JWT1.sid = S1   ✅ 利用可能
Alice  use JWT1   ─→ sid 一致 → 200 OK
Bob    /activate ─→ DB.sid = S2 に上書き, JWT2.sid = S2
                    ├ Alice の JWT1 は次のリクエストで 401 SESSION_INVALIDATED
                    └ Bob の JWT2 は利用可能
```

= **後から activate された端末が勝つ**。`.lic` を友達に渡したら自分が締め出される。

**Frontend 挙動:**

- 認証付きリクエストが 401 `SESSION_INVALIDATED` を受けたら、自動で `/activate` に遷移し、
  「別の端末でアクティベートされたため、ログアウトしました」と通知を表示。

**例外:**

- `/auth/activate` 自体は sid 検証なし (ログインせずに呼べる)
- 視聴ストリーミング (`/audios/{id}/stream`) も sid 検証なし (FR-STREAM-01: guest 可)

## 7. 暗号化方針

> 詳細リテラシーは [PRODUCTION_OPERATIONS_GUIDE.md §11](PRODUCTION_OPERATIONS_GUIDE.md) を参照。

### 7.1 フェーズ別フォーマット

| Phase | フォーマット | 内容秘匿 | 改ざん検知 |
|---|---|---|---|
| A (現在) | JSON 平文 + HMAC-SHA256 署名 | ❌ | ✅ |
| B (次回) | JWE (ECDH-ES + A256GCM) | ✅ | ✅ (GCM tag) |
| C (本番前) | バイナリ magic blob (AES-256-GCM) + Ed25519 署名 | ✅ | ✅ |

`schemaVersion` フィールドでフォーマット世代を判別し、移行期間中は複数世代を受け入れる。

### 7.2 Phase B — JWE 形式

ファイルの内容はコンパクト JWE トークン 1行:

```
eyJhbGciOiJFQ0RILUVTIiwiZW5jIjoiQTI1NkdDTSIsImtpZCI6ImFkbS12MSJ9..IV.ciphertext.tag
```

- アルゴリズム: `ECDH-ES` + `A256GCM`
- claims (暗号化されたペイロード) は §2.1 の JSON フィールドと同一
- `kid` で鍵世代を識別。サーバは対応する EC 秘密鍵で復号

### 7.3 Phase C — バイナリ形式

```
[8B magic "ADMLIC\x01\x00"][12B nonce][N bytes AES-256-GCM ciphertext + 16B tag]
```

- magic bytes でフォーマット検出 / バージョン管理
- nonce は発行ごとにランダム生成 (使い回し禁止)
- GCM tag で改ざん検知を兼ねるため HMAC 署名は不要

### 7.4 鍵管理規則

- 秘密鍵は必ず環境変数 (`ADM_LIC_EC_PRIVATE_KEY` / `ADM_LIC_ENC_KEY`) で管理。コード・ファイルへの埋め込み禁止。
- 鍵ローテーション時は旧 `kid` の鍵を保持し、旧世代の lic を復号できる状態を維持する。
- EC 公開鍵は管理 UI / Admin 発行スクリプトに配置。漏洩しても復号不可。

### 7.5 検証エラーコード

| エラー | HTTP | 説明 |
|---|---|---|
| `INVALID_LICENSE_SIGNATURE` | 401 | HMAC 不一致 / GCM tag 不一致 / JWE 復号失敗 |
| `INVALID_LICENSE_FORMAT` | 400 | 既知 schemaVersion でない / magic bytes 不一致 |
| `LICENSE_REVOKED` | 401 | DB 上で `revoked_at` が設定済み |
| `LICENSE_EXPIRED` | 401 | `expiresAt` を過ぎている |

---

## 8. バージョニング

将来の互換のため、`schemaVersion: 1` フィールドを Phase 2 で追加する。  
未指定の lic は schemaVersion=1 とみなす。

## 8. サンプル

### licensee (月5時間相当)
```json
{ "username": "saaaaa", "role": "licensee", "licenseId": "LIC-2026-0001", "monthlyQuotaTokens": 18000, "issuedAt": "2026-05-26T00:00:00Z" }
```

### creator (DLしない運用なら 0)
```json
{ "username": "mokurorо", "role": "creator", "licenseId": "LIC-2026-C0007", "monthlyQuotaTokens": 0, "issuedAt": "2026-05-26T00:00:00Z" }
```

### admin (動作確認用に少量付与)
```json
{ "username": "root", "role": "admin", "licenseId": "LIC-2026-A0001", "monthlyQuotaTokens": 3600, "issuedAt": "2026-05-26T00:00:00Z", "expiresAt": "2026-08-26T00:00:00Z" }
```
