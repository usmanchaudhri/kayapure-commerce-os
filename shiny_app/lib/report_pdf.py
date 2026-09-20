"""Generate PDF exports for AI analysis reports."""

import os
import re
from datetime import date, datetime

from shiny_app.lib.formatting import fmt_currency

_SHINY_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_PDF_DIR = os.path.join(_SHINY_APP_ROOT, "report_pdfs")
os.makedirs(REPORT_PDF_DIR, exist_ok=True)


_SAFE_PDF_NAME = re.compile(r"^report_[A-Za-z0-9_-]+\.pdf$")


def _pdf_filename(acc_id: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", (acc_id or "account").replace("act_", ""))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"report_{safe_name}_{stamp}.pdf"


def is_safe_pdf_filename(filename: str) -> bool:
    return bool(filename and _SAFE_PDF_NAME.fullmatch(filename))


def resolve_report_pdf_path(filename: str) -> str | None:
    if not is_safe_pdf_filename(filename):
        return None
    root = os.path.abspath(REPORT_PDF_DIR)
    filepath = os.path.abspath(os.path.join(root, filename))
    if not filepath.startswith(root + os.sep):
        return None
    if not os.path.isfile(filepath):
        return None
    return filepath


def _pdf_text(value) -> str:
    """FPDF core fonts are Latin-1; keep the file readable without extra font files."""
    text = "" if value is None else str(value)
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u2192": "->",
        "\u00b7": "-",
        "\u2026": "...",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_report_pdf_bytes(analysis: dict, acc_name: str, acc_id: str) -> tuple[bytes, str]:
    """Generate a PDF in memory. Returns (bytes, filename)."""
    from fpdf import FPDF
    try:
        from fpdf.enums import XPos, YPos

        _next = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}
    except ImportError:
        _next = {"ln": 1}

    a = analysis.get("analysis", {}) if isinstance(analysis, dict) else {}
    summary = a.get("summary", "No summary available.")
    root_cause = a.get("root_cause") or ""
    findings = a.get("key_findings", []) or []
    layer_findings = a.get("layer_findings") or []
    risks = a.get("risks", []) or []
    recs = a.get("recommendations", []) or []
    confidence = a.get("confidence", 0) or 0
    snap = analysis.get("data_snapshot", {}) if isinstance(analysis, dict) else {}
    period = snap.get("period", {}) or {}
    currency = snap.get("currency", "USD")
    total_spend = snap.get("total_spend", 0) or 0
    report_scope = analysis.get("report_scope") or snap.get("scope") or "account"

    period_text = ""
    if period:
        period_text = f"{period.get('start', '?')} to {period.get('end', '?')}"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    title = (
        "AI Campaign Deep Dive Report"
        if report_scope == "campaign"
        else "AI Ad Performance Report"
    )
    pdf.set_title(_pdf_text(f"{title} - {acc_name}"))

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, _pdf_text(title), **_next)

    pdf.set_draw_color(245, 158, 11)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)
    meta = (
        f"{acc_name}  |  {acc_id}  |  {period_text}  |  "
        f"Total Spend: {fmt_currency(total_spend, currency)}"
    )
    def write_text(text: str, h: float = 6) -> None:
        pdf.multi_cell(0, h, _pdf_text(text), **_next)

    write_text(meta, 5)
    pdf.ln(4)

    def section(title: str) -> None:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(51, 65, 85)
        pdf.cell(0, 8, _pdf_text(title), **_next)
        pdf.set_text_color(30, 41, 59)

    section("Summary")
    pdf.set_font("Helvetica", "", 11)
    write_text(summary)
    pdf.ln(3)

    if root_cause:
        section("Root Cause")
        pdf.set_font("Helvetica", "", 11)
        write_text(root_cause)
        pdf.ln(3)

    if findings:
        section("Key Findings")
        pdf.set_font("Helvetica", "", 11)
        for finding in findings:
            write_text(f"- {finding}")
            pdf.ln(1)
        pdf.ln(2)

    if layer_findings:
        section("Layer Diagnostics")
        for item in layer_findings:
            if not isinstance(item, dict):
                continue
            layer = (item.get("layer") or "campaign").upper()
            name = item.get("name") or "-"
            diagnosis = item.get("diagnosis") or ""
            evidence = item.get("evidence") or ""
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(15, 23, 42)
            write_text(f"[{layer}] {name}")
            if diagnosis:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(71, 85, 105)
                write_text(diagnosis, 5)
            if evidence:
                pdf.set_font("Helvetica", "I", 9)
                write_text(f"Evidence: {evidence}", 5)
            pdf.ln(1)
        pdf.ln(2)

    if risks:
        section("Risks")
        pdf.set_text_color(153, 27, 27)
        pdf.set_font("Helvetica", "", 11)
        for risk in risks:
            write_text(f"- {risk}")
            pdf.ln(1)
        pdf.set_text_color(30, 41, 59)
        pdf.ln(2)

    if recs:
        section("Recommendations")
        for i, rec in enumerate(recs, 1):
            if not isinstance(rec, dict):
                rec = {"action": str(rec)}
            action = rec.get("action", "")
            rationale = rec.get("rationale", "")
            impact = rec.get("expected_impact", "")
            priority = str(rec.get("priority", "medium")).upper()
            target_layer = rec.get("target_layer") or ""
            target_name = rec.get("target_name") or ""
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(15, 23, 42)
            write_text(f"{i}. {action}")
            if rationale:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(71, 85, 105)
                write_text(rationale, 5)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(100, 116, 139)
            extras = "  |  ".join(
                part for part in (priority, target_layer, target_name, impact) if part
            )
            if extras:
                pdf.cell(0, 5, _pdf_text(extras), **_next)
            pdf.ln(2)

    conf_pct = int(float(confidence) * 100) if float(confidence) <= 1 else int(float(confidence))
    section("AI Confidence")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 6, f"{conf_pct}%", **_next)
    bar_y = pdf.get_y() + 1
    pdf.set_fill_color(226, 232, 240)
    pdf.rect(10, bar_y, 190, 5, "F")
    fill_w = max(1, min(190, 190 * conf_pct / 100))
    if conf_pct >= 70:
        pdf.set_fill_color(22, 163, 74)
    elif conf_pct >= 40:
        pdf.set_fill_color(217, 119, 6)
    else:
        pdf.set_fill_color(220, 38, 38)
    pdf.rect(10, bar_y, fill_w, 5, "F")
    pdf.ln(12)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 6, f"Generated by KayaPure Commerce OS  |  {date.today().isoformat()}", align="C")

    pdf_bytes = bytes(pdf.output())
    return pdf_bytes, _pdf_filename(acc_id)


def generate_report_pdf(analysis: dict, acc_name: str, acc_id: str) -> str:
    """Generate a styled PDF and write it to disk. Returns the file path."""
    pdf_bytes, filename = generate_report_pdf_bytes(analysis, acc_name, acc_id)
    filepath = os.path.join(REPORT_PDF_DIR, filename)
    with open(filepath, "wb") as handle:
        handle.write(pdf_bytes)
    return filepath
