# licファイル仕様 — Audio Data Management

`.lic` ファイルは user / creator / admin を識別するためのライセンスファイル。
Admin が発行し、利用者は `/activate` 画面でアップロードしてアクティベートする。

## 1. 拡張子・MIME

- 拡張子: `.lic`
- 想定MIME: `application/octet-stream` / `text/plain` / `application/json` (どれでも可)
- エンコーディング: UTF-8 / 改行コード LF または CRLF

## 2. フォーマット

### 2.1 JSON形式 (推奨)

```json
{
  "username": "saaaaa",
  "role": "user",
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
role=user
licenseId=LIC-2026-0001
monthlyQuotaTokens=18000
issuedAt=2026-05-26T00:00:00Z
```

JSON / KV のいずれもフロントの `useAuthStore.activateFromText()` でパース可能。

## 3. フィールド定義

| 名前 | 型 | 必須 | 説明 |
|---|---|---|---|
| `username` | string | ✓ | 表示名。`^[a-zA-Z0-9_.-]{1,32}$` を推奨 |
| `role` | `user`/`creator`/`admin` | ✓ | |
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

## 7. バージョニング

将来の互換のため、`schemaVersion: 1` フィールドを Phase 2 で追加する。  
未指定の lic は schemaVersion=1 とみなす。

## 8. サンプル

### user (月5時間相当)
```json
{ "username": "saaaaa", "role": "user", "licenseId": "LIC-2026-0001", "monthlyQuotaTokens": 18000, "issuedAt": "2026-05-26T00:00:00Z" }
```

### creator (DLしない運用なら 0)
```json
{ "username": "mokurorо", "role": "creator", "licenseId": "LIC-2026-C0007", "monthlyQuotaTokens": 0, "issuedAt": "2026-05-26T00:00:00Z" }
```

### admin (動作確認用に少量付与)
```json
{ "username": "root", "role": "admin", "licenseId": "LIC-2026-A0001", "monthlyQuotaTokens": 3600, "issuedAt": "2026-05-26T00:00:00Z", "expiresAt": "2026-08-26T00:00:00Z" }
```
