import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    ActivityKind,
    ActivityLog,
    Audio,
    CreatorPayout,
    DirectMessage,
    DMSenderKind,
    DownloadKind,
    DownloadLog,
    PayoutStatus,
    TokenConsumption,
)
from app.models.audio import AudioTag, Tag
from app.schemas.audio import CreatorBrief
from app.security.deps import get_current_user
from app.security.signed_url import (
    SignedURLError,
    issue_copy_download,
    verify_copy_download,
)
from app.services import audio_file

# 直近この秒数以内に同ユーザの session 記録があれば新規 INSERT しない。
# 30分とした理由: Admin ログでの「DAU/起動回数」を意味ある粒度で集計するため。
# 短すぎると 1ページ遷移ごとに 1 session 増えてしまい、活発度の判定が壊れる。
SESSION_DEDUP_WINDOW_SEC = 30 * 60

router = APIRouter(prefix="/me", tags=["me"])


class MyDownloadItem(BaseModel):
    id: str
    title: str
    creator: CreatorBrief
    duration_sec: int
    token_cost: int
    tags: list[str] = []
    # v1: list[float] / v2: {"n","max","min","rms"} — 改訂2 で v2 に統一
    peaks: list[Any] | dict[str, Any] = []
    downloaded_at: Any  # datetime | None
    tokens_consumed: int
    file_size_bytes: int
    copy_exists: bool


class MyDownloadsResponse(BaseModel):
    items: list[MyDownloadItem]
    storage_used_bytes: int


@router.get("/downloads/copy-file")
def download_copy_file(
    audio_id: str = Query(...),
    user_id: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        verify_copy_download(audio_id, user_id, exp, sig)
    except SignedURLError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": exc.code, "message": exc.message},
        )

    try:
        parsed_audio_id = uuid.UUID(audio_id)
        parsed_user_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})

    copy_path = audio_file.get_copy_path(parsed_user_id, parsed_audio_id)
    if not copy_path.exists():
        # Fallback: 個人 copy が無ければ原本を直接配信。
        # ストレージ枯渇でユーザが自身の copy を削除した直後でも、
        # signed URL の有効期限内なら DL を継続させたいため (UX 優先)。
        audio = db.execute(select(Audio).where(Audio.id == parsed_audio_id)).scalar_one_or_none()
        if audio is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})
        orig_path = Path(audio.file_path)
        if not orig_path.exists():
            raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "file missing"})
        title = audio.title
        return FileResponse(path=str(orig_path), media_type="audio/wav", filename=f"{title}.wav")

    audio = db.execute(select(Audio).where(Audio.id == parsed_audio_id)).scalar_one_or_none()
    title = audio.title if audio else audio_id
    return FileResponse(path=str(copy_path), media_type="audio/wav", filename=f"{title}.wav")


@router.get("/downloads", response_model=MyDownloadsResponse)
def list_my_downloads(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> MyDownloadsResponse:
    from sqlalchemy.orm import joinedload

    audios = db.execute(
        select(Audio)
        .options(joinedload(Audio.creator), joinedload(Audio.tags))
        .where(Audio.downloaded_by_user_id == current_user.id)
        .order_by(Audio.downloaded_at.desc())
    ).unique().scalars().all()

    audio_ids = [a.id for a in audios]

    # tokens consumed per audio
    token_rows = db.execute(
        select(TokenConsumption.audio_id, TokenConsumption.tokens)
        .where(
            TokenConsumption.user_id == current_user.id,
            TokenConsumption.audio_id.in_(audio_ids),
        )
    ).all()
    tokens_map: dict[uuid.UUID, int] = {r.audio_id: r.tokens for r in token_rows}

    items: list[MyDownloadItem] = []
    storage_used = 0

    for audio in audios:
        copy_path = audio_file.get_copy_path(current_user.id, audio.id)
        copy_exists = copy_path.exists()
        file_size = copy_path.stat().st_size if copy_exists else 0
        storage_used += file_size

        items.append(MyDownloadItem(
            id=str(audio.id),
            title=audio.title,
            creator=CreatorBrief(
                id=str(audio.creator.user_id),
                display_name=audio.creator.display_name,
            ),
            duration_sec=audio.duration_sec,
            token_cost=audio.duration_sec,
            tags=[t.name for t in audio.tags],
            peaks=audio.peaks,
            downloaded_at=audio.downloaded_at,
            tokens_consumed=tokens_map.get(audio.id, 0),
            file_size_bytes=file_size,
            copy_exists=copy_exists,
        ))

    return MyDownloadsResponse(items=items, storage_used_bytes=storage_used)


@router.get("/downloads/{audio_id}/copy-url")
def get_copy_url(
    audio_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})

    audio = db.execute(
        select(Audio).where(Audio.id == parsed_id)
    ).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    if audio.downloaded_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_OWNER", "message": "not your audio"},
        )

    # Log re-download
    db.add(DownloadLog(
        user_id=current_user.id,
        audio_id=parsed_id,
        kind=DownloadKind.redownload,
    ))
    db.commit()

    params = issue_copy_download(audio_id, str(current_user.id))
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": f"/api/v1/me/downloads/copy-file?{qs}"}


@router.delete("/downloads/{audio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_download(
    audio_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})

    audio = db.execute(
        select(Audio.downloaded_by_user_id).where(Audio.id == parsed_id)
    ).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    if audio != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_OWNER", "message": "not your audio"},
        )

    copy_path = audio_file.get_copy_path(current_user.id, parsed_id)
    if copy_path.exists():
        copy_path.unlink(missing_ok=True)


# ─── Session ping (改訂2) ─────────────────────────────────────────────────────

@router.post("/session/ping")
def session_ping(
    response: Response,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict:
    """フロントが主要ページに到達した時に1回叩く。
    直近 30分以内に同ユーザの session 記録があれば 204、なければ INSERT して 201。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=SESSION_DEDUP_WINDOW_SEC)
    recent = db.execute(
        select(ActivityLog.id)
        .where(
            ActivityLog.user_id == current_user.id,
            ActivityLog.kind == ActivityKind.session,
            ActivityLog.created_at >= cutoff,
        )
        .limit(1)
    ).scalar_one_or_none()
    if recent is not None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return {}
    db.add(ActivityLog(user_id=current_user.id, kind=ActivityKind.session))
    db.commit()
    response.status_code = status.HTTP_201_CREATED
    return {"recorded": True}


# ─── 統合通知 (NOTIFICATION_SPEC §5) ─────────────────────────────────────────────

def _count_payouts_pending(db: Session) -> int:
    return int(db.execute(
        select(func.count())
        .select_from(CreatorPayout)
        .where(CreatorPayout.status == PayoutStatus.pending)
    ).scalar_one())


def _count_admin_dm_unread_threads(db: Session, admin_user) -> int:
    """admin 視点: creator から最新メッセージが来ていて、admin の dm_view 後の未読スレッド数。"""
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
    last_creator_msg = (
        select(
            DirectMessage.creator_id.label("creator_id"),
            func.max(DirectMessage.created_at).label("last_msg_at"),
        )
        .where(DirectMessage.sender_kind == DMSenderKind.creator)
        .group_by(DirectMessage.creator_id)
        .subquery()
    )
    rows = db.execute(
        select(last_creator_msg.c.creator_id)
        .select_from(last_creator_msg)
        .outerjoin(last_view, last_view.c.creator_id == last_creator_msg.c.creator_id)
        .where(
            (last_view.c.last_view_at.is_(None)) |
            (last_creator_msg.c.last_msg_at > last_view.c.last_view_at)
        )
    ).all()
    return len(rows)


def _creator_dm_unread(db: Session, current_user) -> int:
    """creator 視点: 自分への admin DM が dm_view 後にあれば 1、なければ 0。"""
    last_view_at = db.execute(
        select(func.max(ActivityLog.created_at))
        .where(
            ActivityLog.user_id == current_user.id,
            ActivityLog.kind == ActivityKind.dm_view,
        )
    ).scalar_one_or_none()
    last_admin_msg_at = db.execute(
        select(func.max(DirectMessage.created_at))
        .where(
            DirectMessage.creator_id == current_user.id,
            DirectMessage.sender_kind == DMSenderKind.admin,
        )
    ).scalar_one_or_none()
    if last_admin_msg_at is None:
        return 0
    if last_view_at is None or last_admin_msg_at > last_view_at:
        return 1
    return 0


@router.get("/notifications")
def notifications(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict:
    """NOTIFICATION_SPEC §5: 領域非依存の統合通知 API。

    レスポンス構造:
      areas: { <area_name>: { action_count, has_info, breakdown } }
      totals: { action_count, has_info }

    領域追加時はここに area を1つ足すだけで、フロントは map で回しているので
    UI 側の改修なしに新領域の通知が表示される (NOTIFICATION_SPEC §5.1)。
    """
    # Commission の集計関数は orders.py に既存
    from app.api.v1.orders import (
        _count_action_required,
        _count_info_only,
        _count_message_unread,
    )

    role = current_user.role.value
    areas: dict[str, dict] = {}

    action_required = _count_action_required(db, current_user)
    message_unread = _count_message_unread(db, current_user)
    info_only = _count_info_only(db, current_user)
    areas["commission"] = {
        "action_count": action_required + message_unread,
        "has_info": info_only > 0,
        "breakdown": {
            "action_required": action_required,
            "message_unread": message_unread,
            "info_only": info_only,
        },
    }

    if role == "admin":
        payouts_pending = _count_payouts_pending(db)
        areas["payouts"] = {
            "action_count": payouts_pending,
            "has_info": False,
            "breakdown": {"pending_approval": payouts_pending},
        }
        dm_unread = _count_admin_dm_unread_threads(db, current_user)
        areas["creator_dm"] = {
            "action_count": dm_unread,
            "has_info": False,
            "breakdown": {"unread_threads": dm_unread},
        }
        # 未実装領域: spec で枠だけ確保 (Phase B 以降に実装が来ても UI 改修不要)
        areas["token_grants"] = {"action_count": 0, "has_info": False, "breakdown": {}}
        areas["lic_requests"] = {"action_count": 0, "has_info": False, "breakdown": {}}
    elif role == "creator":
        dm_unread = _creator_dm_unread(db, current_user)
        areas["creator_dm"] = {
            "action_count": dm_unread,
            "has_info": False,
            "breakdown": {"unread_threads": dm_unread},
        }

    totals_action = sum(a["action_count"] for a in areas.values())
    totals_has_info = any(a["has_info"] for a in areas.values())

    return {
        "areas": areas,
        "totals": {
            "action_count": totals_action,
            "has_info": totals_has_info,
        },
    }
