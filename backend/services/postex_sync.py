"""PostEx order backfill + incremental sync into Postgres."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from config import settings
from models.schemas import PostExCprReceipt, PostExOrder, PostExSyncState

logger = logging.getLogger(__name__)

SYNC_STATE_ID = 1


def _parse_date(value: str | date | datetime | None) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    # PostEx: 2026-09-18T05:29:51.000+0500
    cleaned = text.replace("Z", "+00:00")
    if len(cleaned) >= 5 and (cleaned[-5] in "+-") and cleaned[-3] != ":":
        cleaned = cleaned[:-2] + ":" + cleaned[-2:]
    try:
        return datetime.fromisoformat(cleaned)
    except Exception:
        d = _parse_date(text)
        if d:
            return datetime(d.year, d.month, d.day)
        return None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def get_or_create_sync_state(db: Session) -> PostExSyncState:
    state = db.query(PostExSyncState).filter(PostExSyncState.id == SYNC_STATE_ID).first()
    if state:
        return state
    since = _parse_date(settings.POSTEX_SYNC_SINCE) or date(2024, 1, 1)
    state = PostExSyncState(
        id=SYNC_STATE_ID,
        backfill_complete=False,
        backfill_cursor_date=since.isoformat(),
        status="idle",
        orders_upserted=0,
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def sync_state_dict(state: PostExSyncState) -> dict[str, Any]:
    return {
        "id": state.id,
        "backfill_complete": bool(state.backfill_complete),
        "backfill_cursor_date": state.backfill_cursor_date,
        "last_incremental_at": (
            state.last_incremental_at.isoformat() if state.last_incremental_at else None
        ),
        "last_error": state.last_error,
        "orders_upserted": int(state.orders_upserted or 0),
        "status": state.status,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        "sync_since": settings.POSTEX_SYNC_SINCE,
        "lookback_days": settings.POSTEX_SYNC_LOOKBACK_DAYS,
        "chunk_days": settings.POSTEX_SYNC_CHUNK_DAYS,
    }


def upsert_order_from_api(db: Session, payload: dict[str, Any]) -> PostExOrder:
    tn = str(payload.get("trackingNumber") or "").strip()
    if not tn:
        raise ValueError("trackingNumber required")

    row = db.query(PostExOrder).filter(PostExOrder.tracking_number == tn).first()
    created = False
    if not row:
        row = PostExOrder(tracking_number=tn)
        db.add(row)
        created = True

    row.order_ref_number = str(payload.get("orderRefNumber") or "")[:255]
    row.transaction_status = str(payload.get("transactionStatus") or "")[:100]
    row.transaction_date = _parse_datetime(payload.get("transactionDate"))
    row.order_delivery_date = _parse_datetime(payload.get("orderDeliveryDate"))
    row.order_pickup_date = _parse_datetime(payload.get("orderPickupDate"))

    row.invoice_payment = _as_float(payload.get("invoicePayment"))
    # Prefer existing settlement payment fields from list/track; Payment Status may overwrite
    if payload.get("upfrontPayment") is not None:
        row.upfront_payment = _as_float(payload.get("upfrontPayment"))
    if payload.get("reservePayment") is not None:
        row.reserve_payment = _as_float(payload.get("reservePayment"))
    if payload.get("balancePayment") is not None:
        row.balance_payment = _as_float(payload.get("balancePayment"))
    row.transaction_fee = _as_float(payload.get("transactionFee"))
    row.transaction_tax = _as_float(payload.get("transactionTax"))

    if "settle" in payload:
        row.settle = _as_bool(payload.get("settle"))
    if payload.get("settlementDate"):
        row.settlement_date = _parse_datetime(payload.get("settlementDate"))
    if payload.get("cpr1") or payload.get("cprNumber_1"):
        row.cpr1 = str(payload.get("cpr1") or payload.get("cprNumber_1") or "")[:100]
    if payload.get("cpr1Date") or payload.get("upfrontPaymentDate"):
        row.cpr1_date = _parse_datetime(
            payload.get("cpr1Date") or payload.get("upfrontPaymentDate")
        )
    if payload.get("cpr2") or payload.get("cprNumber_2"):
        row.cpr2 = str(payload.get("cpr2") or payload.get("cprNumber_2") or "")[:100]
    if payload.get("cpr2Date") or payload.get("reservePaymentDate"):
        row.cpr2_date = _parse_datetime(
            payload.get("cpr2Date") or payload.get("reservePaymentDate")
        )

    row.customer_name = str(payload.get("customerName") or "")[:255] or None
    row.customer_phone = str(payload.get("customerPhone") or "")[:50] or None
    row.city_name = str(payload.get("cityName") or "")[:100] or None
    row.merchant_name = str(payload.get("merchantName") or "")[:255] or None
    try:
        items = payload.get("items")
        row.items = int(items) if items is not None and str(items).strip() != "" else None
    except Exception:
        row.items = None

    # Merge raw payload
    existing_raw = dict(row.raw_json or {}) if not created else {}
    existing_raw.update({k: v for k, v in payload.items() if not isinstance(v, (dict, list)) or k == "transactionStatusHistory"})
    # Keep history if present
    if isinstance(payload.get("transactionStatusHistory"), list):
        existing_raw["transactionStatusHistory"] = payload.get("transactionStatusHistory")
    row.raw_json = existing_raw
    row.synced_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    return row


def upsert_cpr(
    db: Session,
    *,
    cpr_number: str,
    tracking_number: str,
    cpr_type: str,
    payment_date: Optional[datetime],
) -> None:
    cpr_number = (cpr_number or "").strip()
    tracking_number = (tracking_number or "").strip()
    if not cpr_number or not tracking_number:
        return
    row = (
        db.query(PostExCprReceipt)
        .filter(
            PostExCprReceipt.cpr_number == cpr_number,
            PostExCprReceipt.tracking_number == tracking_number,
        )
        .first()
    )
    if not row:
        row = PostExCprReceipt(
            cpr_number=cpr_number,
            tracking_number=tracking_number,
        )
        db.add(row)
    row.cpr_type = (cpr_type or "")[:40]
    if payment_date:
        row.payment_date = payment_date
    row.updated_at = datetime.utcnow()


def apply_payment_status(db: Session, tracking_number: str, status: dict[str, Any]) -> None:
    tn = tracking_number.strip()
    row = db.query(PostExOrder).filter(PostExOrder.tracking_number == tn).first()
    if not row:
        row = upsert_order_from_api(
            db,
            {
                "trackingNumber": tn,
                **{k: status.get(k) for k in status.keys()},
            },
        )

    settle = _as_bool(status.get("settle"))
    if settle is not None:
        row.settle = settle
    if status.get("settlementDate"):
        row.settlement_date = _parse_datetime(status.get("settlementDate"))

    if status.get("upfrontPayment") is not None:
        row.upfront_payment = _as_float(status.get("upfrontPayment"))
    if status.get("reservePayment") is not None:
        row.reserve_payment = _as_float(status.get("reservePayment"))
    if status.get("invoicePayment") is not None:
        row.invoice_payment = _as_float(status.get("invoicePayment"))

    cpr1 = str(status.get("cpr1") or status.get("cprNumber_1") or "").strip()
    cpr1_date = _parse_datetime(status.get("cpr1Date") or status.get("upfrontPaymentDate"))
    cpr2 = str(status.get("cpr2") or status.get("cprNumber_2") or "").strip()
    cpr2_date = _parse_datetime(status.get("cpr2Date") or status.get("reservePaymentDate"))

    if cpr1:
        row.cpr1 = cpr1[:100]
        row.cpr1_date = cpr1_date
        # Upfront CPR implies upfront settlement timing; amount may already be on order
        upsert_cpr(
            db,
            cpr_number=cpr1,
            tracking_number=tn,
            cpr_type="Upfront",
            payment_date=cpr1_date,
        )
    if cpr2:
        row.cpr2 = cpr2[:100]
        row.cpr2_date = cpr2_date
        upsert_cpr(
            db,
            cpr_number=cpr2,
            tracking_number=tn,
            cpr_type="Reserve",
            payment_date=cpr2_date,
        )

    # If settled and payment amounts missing, treat invoice as settled reserve
    if row.settle and _as_float(row.upfront_payment) + _as_float(row.reserve_payment) <= 0:
        inv = _as_float(row.invoice_payment)
        if inv > 0:
            row.reserve_payment = inv

    raw = dict(row.raw_json or {})
    raw["paymentStatus"] = {
        k: status.get(k)
        for k in (
            "settle",
            "settlementDate",
            "cpr1",
            "cpr1Date",
            "cpr2",
            "cpr2Date",
            "orderRefNumber",
        )
    }
    row.raw_json = raw
    row.synced_at = datetime.utcnow()


class PostExSyncService:
    """Chunked backfill + incremental lookback sync for PostEx orders."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    def _client(self):
        import sys
        from pathlib import Path

        # shiny_app lives next to backend/
        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from shiny_app.lib.postex_client import get_configured_client

        return get_configured_client()

    async def run(
        self,
        db: Session,
        *,
        mode: str = "auto",
        max_chunks: Optional[int] = None,
        enrich_payments: bool = True,
    ) -> dict[str, Any]:
        """Run backfill and/or incremental sync. Returns sync state dict."""
        if self._lock.locked():
            state = get_or_create_sync_state(db)
            return {
                **sync_state_dict(state),
                "message": "Sync already running",
                "orders_this_run": 0,
                "chunks_this_run": 0,
            }

        async with self._lock:
            # Lock is the concurrency guard; always proceed after acquire so a
            # pre-marked status=running (API) or crashed leftover does not skip work.
            state = get_or_create_sync_state(db)
            state.status = "running"
            state.last_error = None
            db.commit()

            orders_this_run = 0
            chunks_this_run = 0
            try:
                client = self._client()
                mode_l = (mode or "auto").strip().lower()
                if mode_l == "auto":
                    if not state.backfill_complete:
                        orders_this_run, chunks_this_run = await self._backfill(
                            db, client, state, max_chunks=max_chunks
                        )
                    else:
                        orders_this_run, chunks_this_run = await self._incremental(
                            db, client, state, enrich_payments=enrich_payments
                        )
                elif mode_l == "backfill":
                    state.backfill_complete = False
                    if not state.backfill_cursor_date:
                        since = _parse_date(settings.POSTEX_SYNC_SINCE) or date(2024, 1, 1)
                        state.backfill_cursor_date = since.isoformat()
                    db.commit()
                    orders_this_run, chunks_this_run = await self._backfill(
                        db, client, state, max_chunks=max_chunks
                    )
                elif mode_l == "incremental":
                    orders_this_run, chunks_this_run = await self._incremental(
                        db, client, state, enrich_payments=enrich_payments
                    )
                else:
                    raise ValueError(f"Unknown sync mode: {mode}")

                state.status = "idle"
                db.commit()
            except Exception as exc:
                logger.exception("PostEx sync failed: %s", exc)
                state = get_or_create_sync_state(db)
                state.status = "error"
                state.last_error = str(exc)[:2000]
                db.commit()
                raise

            db.refresh(state)
            return {
                **sync_state_dict(state),
                "orders_this_run": orders_this_run,
                "chunks_this_run": chunks_this_run,
            }

    async def _backfill(
        self,
        db: Session,
        client: Any,
        state: PostExSyncState,
        *,
        max_chunks: Optional[int] = None,
    ) -> tuple[int, int]:
        chunk_days = max(1, int(settings.POSTEX_SYNC_CHUNK_DAYS or 14))
        today = date.today()
        cursor = _parse_date(state.backfill_cursor_date) or (
            _parse_date(settings.POSTEX_SYNC_SINCE) or date(2024, 1, 1)
        )
        chunks_done = 0
        trackings_this_run: list[str] = []
        empty_streak = 0

        while cursor <= today:
            if max_chunks is not None and chunks_done >= max_chunks:
                break
            # Speed through empty history: widen window after consecutive empty chunks
            effective_days = chunk_days
            if empty_streak >= 2:
                effective_days = min(60, chunk_days * 4)
            end = min(cursor + timedelta(days=effective_days - 1), today)
            logger.info("PostEx backfill chunk %s → %s", cursor.isoformat(), end.isoformat())
            orders = await client.list_orders(
                order_status_id=0,
                from_date=cursor.isoformat(),
                to_date=end.isoformat(),
            )
            chunk_count = 0
            for order in orders:
                if not isinstance(order, dict):
                    continue
                tn = str(order.get("trackingNumber") or "").strip()
                if not tn:
                    continue
                upsert_order_from_api(db, order)
                trackings_this_run.append(tn)
                state.orders_upserted = int(state.orders_upserted or 0) + 1
                chunk_count += 1

            empty_streak = empty_streak + 1 if chunk_count == 0 else 0

            # Next chunk starts day after end
            cursor = end + timedelta(days=1)
            state.backfill_cursor_date = cursor.isoformat()
            db.commit()
            chunks_done += 1

        if cursor > today:
            state.backfill_complete = True
            state.backfill_cursor_date = today.isoformat()
            db.commit()

        if trackings_this_run:
            await self._enrich_payments(db, client, list(dict.fromkeys(trackings_this_run)))

        return len(trackings_this_run), chunks_done

    async def _incremental(
        self,
        db: Session,
        client: Any,
        state: PostExSyncState,
        *,
        enrich_payments: bool = True,
    ) -> tuple[int, int]:
        lookback = max(1, int(settings.POSTEX_SYNC_LOOKBACK_DAYS or 30))
        today = date.today()
        start = today - timedelta(days=lookback)
        logger.info(
            "PostEx incremental sync %s → %s", start.isoformat(), today.isoformat()
        )
        # Walk lookback in chunks to avoid huge windows
        chunk_days = max(1, int(settings.POSTEX_SYNC_CHUNK_DAYS or 14))
        cursor = start
        trackings: list[str] = []
        chunks_done = 0
        while cursor <= today:
            end = min(cursor + timedelta(days=chunk_days - 1), today)
            orders = await client.list_orders(
                order_status_id=0,
                from_date=cursor.isoformat(),
                to_date=end.isoformat(),
            )
            for order in orders:
                if not isinstance(order, dict):
                    continue
                tn = str(order.get("trackingNumber") or "").strip()
                if not tn:
                    continue
                upsert_order_from_api(db, order)
                trackings.append(tn)
                state.orders_upserted = int(state.orders_upserted or 0) + 1
            cursor = end + timedelta(days=1)
            db.commit()
            chunks_done += 1

        state.last_incremental_at = datetime.utcnow()
        db.commit()

        if enrich_payments and trackings:
            await self._enrich_payments(db, client, list(dict.fromkeys(trackings)))

        return len(trackings), chunks_done

    async def _enrich_payments(
        self,
        db: Session,
        client: Any,
        tracking_numbers: list[str],
        *,
        concurrency: int = 6,
    ) -> None:
        """Refresh Payment Status for delivered / unsettled trackings."""
        if not tracking_numbers:
            return

        # Prefer delivered or unsettle-unknown rows
        candidates: list[str] = []
        for tn in tracking_numbers:
            row = db.query(PostExOrder).filter(PostExOrder.tracking_number == tn).first()
            if not row:
                candidates.append(tn)
                continue
            status = (row.transaction_status or "").lower()
            if status == "delivered" or row.settle is not True:
                candidates.append(tn)

        if not candidates:
            return

        sem = asyncio.Semaphore(max(1, concurrency))
        errors = 0

        async def _one(tn: str) -> None:
            nonlocal errors
            async with sem:
                try:
                    status = await client.get_payment_status(tn)
                    apply_payment_status(db, tn, status)
                except Exception as exc:
                    errors += 1
                    msg = str(exc).lower()
                    if "404" not in msg and "not found" not in msg:
                        logger.warning("Payment status enrich failed for %s: %s", tn, exc)

        # Process in batches to commit periodically
        batch_size = 40
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            await asyncio.gather(*[_one(tn) for tn in batch])
            db.commit()

        if errors:
            logger.info("Payment enrich finished with %s non-fatal errors", errors)


postex_sync_service = PostExSyncService()
