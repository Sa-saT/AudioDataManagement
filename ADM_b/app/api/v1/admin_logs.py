"""Admin activity log endpoints (LOG_SPEC.md).

満足度 (user) / 作業頻度 (creator) を可視化する集計 API。
新規テーブルは追加せず、既存 + activity_logs を SQL 集計する。
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    ActivityKind,
    ActivityLog,
    Audio,
    CandidateResponseStatus,
    CreatorPayout,
    CreatorProfile,
    DownloadKind,
    DownloadLog,
    Favorite,
    License,
    Order,
    OrderCandidateCreator,
    OrderMessage,
    OrderStatus,
    PayoutStatus,
    TokenConsumption,
    User,
    UserRole,
)
from app.security.deps import require_role

router = APIRouter(prefix="/admin/logs", tags=["admin-logs"])
require_admin = require_role("admin")


# ─── Period helpers ───────────────────────────────────────────────────────────

DEFAULT_DAYS = 30
ALLOWED_DAYS = {7, 30, 90}

Signal = Literal["green", "yellow", "red"]


def _validate_days(days: int) -> int:
    if days not in ALLOWED_DAYS:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_DAYS", "message": f"days must be in {sorted(ALLOWED_DAYS)}"},
        )
    return days


def _cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _signal_from_score(score: int) -> Signal:
    if score >= 60:
        return "green"
    if score >= 30:
        return "yellow"
    return "red"


# ─── User satisfaction (LOG_SPEC §3.1 / 3.2) ──────────────────────────────────

class UserMetrics(BaseModel):
    session_count: int
    active_days: int
    download_count: int
    tokens_used: int
    monthly_quota: int
    favorite_added: int
    commission_count: int


class UserLogItem(BaseModel):
    user_id: str
    username: str
    role: str
    score: int
    signal: Signal
    metrics: UserMetrics
    last_active_at: Any  # datetime | None


def _user_score(m: UserMetrics, days: int) -> int:
    """User 満足度 0-100。LOG_SPEC §3.2 の式に準拠。

    積極的に利用しているか + 適切に消費しているか + 深い関与があるか の3軸。
    """
    active_rate = min(m.active_days / days, 1.0)
    quota_rate = min(m.tokens_used / m.monthly_quota, 1.0) if m.monthly_quota > 0 else 0.0
    dl_conv = min((m.download_count / m.session_count) * 5, 1.0) if m.session_count > 0 else 0.0
    commission_factor = min(m.commission_count / 5, 1.0)

    score = (
        0.30 * active_rate
        + 0.25 * quota_rate
        + 0.20 * dl_conv
        + 0.15 * min(m.favorite_added / 10, 1.0)
        + 0.10 * commission_factor
    ) * 100
    return int(round(score))


@router.get("/users", response_model=list[UserLogItem])
def list_user_logs(
    days: int = Query(DEFAULT_DAYS),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserLogItem]:
    days = _validate_days(days)
    cutoff = _cutoff(days)

    users = db.execute(
        select(User).where(User.role == UserRole.user).order_by(User.username)
    ).scalars().all()

    items: list[UserLogItem] = []
    for u in users:
        m = _collect_user_metrics(db, u.id, cutoff)
        score = _user_score(m, days)
        last_active = db.execute(
            select(func.max(ActivityLog.created_at))
            .where(ActivityLog.user_id == u.id, ActivityLog.kind == ActivityKind.session)
        ).scalar_one_or_none()
        items.append(UserLogItem(
            user_id=str(u.id),
            username=u.username,
            role=u.role.value,
            score=score,
            signal=_signal_from_score(score),
            metrics=m,
            last_active_at=last_active,
        ))
    # score 低い順 (admin が問題ユーザを先に発見できる)
    items.sort(key=lambda x: x.score)
    return items


def _collect_user_metrics(db: Session, user_id: uuid.UUID, cutoff: datetime) -> UserMetrics:
    session_count = int(db.execute(
        select(func.count()).select_from(ActivityLog).where(
            ActivityLog.user_id == user_id,
            ActivityLog.kind == ActivityKind.session,
            ActivityLog.created_at >= cutoff,
        )
    ).scalar_one())

    active_days = int(db.execute(
        select(func.count(func.distinct(func.date_trunc("day", ActivityLog.created_at))))
        .where(
            ActivityLog.user_id == user_id,
            ActivityLog.kind == ActivityKind.session,
            ActivityLog.created_at >= cutoff,
        )
    ).scalar_one())

    download_count = int(db.execute(
        select(func.count()).select_from(DownloadLog).where(
            DownloadLog.user_id == user_id,
            DownloadLog.kind == DownloadKind.initial,
            DownloadLog.created_at >= cutoff,
        )
    ).scalar_one())

    tokens_used = int(db.execute(
        select(func.coalesce(func.sum(TokenConsumption.tokens), 0)).where(
            TokenConsumption.user_id == user_id,
            TokenConsumption.created_at >= cutoff,
        )
    ).scalar_one())

    monthly_quota = int(db.execute(
        select(License.monthly_quota_tokens).where(License.user_id == user_id)
    ).scalar_one_or_none() or 0)

    favorite_added = int(db.execute(
        select(func.count()).select_from(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.created_at >= cutoff,
        )
    ).scalar_one())

    commission_count = int(db.execute(
        select(func.count()).select_from(Order).where(
            Order.user_id == user_id,
            Order.created_at >= cutoff,
        )
    ).scalar_one())

    return UserMetrics(
        session_count=session_count,
        active_days=active_days,
        download_count=download_count,
        tokens_used=tokens_used,
        monthly_quota=monthly_quota,
        favorite_added=favorite_added,
        commission_count=commission_count,
    )


# ─── Creator activity (LOG_SPEC §3.3 / 3.4) ───────────────────────────────────

class CreatorMetrics(BaseModel):
    session_count: int
    active_days: int
    upload_count: int
    sold_count: int
    sell_rate: float
    earnings_pending: int
    earnings_paid: int
    commission_done_count: int
    message_count: int


class CreatorLogItem(BaseModel):
    creator_id: str
    username: str
    display_name: str
    rank: str
    score: int
    signal: Signal
    metrics: CreatorMetrics
    last_active_at: Any  # datetime | None


def _creator_score(m: CreatorMetrics, days: int) -> int:
    """Creator 作業頻度 0-100。LOG_SPEC §3.4 の式に準拠。"""
    access_rate = min(m.active_days / days, 1.0)
    upload_rate = min(m.upload_count / max(days / 10, 1.0), 1.0)  # 10日に1本ペースで満点
    message_rate = min(m.message_count / 30, 1.0)
    commission_rate = min(m.commission_done_count / 3, 1.0)

    score = (
        0.25 * access_rate
        + 0.25 * upload_rate
        + 0.20 * m.sell_rate
        + 0.15 * commission_rate
        + 0.15 * message_rate
    ) * 100
    return int(round(score))


@router.get("/creators", response_model=list[CreatorLogItem])
def list_creator_logs(
    days: int = Query(DEFAULT_DAYS),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[CreatorLogItem]:
    days = _validate_days(days)
    cutoff = _cutoff(days)

    rows = db.execute(
        select(User, CreatorProfile)
        .join(CreatorProfile, CreatorProfile.user_id == User.id)
        .where(User.role == UserRole.creator)
        .order_by(User.username)
    ).all()

    items: list[CreatorLogItem] = []
    for user, profile in rows:
        m = _collect_creator_metrics(db, user.id, cutoff)
        score = _creator_score(m, days)
        last_active = db.execute(
            select(func.max(ActivityLog.created_at))
            .where(ActivityLog.user_id == user.id, ActivityLog.kind == ActivityKind.session)
        ).scalar_one_or_none()
        items.append(CreatorLogItem(
            creator_id=str(user.id),
            username=user.username,
            display_name=profile.display_name,
            rank=profile.rank.value,
            score=score,
            signal=_signal_from_score(score),
            metrics=m,
            last_active_at=last_active,
        ))
    # score 低い順 (作業停滞している creator を先に発見)
    items.sort(key=lambda x: x.score)
    return items


def _collect_creator_metrics(
    db: Session, creator_id: uuid.UUID, cutoff: datetime
) -> CreatorMetrics:
    session_count = int(db.execute(
        select(func.count()).select_from(ActivityLog).where(
            ActivityLog.user_id == creator_id,
            ActivityLog.kind == ActivityKind.session,
            ActivityLog.created_at >= cutoff,
        )
    ).scalar_one())

    active_days = int(db.execute(
        select(func.count(func.distinct(func.date_trunc("day", ActivityLog.created_at))))
        .where(
            ActivityLog.user_id == creator_id,
            ActivityLog.kind == ActivityKind.session,
            ActivityLog.created_at >= cutoff,
        )
    ).scalar_one())

    upload_count = int(db.execute(
        select(func.count()).select_from(Audio).where(
            Audio.creator_id == creator_id,
            Audio.created_at >= cutoff,
        )
    ).scalar_one())

    total_uploads_ever = int(db.execute(
        select(func.count()).select_from(Audio).where(Audio.creator_id == creator_id)
    ).scalar_one())

    sold_count = int(db.execute(
        select(func.count()).select_from(Audio).where(
            Audio.creator_id == creator_id,
            Audio.downloaded_at.is_not(None),
            Audio.downloaded_at >= cutoff,
        )
    ).scalar_one())

    sold_total = int(db.execute(
        select(func.count()).select_from(Audio).where(
            Audio.creator_id == creator_id,
            Audio.downloaded_at.is_not(None),
        )
    ).scalar_one())

    sell_rate = (sold_total / total_uploads_ever) if total_uploads_ever > 0 else 0.0

    earnings_pending = int(db.execute(
        select(func.coalesce(func.sum(CreatorPayout.amount_yen), 0)).where(
            CreatorPayout.creator_id == creator_id,
            CreatorPayout.status == PayoutStatus.pending,
        )
    ).scalar_one())

    earnings_paid = int(db.execute(
        select(func.coalesce(func.sum(CreatorPayout.amount_yen), 0)).where(
            CreatorPayout.creator_id == creator_id,
            CreatorPayout.status == PayoutStatus.paid,
            CreatorPayout.created_at >= cutoff,
        )
    ).scalar_one())

    commission_done_count = int(db.execute(
        select(func.count()).select_from(Order).where(
            Order.assigned_creator_id == creator_id,
            Order.status == OrderStatus.done,
            Order.done_at.is_not(None),
            Order.done_at >= cutoff,
        )
    ).scalar_one())

    message_count = int(db.execute(
        select(func.count()).select_from(OrderMessage).where(
            OrderMessage.sender_id == creator_id,
            OrderMessage.created_at >= cutoff,
        )
    ).scalar_one())

    return CreatorMetrics(
        session_count=session_count,
        active_days=active_days,
        upload_count=upload_count,
        sold_count=sold_count,
        sell_rate=round(sell_rate, 3),
        earnings_pending=earnings_pending,
        earnings_paid=earnings_paid,
        commission_done_count=commission_done_count,
        message_count=message_count,
    )


# ─── Detail (heatmap + sparkline + events) ────────────────────────────────────

class HeatmapCell(BaseModel):
    weekday: int  # 0=Mon ... 6=Sun
    hour: int  # 0..23
    count: int


class EventItem(BaseModel):
    ts: Any  # datetime
    kind: str
    detail: str


def _heatmap(db: Session, user_id: uuid.UUID, cutoff: datetime) -> list[HeatmapCell]:
    """activity_logs (session) を曜日×時間で集計。"""
    rows = db.execute(
        select(
            func.extract("dow", ActivityLog.created_at).label("dow"),
            func.extract("hour", ActivityLog.created_at).label("hour"),
            func.count().label("cnt"),
        )
        .where(
            ActivityLog.user_id == user_id,
            ActivityLog.kind == ActivityKind.session,
            ActivityLog.created_at >= cutoff,
        )
        .group_by("dow", "hour")
    ).all()
    cells = []
    for dow, hour, cnt in rows:
        # Postgres dow: 0=Sun, 1=Mon ... 6=Sat → 0=Mon ... 6=Sun に正規化
        weekday = (int(dow) - 1) % 7
        cells.append(HeatmapCell(weekday=weekday, hour=int(hour), count=int(cnt)))
    return cells


def _daily_buckets(
    rows: list[tuple[date, int]], cutoff_date: date, days: int
) -> list[dict[str, Any]]:
    """疎な (date, count) を 0埋め配列にする。"""
    by_date: dict[date, int] = {d: c for d, c in rows}
    out = []
    for i in range(days):
        d = cutoff_date + timedelta(days=i)
        out.append({"date": d.isoformat(), "value": by_date.get(d, 0)})
    return out


class UserDetail(BaseModel):
    user_id: str
    username: str
    score: int
    signal: Signal
    metrics: UserMetrics
    heatmap: list[HeatmapCell]
    sparkline: dict[str, list[dict[str, Any]]]  # downloads / sessions / tokens
    events: list[EventItem]


@router.get("/users/{user_id}/detail", response_model=UserDetail)
def get_user_detail(
    user_id: str,
    days: int = Query(DEFAULT_DAYS),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserDetail:
    days = _validate_days(days)
    cutoff = _cutoff(days)
    cutoff_date = cutoff.date()
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "user"})

    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "user"})

    metrics = _collect_user_metrics(db, uid, cutoff)
    score = _user_score(metrics, days)

    sessions_by_date = db.execute(
        select(
            func.date_trunc("day", ActivityLog.created_at).label("d"),
            func.count().label("c"),
        )
        .where(
            ActivityLog.user_id == uid,
            ActivityLog.kind == ActivityKind.session,
            ActivityLog.created_at >= cutoff,
        )
        .group_by("d")
    ).all()
    downloads_by_date = db.execute(
        select(
            func.date_trunc("day", DownloadLog.created_at).label("d"),
            func.count().label("c"),
        )
        .where(
            DownloadLog.user_id == uid,
            DownloadLog.kind == DownloadKind.initial,
            DownloadLog.created_at >= cutoff,
        )
        .group_by("d")
    ).all()
    tokens_by_date = db.execute(
        select(
            func.date_trunc("day", TokenConsumption.created_at).label("d"),
            func.sum(TokenConsumption.tokens).label("s"),
        )
        .where(
            TokenConsumption.user_id == uid,
            TokenConsumption.created_at >= cutoff,
        )
        .group_by("d")
    ).all()

    sparkline = {
        "sessions": _daily_buckets(
            [(d.date(), int(c)) for d, c in sessions_by_date], cutoff_date, days
        ),
        "downloads": _daily_buckets(
            [(d.date(), int(c)) for d, c in downloads_by_date], cutoff_date, days
        ),
        "tokens": _daily_buckets(
            [(d.date(), int(s or 0)) for d, s in tokens_by_date], cutoff_date, days
        ),
    }

    # Events (直近30件)
    events: list[EventItem] = []
    for dl in db.execute(
        select(DownloadLog, Audio.title)
        .join(Audio, Audio.id == DownloadLog.audio_id)
        .where(DownloadLog.user_id == uid, DownloadLog.created_at >= cutoff)
        .order_by(DownloadLog.created_at.desc())
        .limit(30)
    ).all():
        dl_row, title = dl
        events.append(EventItem(
            ts=dl_row.created_at, kind=dl_row.kind.value, detail=f"「{title}」",
        ))
    events.sort(key=lambda e: e.ts, reverse=True)

    return UserDetail(
        user_id=str(user.id),
        username=user.username,
        score=score,
        signal=_signal_from_score(score),
        metrics=metrics,
        heatmap=_heatmap(db, uid, cutoff),
        sparkline=sparkline,
        events=events[:30],
    )


class CreatorDetail(BaseModel):
    creator_id: str
    username: str
    display_name: str
    rank: str
    score: int
    signal: Signal
    metrics: CreatorMetrics
    rank_median: dict[str, float]
    heatmap: list[HeatmapCell]
    sparkline: dict[str, list[dict[str, Any]]]  # uploads / sold / earnings
    events: list[EventItem]


def _rank_median_metrics(db: Session, rank: str, cutoff: datetime) -> dict[str, float]:
    """同ランクの中央値を返す (レーダーチャート比較用)。"""
    profiles = db.execute(
        select(CreatorProfile).where(CreatorProfile.rank == rank)
    ).scalars().all()
    if not profiles:
        return {}
    vals: dict[str, list[float]] = defaultdict(list)
    for p in profiles:
        m = _collect_creator_metrics(db, p.user_id, cutoff)
        vals["active_days"].append(float(m.active_days))
        vals["upload_count"].append(float(m.upload_count))
        vals["sell_rate"].append(m.sell_rate)
        vals["commission_done_count"].append(float(m.commission_done_count))
        vals["message_count"].append(float(m.message_count))

    def median(xs: list[float]) -> float:
        if not xs:
            return 0.0
        s = sorted(xs)
        n = len(s)
        mid = n // 2
        return (s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2)

    return {k: round(median(v), 3) for k, v in vals.items()}


@router.get("/creators/{creator_id}/detail", response_model=CreatorDetail)
def get_creator_detail(
    creator_id: str,
    days: int = Query(DEFAULT_DAYS),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> CreatorDetail:
    days = _validate_days(days)
    cutoff = _cutoff(days)
    cutoff_date = cutoff.date()
    try:
        cid = uuid.UUID(creator_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "creator"})

    row = db.execute(
        select(User, CreatorProfile)
        .join(CreatorProfile, CreatorProfile.user_id == User.id)
        .where(User.id == cid)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "creator"})
    user, profile = row

    metrics = _collect_creator_metrics(db, cid, cutoff)
    score = _creator_score(metrics, days)

    sessions_by_date = db.execute(
        select(
            func.date_trunc("day", ActivityLog.created_at).label("d"),
            func.count().label("c"),
        )
        .where(
            ActivityLog.user_id == cid,
            ActivityLog.kind == ActivityKind.session,
            ActivityLog.created_at >= cutoff,
        )
        .group_by("d")
    ).all()
    uploads_by_date = db.execute(
        select(
            func.date_trunc("day", Audio.created_at).label("d"),
            func.count().label("c"),
        )
        .where(Audio.creator_id == cid, Audio.created_at >= cutoff)
        .group_by("d")
    ).all()
    sold_by_date = db.execute(
        select(
            func.date_trunc("day", Audio.downloaded_at).label("d"),
            func.count().label("c"),
        )
        .where(
            Audio.creator_id == cid,
            Audio.downloaded_at.is_not(None),
            Audio.downloaded_at >= cutoff,
        )
        .group_by("d")
    ).all()
    earnings_by_date = db.execute(
        select(
            func.date_trunc("day", CreatorPayout.created_at).label("d"),
            func.sum(CreatorPayout.amount_yen).label("s"),
        )
        .where(
            CreatorPayout.creator_id == cid,
            CreatorPayout.created_at >= cutoff,
        )
        .group_by("d")
    ).all()

    sparkline = {
        "sessions": _daily_buckets(
            [(d.date(), int(c)) for d, c in sessions_by_date], cutoff_date, days
        ),
        "uploads": _daily_buckets(
            [(d.date(), int(c)) for d, c in uploads_by_date], cutoff_date, days
        ),
        "sold": _daily_buckets(
            [(d.date(), int(c)) for d, c in sold_by_date], cutoff_date, days
        ),
        "earnings": _daily_buckets(
            [(d.date(), int(s or 0)) for d, s in earnings_by_date], cutoff_date, days
        ),
    }

    events: list[EventItem] = []
    for audio in db.execute(
        select(Audio).where(Audio.creator_id == cid, Audio.created_at >= cutoff)
        .order_by(Audio.created_at.desc()).limit(20)
    ).scalars().all():
        events.append(EventItem(ts=audio.created_at, kind="upload", detail=f"「{audio.title}」"))
    for audio in db.execute(
        select(Audio).where(
            Audio.creator_id == cid,
            Audio.downloaded_at.is_not(None),
            Audio.downloaded_at >= cutoff,
        ).order_by(Audio.downloaded_at.desc()).limit(20)
    ).scalars().all():
        events.append(EventItem(
            ts=audio.downloaded_at, kind="sold",
            detail=f"「{audio.title}」が販売 ({audio.duration_sec}s)",
        ))
    events.sort(key=lambda e: e.ts, reverse=True)

    return CreatorDetail(
        creator_id=str(user.id),
        username=user.username,
        display_name=profile.display_name,
        rank=profile.rank.value,
        score=score,
        signal=_signal_from_score(score),
        metrics=metrics,
        rank_median=_rank_median_metrics(db, profile.rank.value, cutoff),
        heatmap=_heatmap(db, cid, cutoff),
        sparkline=sparkline,
        events=events[:30],
    )
