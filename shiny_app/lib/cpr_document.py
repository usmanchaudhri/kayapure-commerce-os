"""PostEx Cash Payment Receipt (CPR) documents + portal-style PDF export.

The Merchant COD Integration API only exposes CPR numbers via Payment Status.
The merchant portal (merchant.postex.pk) assembles the full CPR view/PDF from
summary + order lines. This module rebuilds that same structure and layout from
Payment Status + List/Track order fields + merchant addresses.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from shiny_app.lib.postex_client import (
    POSTEX_CPR_HEADER_ADDRESS,
    POSTEX_CPR_HEADER_PHONE,
    POSTEX_PDF_DIR,
    WH_TAX_RATE,
)

_SHINY_ROOT = Path(__file__).resolve().parent.parent


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def money(value: Any) -> str:
    return f"{_as_float(value):,.2f}"


def fmt_cpr_date(value: Any) -> str:
    """Format PostEx timestamps / ISO dates as DD/MM/YYYY."""
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    raw = text.replace("Z", "+0000")
    if "T" in raw:
        raw = raw.split("T", 1)[0]
    raw = raw[:10]
    try:
        return date.fromisoformat(raw).strftime("%d/%m/%Y")
    except Exception:
        return text


def fmt_printed_at(value: datetime | None = None) -> str:
    dt = value or datetime.now()
    return dt.strftime("%d/%m/%Y %I:%M %p")


def merchant_destination_label(address: dict[str, Any]) -> str:
    addr = str(address.get("address") or "")
    city = str(address.get("cityName") or "").strip()
    if re.search(r"lahore\s*cantt", addr, re.I):
        return "LAHORE CANTT"
    return city.upper() if city else ""


def pick_default_merchant_address(addresses: list[dict[str, Any]]) -> dict[str, Any]:
    for addr in addresses:
        if isinstance(addr, dict) and "default" in str(addr.get("addressType") or "").lower():
            return addr
    for addr in addresses:
        if isinstance(addr, dict):
            return addr
    return {}


def cpr_rows_from_payment_status(
    status: dict[str, Any],
    *,
    order: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Flatten Payment Status into one row per non-empty CPR number."""
    tracking = str(status.get("trackingNumber") or "").strip()
    order_ref = str(status.get("orderRefNumber") or "").strip()
    settle = status.get("settle")
    settlement_date = str(status.get("settlementDate") or "").strip()
    order = dict(order) if isinstance(order, dict) else {}

    candidates = [
        (
            "Upfront",
            str(
                status.get("cpr1")
                or status.get("cprNumber_1")
                or status.get("cprNumber1")
                or ""
            ).strip(),
            str(
                status.get("cpr1Date") or status.get("upfrontPaymentDate") or ""
            ).strip(),
        ),
        (
            "Reserve",
            str(
                status.get("cpr2")
                or status.get("cprNumber_2")
                or status.get("cprNumber2")
                or ""
            ).strip(),
            str(
                status.get("cpr2Date") or status.get("reservePaymentDate") or ""
            ).strip(),
        ),
    ]

    rows: list[dict[str, Any]] = []
    for cpr_type, cpr_number, payment_date in candidates:
        if not cpr_number:
            continue
        rows.append(
            {
                **order,
                "cprNumber": cpr_number,
                "cprType": cpr_type,
                "paymentDate": payment_date or settlement_date,
                "trackingNumber": tracking
                or str(order.get("trackingNumber") or "").strip(),
                "orderRefNumber": order_ref
                or str(order.get("orderRefNumber") or "").strip(),
                "settle": settle if settle is not None else order.get("settle"),
                "settlementDate": settlement_date,
                "upfrontPaymentDate": str(
                    status.get("cpr1Date")
                    or status.get("upfrontPaymentDate")
                    or order.get("upfrontPaymentDate")
                    or ""
                ).strip(),
                "reservePaymentDate": str(
                    status.get("cpr2Date")
                    or status.get("reservePaymentDate")
                    or order.get("reservePaymentDate")
                    or ""
                ).strip(),
                "paymentStatusRaw": dict(status),
            }
        )
    return rows


def _order_line_from_shipment(
    order: dict[str, Any],
    *,
    merchant_city: str,
) -> dict[str, Any]:
    cod = _as_float(order.get("invoicePayment") or order.get("codAmount"))
    shipping = _as_float(order.get("transactionFee"))
    gst = _as_float(order.get("transactionTax"))
    upfront = _as_float(order.get("upfrontPayment"))
    reserve = _as_float(order.get("reservePayment"))
    if reserve <= 0 and cod > 0 and upfront <= 0:
        reserve = cod
    status = str(order.get("transactionStatus") or "").strip()
    wh_income = round(cod * WH_TAX_RATE, 2) if status.lower() == "delivered" else 0.0
    wh_sales = round(cod * WH_TAX_RATE, 2) if status.lower() == "delivered" else 0.0
    net = round(cod - shipping - gst - wh_income - wh_sales, 2)
    weight = _as_float(order.get("actualWeight") or order.get("bookingWeight"))
    return {
        "trackingNumber": str(order.get("trackingNumber") or "").strip(),
        "originCity": str(order.get("cityName") or order.get("originCity") or "").strip(),
        "destinationCity": merchant_city,
        "status": status,
        "shippingCharges": shipping,
        "upfrontCharges": 0.0,
        "upfrontAmount": upfront,
        "codAmount": cod,
        "reserveAmount": reserve,
        "gst": gst,
        "whIncomeTax": wh_income,
        "whSalesTax": wh_sales,
        "netAmount": net,
        "weightKg": weight,
        "orderDate": order.get("transactionDate") or order.get("orderPickupDate"),
        "deliveryDate": order.get("orderDeliveryDate"),
        "customerName": order.get("customerName"),
        "customerPhone": order.get("customerPhone"),
        "orderRefNumber": order.get("orderRefNumber"),
        "settle": order.get("settle"),
        "settlementDate": order.get("settlementDate"),
        "cprType": order.get("cprType"),
        "paymentDate": order.get("paymentDate"),
        "merchantName": order.get("merchantName"),
    }


def build_cpr_document(
    *,
    cpr_number: str,
    cpr_date: str,
    shipments: list[dict[str, Any]],
    merchant: dict[str, Any] | None = None,
    settle: Any = None,
    settlement_date: str = "",
) -> dict[str, Any]:
    merchant = merchant if isinstance(merchant, dict) else {}
    merchant_city = merchant_destination_label(merchant)
    merchant_name = str(
        merchant.get("contactPersonName")
        or merchant.get("merchantName")
        or (shipments[0].get("merchantName") if shipments else "")
        or ""
    ).strip()
    merchant_phone = str(merchant.get("phone1") or merchant.get("phone2") or "").strip()
    merchant_address = str(merchant.get("address") or "").strip()
    merchant_email = str(merchant.get("email") or "").strip()
    try:
        from config import settings

        if not merchant_email:
            merchant_email = str(
                getattr(settings, "POSTEX_MERCHANT_EMAIL", "") or ""
            ).strip()
    except Exception:
        pass

    lines = [
        _order_line_from_shipment(s, merchant_city=merchant_city) for s in shipments
    ]

    upfront_count = upfront_cod = upfront_pay = 0.0
    delivered_count = delivered_cod = delivered_pay = 0.0
    same_day_count = same_day_cod = same_day_pay = 0.0
    returned_count = returned_cod = returned_pay = 0.0
    shipping_count = 0
    shipping_total = 0.0
    upfront_charges_count = 0
    upfront_charges_total = 0.0
    gst_total = 0.0
    wh_income_total = 0.0
    wh_sales_total = 0.0

    for line in lines:
        status = str(line.get("status") or "").lower()
        cod = _as_float(line.get("codAmount"))
        ship = _as_float(line.get("shippingCharges"))
        if ship:
            shipping_count += 1
            shipping_total += ship
        gst_total += _as_float(line.get("gst"))
        wh_income_total += _as_float(line.get("whIncomeTax"))
        wh_sales_total += _as_float(line.get("whSalesTax"))
        upfront_amt = _as_float(line.get("upfrontAmount"))
        if upfront_amt:
            upfront_charges_count += 1
            upfront_charges_total += upfront_amt

        if "return" in status:
            returned_count += 1
            returned_cod += cod
        elif "same day" in status:
            same_day_count += 1
            same_day_cod += cod
            same_day_pay += cod
        elif status == "delivered":
            delivered_count += 1
            delivered_cod += cod
            delivered_pay += cod
        elif upfront_amt > 0:
            upfront_count += 1
            upfront_cod += upfront_amt
            upfront_pay += upfront_amt
        else:
            delivered_count += 1
            delivered_cod += cod
            delivered_pay += cod

    cod_total = upfront_cod + delivered_cod + same_day_cod + returned_cod
    net_total = round(
        cod_total
        - shipping_total
        - gst_total
        - wh_income_total
        - wh_sales_total
        - upfront_charges_total,
        2,
    )

    summary_rows = [
        {
            "details": "Upfront",
            "count": int(upfront_count),
            "codAmount": upfront_cod,
            "payableAmount": upfront_pay,
        },
        {
            "details": "Delivered",
            "count": int(delivered_count),
            "codAmount": delivered_cod,
            "payableAmount": delivered_pay,
        },
        {
            "details": "Same Day",
            "count": int(same_day_count),
            "codAmount": same_day_cod,
            "payableAmount": same_day_pay,
        },
        {
            "details": "Returned",
            "count": int(returned_count),
            "codAmount": returned_cod,
            "payableAmount": returned_pay,
            "payableParen": True,
        },
    ]

    totals = {
        "codTotal": cod_total,
        "shippingChargesCount": shipping_count,
        "shippingCharges": shipping_total,
        "upfrontChargesCount": upfront_charges_count,
        "upfrontCharges": upfront_charges_total,
        "gst": gst_total,
        "carryForward": 0.0,
        "miscellaneous": 0.0,
        "adjustments": 0.0,
        "netTotal": net_total,
        "whIncomeTax": wh_income_total,
        "whSalesTax": wh_sales_total,
    }
    primary = lines[0] if lines else {}
    return {
        "cprNumber": cpr_number,
        "cprDate": cpr_date,
        "cprType": primary.get("cprType") or "",
        "paymentDate": cpr_date or primary.get("paymentDate") or "",
        "settle": settle if settle is not None else primary.get("settle"),
        "settlementDate": settlement_date or str(primary.get("settlementDate") or ""),
        "trackingNumber": primary.get("trackingNumber") or "",
        "orderRefNumber": primary.get("orderRefNumber") or "",
        "merchantName": merchant_name,
        "merchantAddress": merchant_address,
        "merchantCity": str(merchant.get("cityName") or "").strip(),
        "merchantPhone": merchant_phone,
        "merchantEmail": merchant_email,
        "destinationCity": merchant_city,
        "summaryRows": summary_rows,
        "totals": totals,
        "orders": lines,
        "netAmount": net_total,
        "invoicePayment": cod_total,
    }


def sort_cpr_rows_by_date_desc(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[int, str]:
        raw = str(
            row.get("cprDate")
            or row.get("paymentDate")
            or row.get("settlementDate")
            or ""
        ).strip()
        if not raw:
            return (0, "")
        return (1, raw)

    return sorted(rows, key=sort_key, reverse=True)


def group_cpr_documents(
    receipt_rows: list[dict[str, Any]],
    *,
    merchant: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    meta: dict[str, dict[str, Any]] = {}
    for row in receipt_rows:
        cpr = str(row.get("cprNumber") or "").strip()
        if not cpr:
            continue
        buckets.setdefault(cpr, []).append(row)
        cur = meta.get(cpr) or {}
        pay = str(row.get("paymentDate") or "")
        if pay and (not cur.get("paymentDate") or pay > str(cur.get("paymentDate"))):
            cur["paymentDate"] = pay
        if row.get("settle") is not None:
            cur["settle"] = row.get("settle")
        if row.get("settlementDate"):
            cur["settlementDate"] = row.get("settlementDate")
        if row.get("cprType"):
            cur["cprType"] = row.get("cprType")
        meta[cpr] = cur

    docs: list[dict[str, Any]] = []
    for cpr, shipments in buckets.items():
        info = meta.get(cpr) or {}
        docs.append(
            build_cpr_document(
                cpr_number=cpr,
                cpr_date=str(info.get("paymentDate") or ""),
                shipments=shipments,
                merchant=merchant,
                settle=info.get("settle"),
                settlement_date=str(info.get("settlementDate") or ""),
            )
        )
    return sort_cpr_rows_by_date_desc(docs)


def cpr_detail_fields(row: dict[str, Any]) -> list[tuple[str, str]]:
    settle = row.get("settle")
    if settle is None:
        settled = ""
    elif settle in (True, "true", "True", 1, "1"):
        settled = "Yes"
    else:
        settled = "No"

    pairs = [
        ("CPR number", row.get("cprNumber")),
        ("CPR date", fmt_cpr_date(row.get("cprDate") or row.get("paymentDate"))),
        ("Merchant", row.get("merchantName")),
        ("Merchant phone", row.get("merchantPhone")),
        ("Merchant email", row.get("merchantEmail")),
        ("Merchant address", row.get("merchantAddress")),
        (
            "Net total",
            money(row.get("netAmount") or (row.get("totals") or {}).get("netTotal")),
        ),
        (
            "COD total",
            money(
                row.get("invoicePayment") or (row.get("totals") or {}).get("codTotal")
            ),
        ),
        (
            "Orders",
            str(len(row.get("orders") or []))
            if row.get("orders") is not None
            else "",
        ),
        ("Tracking number", row.get("trackingNumber")),
        ("Order reference", row.get("orderRefNumber")),
        ("Settled", settled),
        ("Settlement date", fmt_cpr_date(row.get("settlementDate"))),
    ]
    out: list[tuple[str, str]] = []
    for label, val in pairs:
        text = "" if val is None else str(val).strip()
        if text:
            out.append((label, text))
    return out


def generate_cpr_pdf_bytes(row: dict[str, Any]) -> tuple[bytes, str]:
    """Render a CPR PDF styled like the PostEx merchant portal export."""
    from fpdf import FPDF

    try:
        from fpdf.enums import XPos, YPos

        _next = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}
    except ImportError:
        _next = {"ln": 1}

    def _t(value: Any) -> str:
        text = "" if value is None else str(value)
        return (
            text.replace("\u2014", "-")
            .replace("\u2013", "-")
            .replace("\u2018", "'")
            .replace("\u2019", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
            .encode("latin-1", "replace")
            .decode("latin-1")
        )

    if not isinstance(row.get("totals"), dict) or not isinstance(row.get("orders"), list):
        row = build_cpr_document(
            cpr_number=str(row.get("cprNumber") or "CPR"),
            cpr_date=str(row.get("paymentDate") or row.get("cprDate") or ""),
            shipments=[row],
            merchant={
                "contactPersonName": row.get("merchantName"),
                "address": row.get("merchantAddress"),
                "cityName": row.get("merchantCity") or row.get("cityName"),
                "phone1": row.get("merchantPhone"),
                "email": row.get("merchantEmail"),
            },
            settle=row.get("settle"),
            settlement_date=str(row.get("settlementDate") or ""),
        )

    cpr_number = str(row.get("cprNumber") or "CPR").strip() or "CPR"
    totals = row.get("totals") or {}
    orders = row.get("orders") or []
    summary_rows = row.get("summaryRows") or []

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_title(_t(f"Cash Payment Receipt - {cpr_number}"))

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 4.5, _t(POSTEX_CPR_HEADER_ADDRESS), **_next)
    pdf.cell(0, 4.5, _t(POSTEX_CPR_HEADER_PHONE), **_next)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 4, _t(f"Printed At  {fmt_printed_at()}"), **_next)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 8, _t("Cash Payment Receipt"), **_next)
    pdf.ln(3)

    y = pdf.get_y()
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(110, 110, 110)
    pdf.set_xy(10, y)
    pdf.cell(45, 5, _t("CPR Number"))
    pdf.set_xy(60, y)
    pdf.cell(45, 5, _t("CPR Date"))
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(20, 20, 20)
    pdf.set_xy(10, y + 5)
    pdf.cell(45, 6, _t(cpr_number))
    pdf.set_xy(60, y + 5)
    pdf.cell(
        45,
        6,
        _t(fmt_cpr_date(row.get("cprDate") or row.get("paymentDate"))),
    )
    pdf.set_y(y + 14)

    y = pdf.get_y()
    left_x, right_x = 10, 110
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(20, 20, 20)
    pdf.set_xy(left_x, y)
    pdf.cell(90, 5, _t("Merchant Details"))
    pdf.set_xy(right_x, y)
    pdf.cell(90, 5, _t("Contact Details"))

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(left_x, y + 6)
    pdf.multi_cell(90, 5, _t(row.get("merchantName") or ""), **_next)
    name_bottom = pdf.get_y()
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(50, 50, 50)
    pdf.set_xy(left_x, name_bottom)
    addr_parts = [p for p in [row.get("merchantAddress"), row.get("merchantCity")] if p]
    pdf.multi_cell(90, 4.5, _t("\n".join(addr_parts)), **_next)
    left_bottom = pdf.get_y()

    pdf.set_xy(right_x, y + 6)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(90, 4.5, _t("Mobile Phone"), **_next)
    pdf.set_x(right_x)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(90, 5, _t(row.get("merchantPhone") or "-"), **_next)
    if row.get("merchantEmail"):
        pdf.set_x(right_x)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(110, 110, 110)
        pdf.cell(90, 4.5, _t("Email"), **_next)
        pdf.set_x(right_x)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(20, 20, 20)
        pdf.cell(90, 5, _t(row.get("merchantEmail")), **_next)
    right_bottom = pdf.get_y()
    pdf.set_y(max(left_bottom, right_bottom) + 4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 6, _t("Summary"), **_next)
    pdf.ln(1)

    col_w = [50, 25, 55, 55]
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(80, 80, 80)
    for i, h in enumerate(["Details", "Count", "COD Amount", "Payable Amount"]):
        pdf.cell(col_w[i], 6, _t(h), border=0, fill=True, align="R" if i else "L")
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 30, 30)
    for srow in summary_rows:
        payable = money(srow.get("payableAmount"))
        if srow.get("payableParen"):
            payable = f"({_as_float(srow.get('payableAmount')):g})"
        vals = [
            str(srow.get("details") or ""),
            str(int(_as_float(srow.get("count")))),
            money(srow.get("codAmount")),
            payable,
        ]
        for i, v in enumerate(vals):
            pdf.cell(col_w[i], 5.5, _t(v), align="R" if i else "L")
        pdf.ln()

    pdf.ln(1)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)

    def _kv_right(label: str, value: str, *, bold: bool = False) -> None:
        pdf.set_font("Helvetica", "B" if bold else "", 9)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(130, 5.5, _t(label), align="R")
        pdf.cell(55, 5.5, _t(value), align="R", **_next)

    _kv_right("Total", money(totals.get("codTotal")), bold=True)
    _kv_right(
        f"Shipping Charges  {int(_as_float(totals.get('shippingChargesCount')))}",
        f"({money(totals.get('shippingCharges'))})",
    )
    _kv_right(
        f"Upfront Charges  {int(_as_float(totals.get('upfrontChargesCount')))}",
        f"({money(totals.get('upfrontCharges'))})",
    )
    _kv_right("GST", f"({money(totals.get('gst'))})")
    _kv_right("Carry Forward", money(totals.get("carryForward")))
    _kv_right("Miscellaneous", f"({money(totals.get('miscellaneous'))})")
    _kv_right("Adjustment(s)", money(totals.get("adjustments")))
    pdf.set_draw_color(180, 180, 180)
    pdf.line(100, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(1)
    _kv_right("Net Total", money(totals.get("netTotal")), bold=True)
    _kv_right("WH Income Tax (2%)", f"({money(totals.get('whIncomeTax'))})")
    _kv_right("WH Sales Tax (2%)", f"({money(totals.get('whSalesTax'))})")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 6, _t("Orders"), **_next)
    pdf.ln(1)

    ocols = [
        (8, "SR."),
        (30, "Tracking / Weight / Date"),
        (24, "Origin City"),
        (22, "Status / Delivery"),
        (18, "Shipping"),
        (18, "Upfront"),
        (18, "COD"),
        (18, "Reserve"),
        (18, "Net"),
        (16, "Dest."),
    ]
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_text_color(70, 70, 70)
    for w, h in ocols:
        pdf.cell(w, 7, _t(h), border=0, fill=True, align="C")
    pdf.ln()

    for idx, line in enumerate(orders, start=1):
        weight = _as_float(line.get("weightKg"))
        track_bits = [str(line.get("trackingNumber") or "")]
        if weight:
            track_bits.append(f"{weight:.2f} kg")
        od = fmt_cpr_date(line.get("orderDate"))
        if od:
            track_bits.append(od)
        status_bits = [str(line.get("status") or "")]
        dd = fmt_cpr_date(line.get("deliveryDate"))
        if dd:
            status_bits.append(f"{dd} (D/R)")

        cells = [
            str(idx),
            "\n".join(track_bits),
            str(line.get("originCity") or ""),
            "\n".join(status_bits),
            money(line.get("shippingCharges")),
            money(line.get("upfrontAmount")),
            money(line.get("codAmount")),
            money(line.get("reserveAmount")),
            money(line.get("netAmount")),
            str(line.get("destinationCity") or ""),
        ]
        row_h = 14
        x0 = pdf.get_x()
        y0 = pdf.get_y()
        if y0 + row_h > 275:
            pdf.add_page()
            y0 = pdf.get_y()
            x0 = pdf.get_x()
        x = x0
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(25, 25, 25)
        for (w, _h), val in zip(ocols, cells):
            pdf.set_xy(x, y0)
            pdf.multi_cell(w, 3.8, _t(val), align="C" if w <= 10 else "L")
            x += w
        pdf.set_xy(x0 + 8, y0 + 11)
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(
            180,
            3,
            _t(
                f"GST {money(line.get('gst'))}   "
                f"WH Inc. Tax (2%) {money(line.get('whIncomeTax'))}   "
                f"WH Sales Tax (2%) {money(line.get('whSalesTax'))}"
            ),
        )
        pdf.set_y(y0 + row_h)

    pdf.ln(3)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(
        0,
        5,
        _t(
            f"{money(totals.get('netTotal'))}   "
            f"0.00   {money(totals.get('shippingCharges'))}   "
            f"{money(totals.get('codTotal'))}   0.00   "
            f"{money(totals.get('gst'))}   "
            f"{money(totals.get('whIncomeTax'))}   "
            f"{money(totals.get('whSalesTax'))}"
        ),
        **_next,
    )

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 4, _t(f"Developed by PostEx. {fmt_printed_at()}  |  1 of 1"), **_next)
    pdf.cell(
        0,
        4,
        _t(
            "Note: Settlements are processed by Call Courier, "
            "the logistics arm of PostEx Group."
        ),
        **_next,
    )

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", cpr_number)[:48] or "cpr"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"postex_cpr_{safe}_{stamp}.pdf"
    return bytes(pdf.output()), filename


def save_cpr_pdf(row: dict[str, Any]) -> str:
    pdf_bytes, filename = generate_cpr_pdf_bytes(row)
    path = POSTEX_PDF_DIR / filename
    path.write_bytes(pdf_bytes)
    return filename
