"""Commission / Order endpoints.

Roles:
  user    – create, submit, cancel, message, download done file
  creator – view assigned, reply, submit-file
  admin   – all of the above + nominate, assign, done, reject, token_cost edit
"""
from __future__ import annotations

import shutil
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.models import (
    ActivityKind,
    ActivityLog,
    CreatorPayout,
    CreatorProfile,
    CreatorRankPrice,
    Order,
    OrderBriefEdit,
    OrderCandidateCreator,
    OrderMessage,
    OrderMessageKind,
    OrderStatus,
    CandidateResponseStatus,
    PayoutStatus,
    SystemSetting,
    TokenConsumption,
    User,
)
from app.models.base import new_uuid
from app.security.deps import get_current_user, get_optional_user, require_role
from app.security.signed_url import (
    SignedURLError,
    issue_order_download,
    issue_submission_stream,
    verify_order_download,
    verify_submission_stream,
)
from app.services import tokens as tokens_service

settings = get_settings()
router = APIRouter(tags=["orders"])


def _build_url(path: str, params: dict) -> str:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{path}?{qs}"


# ─── Helper: commission feature flag ──────────────────────────────────────────

def _commission_enabled(db: Session) -> bool:
    row = db.execute(
        select(SystemSetting.value).where(SystemSetting.key == "commission_enabled")
    ).scalar_one_or_none()
    return row == "true"


def _require_commission(db: Session = Depends(get_db)) -> None:
    if not _commission_enabled(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "COMMISSION_DISABLED", "message": "Commission feature is disabled"},
        )


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CandidateOut(BaseModel):
    id: str
    creator_id: str
    creator_name: str
    response_status: str
    sent_at: Any

class MessageOut(BaseModel):
    id: str
    sender_id: str | None
    sender_name: str | None
    content: str | None
    attachment_path: str | None
    kind: str
    created_at: Any

class OrderOut(BaseModel):
    id: str
    title: str
    serial: int
    description: str | None
    brief: dict | None
    token_cost: int
    desired_deadline: Any  # date
    status: str
    user_id: str
    user_name: str
    assigned_creator_id: str | None
    assigned_creator_name: str | None
    candidates: list[CandidateOut] = []
    messages: list[MessageOut] = []
    file_path: str | None
    notified_at: Any
    closed_at: Any  # 改訂2.2: user が受け取った時刻 (archive flag)
    created_at: Any
    updated_at: Any

class OrderListItem(BaseModel):
    id: str
    title: str
    serial: int
    token_cost: int
    desired_deadline: Any  # date
    status: str
    user_name: str
    assigned_creator_name: str | None
    notified_at: Any
    closed_at: Any  # 改訂2.2
    created_at: Any
    updated_at: Any


def _to_candidate(c: OrderCandidateCreator) -> CandidateOut:
    return CandidateOut(
        id=str(c.id),
        creator_id=str(c.creator_id),
        creator_name=c.creator.display_name,
        response_status=c.response_status.value,
        sent_at=c.sent_at,
    )


def _to_message(m: OrderMessage) -> MessageOut:
    return MessageOut(
        id=str(m.id),
        sender_id=str(m.sender_id) if m.sender_id else None,
        sender_name=m.sender.username if m.sender else None,
        content=m.content,
        attachment_path=m.attachment_path,
        kind=m.kind.value,
        created_at=m.created_at,
    )


def _to_order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=str(order.id),
        title=order.title,
        serial=order.serial,
        description=order.description,
        brief=order.brief,
        token_cost=order.token_cost,
        desired_deadline=order.desired_deadline,
        status=order.status.value,
        user_id=str(order.user_id),
        user_name=order.user.username,
        assigned_creator_id=str(order.assigned_creator_id) if order.assigned_creator_id else None,
        assigned_creator_name=(
            order.assigned_creator.display_name if order.assigned_creator else None
        ),
        candidates=[_to_candidate(c) for c in order.candidates],
        messages=[_to_message(m) for m in order.messages],
        file_path=order.file_path,
        notified_at=order.notified_at,
        closed_at=order.closed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _to_list_item(order: Order) -> OrderListItem:
    return OrderListItem(
        id=str(order.id),
        title=order.title,
        serial=order.serial,
        token_cost=order.token_cost,
        desired_deadline=order.desired_deadline,
        status=order.status.value,
        user_name=order.user.username,
        assigned_creator_name=(
            order.assigned_creator.display_name if order.assigned_creator else None
        ),
        notified_at=order.notified_at,
        closed_at=order.closed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _load_order(db: Session, order_id: uuid.UUID) -> Order:
    order = db.execute(
        select(Order)
        .options(
            joinedload(Order.user),
            joinedload(Order.assigned_creator),
            joinedload(Order.candidates).joinedload(OrderCandidateCreator.creator),
            joinedload(Order.messages).joinedload(OrderMessage.sender),
        )
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "order not found"})
    return order


def _add_status_message(db: Session, order_id: uuid.UUID, sender_id: uuid.UUID, new_status: str, extra: str | None = None) -> None:
    content = f"ステータス変更: {new_status}"
    if extra:
        content += f" — {extra}"
    db.add(OrderMessage(
        order_id=order_id,
        sender_id=sender_id,
        content=content,
        kind=OrderMessageKind.status_change,
    ))


# ─── Public: commission enabled flag ──────────────────────────────────────────

@router.get("/system/commission")
def commission_status(db: Session = Depends(get_db)) -> dict:
    return {"enabled": _commission_enabled(db)}


# ─── Unread notification (改訂2 = 二系統) ──────────────────────────────────────

# 情報通知 (選ばれなかった候補など) の自動解除期間
INFO_NOTIFICATION_TTL_DAYS = 7


def _count_action_required(db: Session, user: User) -> int:
    """要対応 (ステータス遷移ベース)。完了するまで残る。"""
    role = user.role.value
    if role == "user":
        # 自分の発注で reviewing (納品をレビューする番)
        q = select(func.count()).select_from(Order).where(
            Order.user_id == user.id,
            Order.status == OrderStatus.reviewing,
        )
    elif role == "creator":
        # 未回答のノミネーション + assigned で作業中 (音源提出する番)
        pending_q = select(func.count()).select_from(OrderCandidateCreator).where(
            OrderCandidateCreator.creator_id == user.id,
            OrderCandidateCreator.response_status == CandidateResponseStatus.pending,
        )
        assigned_q = select(func.count()).select_from(Order).where(
            Order.assigned_creator_id == user.id,
            Order.status == OrderStatus.assigned,
        )
        return int(db.execute(pending_q).scalar_one()) + int(db.execute(assigned_q).scalar_one())
    else:  # admin
        q = select(func.count()).select_from(Order).where(
            Order.status.in_([OrderStatus.open, OrderStatus.reviewing]),
        )
    return int(db.execute(q).scalar_one())


def _participant_order_ids_subq(user: User):
    """自分がチケットに参加している order_id 集合を返すサブクエリ。"""
    role = user.role.value
    if role == "user":
        return select(Order.id).where(Order.user_id == user.id)
    if role == "creator":
        # 候補 or assigned の order
        candidate_orders = select(OrderCandidateCreator.order_id).where(
            OrderCandidateCreator.creator_id == user.id
        )
        return select(Order.id).where(
            (Order.assigned_creator_id == user.id) |
            Order.id.in_(candidate_orders)
        )
    # admin は全 order
    return select(Order.id)


def _count_message_unread(db: Session, user: User) -> int:
    """チケット内メッセージ未読数。
    自分以外が送信した最新メッセージが、自分の最終 order_view より新しい order の数。
    """
    participant_subq = _participant_order_ids_subq(user).subquery()

    # 自分が最後に order_view した時刻 (per order)
    last_view = (
        select(
            ActivityLog.target_id.label("order_id"),
            func.max(ActivityLog.created_at).label("last_view_at"),
        )
        .where(
            ActivityLog.user_id == user.id,
            ActivityLog.kind == ActivityKind.order_view,
        )
        .group_by(ActivityLog.target_id)
        .subquery()
    )

    # 自分以外が送った最新メッセージ時刻 (per order)
    last_msg = (
        select(
            OrderMessage.order_id.label("order_id"),
            func.max(OrderMessage.created_at).label("last_msg_at"),
        )
        .where(OrderMessage.sender_id != user.id)
        .group_by(OrderMessage.order_id)
        .subquery()
    )

    # 参加 order && メッセージあり && (未閲覧 OR メッセージ > 閲覧)
    q = (
        select(func.count())
        .select_from(last_msg)
        .join(participant_subq, participant_subq.c.id == last_msg.c.order_id)
        .outerjoin(last_view, last_view.c.order_id == last_msg.c.order_id)
        .where(
            (last_view.c.last_view_at.is_(None)) |
            (last_msg.c.last_msg_at > last_view.c.last_view_at)
        )
    )
    return int(db.execute(q).scalar_one())


def _count_info_only(db: Session, user: User) -> int:
    """情報通知。creator のみ。
    自分が accepted で「できる」と返したが、別の creator が選ばれた order。
    `updated_at` が 7日以内 かつ 自分が「結果が確定してから」一度も order_view していないもの。
    """
    if user.role.value != "creator":
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=INFO_NOTIFICATION_TTL_DAYS)

    last_view = (
        select(
            ActivityLog.target_id.label("order_id"),
            func.max(ActivityLog.created_at).label("last_view_at"),
        )
        .where(
            ActivityLog.user_id == user.id,
            ActivityLog.kind == ActivityKind.order_view,
        )
        .group_by(ActivityLog.target_id)
        .subquery()
    )

    q = (
        select(func.count())
        .select_from(OrderCandidateCreator)
        .join(Order, Order.id == OrderCandidateCreator.order_id)
        .outerjoin(last_view, last_view.c.order_id == Order.id)
        .where(
            OrderCandidateCreator.creator_id == user.id,
            OrderCandidateCreator.response_status == CandidateResponseStatus.accepted,
            Order.assigned_creator_id.is_not(None),
            Order.assigned_creator_id != user.id,
            Order.updated_at >= cutoff,
            (last_view.c.last_view_at.is_(None)) |
            (Order.updated_at > last_view.c.last_view_at),
        )
    )
    return int(db.execute(q).scalar_one())


@router.get("/me/commission/unread")
def commission_unread(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """改訂2: 要対応 / メッセージ未読 / 情報通知 を二系統に分けて返す。

    TopNav は以下の判定で表示:
      - action_count > 0 → 橙 + 件数バッジ + 金ドット
      - action_count == 0 && has_info → 橙のみ (件数なし) + 金ドット
      - 両方ゼロ → デフォルト色
    """
    action_required = _count_action_required(db, current_user)
    message_unread = _count_message_unread(db, current_user)
    info_only = _count_info_only(db, current_user)
    action_count = action_required + message_unread
    return {
        "action_count": action_count,
        "has_info": info_only > 0,
        "breakdown": {
            "action_required": action_required,
            "message_unread": message_unread,
            "info_only": info_only,
        },
    }


# ─── Orders list ──────────────────────────────────────────────────────────────

@router.get("/orders", response_model=list[OrderListItem])
def list_orders(
    archived: bool = Query(False, description="改訂2.2: closed_at セット済を含めるか (admin のみ意味あり)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> list[OrderListItem]:
    role = current_user.role.value
    base = (
        select(Order)
        .options(
            joinedload(Order.user),
            joinedload(Order.assigned_creator),
        )
    )
    if role == "user":
        # user/creator は closed (受け取り済) を非表示
        q = base.where(Order.user_id == current_user.id, Order.closed_at.is_(None))
    elif role == "creator":
        candidate_order_ids = select(OrderCandidateCreator.order_id).where(
            OrderCandidateCreator.creator_id == current_user.id
        )
        q = base.where(
            ((Order.assigned_creator_id == current_user.id) |
             Order.id.in_(candidate_order_ids)),
            Order.closed_at.is_(None),
        )
    else:  # admin
        # archived=true なら closed のみ、false なら未 close のみ
        if archived:
            q = base.where(Order.closed_at.is_not(None))
        else:
            q = base.where(Order.closed_at.is_(None))

    rows = db.execute(q.order_by(Order.updated_at.desc())).unique().scalars().all()
    return [_to_list_item(o) for o in rows]


# ─── Create order ─────────────────────────────────────────────────────────────

# 改訂2: タイトル/token_cost は手入力廃止。brief.length_sec から自動算出
# desired_deadline は default = 作成日 + 7日、user が指定すれば優先
class CreateOrderRequest(BaseModel):
    description: str | None = None
    brief: dict | None = None
    desired_deadline: date | None = None


DEFAULT_DEADLINE_DAYS = 7


def _next_global_serial(db: Session) -> int:
    """Commission Order 全体の通し番号を採番する。
    キャンセル/削除された番号は再利用しない (Postgres sequence で担保)。
    """
    return int(db.execute(select(func.nextval("orders_serial_seq"))).scalar_one())


def _generate_title(username: str, serial: int, when: datetime | None = None) -> str:
    """改訂2 / 改訂2.2: 自動タイトル (件名) 生成 `YYYYMMDD_<username>_Order`。
    serial (`#<N>`) は title に含めず、UI で別表示 (REDMINE 風)。"""
    when = when or datetime.now(timezone.utc)
    return f"{when:%Y%m%d}_{username}_Order"


def _extract_length_sec(brief: dict | None) -> int:
    """brief.length_sec を取り出して token_cost として返す。
    未指定/不正な場合は INVALID_TOKEN_COST。
    """
    if not brief or not isinstance(brief, dict):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_TOKEN_COST", "message": "brief.length_sec is required"},
        )
    raw = brief.get("length_sec")
    try:
        length = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_TOKEN_COST", "message": "brief.length_sec must be integer"},
        )
    if length <= 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_TOKEN_COST", "message": "brief.length_sec must be > 0"},
        )
    return length


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    body: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    token_cost = _extract_length_sec(body.brief)
    serial = _next_global_serial(db)
    title = _generate_title(current_user.username, serial)
    deadline = body.desired_deadline or (date.today() + timedelta(days=DEFAULT_DEADLINE_DAYS))
    order = Order(
        user_id=current_user.id,
        serial=serial,
        title=title,
        description=body.description,
        brief=body.brief,
        token_cost=token_cost,
        desired_deadline=deadline,
        status=OrderStatus.draft,
    )
    db.add(order)
    db.commit()
    return _to_order_out(_load_order(db, order.id))


# ─── Order detail ─────────────────────────────────────────────────────────────

@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    try:
        parsed = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "order not found"})
    order = _load_order(db, parsed)
    _check_access(order, current_user)
    return _to_order_out(order)


# ─── View tracking (改訂2) ─────────────────────────────────────────────────────

@router.post("/orders/{order_id}/view", status_code=status.HTTP_201_CREATED)
def record_order_view(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> dict:
    """発注詳細を開いた時に呼び出し、`activity_logs` に order_view を記録する。
    既読時刻として通知バッジ計算に使用される。
    """
    parsed = _parse_uuid(order_id)
    order = _load_order(db, parsed)
    _check_access(order, current_user)
    db.add(ActivityLog(
        user_id=current_user.id,
        kind=ActivityKind.order_view,
        target_id=parsed,
    ))
    db.commit()
    return {"recorded": True}


def _check_access(order: Order, user: User) -> None:
    role = user.role.value
    if role == "admin":
        return
    if role == "user" and order.user_id == user.id:
        return
    if role == "creator":
        is_candidate = any(str(c.creator_id) == str(user.id) for c in order.candidates)
        if order.assigned_creator_id == user.id or is_candidate:
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "access denied"},
    )


# ─── Submit (draft → open) ────────────────────────────────────────────────────

@router.post("/orders/{order_id}/submit", response_model=OrderOut)
def submit_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    is_admin = current_user.role.value == "admin"
    if order.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "not your order"})
    if order.status != OrderStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"expected draft, got {order.status.value}"})

    # Token balance check. admin が代理 submit する場合は order.user の残高で判定
    order_owner = db.get(User, order.user_id) if is_admin and order.user_id != current_user.id else current_user
    lic = order_owner.license if order_owner else None
    if lic is None:
        raise HTTPException(status_code=403, detail={"code": "NO_LICENSE", "message": "no license"})
    available = tokens_service.available_tokens(db, order_owner.id, lic)
    if available < order.token_cost:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "INSUFFICIENT_TOKENS",
                "message": f"need {order.token_cost} tokens but only {available} available",
            },
        )

    order.status = OrderStatus.open
    order.updated_at = func.now()
    _add_status_message(db, parsed, current_user.id, "open")
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Update draft (改訂2: 一時保存編集) ────────────────────────────────────────

class UpdateDraftRequest(BaseModel):
    brief: dict | None = None
    description: str | None = None
    desired_deadline: date | None = None


@router.patch("/orders/{order_id}/draft", response_model=OrderOut)
def update_draft(
    order_id: str,
    body: UpdateDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    """draft 状態の発注を編集する (改訂2: 一時保存からの続き入力)。
    発注者本人 または admin (代理編集) のみ。status≠draft の場合は INVALID_STATE。
    brief を渡した場合は token_cost = brief.length_sec で再計算。
    """
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    if order.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "not your order"},
        )
    if order.status != OrderStatus.draft:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_STATE", "message": f"draft 以外は編集不可 (current: {order.status.value})"},
        )
    if body.brief is not None:
        order.brief = body.brief
        order.token_cost = _extract_length_sec(body.brief)
    if body.description is not None:
        order.description = body.description
    if body.desired_deadline is not None:
        order.desired_deadline = body.desired_deadline
    order.updated_at = func.now()
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Update brief after submit (改訂2.1) ──────────────────────────────────────

# brief field の日本語ラベル (bot メッセージ用)
BRIEF_FIELD_LABEL: dict[str, str] = {
    "sound_type": "サウンドタイプ",
    "purpose": "用途",
    "purpose_note": "用途補足",
    "length_sec": "曲の長さ",
    "bgm_scenes": "BGM シーン",
    "bgm_loop": "BGM ループ",
    "bgm_note": "BGM 補足",
    "se_trigger": "SE トリガー",
    "se_functions": "SE 役割",
    "emotions_target": "狙う感情",
    "emotions_avoid": "避けたい感情",
    "memory_impression": "イメージ",
    "tx_organic_electronic": "テクスチャ (有機/電子)",
    "tx_melody_rhythm": "テクスチャ (メロディ/リズム)",
    "tx_warm_cold": "テクスチャ (温/冷)",
    "tx_sparse_dense": "テクスチャ (疎/密)",
    "tx_static_dynamic": "テクスチャ (静/動)",
    "reference_urls": "参考 URL",
    "reference_elements": "参考要素",
    "reference_avoid": "避ける要素",
    "delivery_format": "納品形式",
    "note": "備考",
}

# 編集可能なステータス (ORDER_SPEC §13.3)
EDITABLE_AFTER_SUBMIT_STATUSES = {
    OrderStatus.open, OrderStatus.recruiting, OrderStatus.assigned,
}


class UpdateBriefRequest(BaseModel):
    brief: dict


def _diff_brief(old: dict | None, new: dict) -> list[tuple[str, Any, Any]]:
    """変更された (field, old_value, new_value) のリストを返す。
    BRIEF_FIELD_LABEL に載っている key のみ対象 (未知 key は無視)。
    """
    old = old or {}
    out: list[tuple[str, Any, Any]] = []
    for key in BRIEF_FIELD_LABEL:
        old_v = old.get(key)
        new_v = new.get(key)
        # 空文字列と None は同等扱い (UI 由来の空項目を変更扱いしない)
        if (old_v in (None, "", [], {})) and (new_v in (None, "", [], {})):
            continue
        if old_v != new_v:
            out.append((key, old_v, new_v))
    return out


def _format_diff_value(v: Any) -> str:
    """bot メッセージ用に diff 値を 1 行で整形。"""
    if v is None or v == "":
        return "(未設定)"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) if v else "(なし)"
    if isinstance(v, bool):
        return "ON" if v else "OFF"
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def _build_brief_edit_message(diffs: list[tuple[str, Any, Any]]) -> str:
    """変更内容を bot メッセージ本文に整形。"""
    lines = ["✏️ ブリーフを編集しました"]
    for key, old_v, new_v in diffs:
        label = BRIEF_FIELD_LABEL.get(key, key)
        lines.append(f"{label}: {_format_diff_value(old_v)} → {_format_diff_value(new_v)}")
    return "\n".join(lines)


@router.patch("/orders/{order_id}/brief-after-submit", response_model=OrderOut)
def update_brief_after_submit(
    order_id: str,
    body: UpdateBriefRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    """発注後 (status=open / recruiting / assigned) のブリーフを編集する。

    動作:
      1. 権限: 発注者本人 または admin
      2. status 制約: reviewing / done / cancelled では不可
      3. brief を上書き + 変更差分を `order_brief_edits` に記録
      4. `length_sec` が変わった場合は `token_cost` を再計算し残量確認
      5. bot メッセージ (kind=brief_edit) をチャットに自動投稿
    """
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    is_admin = current_user.role.value == "admin"
    if order.user_id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "not your order"},
        )
    if order.status not in EDITABLE_AFTER_SUBMIT_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INVALID_STATE",
                "message": f"発注後ブリーフ編集は open / recruiting / assigned のみ可 (current: {order.status.value})",
            },
        )

    diffs = _diff_brief(order.brief, body.brief)
    if not diffs:
        # 変更なし → 何もせず返す
        return _to_order_out(_load_order(db, parsed))

    # 1. 差分を履歴テーブルに記録
    for field, old_v, new_v in diffs:
        db.add(OrderBriefEdit(
            order_id=parsed,
            editor_id=current_user.id,
            field_path=field,
            old_value=old_v,
            new_value=new_v,
        ))

    # 2. brief 上書き + 長さ変更時は token 再計算 + 残量確認
    order.brief = body.brief
    if any(field == "length_sec" for field, _, _ in diffs):
        new_length = _extract_length_sec(body.brief)
        owner = db.get(User, order.user_id)
        lic = owner.license if owner else None
        if lic is None:
            raise HTTPException(status_code=403, detail={"code": "NO_LICENSE", "message": "no license"})
        # 残量計算: 現在の order.token_cost を「予約済」とみなして判定
        # (確定消費はまだ done 時のみ。order_owner の他の予定も含めない簡易判定)
        available = tokens_service.available_tokens(db, owner.id, lic)
        # 差分だけ追加で必要 (現 token_cost は予約済として扱う)
        delta = new_length - order.token_cost
        if delta > 0 and available < delta:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "INSUFFICIENT_TOKENS",
                    "message": f"曲長を {new_length}秒 にするには追加 {delta} token 必要 (残量 {available})",
                },
            )
        order.token_cost = new_length

    # 3. bot メッセージ (sender_id=None で「システム発」)
    db.add(OrderMessage(
        order_id=parsed,
        sender_id=None,
        content=_build_brief_edit_message(diffs),
        kind=OrderMessageKind.brief_edit,
    ))
    order.updated_at = func.now()
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Brief edit history (改訂2.1) ─────────────────────────────────────────────

class BriefEditHistoryItem(BaseModel):
    id: str
    editor_id: str | None
    editor_name: str | None
    field_path: str
    field_label: str
    old_value: Any
    new_value: Any
    created_at: Any


@router.get("/orders/{order_id}/brief-edits", response_model=list[BriefEditHistoryItem])
def list_brief_edits(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> list[BriefEditHistoryItem]:
    """発注後ブリーフ編集の差分履歴を新しい順で返す (詳細画面のモーダル表示用)。"""
    parsed = _parse_uuid(order_id)
    order = _load_order(db, parsed)
    _check_access(order, current_user)
    rows = db.execute(
        select(OrderBriefEdit)
        .options(joinedload(OrderBriefEdit.editor))
        .where(OrderBriefEdit.order_id == parsed)
        .order_by(OrderBriefEdit.created_at.desc())
    ).unique().scalars().all()
    return [
        BriefEditHistoryItem(
            id=str(r.id),
            editor_id=str(r.editor_id) if r.editor_id else None,
            editor_name=r.editor.username if r.editor else None,
            field_path=r.field_path,
            field_label=BRIEF_FIELD_LABEL.get(r.field_path, r.field_path),
            old_value=r.old_value,
            new_value=r.new_value,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ─── Update deadline (改訂2) ───────────────────────────────────────────────────

class UpdateDeadlineRequest(BaseModel):
    desired_deadline: date


@router.patch("/orders/{order_id}/deadline", response_model=OrderOut)
def update_deadline(
    order_id: str,
    body: UpdateDeadlineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    """発注者本人または admin が希望締切日を変更する。
    done/cancelled 後は不可。
    """
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    role = current_user.role.value
    if role != "admin" and order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "not your order"},
        )
    if order.status in (OrderStatus.done, OrderStatus.cancelled):
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_STATE", "message": "cannot change deadline after done/cancelled"},
        )
    order.desired_deadline = body.desired_deadline
    order.updated_at = func.now()
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Close (改訂2.2: user が受け取る → archive) ─────────────────────────────

@router.post("/orders/{order_id}/close", response_model=OrderOut)
def close_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    """改訂2.2 (再): User が「受け取る」を押すと **token 消費 + Creator payout 生成 + closed_at** を同時に実行する。
    admin の done は提出ファイルを最終パスへコピーするだけで、token は消費しない。
    支払いは user 受領のタイミングで確定する設計 (ユーザが受け取らない限り消費されない)。"""
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    # 発注者本人または admin のみ close 可能
    if order.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "not your order"})
    if order.status != OrderStatus.done:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_STATE", "message": f"close 可能なのは done のみ (current: {order.status.value})"},
        )
    if order.closed_at is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_CLOSED", "message": "既に受け取り済 (アーカイブ済)"},
        )

    # ── Token 消費 (order.user の license で残量チェック → INSERT) ──
    owner = db.execute(select(User).where(User.id == order.user_id)).scalar_one()
    lic = owner.license
    if lic is None:
        raise HTTPException(status_code=422, detail={"code": "NO_LICENSE", "message": "user has no license"})
    available = tokens_service.available_tokens(db, owner.id, lic)
    if available < order.token_cost:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "INSUFFICIENT_TOKENS",
                "message": f"受け取りに {order.token_cost} token 必要 (残量 {available})",
            },
        )
    period = tokens_service.current_period_jst()
    db.add(TokenConsumption(
        user_id=order.user_id,
        audio_id=None,
        license_id=lic.id,
        tokens=order.token_cost,
        period_yyyymm=period,
    ))

    # ── Creator payout 生成 (ランク単価 × token_cost) ──
    if order.assigned_creator_id:
        creator_profile = db.execute(
            select(CreatorProfile).where(CreatorProfile.user_id == order.assigned_creator_id)
        ).scalar_one_or_none()
        if creator_profile:
            rank_price = db.execute(
                select(CreatorRankPrice).where(CreatorRankPrice.rank == creator_profile.rank)
            ).scalar_one_or_none()
            if rank_price:
                db.add(CreatorPayout(
                    audio_id=None,
                    creator_id=order.assigned_creator_id,
                    rank_at_payout=creator_profile.rank,
                    unit_price_yen=rank_price.unit_price_yen,
                    amount_yen=rank_price.unit_price_yen * order.token_cost,
                    status=PayoutStatus.pending,
                ))

    # ── アーカイブフラグ ──
    order.closed_at = datetime.now(timezone.utc)
    order.updated_at = func.now()
    _add_status_message(db, parsed, current_user.id, "closed (受け取り完了 / token消費)")
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Submission stream (改訂2.2: 受け取る前のプレビュー) ─────────────────────

@router.get("/orders/{order_id}/submission-stream-url")
def get_submission_stream_url(
    order_id: str,
    start: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> dict:
    """チケット参加者 (user / assigned_creator / admin) が、提出済音源を 10秒チャンクで
    プレビューするための signed URL を発行する。
    対象ステータス: reviewing / done (submission ファイルが存在する状態)。
    """
    parsed = _parse_uuid(order_id)
    order = _load_order(db, parsed)
    _check_access(order, current_user)
    if order.status not in (OrderStatus.reviewing, OrderStatus.done):
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_SUBMISSION_FILE", "message": "submission file not available"},
        )
    params = issue_submission_stream(str(parsed), start)
    return {"url": _build_url("/api/v1/orders/submission-stream", params)}


@router.get("/orders/submission-stream")
def submission_stream(
    order_id: str = Query(...),
    start: int = Query(0, ge=0),
    exp: int = Query(...),
    sig: str = Query(...),
    db: Session = Depends(get_db),
) -> Any:
    """signed URL の検証 → submission ファイルから 10秒チャンクを切り出して返す。
    JWT 不要 (短命 signed URL で代替)。"""
    try:
        verify_submission_stream(order_id, start, exp, sig)
    except SignedURLError as exc:
        raise HTTPException(status_code=403, detail={"code": exc.code, "message": exc.message})

    parsed = _parse_uuid(order_id)
    # 提出ファイル: reviewing は submissions/{id}.wav, done は {id}.wav (どちらかを使う)
    sub_path = Path(settings.ORDERS_DIR) / "submissions" / f"{parsed}.wav"
    final_path = Path(settings.ORDERS_DIR) / f"{parsed}.wav"
    path = sub_path if sub_path.exists() else final_path
    if not path.exists():
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "no submission file"})

    import subprocess
    from fastapi.responses import StreamingResponse
    proc = subprocess.Popen(
        [
            "ffmpeg", "-loglevel", "error",
            "-ss", str(start), "-t", "10",
            "-i", str(path),
            "-c:a", "copy",
            "-f", "wav", "pipe:1",
        ],
        stdout=subprocess.PIPE,
    )

    def _iter_chunks():
        try:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.kill()

    return StreamingResponse(_iter_chunks(), media_type="audio/wav")


# ─── Cancel ───────────────────────────────────────────────────────────────────

@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    _check_access(order, current_user)
    if order.status in (OrderStatus.done, OrderStatus.cancelled):
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": "cannot cancel"})
    order.status = OrderStatus.cancelled
    order.updated_at = func.now()
    _add_status_message(db, parsed, current_user.id, "cancelled")
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Message ──────────────────────────────────────────────────────────────────

class AddMessageRequest(BaseModel):
    content: str


@router.post("/orders/{order_id}/message", response_model=OrderOut)
def add_message(
    order_id: str,
    body: AddMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed)).scalar_one_or_none()
    _check_order_exists(order)
    _check_access(order, current_user)
    if order.status in (OrderStatus.done, OrderStatus.cancelled):
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": "order is closed"})
    db.add(OrderMessage(
        order_id=parsed,
        sender_id=current_user.id,
        content=body.content,
        kind=OrderMessageKind.comment,
    ))
    order.updated_at = func.now()
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Creator: candidate response ──────────────────────────────────────────────

class RespondRequest(BaseModel):
    response: str  # "accepted" | "declined"
    content: str | None = None


@router.post("/orders/{order_id}/respond", response_model=OrderOut)
def respond_to_nomination(
    order_id: str,
    body: RespondRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("creator", "admin")),
    _: None = Depends(_require_commission),
) -> OrderOut:
    if body.response not in ("accepted", "declined"):
        raise HTTPException(status_code=422, detail={"code": "INVALID_RESPONSE", "message": "response must be 'accepted' or 'declined'"})
    parsed = _parse_uuid(order_id)
    # FOR UPDATE: ダブルクリックで accepted を上書きする競合を避ける
    candidate = db.execute(
        select(OrderCandidateCreator)
        .where(
            OrderCandidateCreator.order_id == parsed,
            OrderCandidateCreator.creator_id == current_user.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=403, detail={"code": "NOT_CANDIDATE", "message": "you are not a candidate for this order"})
    candidate.response_status = CandidateResponseStatus(body.response)
    candidate.response_at = func.now()

    order = db.execute(select(Order).where(Order.id == parsed)).scalar_one_or_none()
    order.updated_at = func.now()
    if body.content:
        db.add(OrderMessage(
            order_id=parsed,
            sender_id=current_user.id,
            content=body.content,
            kind=OrderMessageKind.comment,
        ))
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Creator: submit file (assigned → reviewing) ──────────────────────────────

@router.post("/orders/{order_id}/submit-file", response_model=OrderOut)
def submit_file(
    order_id: str,
    file: UploadFile = File(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("creator", "admin")),
    _: None = Depends(_require_commission),
) -> OrderOut:
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    if order.assigned_creator_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "not assigned to this order"})
    if order.status != OrderStatus.assigned:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"expected assigned, got {order.status.value}"})

    # 提出ファイルは submissions/ サブディレクトリへ。
    # 最終納品パス `{ORDERS_DIR}/{order_id}.wav` は admin の done 承認時に確定する
    # → 差し戻し中の reviewing→assigned で誤って user が DL するのを防ぐ
    sub_dir = Path(settings.ORDERS_DIR) / "submissions"
    sub_dir.mkdir(parents=True, exist_ok=True)
    dest = sub_dir / f"{parsed}.wav"
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        import shutil as _shutil
        with open(tmp_path, "wb") as f:
            _shutil.copyfileobj(file.file, f)
        _shutil.copy2(tmp_path, dest)
    finally:
        tmp_path.unlink(missing_ok=True)

    order.status = OrderStatus.reviewing
    order.updated_at = func.now()
    db.add(OrderMessage(
        order_id=parsed,
        sender_id=current_user.id,
        content=note or "音源を提出しました。",
        attachment_path=str(dest),
        kind=OrderMessageKind.submission,
    ))
    _add_status_message(db, parsed, current_user.id, "reviewing")
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── User: download done file ─────────────────────────────────────────────────

@router.get("/orders/{order_id}/file-url")
def get_order_file_url(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> dict:
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed)).scalar_one_or_none()
    _check_order_exists(order)
    if order.status != OrderStatus.done:
        raise HTTPException(status_code=409, detail={"code": "NOT_DONE", "message": "order is not done"})
    if order.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "access denied"})
    params = issue_order_download(str(parsed), str(current_user.id))
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": f"/api/v1/orders/download-file?{qs}"}


@router.get("/orders/download-file")
def download_order_file(
    order_id: str = Query(...),
    user_id: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        verify_order_download(order_id, user_id, exp, sig)
    except SignedURLError as exc:
        raise HTTPException(status_code=403, detail={"code": exc.code, "message": exc.message})

    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed)).scalar_one_or_none()
    if order is None or order.file_path is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "file not found"})
    fp = Path(order.file_path)
    if not fp.exists():
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "file missing"})
    return FileResponse(path=str(fp), media_type="audio/wav", filename=f"{order.title}.wav")


# ─── Admin: nominate candidates ───────────────────────────────────────────────

class NominateRequest(BaseModel):
    creator_ids: list[str]


@router.post("/orders/{order_id}/nominate", response_model=OrderOut)
def nominate_creators(
    order_id: str,
    body: NominateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    _: None = Depends(_require_commission),
) -> OrderOut:
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    if order.status not in (OrderStatus.open, OrderStatus.recruiting):
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"cannot nominate in state {order.status.value}"})

    for cid_str in body.creator_ids:
        cid = uuid.UUID(cid_str)
        exists = db.execute(
            select(OrderCandidateCreator).where(
                OrderCandidateCreator.order_id == parsed,
                OrderCandidateCreator.creator_id == cid,
            )
        ).scalar_one_or_none()
        if not exists:
            db.add(OrderCandidateCreator(
                order_id=parsed,
                creator_id=cid,
                sent_by_admin_id=current_user.id,
            ))
    order.status = OrderStatus.recruiting
    order.updated_at = func.now()
    _add_status_message(db, parsed, current_user.id, "recruiting")
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Admin: assign creator ────────────────────────────────────────────────────

class AssignRequest(BaseModel):
    creator_id: str
    token_cost: int | None = None  # optional adjustment


@router.post("/orders/{order_id}/assign", response_model=OrderOut)
def assign_creator(
    order_id: str,
    body: AssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    _: None = Depends(_require_commission),
) -> OrderOut:
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    if order.status not in (OrderStatus.open, OrderStatus.recruiting):
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"cannot assign in state {order.status.value}"})

    creator_id = uuid.UUID(body.creator_id)
    # Verify creator exists
    profile = db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == creator_id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail={"code": "CREATOR_NOT_FOUND", "message": "creator not found"})

    order.assigned_creator_id = creator_id
    order.assigned_by_admin_id = current_user.id
    order.assigned_at = func.now()
    order.status = OrderStatus.assigned
    order.updated_at = func.now()
    if body.token_cost is not None and body.token_cost > 0:
        order.token_cost = body.token_cost
    _add_status_message(db, parsed, current_user.id, "assigned", f"Creator: {profile.display_name}")
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Admin: reject (reviewing → assigned) ────────────────────────────────────

class RejectRequest(BaseModel):
    reason: str


@router.post("/orders/{order_id}/reject", response_model=OrderOut)
def reject_submission(
    order_id: str,
    body: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    _: None = Depends(_require_commission),
) -> OrderOut:
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    if order.status != OrderStatus.reviewing:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": "order is not in reviewing state"})
    order.status = OrderStatus.assigned
    order.updated_at = func.now()
    db.add(OrderMessage(
        order_id=parsed,
        sender_id=current_user.id,
        content=body.reason,
        kind=OrderMessageKind.rejection,
    ))
    _add_status_message(db, parsed, current_user.id, "assigned (差し戻し)")
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Admin: done (reviewing → done) ──────────────────────────────────────────

@router.post("/orders/{order_id}/done", response_model=OrderOut)
def mark_done(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    _: None = Depends(_require_commission),
) -> OrderOut:
    parsed = _parse_uuid(order_id)
    order = db.execute(select(Order).where(Order.id == parsed).with_for_update()).scalar_one_or_none()
    _check_order_exists(order)
    if order.status != OrderStatus.reviewing:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": "order is not in reviewing state"})

    # Find latest submission attachment
    latest_submission = db.execute(
        select(OrderMessage)
        .where(
            OrderMessage.order_id == parsed,
            OrderMessage.kind == OrderMessageKind.submission,
            OrderMessage.attachment_path.isnot(None),
        )
        .order_by(OrderMessage.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest_submission is None or not Path(latest_submission.attachment_path).exists():
        raise HTTPException(status_code=409, detail={"code": "NO_SUBMISSION_FILE", "message": "no submitted file found"})

    # Copy submission to final path (改訂2.2: token 消費 / payout 生成は close 時に移動)
    final_dir = Path(settings.ORDERS_DIR)
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / f"{parsed}.wav"
    shutil.copy2(latest_submission.attachment_path, final_path)

    order.status = OrderStatus.done
    order.file_path = str(final_path)
    order.done_by_admin_id = current_user.id
    order.done_at = func.now()
    order.notified_at = func.now()
    order.updated_at = func.now()

    db.add(OrderMessage(
        order_id=parsed,
        sender_id=current_user.id,
        content="発注完了しました。音源をダウンロードできます。",
        kind=OrderMessageKind.done,
    ))
    db.commit()
    return _to_order_out(_load_order(db, parsed))


# ─── Admin: settings ──────────────────────────────────────────────────────────

@router.get("/admin/settings")
def get_settings_api(
    db: Session = Depends(get_db),
    _cu: User = Depends(require_role("admin")),
) -> list[dict]:
    rows = db.execute(select(SystemSetting)).scalars().all()
    return [{"key": r.key, "value": r.value, "description": r.description} for r in rows]


class UpdateSettingRequest(BaseModel):
    value: str


@router.patch("/admin/settings/{key}")
def update_setting(
    key: str,
    body: UpdateSettingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> dict:
    setting = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if setting is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "setting not found"})
    setting.value = body.value
    setting.updated_by_admin_id = current_user.id
    setting.updated_at = func.now()
    db.commit()
    return {"key": setting.key, "value": setting.value}


# ─── Util ──────────────────────────────────────────────────────────────────────

def _parse_uuid(s: str) -> uuid.UUID:
    try:
        return uuid.UUID(s)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})


def _check_order_exists(order: Order | None) -> None:
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "order not found"})
