"""PostEx shipping tab — create, track, list, CPR receipts, airway bill, load sheet."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.handlers.growth_feature_common import error_block, loading_block
from shiny_app.lib.postex_client import (
    PostExError,
    cpr_detail_fields,
    get_configured_client,
    save_cpr_pdf,
    save_postex_pdf,
)

POSTEX_TRACKING_URL = "https://postex.pk/tracking"


def _postex_web_url(tracking_number: str) -> str:
    from urllib.parse import quote

    tn = (tracking_number or "").strip()
    return f"{POSTEX_TRACKING_URL}?trackingNumber={quote(tn, safe='')}"


def _postex_link(tracking_number: str, label: str | None = None) -> ui.Tag:
    tn = (tracking_number or "").strip()
    if not tn:
        return ui.span("—")
    text = label or "Open on PostEx"
    return ui.tags.a(
        text,
        href=_postex_web_url(tn),
        target="_blank",
        rel="noopener noreferrer",
        class_="postex-ext-link",
    )


def _safe_str(input: Inputs, name: str, default: str = "") -> str:
    try:
        val = getattr(input, name)()
    except Exception:
        return default
    if val is None:
        return default
    return str(val).strip()


def _safe_int(input: Inputs, name: str, default: int) -> int:
    try:
        val = getattr(input, name)()
    except Exception:
        return default
    try:
        return int(val)
    except Exception:
        return default


def _parse_tracking_list(raw: str) -> list[str]:
    parts: list[str] = []
    for chunk in (raw or "").replace("\n", ",").split(","):
        t = chunk.strip()
        if t:
            parts.append(t)
    return parts


def _fmt_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text


def _fmt_display_datetime(value: Any) -> str:
    """Shorten PostEx ISO timestamps (e.g. 2026-08-25T10:49:07.000+0500) for tables."""
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    if "T" in text:
        date_part, _, rest = text.partition("T")
        time_part = rest[:8] if len(rest) >= 8 else rest.split("+")[0].split(".")[0]
        return f"{date_part} {time_part}".strip()
    return text


def _kv_table(data: dict[str, Any], keys: list[str] | None = None) -> ui.Tag:
    preferred = keys or list(data.keys())
    rows = []
    for key in preferred:
        if key not in data:
            continue
        val = data.get(key)
        if isinstance(val, (dict, list)):
            continue
        rows.append(
            ui.tags.tr(
                ui.tags.th(str(key)),
                ui.tags.td("" if val is None else str(val)),
            )
        )
    if not rows:
        return ui.div("No fields to display.", class_="gf-card-sub")
    return ui.div(
        ui.tags.table(ui.tags.tbody(*rows)),
        class_="table-scroll-wrap postex-kv-table",
    )


def _orders_table(rows: list[dict[str, Any]]) -> ui.Tag:
    if not rows:
        return ui.div("No orders found for this range.", class_="gf-card-sub")

    columns = [
        "trackingNumber",
        "orderRefNumber",
        "customerName",
        "customerPhone",
        "cityName",
        "invoicePayment",
        "transactionStatus",
        "transactionDate",
        "items",
    ]
    present = []
    for col in columns:
        if any(col in row for row in rows):
            present.append(col)

    header_cells = [ui.tags.th(c) for c in present]
    header_cells.append(ui.tags.th("PostEx"))
    header = ui.tags.tr(*header_cells)
    body = []
    for row in rows[:200]:
        cells = [ui.tags.td("" if row.get(c) is None else str(row.get(c))) for c in present]
        tracking = str(row.get("trackingNumber") or "").strip()
        cells.append(ui.tags.td(_postex_link(tracking, "View")))
        body.append(ui.tags.tr(*cells))

    return ui.div(
        ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body)),
        class_="table-scroll-wrap postex-orders-table",
    )


def _cpr_accordion(rows: list[dict[str, Any]]) -> ui.Tag:
    if not rows:
        return ui.div(
            "No Cash Payment Receipts found for this range "
            "(orders without CPR numbers are omitted).",
            class_="gf-card-sub",
        )

    from shiny_app.lib.cpr_document import fmt_cpr_date, money

    items: list[ui.Tag] = []
    for idx, row in enumerate(rows[:500]):
        cpr_number = str(row.get("cprNumber") or "").strip() or f"CPR-{idx}"
        cpr_date = fmt_cpr_date(row.get("cprDate") or row.get("paymentDate"))
        net = money(row.get("netAmount") or (row.get("totals") or {}).get("netTotal"))
        order_count = len(row.get("orders") or [])
        merchant = str(row.get("merchantName") or "").strip()
        settled = row.get("settle")
        settled_text = (
            "Settled"
            if settled in (True, "true", "True", 1, "1")
            else "Unsettled"
            if settled is not None
            else ""
        )
        summary_bits = [b for b in [cpr_number, cpr_date, merchant, f"Net {net}", f"{order_count} order(s)", settled_text] if b]

        # Header fields
        meta_rows = []
        for label, value in cpr_detail_fields(row):
            meta_rows.append(
                ui.tags.tr(ui.tags.th(label), ui.tags.td(value))
            )

        # Summary table (portal style)
        summary_body = []
        for srow in row.get("summaryRows") or []:
            payable = money(srow.get("payableAmount"))
            if srow.get("payableParen"):
                payable = f"({payable})"
            summary_body.append(
                ui.tags.tr(
                    ui.tags.td(str(srow.get("details") or "")),
                    ui.tags.td(str(int(float(srow.get("count") or 0)))),
                    ui.tags.td(money(srow.get("codAmount"))),
                    ui.tags.td(payable),
                )
            )
        totals = row.get("totals") or {}
        totals_block = ui.div(
            ui.tags.table(
                ui.tags.thead(
                    ui.tags.tr(
                        ui.tags.th("Details"),
                        ui.tags.th("Count"),
                        ui.tags.th("COD Amount"),
                        ui.tags.th("Payable Amount"),
                    )
                ),
                ui.tags.tbody(*summary_body),
            ),
            ui.div(
                ui.div(f"Total COD: {money(totals.get('codTotal'))}"),
                ui.div(
                    f"Shipping Charges ({int(float(totals.get('shippingChargesCount') or 0))}): "
                    f"({money(totals.get('shippingCharges'))})"
                ),
                ui.div(f"GST: ({money(totals.get('gst'))})"),
                ui.div(f"WH Income Tax (2%): ({money(totals.get('whIncomeTax'))})"),
                ui.div(f"WH Sales Tax (2%): ({money(totals.get('whSalesTax'))})"),
                ui.div(f"Net Total: {money(totals.get('netTotal'))}", class_="postex-cpr-net"),
                class_="postex-cpr-totals",
            ),
            class_="table-scroll-wrap postex-orders-table",
        )

        # Orders table
        order_rows = []
        for i, line in enumerate(row.get("orders") or [], start=1):
            weight = line.get("weightKg")
            track = str(line.get("trackingNumber") or "")
            if weight:
                track = f"{track} ({float(weight):.2f} kg)"
            order_rows.append(
                ui.tags.tr(
                    ui.tags.td(str(i)),
                    ui.tags.td(track),
                    ui.tags.td(str(line.get("originCity") or "")),
                    ui.tags.td(str(line.get("destinationCity") or "")),
                    ui.tags.td(str(line.get("status") or "")),
                    ui.tags.td(money(line.get("shippingCharges"))),
                    ui.tags.td(money(line.get("codAmount"))),
                    ui.tags.td(money(line.get("reserveAmount"))),
                    ui.tags.td(money(line.get("gst"))),
                    ui.tags.td(money(line.get("whIncomeTax"))),
                    ui.tags.td(money(line.get("whSalesTax"))),
                    ui.tags.td(money(line.get("netAmount"))),
                )
            )
        orders_table = ui.div(
            ui.tags.table(
                ui.tags.thead(
                    ui.tags.tr(
                        ui.tags.th("SR."),
                        ui.tags.th("Tracking"),
                        ui.tags.th("Origin"),
                        ui.tags.th("Destination"),
                        ui.tags.th("Status"),
                        ui.tags.th("Shipping"),
                        ui.tags.th("COD"),
                        ui.tags.th("Reserve"),
                        ui.tags.th("GST"),
                        ui.tags.th("WH Inc."),
                        ui.tags.th("WH Sales"),
                        ui.tags.th("Net"),
                    )
                ),
                ui.tags.tbody(*order_rows),
            ),
            class_="table-scroll-wrap postex-orders-table",
        )

        tracking = str(row.get("trackingNumber") or "").strip()
        download_btn = ui.tags.button(
            "Download CPR PDF",
            type="button",
            class_="btn-download-pdf postex-cpr-pdf-btn",
            onclick=(
                "Shiny.setInputValue('postex_cpr_pdf', "
                f"'{idx}', {{priority: 'event'}});"
            ),
        )
        actions = ui.div(
            download_btn,
            _postex_link(tracking, "Track on PostEx") if tracking else ui.span(),
            class_="postex-cpr-actions",
        )

        items.append(
            ui.tags.details(
                ui.tags.summary(
                    ui.span(" · ".join(summary_bits), class_="postex-cpr-summary-text"),
                    class_="postex-cpr-summary",
                ),
                ui.div(
                    ui.div("Receipt", class_="gf-card-title"),
                    ui.div(
                        ui.tags.table(ui.tags.tbody(*meta_rows)),
                        class_="table-scroll-wrap postex-kv-table",
                    ),
                    ui.div("Summary", class_="gf-card-title"),
                    totals_block,
                    ui.div("Orders", class_="gf-card-title"),
                    orders_table,
                    actions,
                    class_="postex-cpr-panel",
                ),
                class_="postex-cpr-item",
            )
        )

    return ui.div(*items, class_="postex-cpr-list")


def _history_list(history: Any) -> ui.Tag:
    if not isinstance(history, list) or not history:
        return ui.div()
    items = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        msg = entry.get("transactionStatusMessage") or ""
        code = entry.get("transactionStatusMessageCode") or ""
        label = f"{code} — {msg}" if code else str(msg)
        items.append(ui.tags.li(label))
    if not items:
        return ui.div()
    return ui.div(
        ui.div("Status history", class_="gf-card-title"),
        ui.tags.ul(*items, class_="postex-history"),
        class_="gf-card postex-card",
    )


def _fmt_pkr(amount: Any) -> str:
    try:
        val = float(amount or 0)
    except (TypeError, ValueError):
        val = 0.0
    return f"PKR {val:,.0f}"


def _sales_kpi_cards(summary: dict[str, Any]) -> ui.Tag:
    cards = [
        ("Gross COD", summary.get("gross_cod"), f"{summary.get('order_count', 0)} orders"),
        (
            "Delivered COD",
            summary.get("delivered_cod"),
            f"{summary.get('delivered_count', 0)} delivered",
        ),
        (
            "Settled",
            summary.get("settled_amount"),
            f"{summary.get('settled_count', 0)} settled",
        ),
        (
            "Unsettled delivered",
            summary.get("unsettled_delivered"),
            "Delivered, not settled",
        ),
        ("Order count", summary.get("order_count"), "In selected range"),
    ]
    kpi_row = [
        ui.div(
            ui.div(label, class_="gf-kpi-label"),
            ui.div(
                _fmt_pkr(val) if label != "Order count" else str(int(val or 0)),
                class_="gf-kpi-value",
            ),
            ui.div(sub, class_="gf-kpi-sub"),
            class_="gf-kpi-card",
        )
        for label, val, sub in cards
    ]
    return ui.div(*kpi_row, class_="gf-kpi-grid")


def _db_orders_table(rows: list[dict[str, Any]]) -> ui.Tag:
    if not rows:
        return ui.div("No synced orders in the database yet.", class_="gf-card-sub")
    header = ui.tags.tr(
        ui.tags.th("Tracking"),
        ui.tags.th("Status"),
        ui.tags.th("Date"),
        ui.tags.th("Invoice"),
        ui.tags.th("Settle"),
        ui.tags.th("City"),
        ui.tags.th("PostEx"),
    )
    body = []
    for row in rows[:100]:
        tn = str(row.get("tracking_number") or "")
        body.append(
            ui.tags.tr(
                ui.tags.td(tn),
                ui.tags.td(str(row.get("transaction_status") or "")),
                ui.tags.td(_fmt_display_datetime(row.get("transaction_date"))),
                ui.tags.td(_fmt_pkr(row.get("invoice_payment"))),
                ui.tags.td("Yes" if row.get("settle") else "No"),
                ui.tags.td(str(row.get("city_name") or "")),
                ui.tags.td(_postex_link(tn, "View")),
            )
        )
    return ui.div(
        ui.tags.table(ui.tags.thead(header), ui.tags.tbody(*body)),
        class_="table-scroll-wrap postex-orders-table",
    )


def register(input: Inputs, output: Outputs, session: Session) -> None:
    create_loading = reactive.Value(False)
    create_error = reactive.Value("")
    create_result = reactive.Value(None)

    track_loading = reactive.Value(False)
    track_error = reactive.Value("")
    track_result = reactive.Value(None)

    list_loading = reactive.Value(False)
    list_error = reactive.Value("")
    list_result = reactive.Value(None)

    cpr_loading = reactive.Value(False)
    cpr_error = reactive.Value("")
    cpr_result = reactive.Value(None)
    cpr_pdf_message = reactive.Value("")
    cpr_pdf_error = reactive.Value("")

    awb_loading = reactive.Value(False)
    awb_error = reactive.Value("")
    awb_message = reactive.Value("")

    ls_loading = reactive.Value(False)
    ls_error = reactive.Value("")
    ls_message = reactive.Value("")

    sales_loading = reactive.Value(False)
    sales_error = reactive.Value("")
    sales_message = reactive.Value("")
    sales_summary_data = reactive.Value(None)
    sales_orders_data = reactive.Value(None)
    sales_sync_state = reactive.Value(None)
    sales_tick = reactive.Value(0)

    def _sales_date_bounds():
        from datetime import datetime as dt

        from_raw = _safe_str(input, "postex_sales_from")
        to_raw = _safe_str(input, "postex_sales_to")

        from_dt = None
        to_dt = None
        if from_raw:
            text = from_raw[:10]
            d = date.fromisoformat(text)
            from_dt = dt(d.year, d.month, d.day)
        if to_raw:
            text = to_raw[:10]
            d = date.fromisoformat(text)
            to_dt = dt(d.year, d.month, d.day, 23, 59, 59)
        return from_dt, to_dt

    def _load_sales_summary():
        from models.database import SessionLocal
        from models.schemas import PostExOrder
        from services.postex_sales import sales_summary
        from services.postex_sync import get_or_create_sync_state, sync_state_dict
        from sqlalchemy import desc

        from_dt, to_dt = _sales_date_bounds()
        db = SessionLocal()
        try:
            summary = sales_summary(db, from_dt=from_dt, to_dt=to_dt)
            state = get_or_create_sync_state(db)
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
            rows = (
                q.order_by(desc(PostExOrder.transaction_date), PostExOrder.tracking_number)
                .limit(50)
                .all()
            )
            items = [
                {
                    "tracking_number": r.tracking_number,
                    "transaction_status": r.transaction_status,
                    "transaction_date": r.transaction_date.isoformat()
                    if r.transaction_date
                    else None,
                    "invoice_payment": r.invoice_payment,
                    "settle": r.settle,
                    "city_name": r.city_name,
                }
                for r in rows
            ]
            sales_summary_data.set(summary)
            sales_orders_data.set(items)
            sales_sync_state.set(sync_state_dict(state))
            sales_error.set("")
        finally:
            db.close()

    @reactive.effect
    def _sales_initial_load():
        sales_tick.get()
        try:
            _load_sales_summary()
        except Exception as exc:
            sales_error.set(str(exc))

    @reactive.effect
    @reactive.event(input.postex_sales_refresh_btn)
    def _on_sales_refresh():
        sales_message.set("")
        try:
            _load_sales_summary()
            sales_message.set("Summary refreshed.")
        except Exception as exc:
            sales_error.set(str(exc))

    @reactive.effect
    @reactive.event(input.postex_sales_sync_btn)
    async def _on_sales_sync():
        import asyncio

        sales_loading.set(True)
        sales_error.set("")
        sales_message.set("Starting PostEx sync…")
        # Let the UI paint loading state before the long await.
        await asyncio.sleep(0)
        try:
            ui.notification_show("PostEx sync started…", type="message", duration=4)
        except Exception:
            pass
        try:
            from models.database import SessionLocal
            from services.postex_sync import get_or_create_sync_state, postex_sync_service

            db = SessionLocal()
            try:
                state = get_or_create_sync_state(db)
                # Finish remaining backfill in one click (empty history is fast).
                # Cap chunks only as a safety valve for very long runs.
                max_chunks = None if state.backfill_complete else 120
                result = await postex_sync_service.run(
                    db, mode="auto", max_chunks=max_chunks
                )
                sales_sync_state.set(result)
                orders_run = int(result.get("orders_this_run") or 0)
                chunks_run = int(result.get("chunks_this_run") or 0)
                if result.get("message") == "Sync already running":
                    msg = "Sync already running — wait a moment, then refresh."
                elif result.get("backfill_complete"):
                    msg = (
                        f"Sync complete ({chunks_run} chunk(s), {orders_run} order(s) this run). "
                        f"Lifetime upserted: {result.get('orders_upserted', 0)}."
                    )
                else:
                    msg = (
                        f"Backfill progressed to {result.get('backfill_cursor_date')} "
                        f"({chunks_run} chunk(s), {orders_run} order(s) this run). "
                        f"Click Sync now again to continue."
                    )
                sales_message.set(msg)
                try:
                    ui.notification_show(msg, type="message", duration=8)
                except Exception:
                    pass
            finally:
                db.close()
            _load_sales_summary()
        except Exception as exc:
            sales_error.set(str(exc))
            try:
                ui.notification_show(f"PostEx sync failed: {exc}", type="error", duration=10)
            except Exception:
                pass
        finally:
            sales_loading.set(False)

    @reactive.effect
    @reactive.event(input.postex_create_btn)
    async def _on_create():
        create_loading.set(True)
        create_error.set("")
        create_result.set(None)
        try:
            payload = {
                "orderRefNumber": _safe_str(input, "postex_create_ref"),
                "invoicePayment": _safe_str(input, "postex_create_payment"),
                "customerName": _safe_str(input, "postex_create_customer"),
                "customerPhone": _safe_str(input, "postex_create_phone"),
                "deliveryAddress": _safe_str(input, "postex_create_address"),
                "cityName": _safe_str(input, "postex_create_city"),
                "items": _safe_int(input, "postex_create_items", 1),
                "invoiceDivision": _safe_int(input, "postex_create_division", 1),
            }
            detail = _safe_str(input, "postex_create_detail")
            notes = _safe_str(input, "postex_create_notes")
            if detail:
                payload["orderDetail"] = detail
            if notes:
                payload["transactionNotes"] = notes

            required = [
                "orderRefNumber",
                "invoicePayment",
                "customerName",
                "customerPhone",
                "deliveryAddress",
                "cityName",
            ]
            missing = [k for k in required if not payload.get(k)]
            if missing:
                raise PostExError(f"Missing required fields: {', '.join(missing)}")

            client = get_configured_client()
            result = await client.create_order(payload)
            create_result.set(result)
        except PostExError as exc:
            create_error.set(str(exc))
        except Exception as exc:
            create_error.set(str(exc))
        finally:
            create_loading.set(False)

    @reactive.effect
    @reactive.event(input.postex_track_btn)
    async def _on_track():
        track_loading.set(True)
        track_error.set("")
        track_result.set(None)
        try:
            tracking = _safe_str(input, "postex_track_id")
            if not tracking:
                raise PostExError("Enter a tracking number")
            client = get_configured_client()
            track_result.set(await client.track_order(tracking))
        except PostExError as exc:
            track_error.set(str(exc))
        except Exception as exc:
            track_error.set(str(exc))
        finally:
            track_loading.set(False)

    @reactive.effect
    @reactive.event(input.postex_list_btn)
    async def _on_list():
        list_loading.set(True)
        list_error.set("")
        list_result.set(None)
        try:
            from_d = _fmt_date(input.postex_list_from())
            to_d = _fmt_date(input.postex_list_to())
            if not from_d or not to_d:
                raise PostExError("Select from and to dates")
            status_id = _safe_int(input, "postex_list_order_status", 0)
            client = get_configured_client()
            rows = await client.list_orders(
                order_status_id=status_id,
                from_date=from_d,
                to_date=to_d,
            )
            list_result.set(rows)
        except PostExError as exc:
            list_error.set(str(exc))
        except Exception as exc:
            list_error.set(str(exc))
        finally:
            list_loading.set(False)

    @reactive.effect
    @reactive.event(input.postex_cpr_btn)
    async def _on_cpr():
        cpr_loading.set(True)
        cpr_error.set("")
        cpr_result.set(None)
        cpr_pdf_error.set("")
        cpr_pdf_message.set("")
        try:
            from_d = _fmt_date(input.postex_cpr_from())
            to_d = _fmt_date(input.postex_cpr_to())
            if not from_d or not to_d:
                raise PostExError("Select from and to dates")
            status_id = _safe_int(input, "postex_cpr_order_status", 5)
            client = get_configured_client()
            rows = await client.list_cash_payment_receipts(
                from_date=from_d,
                to_date=to_d,
                order_status_id=status_id,
            )
            cpr_result.set(rows)
        except PostExError as exc:
            cpr_error.set(str(exc))
        except Exception as exc:
            cpr_error.set(str(exc))
        finally:
            cpr_loading.set(False)

    @reactive.effect
    @reactive.event(input.postex_cpr_pdf)
    async def _on_cpr_pdf():
        cpr_pdf_error.set("")
        cpr_pdf_message.set("")
        try:
            raw = str(input.postex_cpr_pdf() or "").strip()
            idx = int(raw)
            rows = cpr_result.get() or []
            if idx < 0 or idx >= len(rows):
                raise PostExError("CPR row not found — reload receipts and try again")
            row = rows[idx]
            filename = save_cpr_pdf(row)
            cpr_number = str(row.get("cprNumber") or "CPR")
            await session.send_custom_message(
                "download_pdf",
                {"url": f"/api/postex/pdfs/{filename}", "filename": filename},
            )
            cpr_pdf_message.set(f"Downloading PDF for {cpr_number}…")
        except PostExError as exc:
            cpr_pdf_error.set(str(exc))
        except Exception as exc:
            cpr_pdf_error.set(str(exc))

    @reactive.effect
    @reactive.event(input.postex_awb_btn)
    async def _on_awb():
        awb_loading.set(True)
        awb_error.set("")
        awb_message.set("")
        try:
            tracking = _parse_tracking_list(_safe_str(input, "postex_awb_tracking"))
            client = get_configured_client()
            pdf_bytes = await client.get_airway_bill(tracking)
            filename = save_postex_pdf(pdf_bytes, "airway_bill")
            awb_message.set(f"Airway bill ready ({len(tracking)} tracking number(s)).")
            await session.send_custom_message(
                "download_pdf",
                {"url": f"/api/postex/pdfs/{filename}", "filename": filename},
            )
        except PostExError as exc:
            awb_error.set(str(exc))
        except Exception as exc:
            awb_error.set(str(exc))
        finally:
            awb_loading.set(False)

    @reactive.effect
    @reactive.event(input.postex_ls_btn)
    async def _on_load_sheet():
        ls_loading.set(True)
        ls_error.set("")
        ls_message.set("")
        try:
            tracking = _parse_tracking_list(_safe_str(input, "postex_ls_tracking"))
            address = _safe_str(input, "postex_ls_address")
            city = _safe_str(input, "postex_ls_city")
            contact = _safe_str(input, "postex_ls_contact")
            if not address or not city or not contact:
                raise PostExError("Pickup address, city, and contact are required")
            client = get_configured_client()
            pdf_bytes = await client.generate_load_sheet(
                tracking_numbers=tracking,
                pickup_address=address,
                city_name=city,
                contact_number=contact,
            )
            filename = save_postex_pdf(pdf_bytes, "load_sheet")
            ls_message.set(f"Load sheet ready ({len(tracking)} tracking number(s)).")
            await session.send_custom_message(
                "download_pdf",
                {"url": f"/api/postex/pdfs/{filename}", "filename": filename},
            )
        except PostExError as exc:
            ls_error.set(str(exc))
        except Exception as exc:
            ls_error.set(str(exc))
        finally:
            ls_loading.set(False)

    @render.ui
    def postex_create_status():
        if create_loading.get():
            return loading_block("Creating PostEx order…")
        if create_error.get():
            return error_block("Create order failed", create_error.get())
        if create_result.get():
            return ui.div(
                "Order created successfully.",
                class_="gf-card-sub postex-success",
            )
        return ui.div(
            "Fill the form and create a COD order. Requires POSTEX_TOKEN in backend/.env.",
            class_="gf-card-sub",
        )

    @render.ui
    def postex_create_result():
        data = create_result.get()
        if not data or create_loading.get() or create_error.get():
            return ui.div()
        return ui.div(
            ui.div("Created shipment", class_="gf-card-title"),
            _kv_table(
                data,
                ["trackingNumber", "orderStatus", "orderDate"],
            ),
            ui.tags.pre(json.dumps(data, indent=2, default=str), class_="postex-raw"),
            class_="gf-card postex-card",
        )

    @render.ui
    def postex_track_status():
        if track_loading.get():
            return loading_block("Tracking order…")
        if track_error.get():
            return error_block("Track failed", track_error.get())
        if not track_result.get():
            return ui.div("Enter a PostEx tracking number (e.g. CX-…).", class_="gf-card-sub")
        return ui.div()

    @render.ui
    def postex_track_result():
        data = track_result.get()
        if not data or track_loading.get() or track_error.get():
            return ui.div()
        history = data.get("transactionStatusHistory")
        tracking = str(data.get("trackingNumber") or "").strip()
        return ui.div(
            ui.div(
                ui.div(
                    ui.div("Order status", class_="gf-card-title"),
                    _postex_link(tracking, "Open this order on PostEx ↗")
                    if tracking
                    else ui.div(),
                    class_="postex-card-heading",
                ),
                _kv_table(
                    data,
                    [
                        "trackingNumber",
                        "orderRefNumber",
                        "transactionStatus",
                        "customerName",
                        "customerPhone",
                        "cityName",
                        "deliveryAddress",
                        "invoicePayment",
                        "transactionDate",
                        "orderPickupDate",
                        "orderDeliveryDate",
                        "items",
                    ],
                ),
                class_="gf-card postex-card",
            ),
            _history_list(history),
            ui.div(
                ui.div("Raw response", class_="gf-card-title"),
                ui.tags.pre(json.dumps(data, indent=2, default=str), class_="postex-raw"),
                class_="gf-card postex-card",
            ),
            class_="postex-results",
        )

    @render.ui
    def postex_list_feedback():
        if list_loading.get():
            return loading_block("Loading PostEx orders…")
        if list_error.get():
            return error_block("List orders failed", list_error.get())
        rows = list_result.get()
        if rows is None:
            return ui.div(
                "Choose a date range and status, then load orders.",
                class_="gf-card-sub",
            )
        return ui.div(f"{len(rows)} order(s) returned.", class_="gf-card-sub")

    @render.ui
    def postex_list_result():
        rows = list_result.get()
        if rows is None or list_loading.get() or list_error.get():
            return ui.div()
        return ui.div(
            ui.div("Orders", class_="gf-card-title"),
            _orders_table(rows),
            class_="gf-card postex-card",
        )

    @render.ui
    def postex_cpr_feedback():
        if cpr_loading.get():
            return loading_block("Loading Cash Payment Receipts…")
        if cpr_error.get():
            return error_block("CPR load failed", cpr_error.get())
        if cpr_pdf_error.get():
            return error_block("CPR PDF download failed", cpr_pdf_error.get())
        rows = cpr_result.get()
        if rows is None:
            return ui.div(
                "Choose a date range (defaults to Delivered orders), then click "
                "“Load CPR receipts”. Expand a receipt for full details and PDF download.",
                class_="gf-card-sub",
            )
        bits = [f"{len(rows)} Cash Payment Receipt(s), newest first."]
        if cpr_pdf_message.get():
            bits.append(cpr_pdf_message.get())
        return ui.div(" ".join(bits), class_="gf-card-sub")

    @render.ui
    def postex_cpr_result():
        rows = cpr_result.get()
        if rows is None or cpr_loading.get() or cpr_error.get():
            return ui.div()
        return ui.div(
            ui.div("Cash Payment Receipts (CPR)", class_="gf-card-title"),
            ui.div(
                "Expand a receipt for portal-style Summary + Orders, then download the CPR PDF.",
                class_="gf-card-sub",
            ),
            _cpr_accordion(rows),
            class_="gf-card postex-card",
        )

    @render.ui
    def postex_awb_status():
        if awb_loading.get():
            return loading_block("Generating airway bill…")
        if awb_error.get():
            return error_block("Airway bill failed", awb_error.get())
        if awb_message.get():
            return ui.div(awb_message.get(), class_="gf-card-sub postex-success")
        return ui.div()

    @render.ui
    def postex_ls_status():
        if ls_loading.get():
            return loading_block("Generating load sheet…")
        if ls_error.get():
            return error_block("Load sheet failed", ls_error.get())
        if ls_message.get():
            return ui.div(ls_message.get(), class_="gf-card-sub postex-success")
        return ui.div()

    @render.ui
    def postex_sales_status():
        if sales_loading.get():
            return loading_block("Syncing PostEx orders…")
        if sales_error.get():
            return error_block("Sales sync / summary failed", sales_error.get())
        state = sales_sync_state.get() or {}
        bits = []
        status = state.get("status") or "idle"
        bits.append(f"Status: {status}")
        if state.get("backfill_complete"):
            bits.append("Backfill: complete")
        else:
            bits.append(
                f"Backfill cursor: {state.get('backfill_cursor_date') or '—'}"
            )
        if state.get("last_incremental_at"):
            bits.append(f"Last incremental: {_fmt_display_datetime(state.get('last_incremental_at'))}")
        if state.get("orders_upserted") is not None:
            bits.append(f"Orders upserted: {state.get('orders_upserted')}")
        if state.get("last_error"):
            bits.append(f"Last error: {state.get('last_error')}")
        line = " · ".join(bits) if bits else "No sync state yet — click Sync now."
        children = [ui.div(line, class_="gf-card-sub")]
        if sales_message.get():
            children.append(
                ui.div(sales_message.get(), class_="gf-card-sub postex-success")
            )
        return ui.div(*children)

    @render.ui
    def postex_sales_kpis():
        summary = sales_summary_data.get()
        if sales_loading.get() and summary is None:
            return ui.div()
        if summary is None:
            return ui.div(
                "Click Refresh summary (or Sync now) to load consolidated totals.",
                class_="gf-card-sub",
            )
        return ui.div(
            ui.div("Sales summary", class_="gf-card-title"),
            _sales_kpi_cards(summary),
            class_="gf-card postex-card",
        )

    @render.ui
    def postex_sales_orders():
        rows = sales_orders_data.get()
        if rows is None or sales_loading.get():
            return ui.div()
        return ui.div(
            ui.div("Recent synced orders", class_="gf-card-title"),
            _db_orders_table(rows),
            class_="gf-card postex-card",
        )
