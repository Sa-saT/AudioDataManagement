"""Admin-only endpoints: user/creator management, payouts, token grants, lic issuance."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audio import Audio
from app.models.creator import CreatorProfile, CreatorRank
from app.models.payment import CreatorPayout, PayoutStatus, TokenGrant
from app.models.user import License, User, UserRole
from app.security.deps import require_role
from app.security.license import compute_signature, issue_jwe_license

router = APIRouter(prefix="/admin", tags=["admin"])
require_admin = require_role("admin")


def _err(code: str, msg: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": msg})


# ─── Schemas ─────────────────────────────────────────────────────────────────

class UserListItem(BaseModel):
    id: str
    username: str
    role: str
    license_code: str | None
    monthly_quota_tokens: int | None
    group_name: str | None
    rank: str | None
    display_name: str | None
    created_at: datetime

class RankUpdateRequest(BaseModel):
    rank: str

class GroupUpdateRequest(BaseModel):
    group_name: str | None = Field(None, max_length=64)

class PayoutItem(BaseModel):
    id: str
    audio_title: str | None
    creator_name: str | None
    creator_id: str
    rank_at_payout: str
    amount_yen: int
    status: str
    created_at: datetime
    paid_at: datetime | None

class TokenGrantRequest(BaseModel):
    user_id: str
    tokens: int = Field(..., gt=0)
    reason: str | None = None

class TokenGrantResult(BaseModel):
    id: str
    user_id: str
    tokens: int
    period_yyyymm: int

class LicIssueRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=32)
    role: str
    # user のみ意味を持つ。creator/admin は省略可 (デフォルト 0)
    monthly_quota_tokens: int = Field(0, ge=0)
    group: str | None = Field(None, max_length=64)
    expires_at: datetime | None = None

class MonthlyCreatorStat(BaseModel):
    yyyymm: int
    uploads: int
    dls: int

class CreatorStats(BaseModel):
    user_id: str
    total_uploads: int
    total_sold: int
    total_unsold: int
    payout_total_yen: int
    payout_pending_yen: int
    monthly: list[MonthlyCreatorStat]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _jst_period() -> int:
    from zoneinfo import ZoneInfo
    now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
    return now_jst.year * 100 + now_jst.month


def _next_license_code(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"LIC-{year}-"
    count = db.execute(
        select(func.count()).select_from(License).where(License.license_code.like(f"{prefix}%"))
    ).scalar() or 0
    return f"{prefix}{count + 1:04d}"


# ─── Users ───────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserListItem])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserListItem]:
    users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    result = []
    for u in users:
        lic = u.license
        cp = u.creator_profile
        result.append(UserListItem(
            id=str(u.id),
            username=u.username,
            role=u.role.value,
            license_code=lic.license_code if lic else None,
            monthly_quota_tokens=lic.monthly_quota_tokens if lic else None,
            group_name=lic.group_name if lic else None,
            rank=cp.rank.value if cp else None,
            display_name=cp.display_name if cp else None,
            created_at=u.created_at,
        ))
    return result


@router.patch("/users/{user_id}/group", response_model=dict)
def update_group(
    user_id: str,
    body: GroupUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise _err("INVALID_ID", "invalid user_id", 400)

    lic = db.execute(
        select(License).where(License.user_id == uid)
    ).scalar_one_or_none()
    if lic is None:
        raise _err("NOT_FOUND", "license not found for user", 404)

    lic.group_name = body.group_name or None
    db.commit()
    return {"user_id": user_id, "group_name": lic.group_name}


# ─── Creator rank ─────────────────────────────────────────────────────────────

@router.patch("/creators/{user_id}/rank", response_model=dict)
def update_rank(
    user_id: str,
    body: RankUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise _err("INVALID_ID", "invalid user_id", 400)

    if body.rank not in {r.value for r in CreatorRank}:
        raise _err("INVALID_RANK", f"rank must be one of {[r.value for r in CreatorRank]}", 400)

    cp = db.execute(select(CreatorProfile).where(CreatorProfile.user_id == uid)).scalar_one_or_none()
    if cp is None:
        raise _err("NOT_FOUND", "creator profile not found", 404)

    cp.rank = CreatorRank(body.rank)
    db.commit()
    return {"user_id": user_id, "rank": body.rank}


# ─── Creator stats ────────────────────────────────────────────────────────────

@router.get("/creators/{user_id}/stats", response_model=CreatorStats)
def get_creator_stats(
    user_id: str,
    months: int = 6,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> CreatorStats:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise _err("INVALID_ID", "invalid user_id", 400)

    # Total uploads / sold / unsold
    total_uploads = db.execute(
        select(func.count()).select_from(Audio).where(Audio.creator_id == uid)
    ).scalar() or 0
    total_sold = db.execute(
        select(func.count()).select_from(Audio).where(
            Audio.creator_id == uid, Audio.downloaded_by_user_id.isnot(None)
        )
    ).scalar() or 0

    # Payout totals
    payout_rows = db.execute(
        select(CreatorPayout.amount_yen, CreatorPayout.status).where(
            CreatorPayout.creator_id == uid
        )
    ).all()
    payout_total = sum(r.amount_yen for r in payout_rows)
    payout_pending = sum(r.amount_yen for r in payout_rows if r.status == PayoutStatus.pending)

    # Monthly uploads: group by YYYYMM
    upload_rows = db.execute(
        select(
            func.to_char(Audio.created_at, "YYYYMM").label("yyyymm"),
            func.count().label("cnt"),
        ).where(Audio.creator_id == uid)
        .group_by("yyyymm")
        .order_by("yyyymm")
    ).all()

    # Monthly DLs: use creator_payouts.created_at as DL timestamp
    dl_rows = db.execute(
        select(
            func.to_char(CreatorPayout.created_at, "YYYYMM").label("yyyymm"),
            func.count().label("cnt"),
        ).where(CreatorPayout.creator_id == uid)
        .group_by("yyyymm")
        .order_by("yyyymm")
    ).all()

    # Merge by yyyymm, keep last N months
    combined: dict[int, dict[str, int]] = defaultdict(lambda: {"uploads": 0, "dls": 0})
    for r in upload_rows:
        combined[int(r.yyyymm)]["uploads"] = r.cnt
    for r in dl_rows:
        combined[int(r.yyyymm)]["dls"] = r.cnt

    sorted_months = sorted(combined.keys(), reverse=True)[:months]
    monthly = [
        MonthlyCreatorStat(
            yyyymm=m,
            uploads=combined[m]["uploads"],
            dls=combined[m]["dls"],
        )
        for m in sorted(sorted_months)
    ]

    return CreatorStats(
        user_id=user_id,
        total_uploads=total_uploads,
        total_sold=total_sold,
        total_unsold=total_uploads - total_sold,
        payout_total_yen=payout_total,
        payout_pending_yen=payout_pending,
        monthly=monthly,
    )


# ─── Payouts ─────────────────────────────────────────────────────────────────

@router.get("/payouts", response_model=list[PayoutItem])
def list_payouts(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[PayoutItem]:
    q = select(CreatorPayout, Audio.title, CreatorProfile.display_name).join(
        Audio, CreatorPayout.audio_id == Audio.id, isouter=True
    ).join(
        CreatorProfile, CreatorPayout.creator_id == CreatorProfile.user_id, isouter=True
    ).order_by(CreatorPayout.created_at.desc())

    if status_filter in ("pending", "paid", "cancelled"):
        q = q.where(CreatorPayout.status == PayoutStatus(status_filter))

    rows = db.execute(q).all()
    return [
        PayoutItem(
            id=str(p.id),
            audio_title=title,
            creator_name=dname,
            creator_id=str(p.creator_id),
            rank_at_payout=p.rank_at_payout.value,
            amount_yen=p.amount_yen,
            status=p.status.value,
            created_at=p.created_at,
            paid_at=p.paid_at,
        )
        for p, title, dname in rows
    ]


@router.patch("/payouts/{payout_id}/paid", response_model=dict)
def mark_payout_paid(
    payout_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    try:
        pid = uuid.UUID(payout_id)
    except ValueError:
        raise _err("INVALID_ID", "invalid payout_id", 400)

    payout = db.get(CreatorPayout, pid)
    if payout is None:
        raise _err("NOT_FOUND", "payout not found", 404)
    if payout.status != PayoutStatus.pending:
        raise _err("ALREADY_PROCESSED", f"payout status is already '{payout.status.value}'", 409)

    payout.status = PayoutStatus.paid
    payout.paid_at = datetime.now(timezone.utc)
    payout.paid_by_admin_id = admin.id
    db.commit()
    return {"payout_id": payout_id, "status": "paid"}


# ─── Token grants ─────────────────────────────────────────────────────────────

@router.post("/token-grants", response_model=TokenGrantResult, status_code=201)
def grant_tokens(
    body: TokenGrantRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TokenGrantResult:
    try:
        uid = uuid.UUID(body.user_id)
    except ValueError:
        raise _err("INVALID_ID", "invalid user_id", 400)

    user = db.get(User, uid)
    if user is None:
        raise _err("NOT_FOUND", "user not found", 404)

    grant = TokenGrant(
        user_id=uid,
        granted_by_admin_id=admin.id,
        tokens=body.tokens,
        period_yyyymm=_jst_period(),
        reason=body.reason,
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    return TokenGrantResult(
        id=str(grant.id),
        user_id=str(grant.user_id),
        tokens=grant.tokens,
        period_yyyymm=grant.period_yyyymm,
    )


# ─── License issuance ────────────────────────────────────────────────────────

@router.post("/licenses", status_code=201)
def issue_license(
    body: LicIssueRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    if body.role not in {"licensee", "creator", "admin"}:
        raise _err("INVALID_ROLE", "role must be licensee, creator, or admin", 400)

    license_id = _next_license_code(db)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lic: dict = {
        "username": body.username,
        "role": body.role,
        "licenseId": license_id,
        "monthlyQuotaTokens": body.monthly_quota_tokens,
        "issuedAt": now_str,
    }
    if body.group:
        lic["group"] = body.group
    if body.expires_at is not None:
        lic["expiresAt"] = body.expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    from app.config import get_settings

    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in body.username)
    filename = f"{safe_name}.lic"

    if get_settings().ADM_LIC_EC_PRIVATE_KEY:
        # Phase B: JWE (ECDH-ES + A256GCM) — content-encrypted, no plaintext HMAC
        lic_bytes = issue_jwe_license(lic).encode("ascii")
    else:
        # Phase A: JSON + HMAC (fallback when EC key not configured)
        lic["signature"] = compute_signature(lic)
        lic_bytes = json.dumps(lic, ensure_ascii=False, indent=2).encode("utf-8")

    return Response(
        content=lic_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
