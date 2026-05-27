"""Admin-only endpoints: user/creator management, payouts, token grants, lic issuance."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.creator import CreatorProfile, CreatorRank
from app.models.payment import CreatorPayout, PayoutStatus, TokenGrant
from app.models.user import License, User, UserRole
from app.security.deps import require_role
from app.security.license import compute_signature

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
    rank: str | None
    display_name: str | None
    created_at: datetime

class RankUpdateRequest(BaseModel):
    rank: str

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
    expires_at: datetime | None = None

class LicIssuePreview(BaseModel):
    license_id: str
    lic_json: str


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
            rank=cp.rank.value if cp else None,
            display_name=cp.display_name if cp else None,
            created_at=u.created_at,
        ))
    return result


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


# ─── Payouts ─────────────────────────────────────────────────────────────────

@router.get("/payouts", response_model=list[PayoutItem])
def list_payouts(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[PayoutItem]:
    from app.models.audio import Audio

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
    if body.role not in {"user", "creator", "admin"}:
        raise _err("INVALID_ROLE", "role must be user, creator, or admin", 400)

    license_id = _next_license_code(db)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lic: dict = {
        "username": body.username,
        "role": body.role,
        "licenseId": license_id,
        "monthlyQuotaTokens": body.monthly_quota_tokens,
        "issuedAt": now_str,
    }
    if body.expires_at is not None:
        lic["expiresAt"] = body.expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    lic["signature"] = compute_signature(lic)

    lic_bytes = json.dumps(lic, ensure_ascii=False, indent=2).encode("utf-8")
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in body.username)
    filename = f"{safe_name}.lic"

    return Response(
        content=lic_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
