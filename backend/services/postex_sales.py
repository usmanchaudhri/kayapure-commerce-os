"""PostEx sales aggregation helpers (from persisted postex_orders)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.schemas import PostExOrder


def _as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def settled_amount_for_row(order: PostExOrder) -> float:
    """Amount counted as settled for one order row."""
    if not order.settle:
        return 0.0
    upfront = _as_float(order.upfront_payment)
    reserve = _as_float(order.reserve_payment)
    total = upfront + reserve
    if total > 0:
        return total
    return _as_float(order.invoice_payment)


def sales_summary(
    db: Session,
    *,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
) -> dict[str, Any]:
    """Consolidate gross / delivered / settled totals from postex_orders."""
    q = db.query(PostExOrder)
    if from_dt is not None:
        q = q.filter(
            PostExOrder.transaction_date.isnot(None),
            PostExOrder.transaction_date >= from_dt,
        )
    if to_dt is not None:
        q = q.filter(
            PostExOrder.transaction_date.isnot(None),
            PostExOrder.transaction_date <= to_dt,
        )

    orders = q.all()
    order_count = len(orders)
    gross_cod = 0.0
    delivered_cod = 0.0
    settled_amount = 0.0
    unsettled_delivered = 0.0
    delivered_count = 0
    settled_count = 0

    for order in orders:
        inv = _as_float(order.invoice_payment)
        gross_cod += inv
        status = (order.transaction_status or "").strip().lower()
        is_delivered = status == "delivered"
        if is_delivered:
            delivered_count += 1
            delivered_cod += inv
            if order.settle:
                settled_count += 1
                settled_amount += settled_amount_for_row(order)
            else:
                unsettled_delivered += inv
        elif order.settle:
            settled_count += 1
            settled_amount += settled_amount_for_row(order)

    return {
        "order_count": order_count,
        "delivered_count": delivered_count,
        "settled_count": settled_count,
        "gross_cod": round(gross_cod, 2),
        "delivered_cod": round(delivered_cod, 2),
        "settled_amount": round(settled_amount, 2),
        "unsettled_delivered": round(unsettled_delivered, 2),
        "from": from_dt.isoformat() if from_dt else None,
        "to": to_dt.isoformat() if to_dt else None,
    }
