# licファイル暗号化 — 仕組み解説と実務トレンド比較

> 作成: 2026-06-01  
> 目的: Phase B (JWE) の実装内容を技術的に検証し、実務標準との整合性を確認する  
> 対象読者: ADM オーナー (実装者本人)

---

## 1. 何を・なぜ実施したか

### 1.1 Before (Phase A)

```json
{
  "username": "saaaaa",
  "role": "admin",
  "licenseId": "LIC-2026-A0001",
  "monthlyQuotaTokens": 3600,
  "issuedAt": "2026-06-01T00:00:00Z",
  "signature": "k3Xz9..."
}
```

- ファイルの **中身が平文で丸見え**。role / quota / username がそのまま読める
- HMAC-SHA256 で改ざんは防げるが「内容の秘匿」は一切ない
- 共有秘密鍵 (`LICENSE_SECRET`) 1本で署名・検証両方を行う **対称方式**

### 1.2 After (Phase B)

```
eyJhbGciOiJFQ0RILUVTIiwiZW5jIjoiQTI1NkdDTSIsImVwayI6...
..
iv_base64url.ciphertext_base64url.tag_base64url
```

- ファイルを見ても **内容が一切わからない** (暗号文のみ)
- **改ざんを試みても GCM tag の不一致で即検知**
- 署名用秘密鍵と復号用秘密鍵が同一 (EC鍵ペアの秘密鍵) → サーバのみが復号できる

---

## 2. 具体的な暗号化の仕組み

### 2.1 全体フロー図

```
【発行時 (Admin サーバ)】

 EC秘密鍵 (PEM)
    │
    └─→ EC公開鍵を取り出す
              │
              ▼
 一時鍵ペア (Ephemeral P-256) を os.urandom で毎回生成
    │
    ├─→ 一時公開鍵  ──→ JWEヘッダー内 "epk" フィールドに埋め込む (公開情報)
    │
    └─→ 一時秘密鍵 × EC公開鍵 ──→ ECDH ──→ 共有シークレット Z (32 bytes)
                                              │
                                              ▼
                                     Concat KDF (SHA-256)
                                              │
                                              ▼
                                     CEK: AES-256 鍵 (32 bytes)
                                              │
                              ┌───────────────┘
                              │
                 IV = os.urandom(12)  ← 毎回ランダム
                              │
                              ▼
              AES-256-GCM(CEK, IV, plaintext, AAD=JWEヘッダー)
                              │
                         ┌────┴────┐
                     ciphertext   GCM tag (16 bytes)
                              │
                              ▼
           header_b64 . "" . iv_b64 . ct_b64 . tag_b64
                      ↑
              encrypted_key = 空 (ECDH-ES は鍵をラップしない)


【検証時 (Admin サーバ)】

 JWE compact token
    │
    ├─→ header decode → "epk" フィールドから一時公開鍵を復元
    │
    └─→ EC秘密鍵 (環境変数) × 一時公開鍵 ──→ ECDH ──→ 同じ Z
                                                         │
                                                    Concat KDF
                                                         │
                                                    同じ CEK
                                                         │
                                              AES-256-GCM.decrypt()
                                                         │
                                                  ┌──────┴──────┐
                                                  │              │
                                            GCM tag 検証    平文 JSON
                                            (不一致 → 即エラー)
```

### 2.2 各ステップの詳細

#### ① EC鍵ペア (P-256 / secp256r1)

| 項目 | 値 |
|---|---|
| 曲線 | NIST P-256 (secp256r1) |
| 秘密鍵サイズ | 256 bits (32 bytes) |
| 公開鍵サイズ | 512 bits (x, y 各 32 bytes) |
| セキュリティ強度 | 128-bit equivalent |

P-256 は TLS 1.3 で最も普及している楕円曲線。`cryptography` ライブラリの `ec.SECP256R1()` で生成。

#### ② Ephemeral Key (一時鍵)

```python
ephem_priv = ec.generate_private_key(ec.SECP256R1())  # 発行のたびに新しい鍵
```

**ポイント:** lic ファイルを 1000 枚発行しても、1000 枚すべて異なる一時鍵ペアが使われる。  
ある lic の暗号文から他の lic の平文を推測する手がかりが一切ない。

#### ③ ECDH (楕円曲線ディフィー・ヘルマン)

```
Z = ephem_priv × recipient_pub_point  (楕円曲線上の点のスカラー乗算)
Z_bytes = Z.x  (共有シークレットは x 座標のみ使用)
```

ECDH の核心: 一時秘密鍵 × 受信者公開鍵 ＝ 受信者秘密鍵 × 一時公開鍵 → **同じ Z が得られる**  
これにより発行者と検証者が同じ CEK を導出できる。

#### ④ Concat KDF (RFC 7518 §4.6.2)

```python
other_info = (
    len("A256GCM").to_bytes(4, "big") + b"A256GCM"   # algorithmID
    + (0).to_bytes(4, "big")                           # apu (empty)
    + (0).to_bytes(4, "big")                           # apv (empty)
    + (256).to_bytes(4, "big")                         # keydatalen
)
CEK = SHA-256( counter=1 || Z || other_info )[:32]
```

- Z (ECDH 生の出力) を直接鍵として使わず、**SHA-256 ベースの KDF で整形**
- `algorithmID` として `"A256GCM"` を含めるので、別用途に鍵が流用されない
- 256 bits = 32 bytes が AES-256 の鍵長

#### ⑤ AES-256-GCM (認証付き暗号)

```python
ct_tag = AESGCM(cek).encrypt(iv, plaintext, aad=header_b64.encode())
ciphertext = ct_tag[:-16]  # 最後 16 bytes が GCM tag
tag        = ct_tag[-16:]
```

| 役割 | 何が担保されるか |
|---|---|
| AES-256 (CTR モード) | 平文の機密性 |
| GHASH (GCM tag) | 暗号文 + AAD の完全性・改ざん検知 |
| AAD = JWEヘッダー | ヘッダー自体の改ざんも GCM tag で検知 |

**IV は `os.urandom(12)` で毎回生成。** GCM はIV再利用が致命的脆弱性になるため、乱数生成が必須。

#### ⑥ JWE Compact Serialization (RFC 7516)

```
header_b64 . encrypted_key_b64 . iv_b64 . ciphertext_b64 . tag_b64
```

5 つの部分をドットで繋ぐ標準フォーマット。  
ECDH-ES は鍵をラップしない (Direct Key Agreement) ため `encrypted_key` は空文字列 → `".."`。

---

## 3. 実務トレンドとの比較

### 3.1 ライセンスファイル保護の主要アプローチ

| アプローチ | 代表例 | 内容秘匿 | 改ざん検知 | 複雑さ | ADM との適合 |
|---|---|---|---|---|---|
| **JSON + HMAC** (Phase A) | 自社ツール多数 | ❌ | ✅ | 低 | ✅ 初期用途 |
| **JWE (ECDH-ES + A256GCM)** (Phase B) | Keycloak / Auth0 JWT | ✅ | ✅ | 中 | ✅ 今回実装 |
| **RSA-OAEP + AES** | JetBrains lic 旧世代 | ✅ | ✅ (署名別途) | 中〜高 | △ 鍵サイズ大、ECC の方が効率的 |
| **X.509証明書 + PKCS#7** | Adobe / Microsoft lic | ✅ | ✅ | 高 | ✗ 過剰。CA構築が必要 |
| **バイナリ magic + AES-GCM** (Phase C) | Steam / Spotify | ✅ | ✅ | 中 | ✅ Phase 4 前に実装予定 |
| **HSM + KMS wrap** | AWS / Azure ライセンス管理 | ✅✅ | ✅✅ | 非常に高 | ✗ 過剰 (コスト・インフラ) |
| **ハードウェアドングル** | Avid (Pro Tools) 旧世代 | ✅✅ | ✅✅ | 高 | ✗ 論外 (物理配布が前提) |

→ **ADM の規模・運用コスト・セキュリティ要件のバランスで JWE は最適解のゾーン**。

### 3.2 ECDH-ES vs RSA-OAEP — 業界の傾向変化

2016 年以前は RSA-OAEP (2048〜4096 bit) が主流だったが、現在は **ECDH 系が推奨**:

| 比較項目 | RSA-OAEP-256 (2048 bit) | ECDH-ES + P-256 |
|---|---|---|
| セキュリティ強度 | 112 bit | 128 bit |
| 鍵ペア生成 | 遅い (素数探索) | 高速 |
| 暗号文サイズ | 大 (RSA block サイズに依存) | 小 |
| PFS (前方秘匿性) | ❌ (同じ鍵ペアを再利用) | ✅ (Ephemeral key で毎回異なる) |
| RFC 標準 | RFC 7518 ✅ | RFC 7518 ✅ |
| TLS 1.3 での扱い | RSA鍵交換は**廃止** | ECDHE が標準 |

TLS 1.3 が RSA 鍵交換を廃止し ECDHE のみにしたのは 2018年 (RFC 8446)。  
これがECC系への移行の象徴的な出来事。**今回の実装はその流れと一致している。**

### 3.3 Forward Secrecy (前方秘匿性) の視点

**Forward Secrecy = 秘密鍵が漏洩しても過去の通信/ファイルが復号されない性質。**

| フォーマット | PFS があるか |
|---|---|
| Phase A: HMAC | ✅ 共有秘密鍵が漏洩すると全 lic の改ざんが可能だが復号の概念がない |
| Phase B: ECDH-ES | **準 PFS** — 一時鍵は発行時のみ存在し捨てられる。サーバの秘密鍵が漏洩した場合、EPK (公開鍵) を使えば全lic を復号できるが、**各 lic の独立性**は保たれる |
| TLS 1.3 の ECDHE | ✅ 完全 PFS — セッションキーを捨てる |

Phase B の構造は「毎回ランダムな一時鍵」を使う点で TLS 1.3 の ECDHE と同じ思想。  
ただし lic ファイルはサーバ秘密鍵で復号するため、**「サーバ秘密鍵漏洩 → 全 lic 復号可能」** という限界は残る。  
→ これは ECDH-ES の構造上の特性であり、**ADM の使途 (単一サーバが発行・検証) では許容範囲**。

### 3.4 GCM tag = 「署名 + MAC 兼用」

Phase A は HMAC を別フィールドで持っていた。Phase B は GCM tag が同等の役割を果たす。

```
Phase A:  暗号化なし + HMAC (別途計算)
Phase B:  AES-GCM = 暗号化 + 認証タグ が一体 (AEAD: Authenticated Encryption with Associated Data)
```

**AEAD は現代暗号の標準思想。** 「暗号化と認証を分離するな」はよく知られた格言 (Encrypt-then-MAC / Galois mode)。  
ChaCha20-Poly1305 (TLS 1.3 / WireGuard) も同じ AEAD 構成。

### 3.5 AAD (Additional Authenticated Data) の重要性

```python
ct_tag = AESGCM(cek).encrypt(iv, plaintext, aad=header_b64.encode("ascii"))
#                                                 ↑
#                             JWE ヘッダー (alg, enc, epk, kid) をAADとして認証対象に
```

ヘッダーに `"alg": "none"` を書き込んで署名を無効化する古典的な JWT 攻撃 (Algorithm Confusion Attack) がある。  
AAD をヘッダーにすることで **「ヘッダーを 1 bit でも変えると GCM tag が不一致になる」** → この攻撃を原理的に防ぐ。

---

## 4. 実装の評価

### 4.1 良い点

| 評価項目 | 判定 | 根拠 |
|---|---|---|
| RFC 7516 / 7518 準拠 | ✅ | JWE Compact Serialization, ECDH-ES, Concat KDF すべて RFC どおり |
| IV ランダム生成 | ✅ | `os.urandom(12)` — OS の CSPRNG を使用 |
| IV 再利用なし | ✅ | 発行のたびに新規生成 |
| Ephemeral key | ✅ | 発行ごとに新しい一時鍵ペア |
| AAD でヘッダー認証 | ✅ | アルゴリズム混乱攻撃を防ぐ |
| Backward compat | ✅ | `schemaVersion` + フォーマット自動検出で Phase A lic も動作継続 |
| kid によるkey rotation 準備 | ✅ | ヘッダーに `kid` 埋め込み済み (複数鍵サポートの拡張余地あり) |
| 鍵はenv varのみ | ✅ | コード・ファイルへの鍵埋め込みなし |

### 4.2 注意点・将来の改善余地

#### ① APU / APV が空

```python
+ struct.pack(">I", 0)  # empty apu
+ struct.pack(">I", 0)  # empty apv
```

`apu` (Agreement PartyUInfo) に発行者識別子 (例: `"adm-server"`)、  
`apv` (Agreement PartyVInfo) に受信者識別子 (例: licenseId) を入れると、  
**「他のシステムや別ユーザ向けに生成された CEK の流用」** を防ぐ binding が強まる。

ADM 規模では現状でも安全だが、将来的に複数のシステムで同じ EC 鍵を使い回す場合は要対処。

#### ② 秘密鍵が単一 SPOF

現状は `kid="adm-v1"` 固定で鍵は 1 本。鍵が漏洩した場合のローテーション手順は:

1. 新しい EC 鍵ペア生成 → `ADM_LIC_EC_PRIVATE_KEY` を差し替え
2. 旧 kid (`adm-v1`) の鍵を **別の環境変数で保持** (旧 lic の復号用)
3. 新規発行は `kid="adm-v2"` で

**現時点のコードは複数 kid 対応をしていない** → ローテーション時は `_load_ec_private_key()` を kid で分岐できるよう拡張が必要。

#### ③ `_load_ec_private_key()` に lru_cache がない

```python
def _load_ec_private_key():
    pem = get_settings().ADM_LIC_EC_PRIVATE_KEY
    return load_pem_private_key(pem.encode(), password=None)
    # ← リクエストごとに PEM パース (数 ms の余分なコスト)
```

`get_settings()` 自体は `@lru_cache` 済みだが、PEM パースは毎回実行される。  
lic 発行は頻度が低いので実害はないが、意識はしておく。

#### ④ サーバ秘密鍵漏洩時の全lic復号可能性

これは ECDH-ES + 単一サーバの構造上避けられない。  
**この用途 (Admin サーバが発行・検証) では設計上許容される** が、以下のリスク管理が重要:

- `ADM_LIC_EC_PRIVATE_KEY` を Fly.io secrets / AWS Secrets Manager で管理
- 秘密鍵を git commit しない (`init_db.sh` が `.env` を生成し `.gitignore` で除外)
- 漏洩検知時は即座に鍵ローテーション + 全 lic 再発行

### 4.3 Phase C (バイナリ形式) との比較

| 特性 | Phase B (JWE) | Phase C (バイナリ) |
|---|---|---|
| 可読性 | base64url テキスト (コピペ可) | バイナリ (テキストエディタ不可) |
| サイズ | ~500〜700 bytes | ~50〜70 bytes |
| 標準準拠 | RFC 7516 ✅ | 独自仕様 |
| ライブラリ依存 | JWE ライブラリ不要 (自前実装) | なし |
| Ed25519 署名 | なし | ✅ (独立した署名アルゴリズム) |

Phase C は「ファイルを見ただけで何かわからない」という心理的障壁も含め、より強固な難読化。  
ただし RFC 標準でない分、将来の実装者が理解しにくい。  
**ADM の用途・規模では Phase B で十分**。Phase C は本番化直前の選択肢。

---

## 5. 全体の妥当性評価

### セキュリティ的に理にかなっているか

```
問: role=admin の lic を role=licensee に改ざんできるか?
答: ❌ 不可能
    → ciphertext を変えると GCM tag が不一致 → 検証エラー
    → header の enc/alg を変えると GCM tag (AAD) が不一致 → 検証エラー

問: 有効な lic を別人が使い回せるか?
答: ❌ サーバ側で licenseId を DB の revoked_at で管理する設計
    → lic ファイル単体では役に立たない (サーバ DB が最終権限)

問: 暗号文からロールや quota を推測できるか?
答: ❌ AES-256-GCM は IND-CPA 安全 (選択平文攻撃に対して識別不可能)

問: 同じユーザ向けに発行した 2 枚の lic は関連性があるか?
答: ❌ 毎回異なる Ephemeral keypair → 暗号文は統計的に無相関
```

### 実務標準との整合

- **JOSE (RFC 7515-7520) 準拠**: JWE は Auth0 / Keycloak / OpenID Connect で広く使われる
- **TLS 1.3 と同じ鍵交換思想 (ECDHE)**: 業界の主流設計と一致
- **AEAD (認証付き暗号)**: 現代暗号の標準。「暗号化と認証を分離するな」原則を守っている
- **`os.urandom` による IV**: OS の CSPRNG を使う — 暗号ライブラリの推奨する最善手

### 結論

Phase B の実装は **現時点のセキュリティ要件・スケール・運用コストのバランスで最適解**。  
RFC 標準準拠・Ephemeral key・GCM tag による AEAD・AAD でのヘッダー認証、いずれも実務で推奨されるアプローチを正確に踏んでいる。

将来の改善優先順位:
1. **kid ローテーション対応** (鍵漏洩時の手順整備)
2. **APU/APV への binding 追加** (複数システム展開時)
3. **Phase C 移行判断** (本番化前にバイナリ形式にするかどうか)

---

## 付録: 鍵生成コマンド

```bash
# P-256 EC 秘密鍵 (PKCS8 PEM) 生成
python3 -c "
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
k = ec.generate_private_key(ec.SECP256R1())
print(k.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode())
"

# 公開鍵を取り出す (配布・保管用)
python3 -c "
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PublicFormat
pem = open('.env').read()  # ADM_LIC_EC_PRIVATE_KEY の値
# または:
import os; priv = load_pem_private_key(os.environ['ADM_LIC_EC_PRIVATE_KEY'].replace('\\\\n','\\n').encode(), password=None)
print(priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode())
"
```

---

## 6. 現状の動作状態と有効化手順 (2026-06-01 確認)

### 6.1 既存テスト用 lic ファイルは引き続き使えるか

**使えます。**

Desktop に保存している `demo_admin.lic` / `demo_creator.lic` / `demo_user.lic` は  
Phase A (JSON 平文 + HMAC) 形式。現在の `parse_lic_text()` は先頭文字で形式を自動判別するため、  
追加作業なしでそのまま `/activate` にアップロードできる。

```python
# parse_lic_text() の分岐 (license.py)
if _is_jwe_token(stripped):   # "eyJ..." 5-part → Phase B (JWE)
    return parse_jwe_lic_text(stripped)
if stripped.startswith("{"):  # "{" → Phase A JSON ← 既存 desktop/*.lic はここ
    ...
```

### 6.2 Admin 画面からの暗号化 lic 発行は実装済みか

**コードは実装済み。ただし現状は Phase A のまま発行される。**

`ADM_b/.env` に `ADM_LIC_EC_PRIVATE_KEY` が設定されていないため、  
`admin.py` の分岐で Phase A にフォールバックしている:

```python
# admin.py — POST /admin/licenses
if get_settings().ADM_LIC_EC_PRIVATE_KEY:
    lic_bytes = issue_jwe_license(lic).encode("ascii")   # Phase B ← 鍵未設定なので通らない
else:
    lic["signature"] = compute_signature(lic)             # Phase A ← 現状ここ
    lic_bytes = json.dumps(lic, ...).encode("utf-8")
```

### 6.3 Phase B を有効化するには

`.env` に EC 秘密鍵を追加するだけで即切り替わる。既存 Phase A lic は動作し続ける。

```bash
# ① 鍵生成
python3 -c "
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
k = ec.generate_private_key(ec.SECP256R1())
print(k.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode())
"

# ② 出力された PEM を ADM_b/.env に追記
# ADM_LIC_EC_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"

# ③ サーバ再起動後、Admin 画面から発行した lic が JWE 形式になる
```

### 6.4 状態まとめ

| 項目 | 状態 |
|---|---|
| 既存 `desktop/*.lic` の動作 | ✅ そのまま使える (Phase A backward compat) |
| Phase B 発行コード (`license.py` / `admin.py`) | ✅ 実装済み |
| Phase B 発行の有効化 | ⬜ `.env` に `ADM_LIC_EC_PRIVATE_KEY` を追加すれば即有効 |
| Phase C (バイナリ形式) | ⬜ Phase 4 前に実装予定 |

---

*本ドキュメントは `docs/LICENSE_FILE_SPEC.md §7` および `docs/PRODUCTION_OPERATIONS_GUIDE.md §11` の技術解説補足版。*
