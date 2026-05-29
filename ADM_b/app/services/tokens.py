"""Monthly token quota calculation (JST month boundary)."""
from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import License, Order, OrderStatus, TokenConsumption, TokenGrant


def current_period_jst() -> int:
    """Return current period as integer YYYYMM in JST."""
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    return now.year * 100 + now.month


def reserved_by_open_orders(db: Session, user_id: uuid.UUID) -> int:
    """改訂2.2: 受け取り (close) 前の Commission Order が「予約」している token 数。

    submit 直後から受け取るまで token は予約状態となり、
    新しい発注や音源 DL に使えなくなる (overdraft 防止)。
    cancel された order は予約から外れる。
    """
    return int(db.execute(
        select(func.coalesce(func.sum(Order.token_cost), 0)).where(
            Order.user_id == user_id,
            Order.status.in_([
                OrderStatus.open, OrderStatus.recruiting,
                OrderStatus.assigned, OrderStatus.reviewing, OrderStatus.done,
            ]),
            Order.closed_at.is_(None),
        )
    ).scalar_one())


def available_tokens(db: Session, user_id: uuid.UUID, license_obj: License) -> int:
    """Available = quota + grants − consumed − **reserved by open orders** (current JST month).

    改訂2.2: 進行中の Order が予約している token を差し引く。
    submit 時点で残量チェックが意味を持つ (Order時点で出来ない仕様)。
    """
    period = current_period_jst()
    granted_extra: int = db.execute(
        select(func.coalesce(func.sum(TokenGrant.tokens), 0)).where(
            TokenGrant.user_id == user_id, TokenGrant.period_yyyymm == period
        )
    ).scalar_one()
    consumed: int = db.execute(
        select(func.coalesce(func.sum(TokenConsumption.tokens), 0)).where(
            TokenConsumption.user_id == user_id, TokenConsumption.period_yyyymm == period
        )
    ).scalar_one()
    reserved = reserved_by_open_orders(db, user_id)
    return int(license_obj.monthly_quota_tokens) + int(granted_extra) - int(consumed) - int(reserved)
