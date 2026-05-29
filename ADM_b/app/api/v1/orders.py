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
    CreatorPayout,
    CreatorProfile,
    CreatorRankPrice,
    Order,
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
    verify_order_download,
)
from app.services import tokens as tokens_service

settings = get_settings()
router = APIRouter(tags=["orders"])


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
    description: str | None
    brief: dict | None
    token_cost: int
    status: str
    user_id: str
    user_name: str
    assigned_creator_id: str | None
    assigned_creator_name: str | None
    candidates: list[CandidateOut] = []
    messages: list[MessageOut] = []
    file_path: str | None
    notified_at: Any
    created_at: Any
    updated_at: Any

class OrderListItem(BaseModel):
    id: str
    title: str
    token_cost: int
    status: str
    user_name: str
    assigned_creator_name: str | None
    notified_at: Any
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
        description=order.description,
        brief=order.brief,
        token_cost=order.token_cost,
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
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _to_list_item(order: Order) -> OrderListItem:
    return OrderListItem(
        id=str(order.id),
        title=order.title,
        token_cost=order.token_cost,
        status=order.status.value,
        user_name=order.user.username,
        assigned_creator_name=(
            order.assigned_creator.display_name if order.assigned_creator else None
        ),
        notified_at=order.notified_at,
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


# ─── Unread / action-required count (per role) ────────────────────────────────

@router.get("/me/commission/unread")
def commission_unread(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return count of Commission items that require the current user's action."""
    role = current_user.role.value

    if role == "user":
        # Orders submitted by this user that are awaiting their review/approval
        q = select(func.count()).select_from(Order).where(
            Order.user_id == current_user.id,
            Order.status.in_([OrderStatus.reviewing]),
        )
    elif role == "creator":
        # Nominations sent to this creator that haven't been answered yet
        q = select(func.count()).select_from(OrderCandidateCreator).where(
            OrderCandidateCreator.creator_id == current_user.id,
            OrderCandidateCreator.response_status == CandidateResponseStatus.pending,
        )
    else:  # admin
        # Orders waiting for admin action (nominate creators or mark done/reject)
        q = select(func.count()).select_from(Order).where(
            Order.status.in_([OrderStatus.open, OrderStatus.reviewing]),
        )

    count = db.execute(q).scalar_one()
    return {"count": int(count)}


# ─── Orders list ──────────────────────────────────────────────────────────────

@router.get("/orders", response_model=list[OrderListItem])
def list_orders(
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
        q = base.where(Order.user_id == current_user.id)
    elif role == "creator":
        # orders where this creator is a candidate or assigned
        candidate_order_ids = select(OrderCandidateCreator.order_id).where(
            OrderCandidateCreator.creator_id == current_user.id
        )
        q = base.where(
            (Order.assigned_creator_id == current_user.id) |
            Order.id.in_(candidate_order_ids)
        )
    else:  # admin
        q = base

    rows = db.execute(q.order_by(Order.updated_at.desc())).unique().scalars().all()
    return [_to_list_item(o) for o in rows]


# ─── Create order ─────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    title: str
    description: str | None = None
    brief: dict | None = None
    token_cost: int


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    body: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(_require_commission),
) -> OrderOut:
    if body.token_cost <= 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_TOKEN_COST", "message": "token_cost must be > 0"},
        )
    order = Order(
        user_id=current_user.id,
        title=body.title,
        description=body.description,
        brief=body.brief,
        token_cost=body.token_cost,
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
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "not your order"})
    if order.status != OrderStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"expected draft, got {order.status.value}"})

    # Token balance check (reservation, not consumption yet)
    lic = current_user.license
    if lic is None:
        raise HTTPException(status_code=403, detail={"code": "NO_LICENSE", "message": "no license"})
    available = tokens_service.available_tokens(db, current_user.id, lic)
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

    # Copy submission to final path
    final_dir = Path(settings.ORDERS_DIR)
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / f"{parsed}.wav"
    shutil.copy2(latest_submission.attachment_path, final_path)

    # Token consumption
    user = db.execute(select(User).where(User.id == order.user_id)).scalar_one()
    lic = user.license
    if lic is None:
        raise HTTPException(status_code=422, detail={"code": "NO_LICENSE", "message": "user has no license"})
    period = tokens_service.current_period_jst()
    db.add(TokenConsumption(
        user_id=order.user_id,
        audio_id=None,  # no audio_id for orders
        license_id=lic.id,
        tokens=order.token_cost,
        period_yyyymm=period,
    ))

    # Creator payout
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
