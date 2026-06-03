#!/usr/bin/env python3
"""
開発用 .lic ファイル発行スクリプト。

使い方:
    cd ADM_b && source venv/bin/activate
    python scripts/issue_lic.py --username saaaaa --role licensee --quota 30000 \\
        --out /tmp/saaaaa.lic
    # → /tmp/saaaaa.lic に署名付きライセンスを書き出し

    # Phase C バイナリ形式:
    python scripts/issue_lic.py --username saaaaa --role licensee --format phase-c \\
        --out /tmp/saaaaa.lic

オプション:
    --username  ユーザ名 (英数 / _ . - 1〜32文字)
    --role      licensee / creator / admin
    --quota     月間 token 量 (デフォルト 30000)
    --expires   有効期限 ISO8601 (省略時は無期限)
    --license-code  ライセンスコード (省略時は LIC-YYYY-NNNN を自動採番)
    --format    phase-a (デフォルト: JSON+HMAC) / phase-c (バイナリ AES-256-GCM)
    --out       出力先 .lic パス (省略時は ./{username}.lic)

LICENSE_SECRET / ADM_LIC_ENC_KEY は ADM_b/.env から自動読込。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make `app.*` importable when run from ADM_b/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.security.license import compute_signature, issue_phase_c_license  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Issue a development .lic file")
    p.add_argument("--username", required=True)
    p.add_argument("--role", required=True, choices=("licensee", "creator", "admin"))
    p.add_argument("--quota", type=int, default=30_000, help="monthly_quota_tokens")
    p.add_argument("--expires", help="ISO8601 expiry (e.g. 2030-12-31T23:59:59Z)")
    p.add_argument("--license-code", help="custom license code")
    p.add_argument(
        "--format",
        choices=("phase-a", "phase-c"),
        default="phase-a",
        help="phase-a: JSON+HMAC (default) / phase-c: binary AES-256-GCM",
    )
    p.add_argument("--out", help="output .lic path (default: ./{username}.lic)")
    args = p.parse_args()

    license_code = args.license_code or f"LIC-DEV-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    payload: dict = {
        "username": args.username,
        "role": args.role,
        "licenseId": license_code,
        "monthlyQuotaTokens": args.quota,
        "issuedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    if args.expires:
        payload["expiresAt"] = args.expires

    out = Path(args.out) if args.out else Path.cwd() / f"{args.username}.lic"

    if args.format == "phase-c":
        data = issue_phase_c_license(payload)
        out.write_bytes(data)
        fmt_label = "Phase C (AES-256-GCM binary)"
    else:
        payload["signature"] = compute_signature(payload)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        fmt_label = "Phase A (JSON + HMAC)"

    print(f"✔ wrote {out}")
    print(f"  format   = {fmt_label}")
    print(f"  username = {args.username}")
    print(f"  role     = {args.role}")
    print(f"  quota    = {args.quota:,} tk")
    print(f"  code     = {license_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
