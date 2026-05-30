"""DM (Direct Message) endpoints.

DM_SPEC §5 参照。admin 視点と creator 視点の2系統。
admin はチーム扱いで、creator_id をスレッドのキーにする。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import (
    ActivityKind,
    ActivityLog,
    CreatorProfile,
    DirectMessage,
    DMSenderKind,
    User,
)
from app.security.deps import get_current_user, require_role

DM_MAX_CONTENT_LENGTH = 4000


# ─── Schemas ──────────────────────────────────────────────────────────────────

class DMOut(BaseModel):
    id: str
    sender_id: str | None
    sender_name: str | None
    sender_kind: str  # 'admin' | 'creator'
    content: str
    attachment_path: str | None
    created_at: Any


class DMSendRequest(BaseModel):
    content: str


class CreatorThreadSummary(BaseModel):
    creator_id: str
    creator_name: str
    creator_display_name: str | None
    last_message_at: Any  # datetime | None
    last_message_preview: str | None
    unread: bool


def _to_dm_out(m: DirectMessage) -> DMOut:
    return DMOut(
        id=str(m.id),
        sender_id=str(m.sender_id) if m.sender_id else None,
        sender_name=m.sender.username if m.sender else None,
        sender_kind=m.sender_kind.value,
        content=m.content,
        attachment_path=m.attachment_path,
        created_at=m.created_at,
    )


def _validate_content(content: str) -> str:
    c = (content or "").strip()
    if not c:
        raise HTTPException(status_code=422, detail={"code": "EMPTY_CONTENT", "message": "content is empty"})
    if len(c) > DM_MAX_CONTENT_LENGTH:
        raise HTTPException(
            status_code=422,
            detail={"code": "CONTENT_TOO_LONG", "message": f"max {DM_MAX_CONTENT_LENGTH} chars"},
        )
    return c


def _record_dm_view(db: Session, user: User, creator_id) -> None:
    """activity_logs に dm_view を記録 (target_id = creator_id)。"""
    db.add(ActivityLog(user_id=user.id, kind=ActivityKind.dm_view, target_id=creator_id))
    db.commit()


# ─── Admin router ─────────────────────────────────────────────────────────────

admin_router = APIRouter(prefix="/admin/dm", tags=["dm"])


@admin_router.get("/creators", response_model=list[CreatorThreadSummary])
def admin_list_dm_threads(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role("admin")),
) -> list[CreatorThreadSummary]:
    """admin: DM 履歴がある creator 一覧 (新しい順)。"""
    # 各 creator の最新 DM
    latest = (
        select(
            DirectMessage.creator_id.label("creator_id"),
            func.max(DirectMessage.created_at).label("last_at"),
        )
        .group_by(DirectMessage.creator_id)
        .subquery()
    )
    # admin の最終 dm_view (per creator)
    last_view = (
        select(
            ActivityLog.target_id.label("creator_id"),
            func.max(ActivityLog.created_at).label("last_view_at"),
        )
        .where(
            ActivityLog.user_id == admin_user.id,
            ActivityLog.kind == ActivityKind.dm_view,
        )
        .group_by(ActivityLog.target_id)
        .subquery()
    )
    rows = db.execute(
        select(User, CreatorProfile, latest.c.last_at, last_view.c.last_view_at)
        .join(latest, latest.c.creator_id == User.id)
        .join(CreatorProfile, CreatorProfile.user_id == User.id, isouter=True)
        .join(last_view, last_view.c.creator_id == User.id, isouter=True)
        .order_by(latest.c.last_at.desc())
    ).all()
    out: list[CreatorThreadSummary] = []
    for user_row, profile, last_at, last_view_at in rows:
        # 最新メッセージのプレビュー
        last_msg = db.execute(
            select(DirectMessage)
            .where(DirectMessage.creator_id == user_row.id)
            .order_by(DirectMessage.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        preview = (last_msg.content[:60] if last_msg and last_msg.content else None)
        unread = bool(last_msg and last_msg.sender_kind == DMSenderKind.creator and
                      (last_view_at is None or last_msg.created_at > last_view_at))
        out.append(CreatorThreadSummary(
            creator_id=str(user_row.id),
            creator_name=user_row.username,
            creator_display_name=profile.display_name if profile else None,
            last_message_at=last_at,
            last_message_preview=preview,
            unread=unread,
        ))
    return out


@admin_router.get("/creators/{creator_id}", response_model=list[DMOut])
def admin_get_dm_thread(
    creator_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[DMOut]:
    """admin: 特定 creator との DM 全件 (古い順)。"""
    msgs = db.execute(
        select(DirectMessage)
        .where(DirectMessage.creator_id == creator_id)
        .options(joinedload(DirectMessage.sender))
        .order_by(DirectMessage.created_at.asc())
    ).scalars().all()
    return [_to_dm_out(m) for m in msgs]


@admin_router.post("/creators/{creator_id}", response_model=DMOut, status_code=status.HTTP_201_CREATED)
def admin_send_dm(
    creator_id: str,
    body: DMSendRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role("admin")),
) -> DMOut:
    content = _validate_content(body.content)
    # creator の存在チェック
    creator = db.execute(select(User).where(User.id == creator_id)).scalar_one_or_none()
    if creator is None or creator.role.value != "creator":
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "creator not found"})
    msg = DirectMessage(
        creator_id=creator.id,
        sender_id=admin_user.id,
        sender_kind=DMSenderKind.admin,
        content=content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return DMOut(
        id=str(msg.id),
        sender_id=str(admin_user.id),
        sender_name=admin_user.username,
        sender_kind="admin",
        content=msg.content,
        attachment_path=None,
        created_at=msg.created_at,
    )


@admin_router.post("/creators/{creator_id}/view", status_code=status.HTTP_201_CREATED)
def admin_mark_dm_view(
    creator_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role("admin")),
) -> dict:
    import uuid as _uuid
    try:
        cid = _uuid.UUID(creator_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "creator not found"})
    _record_dm_view(db, admin_user, cid)
    return {"recorded": True}


# ─── Creator router (mounted under /me) ───────────────────────────────────────

me_router = APIRouter(prefix="/me/dm", tags=["dm"])


@me_router.get("/admin", response_model=list[DMOut])
def creator_get_dm_thread(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("creator")),
) -> list[DMOut]:
    """creator: admin チームとの DM 全件 (古い順)。"""
    msgs = db.execute(
        select(DirectMessage)
        .where(DirectMessage.creator_id == current_user.id)
        .options(joinedload(DirectMessage.sender))
        .order_by(DirectMessage.created_at.asc())
    ).scalars().all()
    return [_to_dm_out(m) for m in msgs]


@me_router.post("/admin", response_model=DMOut, status_code=status.HTTP_201_CREATED)
def creator_send_dm(
    body: DMSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("creator")),
) -> DMOut:
    content = _validate_content(body.content)
    msg = DirectMessage(
        creator_id=current_user.id,
        sender_id=current_user.id,
        sender_kind=DMSenderKind.creator,
        content=content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return DMOut(
        id=str(msg.id),
        sender_id=str(current_user.id),
        sender_name=current_user.username,
        sender_kind="creator",
        content=msg.content,
        attachment_path=None,
        created_at=msg.created_at,
    )


@me_router.post("/admin/view", status_code=status.HTTP_201_CREATED)
def creator_mark_dm_view(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("creator")),
) -> dict:
    # creator 視点ではスレッドは 1 本 (admin チーム)。target_id は自分の id でよい
    _record_dm_view(db, current_user, current_user.id)
    return {"recorded": True}
