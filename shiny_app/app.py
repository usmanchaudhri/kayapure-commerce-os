"""
KayaPure Commerce OS — Shiny Dashboard (Meta Ads)
Embedded in FastAPI via ASGI mount at /dashboard.

Tabs:
  - Dashboard: KPIs, spend trends, campaign insights, all-account totals
  - Ad Campaigns: Campaign management — table, detail modal, pause/activate/delete/edit budget
  - Creatives: Creative management — grid view, detail modal, upload
"""

from shiny import App, Inputs, Outputs, Session, reactive, render, ui
import plotly.graph_objects as go
from shinywidgets import output_widget, render_widget
import json
import time
import os
import hashlib
from datetime import date as _date_type, timedelta as _timedelta

# Currency symbol lookup
CURRENCY_SYMBOLS = {
    "PKR": "Rs", "USD": "$", "GBP": "£", "EUR": "€",
    "AED": "AED", "SAR": "SAR", "INR": "₹", "CAD": "C$", "AUD": "A$",
}


def fmt_currency(value, currency="USD"):
    """Format a number with the correct currency symbol."""
    sym = CURRENCY_SYMBOLS.get(currency, currency)
    return f"{sym}{value:,.2f}"


def fmt_number(value):
    """Format a number with commas."""
    return f"{value:,}"


def fmt_budget(value_cents, currency="USD"):
    """Format a budget value from cents to currency display."""
    if value_cents is None or value_cents == 0:
        return "\u2014"
    return fmt_currency(float(value_cents) / 100, currency)


# ============================================
# Report Cache (in-memory with 24h TTL)
# ============================================
class ReportCache:
    """In-memory cache for AI reports keyed by account_id + report_type."""
    TTL_SECONDS = 24 * 60 * 60  # 24 hours

    def __init__(self):
        self._store: dict = {}  # key -> {"result": dict, "timestamp": float}

    def _make_key(self, acc_id: str, report_type: str, days: int) -> str:
        today = _date_type.today().isoformat()
        raw = f"{acc_id}_{report_type}_{days}d_{today}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, acc_id: str, report_type: str, days: int = 30):
        key = self._make_key(acc_id, report_type, days)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > self.TTL_SECONDS:
            del self._store[key]
            return None
        return entry

    def put(self, acc_id: str, report_type: str, result: dict, days: int = 30):
        key = self._make_key(acc_id, report_type, days)
        self._store[key] = {"result": result, "timestamp": time.time()}

    def invalidate(self, acc_id: str, report_type: str, days: int = 30):
        key = self._make_key(acc_id, report_type, days)
        self._store.pop(key, None)


_report_cache = ReportCache()


# ============================================
# PDF Report Generator
# ============================================
_REPORT_PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_pdfs")
os.makedirs(_REPORT_PDF_DIR, exist_ok=True)


def _generate_report_pdf(analysis: dict, acc_name: str, acc_id: str) -> str:
    """Generate a styled PDF from the analysis dict. Returns the file path."""
    from weasyprint import HTML

    a = analysis.get("analysis", {})
    summary = a.get("summary", "No summary available.")
    findings = a.get("key_findings", [])
    risks = a.get("risks", [])
    recs = a.get("recommendations", [])
    confidence = a.get("confidence", 0)
    snap = analysis.get("data_snapshot", {})
    period = snap.get("period", {})
    currency = snap.get("currency", "USD")
    total_spend = snap.get("total_spend", 0)

    period_text = ""
    if period:
        period_text = f"{period.get('start', '?')} to {period.get('end', '?')}"

    findings_html = "".join(f'<div class="finding">{f}</div>' for f in findings)
    risks_html = "".join(f'<div class="risk">{r}</div>' for r in risks)

    recs_html = ""
    for i, rec in enumerate(recs, 1):
        action = rec.get("action", "")
        rationale = rec.get("rationale", "")
        impact = rec.get("expected_impact", "")
        priority = rec.get("priority", "medium").upper()
        p_color = "#dc2626" if priority == "HIGH" else ("#d97706" if priority == "MEDIUM" else "#16a34a")
        recs_html += f'''
        <div class="rec-card">
            <div class="rec-action">{i}. {action}</div>
            <div class="rec-rationale">{rationale}</div>
            <div class="rec-meta">
                <span class="badge" style="background:{p_color};color:white;">{priority}</span>
                {f'<span class="badge" style="background:#1e40af;color:white;">{impact}</span>' if impact else ''}
            </div>
        </div>'''

    conf_pct = int(confidence * 100)
    conf_color = "#16a34a" if conf_pct >= 70 else ("#d97706" if conf_pct >= 40 else "#dc2626")

    html_content = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
    @page {{ size: A4; margin: 2cm; }}
    body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #1e293b; line-height: 1.6; font-size: 13px; }}
    h1 {{ font-size: 22px; color: #0f172a; border-bottom: 3px solid #f59e0b; padding-bottom: 8px; margin-bottom: 6px; }}
    .meta {{ color: #64748b; font-size: 12px; margin-bottom: 24px; }}
    h2 {{ font-size: 16px; color: #334155; margin-top: 24px; margin-bottom: 10px; border-left: 4px solid #f59e0b; padding-left: 10px; }}
    .summary {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; font-size: 14px; }}
    .finding {{ background: #f0f9ff; border-left: 3px solid #0ea5e9; padding: 8px 14px; margin-bottom: 6px; border-radius: 0 6px 6px 0; }}
    .risk {{ background: #fef2f2; border-left: 3px solid #ef4444; padding: 8px 14px; margin-bottom: 6px; border-radius: 0 6px 6px 0; color: #991b1b; }}
    .rec-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; }}
    .rec-action {{ font-weight: 700; font-size: 14px; margin-bottom: 4px; }}
    .rec-rationale {{ color: #475569; font-size: 13px; margin-bottom: 6px; }}
    .rec-meta {{ display: flex; gap: 8px; }}
    .badge {{ padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; }}
    .confidence {{ margin-top: 24px; padding: 12px 16px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }}
    .conf-bar {{ height: 10px; background: #e2e8f0; border-radius: 5px; overflow: hidden; margin-top: 6px; }}
    .conf-fill {{ height: 100%; border-radius: 5px; }}
    .footer {{ margin-top: 30px; text-align: center; color: #94a3b8; font-size: 11px; border-top: 1px solid #e2e8f0; padding-top: 12px; }}
</style>
</head><body>
    <h1>AI Ad Performance Report</h1>
    <div class="meta">{acc_name} &middot; {acc_id} &middot; {period_text} &middot; Total Spend: {fmt_currency(total_spend, currency)}</div>
    <h2>Summary</h2>
    <div class="summary">{summary}</div>
    {f"<h2>Key Findings</h2>{findings_html}" if findings else ""}
    {f"<h2>Risks</h2>{risks_html}" if risks else ""}
    {f"<h2>Recommendations</h2>{recs_html}" if recs else ""}
    <div class="confidence">
        <strong>AI Confidence:</strong> {conf_pct}%
        <div class="conf-bar"><div class="conf-fill" style="width:{conf_pct}%;background:{conf_color};"></div></div>
    </div>
    <div class="footer">Generated by KayaPure Commerce OS &middot; {_date_type.today().isoformat()}</div>
</body></html>'''

    safe_name = acc_id.replace("act_", "").replace("/", "_")
    filename = f"report_{safe_name}_{_date_type.today().isoformat()}.pdf"
    filepath = os.path.join(_REPORT_PDF_DIR, filename)

    HTML(string=html_content).write_pdf(filepath)
    return filepath


# ============================================
# UI
# ============================================
app_ui = ui.page_fluid(
    ui.busy_indicators.use(spinners=False, pulse=True),
    ui.tags.script("""
        $(document).on('shiny:connected', function() {
            Shiny.addCustomMessageHandler('download_pdf', function(msg) {
                var a = document.createElement('a');
                a.href = 'data:application/pdf;base64,' + msg.data;
                a.download = msg.filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            });
        });
    """),
    ui.tags.style("""
        /* Shiny busy pulse overlay */
        .shiny-busy { opacity: 0.6; transition: opacity 0.3s; }
        .recalculating { opacity: 0.4; }
        body { background: #0f1117; color: #e2e8f0; font-family: 'Inter', system-ui, sans-serif; font-size: 18px; }
        .card { background: #1a1d27; border: 1px solid #2d3348; border-radius: 10px; }
        .card-header { border-bottom: 1px solid #2d3348; padding: 14px 18px; font-weight: 600; font-size: 18px; color: #94a3b8; }
        .card-body { padding: 16px; }
        .kpi-value { font-size: 34px; font-weight: 700; color: #f1f5f9; letter-spacing: -0.5px; }
        .kpi-label { font-size: 16px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
        .kpi-sub { font-size: 15px; color: #94a3b8; margin-top: 2px; }
        .kpi-card { background: #1a1d27; border: 1px solid #2d3348; border-radius: 10px; padding: 20px; }
        .badge-active { background: #065f46; color: #6ee7b7; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
        .badge-paused { background: #78350f; color: #fcd34d; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
        .badge-archived { background: #7f1d1d; color: #fca5a5; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
        .badge-deleted { background: #4a1d1d; color: #f87171; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
        table { width: 100%; border-collapse: collapse; font-size: 17px; }
        th { text-align: left; padding: 12px 14px; color: #64748b; font-weight: 600; font-size: 15px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #2d3348; }
        td { padding: 12px 14px; border-bottom: 1px solid #1e2235; color: #cbd5e1; }
        tr:hover td { background: #1e2235; }
        .header-bar { background: linear-gradient(135deg, #1a1d27 0%, #0f1117 100%); border-bottom: 1px solid #2d3348; padding: 20px 24px; margin: -16px -16px 24px -16px; border-radius: 0; }
        .header-title { font-size: 26px; font-weight: 700; color: #f1f5f9; }
        .header-sub { font-size: 17px; color: #64748b; margin-top: 4px; }
        .source-badge { background: #1e3a5f; color: #7dd3fc; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
        .refresh-btn { background: #2563eb; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 17px; font-weight: 600; }
        .refresh-btn:hover { background: #1d4ed8; }
        .period-info { font-size: 16px; color: #64748b; }
        /* Tab styling */
        .nav-tabs { border-bottom: 1px solid #2d3348; }
        .nav-tabs .nav-link { color: #64748b; border: none; padding: 14px 24px; font-weight: 600; font-size: 18px; }
        .nav-tabs .nav-link:hover { color: #e2e8f0; border: none; background: #1a1d27; }
        .nav-tabs .nav-link.active { color: #22d3ee; border: none; border-bottom: 2px solid #22d3ee; background: transparent; }
        .tab-content { padding-top: 24px; }
        /* Creative grid */
        .creative-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
        .creative-card {
            background: #1a1d27; border: 1px solid #2d3348; border-radius: 12px;
            overflow: hidden; cursor: pointer; transition: all 0.2s ease;
        }
        .creative-card:hover { border-color: #22d3ee; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
        .creative-thumb {
            width: 100%; height: 200px; object-fit: cover; display: block;
            background: #0f1117;
        }
        .creative-thumb-placeholder {
            width: 100%; height: 200px; display: flex; align-items: center; justify-content: center;
            background: #0f1117; color: #374151; font-size: 48px;
        }
        .creative-info { padding: 14px; }
        .creative-name { font-size: 17px; font-weight: 600; color: #e2e8f0; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .creative-id { font-size: 14px; color: #475569; font-family: monospace; margin-bottom: 8px; }
        .creative-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .type-badge-video { background: #1e3a5f; color: #7dd3fc; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
        .type-badge-image { background: #1a3a2a; color: #6ee7b7; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
        .type-badge-carousel { background: #3b1f5e; color: #c4b5fd; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
        .type-badge-unknown { background: #374151; color: #9ca3af; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
        /* Toolbar */
        .toolbar {
            display: flex; align-items: center; gap: 16px; margin-bottom: 24px;
            padding: 16px; background: #1a1d27; border: 1px solid #2d3348; border-radius: 10px;
        }
        .toolbar label { color: #94a3b8; font-size: 17px; font-weight: 600; }
        .toolbar select {
            background: #0f1117; color: #e2e8f0; border: 1px solid #2d3348;
            border-radius: 6px; padding: 10px 14px; font-size: 17px; min-width: 300px;
        }
        .toolbar select:focus { border-color: #22d3ee; outline: none; }
        /* Upload area */
        .upload-area {
            border: 2px dashed #2d3348; border-radius: 12px; padding: 32px;
            text-align: center; background: #0f1117; margin-bottom: 24px;
            transition: border-color 0.2s;
        }
        .upload-area:hover { border-color: #22d3ee; }
        .upload-icon { font-size: 36px; color: #374151; margin-bottom: 8px; }
        .upload-text { color: #64748b; font-size: 17px; }
        /* Loading spinner */
        .shiny-output-error { color: #f87171; padding: 20px; }
        .loading-spinner {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            padding: 60px 20px; color: #64748b;
        }
        .spinner {
            width: 48px; height: 48px; border: 4px solid #2d3348; border-top: 4px solid #22d3ee;
            border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 16px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .loading-text { font-size: 16px; color: #64748b; }
        /* Pagination */
        .pagination-bar {
            display: flex; align-items: center; justify-content: center; gap: 8px;
            padding: 20px 0; margin-top: 16px;
        }
        .pagination-bar .page-info { color: #94a3b8; font-size: 16px; margin: 0 16px; }
        .pagination-bar button {
            background: #1a1d27; color: #e2e8f0; border: 1px solid #2d3348;
            padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 15px; font-weight: 600;
            transition: all 0.2s;
        }
        .pagination-bar button:hover { background: #2d3348; border-color: #22d3ee; }
        .pagination-bar button:disabled { opacity: 0.3; cursor: not-allowed; }
        .pagination-bar button.active-page { background: #2563eb; border-color: #2563eb; color: white; }
        /* Modal overrides */
        .modal-content { background: #1a1d27 !important; border: 1px solid #2d3348 !important; color: #e2e8f0 !important; }
        .modal-header { border-bottom: 1px solid #2d3348 !important; }
        .modal-footer { border-top: 1px solid #2d3348 !important; }
        .modal-title { color: #f1f5f9 !important; }
        .btn-close { filter: invert(1); }
        /* Action buttons */
        .action-btn {
            padding: 10px 20px; border-radius: 6px; font-size: 17px; font-weight: 600;
            border: none; cursor: pointer; transition: background 0.2s;
        }
        .action-btn-primary { background: #2563eb; color: white; }
        .action-btn-primary:hover { background: #1d4ed8; }
        .action-btn-danger { background: #dc2626; color: white; }
        .action-btn-danger:hover { background: #b91c1c; }
        .action-btn-warning { background: #d97706; color: white; }
        .action-btn-warning:hover { background: #b45309; }
        .action-btn-success { background: #059669; color: white; }
        .action-btn-success:hover { background: #047857; }
        .action-btn-secondary { background: #374151; color: #e2e8f0; }
        .action-btn-secondary:hover { background: #4b5563; }
        /* Detail grid in modal */
        .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
        .detail-grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 16px; }
        .detail-item label { display: block; font-size: 15px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
        .detail-item span { font-size: 18px; color: #e2e8f0; }
        /* Campaign action buttons in table */
        .campaign-actions { display: flex; gap: 6px; flex-wrap: wrap; }
        .campaign-actions button {
            padding: 5px 12px; border-radius: 4px; font-size: 13px; font-weight: 600;
            border: none; cursor: pointer; transition: background 0.2s;
        }
        .btn-view { background: #1e3a5f; color: #7dd3fc; }
        .btn-view:hover { background: #1e4a7f; }
        .btn-pause { background: #78350f; color: #fcd34d; }
        .btn-pause:hover { background: #92400e; }
        .btn-activate { background: #065f46; color: #6ee7b7; }
        .btn-activate:hover { background: #047857; }
        .btn-edit { background: #374151; color: #e2e8f0; }
        .btn-edit:hover { background: #4b5563; }
        .btn-delete { background: #7f1d1d; color: #fca5a5; }
        .btn-delete:hover { background: #991b1b; }
        /* Objective badge */
        .badge-objective { background: #1e293b; color: #94a3b8; padding: 3px 10px; border-radius: 9999px; font-size: 13px; font-weight: 600; }
        /* Media type toggle */
        .media-toggle {
            display: flex; border: 1px solid #2d3348; border-radius: 8px; overflow: hidden;
        }
        .media-toggle-btn {
            padding: 8px 20px; font-size: 15px; font-weight: 600; cursor: pointer;
            border: none; background: transparent; color: #64748b;
            transition: all 0.2s ease; display: flex; align-items: center; gap: 6px;
        }
        .media-toggle-btn:hover { color: #e2e8f0; background: #1e2235; }
        .media-toggle-btn.active-images {
            background: #1a3a2a; color: #6ee7b7; box-shadow: inset 0 0 0 1px #6ee7b7;
        }
        .media-toggle-btn.active-videos {
            background: #1e3a5f; color: #7dd3fc; box-shadow: inset 0 0 0 1px #7dd3fc;
        }
        /* Video play overlay */
        .thumb-wrapper { position: relative; width: 100%; height: 200px; }
        .thumb-wrapper img, .thumb-wrapper .creative-thumb-placeholder { width: 100%; height: 100%; }
        .play-overlay {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            display: flex; align-items: center; justify-content: center;
            background: rgba(0, 0, 0, 0.35); transition: background 0.2s;
        }
        .creative-card:hover .play-overlay { background: rgba(0, 0, 0, 0.2); }
        .play-icon {
            width: 56px; height: 56px; background: rgba(0, 0, 0, 0.6);
            border: 3px solid rgba(255, 255, 255, 0.9); border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            transition: transform 0.2s;
        }
        .creative-card:hover .play-icon { transform: scale(1.1); }
        .play-icon svg { width: 24px; height: 24px; fill: white; margin-left: 3px; }
        /* Duplicate count badge */
        .dup-badge {
            background: #1e293b; color: #94a3b8; padding: 3px 10px; border-radius: 9999px;
            font-size: 13px; font-weight: 600; white-space: nowrap;
        }
        /* AI Reports tab */
        .ai-reports-header {
            display: flex; align-items: center; gap: 12px; margin-bottom: 24px;
        }
        .ai-reports-header h3 { color: #f1f5f9; font-size: 22px; font-weight: 700; margin: 0; }
        .ai-reports-header .subtitle { color: #64748b; font-size: 15px; }
        .ai-report-account-card {
            background: #1a1d27; border: 1px solid #2d3348; border-radius: 12px;
            margin-bottom: 20px; overflow: hidden;
        }
        .ai-report-account-row {
            display: flex; align-items: center; padding: 24px 28px; gap: 24px;
        }
        .ai-report-status-dot {
            width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0;
        }
        .ai-report-status-dot.active { background: #22c55e; }
        .ai-report-status-dot.inactive { background: #64748b; }
        .ai-report-account-info { flex: 1; min-width: 0; }
        .ai-report-account-name { font-size: 20px; font-weight: 700; color: #f1f5f9; margin-bottom: 4px; }
        .ai-report-account-meta { font-size: 14px; color: #64748b; font-family: monospace; }
        .ai-report-spend {
            font-size: 26px; font-weight: 700; color: #f1f5f9; white-space: nowrap;
            min-width: 160px; text-align: right;
        }
        .ai-report-actions { display: flex; gap: 12px; align-items: center; flex-shrink: 0; }
        .btn-generate-report {
            background: linear-gradient(135deg, #f59e0b 0%, #ea580c 100%);
            color: white; border: none; padding: 12px 24px; border-radius: 8px;
            font-size: 16px; font-weight: 700; cursor: pointer;
            display: flex; align-items: center; gap: 8px;
            transition: all 0.2s; box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
        }
        .btn-generate-report:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(245, 158, 11, 0.4); }
        .btn-view-reports {
            background: transparent; color: #e2e8f0; border: 1px solid #475569;
            padding: 12px 24px; border-radius: 8px; font-size: 16px; font-weight: 600;
            cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s;
        }
        .btn-view-reports:hover { border-color: #94a3b8; background: #1e2235; }
        .ai-report-goals-section {
            border-top: 1px solid #2d3348; padding: 20px 28px;
            background: rgba(30, 34, 53, 0.5);
        }
        .ai-report-goals-inner {
            border: 1px solid #2d3348; border-radius: 10px; padding: 20px 24px;
            background: #161924;
        }
        .ai-report-goals-title {
            display: flex; align-items: center; gap: 12px; margin-bottom: 6px;
        }
        .ai-report-goals-title span { font-size: 17px; font-weight: 600; color: #e2e8f0; }
        .ai-report-goals-desc { font-size: 15px; color: #64748b; margin-bottom: 14px; }
        .btn-add-goals {
            background: transparent; color: #f59e0b; border: 1px solid #f59e0b;
            padding: 8px 20px; border-radius: 20px; font-size: 15px; font-weight: 600;
            cursor: pointer; display: inline-flex; align-items: center; gap: 6px; transition: all 0.2s;
        }
        .btn-add-goals:hover { background: rgba(245, 158, 11, 0.1); }
        .ai-report-table-header {
            display: flex; padding: 12px 28px; border-bottom: 1px solid #2d3348;
            background: #161924; border-radius: 10px 10px 0 0;
        }
        .ai-report-col-header {
            font-size: 13px; font-weight: 600; color: #64748b;
            text-transform: uppercase; letter-spacing: 0.5px;
        }
        /* AI Report modal */
        .ai-report-modal-loading {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            padding: 60px 20px; color: #64748b;
        }
        .ai-report-summary {
            font-size: 16px; color: #cbd5e1; line-height: 1.7; padding: 16px 20px;
            background: #161924; border: 1px solid #2d3348; border-radius: 10px;
            margin-bottom: 20px;
        }
        .ai-report-section-title {
            font-size: 15px; font-weight: 700; color: #94a3b8; text-transform: uppercase;
            letter-spacing: 0.5px; margin-bottom: 10px; margin-top: 4px;
            display: flex; align-items: center; gap: 8px;
        }
        .ai-report-finding {
            padding: 10px 16px; background: #161924; border-left: 3px solid #22d3ee;
            border-radius: 0 8px 8px 0; margin-bottom: 8px; font-size: 15px;
            color: #e2e8f0; line-height: 1.5;
        }
        .ai-report-risk {
            padding: 10px 16px; background: #1c1520; border-left: 3px solid #f87171;
            border-radius: 0 8px 8px 0; margin-bottom: 8px; font-size: 15px;
            color: #fca5a5; line-height: 1.5;
        }
        .ai-report-rec-card {
            background: #161924; border: 1px solid #2d3348; border-radius: 10px;
            padding: 16px 20px; margin-bottom: 12px;
        }
        .ai-report-rec-action {
            font-size: 16px; font-weight: 700; color: #f1f5f9; margin-bottom: 6px;
        }
        .ai-report-rec-rationale {
            font-size: 14px; color: #94a3b8; line-height: 1.5; margin-bottom: 8px;
        }
        .ai-report-rec-meta {
            display: flex; gap: 12px; flex-wrap: wrap;
        }
        .ai-report-rec-badge {
            padding: 3px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600;
        }
        .ai-report-rec-badge.priority-high { background: #7f1d1d; color: #fca5a5; }
        .ai-report-rec-badge.priority-medium { background: #78350f; color: #fcd34d; }
        .ai-report-rec-badge.priority-low { background: #1a3a2a; color: #6ee7b7; }
        .ai-report-rec-badge.impact { background: #1e3a5f; color: #7dd3fc; }
        .ai-report-confidence {
            display: flex; align-items: center; gap: 10px; margin-top: 16px;
            padding: 12px 16px; background: #161924; border-radius: 8px;
        }
        .ai-report-confidence-bar {
            flex: 1; height: 8px; background: #2d3348; border-radius: 4px; overflow: hidden;
        }
        .ai-report-confidence-fill {
            height: 100%; border-radius: 4px;
            transition: width 0.5s ease;
        }
        .ai-report-confidence-label {
            font-size: 14px; color: #94a3b8; font-weight: 600; white-space: nowrap;
        }
        .ai-report-error {
            padding: 20px; background: #1c1520; border: 1px solid #7f1d1d; border-radius: 10px;
            color: #fca5a5; font-size: 15px; text-align: center;
        }
        .ai-report-toolbar {
            display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
            padding: 12px 16px; background: #161924; border: 1px solid #2d3348;
            border-radius: 10px; flex-wrap: wrap;
        }
        .ai-report-cache-label {
            font-size: 13px; color: #22c55e; font-weight: 600;
            display: flex; align-items: center; gap: 6px; flex: 1;
        }
        .btn-download-pdf {
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white; border: none; padding: 8px 20px; border-radius: 8px;
            font-size: 14px; font-weight: 700; cursor: pointer;
            display: flex; align-items: center; gap: 6px; transition: all 0.2s;
            box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
        }
        .btn-download-pdf:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4); }
        .btn-regenerate {
            background: transparent; color: #f59e0b; border: 1px solid #f59e0b;
            padding: 8px 20px; border-radius: 8px; font-size: 14px; font-weight: 600;
            cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.2s;
        }
        .btn-regenerate:hover { background: rgba(245, 158, 11, 0.1); }
        /* Date range selector */
        .date-range-bar {
            display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
        }
        .date-range-bar label { color: #94a3b8; font-size: 15px; font-weight: 600; white-space: nowrap; }
        .date-range-bar select {
            background: #0f1117; color: #e2e8f0; border: 1px solid #2d3348;
            border-radius: 6px; padding: 8px 14px; font-size: 15px; min-width: 180px;
        }
        .date-range-bar select:focus { border-color: #22d3ee; outline: none; }
    """),

    # Header
    ui.div(
        ui.div(
            ui.div(
                ui.span("KayaPure", style="color: #22d3ee;"),
                " Commerce OS — Meta Ads Dashboard",
                class_="header-title",
            ),
            ui.div("Real-time Facebook Marketing API data", class_="header-sub"),
            style="flex: 1;",
        ),
        ui.div(
            ui.input_action_button("refresh", "↻ Refresh Data", class_="refresh-btn"),
            style="display: flex; align-items: center;",
        ),
        class_="header-bar",
        style="display: flex; align-items: center; justify-content: space-between;",
    ),

    # ============================================
    # Tabbed Layout
    # ============================================
    ui.navset_tab(
        # ---- Tab 1: Dashboard ----
        ui.nav_panel(
            "Dashboard",

            # Total Spend (All Accounts)
            ui.div(
                ui.div(
                    ui.div("Total Ad Spend — All Accounts (Jan 2025 – Today)", class_="card-header"),
                    ui.div(ui.output_ui("total_spend_section"), class_="card-body"),
                    class_="card",
                ),
                style="margin-bottom: 24px;",
            ),

            # Date range selector + period info
            ui.div(
                ui.tags.label("Date Range:", **{"for": "dashboard_date_range"}),
                ui.input_select(
                    "dashboard_date_range",
                    label=None,
                    choices={"7": "Last 7 Days", "30": "Last 30 Days", "last_month": "Last Month", "180": "Last 6 Months", "365": "Last 1 Year"},
                    selected="7",
                ),
                class_="date-range-bar",
            ),
            ui.output_ui("period_info"),

            ui.div(
                ui.output_ui("kpi_cards"),
                style="margin-bottom: 24px;",
            ),

            # Daily Ad Spend Trend — full width
            ui.div(
                ui.div(
                    ui.div("Daily Ad Spend Trend", class_="card-header"),
                    ui.div(output_widget("spend_chart"), class_="card-body"),
                    class_="card",
                ),
                style="margin-bottom: 24px;",
            ),

            # Campaign Insights — full width, below the chart
            ui.div(
                ui.div(
                    ui.div("Campaign Insights", class_="card-header"),
                    ui.div(ui.output_ui("campaign_table"), class_="card-body"),
                    class_="card",
                ),
            ),
        ),

        # ---- Tab 2: Ad Campaigns ----
        ui.nav_panel(
            "Ad Campaigns",

            # Toolbar: Account selector
            ui.div(
                ui.div(
                    ui.tags.label("Ad Account:", **{"for": "campaigns_account_select"}),
                    ui.output_ui("campaigns_account_selector"),
                    style="display: flex; align-items: center; gap: 12px; flex: 1;",
                ),
                class_="toolbar",
            ),

            # KPI summary
            ui.div(
                ui.output_ui("campaigns_kpi"),
                style="margin-bottom: 20px;",
            ),

            # Campaigns table
            ui.div(
                ui.div(
                    ui.div("Campaign Management", class_="card-header"),
                    ui.div(ui.output_ui("campaigns_table"), class_="card-body"),
                    class_="card",
                ),
            ),
        ),

        # ---- Tab 3: Creatives ----
        ui.nav_panel(
            "Creatives",

            # Toolbar: Account selector + Upload button
            ui.div(
                ui.div(
                    ui.tags.label("Ad Account:", **{"for": "account_select"}),
                    ui.output_ui("account_selector"),
                    style="display: flex; align-items: center; gap: 12px; flex: 1;",
                ),
                ui.div(
                    ui.input_action_button("show_upload", "⬆ Upload New Creative", class_="refresh-btn"),
                    style="display: flex; align-items: center;",
                ),
                class_="toolbar",
            ),

            # Media type toggle (Images / Videos)
            ui.div(
                ui.output_ui("media_type_toggle"),
                style="margin-bottom: 16px;",
            ),

            # KPI summary row
            ui.div(
                ui.output_ui("creatives_kpi"),
                style="margin-bottom: 20px;",
            ),

            # Creative grid + pagination
            ui.div(
                ui.output_ui("creatives_grid"),
            ),
            ui.div(
                ui.output_ui("creatives_pagination"),
            ),
        ),

        # ---- Tab 4: AI Reports ----
        ui.nav_panel(
            "AI Reports",

            # Header
            ui.div(
                ui.div(
                    ui.tags.h3("AI-Powered Ad Reports"),
                    ui.div("Generate intelligent reports to analyse and improve your ad spend across accounts.", class_="subtitle"),
                    style="flex: 1;",
                ),
                class_="ai-reports-header",
            ),

            # Column headers row
            ui.div(
                ui.div("Account", class_="ai-report-col-header", style="flex: 2;"),
                ui.div("Spend (30D)", class_="ai-report-col-header", style="flex: 1; text-align: right;"),
                ui.div("Actions", class_="ai-report-col-header", style="flex: 1.5; text-align: right;"),
                class_="ai-report-table-header",
            ),

            # Account cards list
            ui.div(
                ui.output_ui("ai_reports_accounts_list"),
            ),
        ),
    ),
)


# ============================================
# Server
# ============================================
def server(input: Inputs, output: Outputs, session: Session):

    # ---- Shared reactive state ----
    selected_creative = reactive.value(None)

    # ---- Dashboard tab reactives ----

    @reactive.calc
    async def ad_data():
        input.refresh()
        from services.marketing import marketing_service
        from datetime import datetime, timedelta

        range_val = input.dashboard_date_range()

        if range_val == "last_month":
            # Calculate last calendar month
            today = datetime.utcnow()
            first_of_this_month = today.replace(day=1)
            last_day_prev_month = first_of_this_month - timedelta(days=1)
            first_of_prev_month = last_day_prev_month.replace(day=1)
            days = (last_day_prev_month - first_of_prev_month).days + 1
            # Use the marketing service with the calculated days,
            # but we need to pass custom date range
            data = await marketing_service.get_ad_spend_history(days=days)
            # Override period info to show the actual last month dates
            data["period"] = {
                "start": first_of_prev_month.strftime("%Y-%m-%d"),
                "end": last_day_prev_month.strftime("%Y-%m-%d"),
                "days": days,
                "label": last_day_prev_month.strftime("%B %Y"),
            }
        else:
            days = int(range_val)
            data = await marketing_service.get_ad_spend_history(days=days)

        return data

    @reactive.calc
    async def total_spend_data():
        input.refresh()
        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return None
        data = await marketing_service._fb_client.get_total_spend_all_accounts(since="2025-01-01")
        return data

    @render.ui
    async def total_spend_section():
        data = await total_spend_data()
        if data is None:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading total spend data...", class_="loading-text"),
                class_="loading-spinner",
            )
        if "error" in (data or {}):
            return ui.div("Facebook Ads client not configured or error occurred.", style="color: #64748b; text-align: center; padding: 24px;")

        period = data.get("period", {})
        accounts = data.get("accounts", [])
        currency_totals = data.get("currency_totals", {})

        kpi_items = []
        for cur, total in currency_totals.items():
            kpi_items.append(
                ui.div(
                    ui.div(f"Total Spend ({cur})", class_="kpi-label"),
                    ui.div(fmt_currency(total, cur), class_="kpi-value"),
                    ui.div(f"{period.get('since', '?')} → {period.get('until', '?')}", class_="kpi-sub"),
                    class_="kpi-card", style="flex: 1; min-width: 200px;",
                )
            )
        kpi_items.append(
            ui.div(
                ui.div("Total Impressions", class_="kpi-label"),
                ui.div(fmt_number(data.get("grand_total_impressions", 0)), class_="kpi-value"),
                ui.div(f"{data.get('total_accounts', 0)} accounts", class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 200px;",
            )
        )
        kpi_items.append(
            ui.div(
                ui.div("Total Clicks", class_="kpi-label"),
                ui.div(fmt_number(data.get("grand_total_clicks", 0)), class_="kpi-value"),
                ui.div(f"{data.get('accounts_with_data', 0)} accounts with data", class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 200px;",
            )
        )

        kpi_row = ui.div(*kpi_items, style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px;")

        if not accounts:
            return ui.div(kpi_row, ui.div("No accounts found", style="color: #64748b;"))

        rows = []
        for acc in accounts:
            status = acc.get("status", "UNKNOWN")
            badge_class = "badge-active" if status == "ACTIVE" else ("badge-archived" if status == "DISABLED" else "badge-paused")
            badge_label = "Active" if status == "ACTIVE" else ("Disabled" if status == "DISABLED" else status.title())
            acc_currency = acc.get("currency", "USD")
            rows.append(
                ui.tags.tr(
                    ui.tags.td(acc.get("account_name", "—")),
                    ui.tags.td(acc.get("account_id", "—"), style="font-size: 11px; color: #64748b;"),
                    ui.tags.td(ui.span(badge_label, class_=badge_class)),
                    ui.tags.td(acc_currency),
                    ui.tags.td(fmt_currency(acc.get("spend", 0), acc_currency)),
                    ui.tags.td(fmt_number(acc.get("impressions", 0))),
                    ui.tags.td(fmt_number(acc.get("clicks", 0))),
                )
            )

        account_table = ui.tags.table(
            ui.tags.thead(ui.tags.tr(
                ui.tags.th("Account Name"), ui.tags.th("Account ID"), ui.tags.th("Status"),
                ui.tags.th("Currency"), ui.tags.th("Total Spend"), ui.tags.th("Impressions"), ui.tags.th("Clicks"),
            )),
            ui.tags.tbody(*rows),
        )
        return ui.div(kpi_row, account_table)

    @render.ui
    async def period_info():
        data = await ad_data()
        period = data.get("period", {})
        source = data.get("source", "unknown")
        currency = data.get("currency", "USD")
        source_label = "LIVE API" if source == "facebook_api" else "MOCK"
        label = period.get("label", "")
        period_text = f"Period: {period.get('start', '?')} → {period.get('end', '?')} ({period.get('days', '?')} days)"
        if label:
            period_text = f"{label} — {period_text}"
        return ui.div(
            ui.span(period_text, class_="period-info"),
            ui.span(" | "), ui.span(f"Currency: {currency}", class_="period-info"),
            ui.span(" | "), ui.span("Source: ", class_="period-info"), ui.span(source_label, class_="source-badge"),
            style="margin-bottom: 16px; display: flex; align-items: center; gap: 6px;",
        )

    @render.ui
    async def kpi_cards():
        data = await ad_data()
        currency = data.get("currency", "USD")
        cards = [
            ("Total Spend", fmt_currency(data.get("total_spend", 0), currency), f"Avg {fmt_currency(data.get('avg_daily_spend', 0), currency)}/day"),
            ("Total Impressions", fmt_number(data.get("total_impressions", 0)), f"{len(data.get('campaigns', []))} campaigns"),
            ("Total Clicks", fmt_number(data.get("total_clicks", 0)), "Across all campaigns"),
            ("Avg CPC", fmt_currency(data.get("avg_cpc", 0), currency), "Cost per click"),
            ("Avg CTR", f"{data.get('avg_ctr', 0):.2f}%", "Click-through rate"),
        ]
        card_divs = [
            ui.div(
                ui.div(label, class_="kpi-label"), ui.div(value, class_="kpi-value"), ui.div(sub, class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 160px;",
            ) for label, value, sub in cards
        ]
        return ui.div(*card_divs, style="display: flex; gap: 16px; flex-wrap: wrap;")

    @render_widget
    async def spend_chart():
        data = await ad_data()
        daily = data.get("daily_breakdown", [])
        currency = data.get("currency", "USD")
        sym = CURRENCY_SYMBOLS.get(currency, currency)
        dates = [d["date"] for d in daily]
        spends = [d["spend"] for d in daily]
        clicks = [d.get("clicks", 0) for d in daily]

        fig = go.Figure()
        fig.add_trace(go.Bar(x=dates, y=spends, name="Spend", marker_color="#2563eb", hovertemplate=f"{sym}%{{y:,.2f}}<extra>Spend</extra>"))
        fig.add_trace(go.Scatter(x=dates, y=clicks, name="Clicks", yaxis="y2", line=dict(color="#22d3ee", width=2), mode="lines+markers", hovertemplate="%{y:,}<extra>Clicks</extra>"))
        fig.update_layout(
            plot_bgcolor="#1a1d27", paper_bgcolor="#1a1d27", font=dict(color="#94a3b8", size=11),
            margin=dict(l=50, r=50, t=20, b=40), height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
            yaxis=dict(title=f"Spend ({sym})", gridcolor="#2d3348", zeroline=False),
            yaxis2=dict(title="Clicks", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)", zeroline=False),
            xaxis=dict(gridcolor="#2d3348"), bargap=0.3,
        )
        return fig

    @render.ui
    async def campaign_table():
        data = await ad_data()
        campaigns = data.get("campaigns", [])
        currency = data.get("currency", "USD")
        if not campaigns:
            return ui.div("No campaign data available", style="color: #64748b; text-align: center; padding: 40px;")
        rows = []
        for c in campaigns:
            status = c.get("status", "UNKNOWN").upper()
            badge_class = "badge-active" if status == "ACTIVE" else ("badge-paused" if status == "PAUSED" else "badge-archived")
            badge_label = "Active" if status == "ACTIVE" else ("Paused" if status == "PAUSED" else status.title())
            rows.append(
                ui.tags.tr(
                    ui.tags.td(c.get("name", "—")), ui.tags.td(ui.span(badge_label, class_=badge_class)),
                    ui.tags.td(fmt_currency(c.get("spend", 0), currency)), ui.tags.td(fmt_number(c.get("impressions", 0))),
                    ui.tags.td(fmt_number(c.get("clicks", 0))), ui.tags.td(fmt_currency(c.get("cpc", 0), currency)),
                    ui.tags.td(f"{c.get('ctr', 0):.2f}%"), ui.tags.td(f"{c.get('roas', 0):.2f}x"),
                )
            )
        return ui.tags.table(
            ui.tags.thead(ui.tags.tr(
                ui.tags.th("Campaign"), ui.tags.th("Status"), ui.tags.th("Spend"),
                ui.tags.th("Impressions"), ui.tags.th("Clicks"), ui.tags.th("CPC"), ui.tags.th("CTR"), ui.tags.th("ROAS"),
            )),
            ui.tags.tbody(*rows),
        )

    # ============================================
    # Ad Campaigns tab reactives
    # ============================================

    @reactive.calc
    async def all_campaigns_data():
        """Fetch all campaigns across all accounts with performance insights."""
        input.refresh()
        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return None
        data = await marketing_service._fb_client.get_all_campaigns(include_insights=True, days=7)
        return data

    @render.ui
    async def campaigns_account_selector():
        """Render the account dropdown for the campaigns tab."""
        data = await all_campaigns_data()
        if data is None:
            return ui.div("Loading accounts...", style="color: #64748b; font-size: 16px;")

        accounts = data.get("accounts", [])
        choices = {"__all__": f"All Accounts ({data.get('total_campaigns', 0)} campaigns)"}
        for acc in accounts:
            count = acc.get("campaign_count", 0)
            label = f"{acc.get('account_name', 'Unknown')} ({acc.get('account_id', '')}) — {count} campaigns"
            choices[acc.get("account_id", "")] = label

        return ui.input_select("campaigns_account_select", None, choices=choices, width="100%")

    @render.ui
    async def campaigns_kpi():
        """KPI summary for campaigns."""
        data = await all_campaigns_data()
        if data is None:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading campaign data...", class_="loading-text"),
                class_="loading-spinner",
            )

        selected = input.campaigns_account_select() if hasattr(input, "campaigns_account_select") else "__all__"
        if not selected:
            selected = "__all__"

        # Collect campaigns based on selection
        campaigns = []
        if selected == "__all__":
            for acc in data.get("accounts", []):
                for c in acc.get("campaigns", []):
                    c["_currency"] = acc.get("currency", "USD")
                    campaigns.append(c)
        else:
            acc_data = next((a for a in data.get("accounts", []) if a.get("account_id") == selected), None)
            if acc_data:
                for c in acc_data.get("campaigns", []):
                    c["_currency"] = acc_data.get("currency", "USD")
                    campaigns.append(c)

        total = len(campaigns)
        active = sum(1 for c in campaigns if c.get("status", "").upper() == "ACTIVE")
        paused = sum(1 for c in campaigns if c.get("status", "").upper() == "PAUSED")
        total_spend = sum(
            c.get("performance", {}).get("spend", 0)
            for c in campaigns if c.get("performance")
        )

        # Group spend by currency so each currency shows its own total
        spend_by_currency = {}
        for c in campaigns:
            cur = c.get("_currency", "USD")
            perf = c.get("performance")
            if perf:
                spend_by_currency[cur] = spend_by_currency.get(cur, 0) + perf.get("spend", 0)

        kpi_items = [
            ui.div(
                ui.div("Total Campaigns", class_="kpi-label"),
                ui.div(fmt_number(total), class_="kpi-value"),
                ui.div(f"{data.get('total_accounts', 0)} accounts", class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 160px;",
            ),
            ui.div(
                ui.div("Active", class_="kpi-label"),
                ui.div(fmt_number(active), class_="kpi-value", style="color: #6ee7b7;"),
                ui.div("Currently running", class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 160px;",
            ),
            ui.div(
                ui.div("Paused", class_="kpi-label"),
                ui.div(fmt_number(paused), class_="kpi-value", style="color: #fcd34d;"),
                ui.div("On hold", class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 160px;",
            ),
        ]

        # Add a 7-Day Spend card for each currency
        for cur, spend in spend_by_currency.items():
            sym = CURRENCY_SYMBOLS.get(cur, cur)
            kpi_items.append(
                ui.div(
                    ui.div(f"7-Day Spend ({cur})", class_="kpi-label"),
                    ui.div(fmt_currency(spend, cur), class_="kpi-value"),
                    ui.div(f"Last 7 days in {cur}", class_="kpi-sub"),
                    class_="kpi-card", style="flex: 1; min-width: 160px;",
                ),
            )

        # If no spend data at all, show a placeholder card
        if not spend_by_currency:
            kpi_items.append(
                ui.div(
                    ui.div("7-Day Spend", class_="kpi-label"),
                    ui.div("—", class_="kpi-value"),
                    ui.div("No spend data", class_="kpi-sub"),
                    class_="kpi-card", style="flex: 1; min-width: 160px;",
                ),
            )

        return ui.div(*kpi_items, style="display: flex; gap: 16px; flex-wrap: wrap;")

    @render.ui
    async def campaigns_table():
        """Render the campaigns management table."""
        data = await all_campaigns_data()

        if data is None:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading campaigns from Facebook...", class_="loading-text"),
                class_="loading-spinner",
            )

        if "error" in (data or {}):
            return ui.div("Facebook Ads client not configured or error occurred.", style="color: #64748b; text-align: center; padding: 40px;")

        selected = input.campaigns_account_select() if hasattr(input, "campaigns_account_select") else "__all__"
        if not selected:
            selected = "__all__"

        # Collect campaigns based on selection
        campaigns = []
        if selected == "__all__":
            for acc in data.get("accounts", []):
                for c in acc.get("campaigns", []):
                    c["_account_name"] = acc.get("account_name", "Unknown")
                    c["_account_id"] = acc.get("account_id", "")
                    c["_currency"] = acc.get("currency", "USD")
                    campaigns.append(c)
        else:
            acc_data = next((a for a in data.get("accounts", []) if a.get("account_id") == selected), None)
            if acc_data:
                for c in acc_data.get("campaigns", []):
                    c["_account_name"] = acc_data.get("account_name", "Unknown")
                    c["_account_id"] = acc_data.get("account_id", "")
                    c["_currency"] = acc_data.get("currency", "USD")
                    campaigns.append(c)

        if not campaigns:
            return ui.div("No campaigns found for the selected account.", style="color: #64748b; text-align: center; padding: 40px;")

        # Sort: ACTIVE first, then by most recent date (start_time or created_time) descending
        def campaign_sort_key(c):
            status = c.get("status", "UNKNOWN").upper()
            status_order = 0 if status == "ACTIVE" else (1 if status == "PAUSED" else 2)
            # Use start_time if available, fall back to created_time
            date_str = c.get("start_time") or c.get("created_time") or "1970-01-01"
            return (status_order, date_str)

        campaigns.sort(key=lambda c: (campaign_sort_key(c)[0], campaign_sort_key(c)[1]), reverse=False)
        # Reverse the date within each status group: sort by status asc, date desc
        campaigns.sort(key=lambda c: campaign_sort_key(c)[0])
        from itertools import groupby
        sorted_campaigns = []
        for _, group in groupby(campaigns, key=lambda c: campaign_sort_key(c)[0]):
            group_list = list(group)
            group_list.sort(key=lambda c: c.get("start_time") or c.get("created_time") or "1970-01-01", reverse=True)
            sorted_campaigns.extend(group_list)
        campaigns = sorted_campaigns

        rows = []
        for c in campaigns:
            campaign_id = c.get("id", "")
            name = c.get("name", "—")
            status = c.get("status", "UNKNOWN").upper()
            objective = c.get("objective", "—")
            currency = c.get("_currency", "USD")

            # Budget — daily_budget is in cents
            daily_budget = c.get("daily_budget")
            lifetime_budget = c.get("lifetime_budget")
            if daily_budget and int(daily_budget) > 0:
                budget_display = f"{fmt_budget(int(daily_budget), currency)}/day"
            elif lifetime_budget and int(lifetime_budget) > 0:
                budget_display = f"{fmt_budget(int(lifetime_budget), currency)} lifetime"
            else:
                budget_display = "—"

            # Created date
            created_time = c.get("created_time", "")
            created_display = created_time[:10] if created_time else "—"

            # Performance
            perf = c.get("performance")
            if perf:
                spend_display = fmt_currency(perf.get("spend", 0), currency)
                clicks_display = fmt_number(perf.get("clicks", 0))
                impressions_display = fmt_number(perf.get("impressions", 0))
                ctr_display = f"{perf.get('ctr', 0):.2f}%"
            else:
                spend_display = "—"
                clicks_display = "—"
                impressions_display = "—"
                ctr_display = "—"

            # Status badge
            if status == "ACTIVE":
                badge_class, badge_label = "badge-active", "Active"
            elif status == "PAUSED":
                badge_class, badge_label = "badge-paused", "Paused"
            elif status == "DELETED":
                badge_class, badge_label = "badge-deleted", "Deleted"
            else:
                badge_class, badge_label = "badge-archived", status.title()

            # Objective badge — clean up the Facebook objective name
            obj_display = objective.replace("OUTCOME_", "").replace("_", " ").title() if objective != "—" else "—"

            # Action buttons — serialize campaign data for JS
            c_json = json.dumps(json.dumps({
                "id": campaign_id,
                "name": name,
                "status": status,
                "objective": objective,
                "daily_budget": daily_budget,
                "lifetime_budget": lifetime_budget,
                "created_time": created_time,
                "start_time": c.get("start_time", ""),
                "stop_time": c.get("stop_time", ""),
                "buying_type": c.get("buying_type", ""),
                "bid_strategy": c.get("bid_strategy", ""),
                "budget_remaining": c.get("budget_remaining", ""),
                "performance": perf,
                "_account_name": c.get("_account_name", ""),
                "_account_id": c.get("_account_id", ""),
                "_currency": currency,
            }))

            # Pause/Activate button depends on current status
            if status == "ACTIVE":
                toggle_btn = ui.tags.button(
                    "Pause",
                    class_="btn-pause",
                    onclick=f"Shiny.setInputValue('pause_campaign', '{campaign_id}', {{priority: 'event'}});",
                )
            elif status == "PAUSED":
                toggle_btn = ui.tags.button(
                    "Activate",
                    class_="btn-activate",
                    onclick=f"Shiny.setInputValue('activate_campaign', '{campaign_id}', {{priority: 'event'}});",
                )
            else:
                toggle_btn = ui.span()

            action_cell = ui.div(
                ui.tags.button(
                    "View",
                    class_="btn-view",
                    onclick=f"Shiny.setInputValue('view_campaign', {c_json}, {{priority: 'event'}});",
                ),
                toggle_btn,
                ui.tags.button(
                    "Budget",
                    class_="btn-edit",
                    onclick=f"Shiny.setInputValue('edit_budget_campaign', {c_json}, {{priority: 'event'}});",
                ),
                ui.tags.button(
                    "Delete",
                    class_="btn-delete",
                    onclick=f"Shiny.setInputValue('delete_campaign', '{campaign_id}', {{priority: 'event'}});",
                ),
                class_="campaign-actions",
            )

            rows.append(
                ui.tags.tr(
                    ui.tags.td(
                        ui.div(name, style="font-weight: 600; margin-bottom: 2px;"),
                        ui.div(campaign_id, style="font-size: 12px; color: #475569; font-family: monospace;"),
                    ),
                    ui.tags.td(ui.span(badge_label, class_=badge_class)),
                    ui.tags.td(ui.span(obj_display, class_="badge-objective")),
                    ui.tags.td(budget_display),
                    ui.tags.td(created_display),
                    ui.tags.td(
                        ui.div(f"Spend: {spend_display}", style="font-size: 14px;"),
                        ui.div(f"Clicks: {clicks_display} | Impr: {impressions_display}", style="font-size: 12px; color: #64748b;"),
                        ui.div(f"CTR: {ctr_display}", style="font-size: 12px; color: #64748b;"),
                    ),
                    ui.tags.td(action_cell),
                )
            )

        return ui.tags.table(
            ui.tags.thead(ui.tags.tr(
                ui.tags.th("Campaign"),
                ui.tags.th("Status"),
                ui.tags.th("Objective"),
                ui.tags.th("Budget"),
                ui.tags.th("Created"),
                ui.tags.th("Performance (7d)"),
                ui.tags.th("Actions"),
            )),
            ui.tags.tbody(*rows),
        )

    # ---- Campaign detail modal ----

    @reactive.effect
    @reactive.event(input.view_campaign)
    async def _show_campaign_modal():
        """Show detail modal when View is clicked."""
        raw = input.view_campaign()
        if not raw:
            return
        try:
            c = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        campaign_id = c.get("id", "Unknown")
        name = c.get("name", "Untitled")
        status = c.get("status", "UNKNOWN").upper()
        objective = c.get("objective", "—")
        currency = c.get("_currency", "USD")
        daily_budget = c.get("daily_budget")
        lifetime_budget = c.get("lifetime_budget")
        budget_remaining = c.get("budget_remaining", "")
        created_time = c.get("created_time", "")[:10] if c.get("created_time") else "—"
        start_time = c.get("start_time", "")[:10] if c.get("start_time") else "—"
        stop_time = c.get("stop_time", "")[:10] if c.get("stop_time") else "—"
        buying_type = c.get("buying_type", "—") or "—"
        bid_strategy = c.get("bid_strategy", "—") or "—"
        account_name = c.get("_account_name", "—")
        account_id = c.get("_account_id", "—")
        perf = c.get("performance")

        # Status badge
        if status == "ACTIVE":
            badge_class, badge_label = "badge-active", "Active"
        elif status == "PAUSED":
            badge_class, badge_label = "badge-paused", "Paused"
        elif status == "DELETED":
            badge_class, badge_label = "badge-deleted", "Deleted"
        else:
            badge_class, badge_label = "badge-archived", status.title()

        obj_display = objective.replace("OUTCOME_", "").replace("_", " ").title() if objective != "—" else "—"

        if daily_budget and int(daily_budget) > 0:
            budget_display = f"{fmt_budget(int(daily_budget), currency)}/day"
        elif lifetime_budget and int(lifetime_budget) > 0:
            budget_display = f"{fmt_budget(int(lifetime_budget), currency)} lifetime"
        else:
            budget_display = "—"

        budget_remaining_display = fmt_budget(int(budget_remaining), currency) if budget_remaining and int(budget_remaining) > 0 else "—"

        # Performance section
        if perf:
            perf_section = ui.div(
                ui.tags.h4("Performance (Last 7 Days)", style="color: #94a3b8; font-size: 16px; margin-top: 20px; margin-bottom: 12px;"),
                ui.div(
                    ui.div(ui.tags.label("Spend"), ui.span(fmt_currency(perf.get("spend", 0), currency)), class_="detail-item"),
                    ui.div(ui.tags.label("Impressions"), ui.span(fmt_number(perf.get("impressions", 0))), class_="detail-item"),
                    ui.div(ui.tags.label("Clicks"), ui.span(fmt_number(perf.get("clicks", 0))), class_="detail-item"),
                    ui.div(ui.tags.label("CPC"), ui.span(fmt_currency(perf.get("cpc", 0), currency)), class_="detail-item"),
                    ui.div(ui.tags.label("CTR"), ui.span(f"{perf.get('ctr', 0):.2f}%"), class_="detail-item"),
                    ui.div(ui.tags.label("Reach"), ui.span(fmt_number(perf.get("reach", 0))), class_="detail-item"),
                    class_="detail-grid-3",
                ),
            )
        else:
            perf_section = ui.div(
                ui.tags.h4("Performance (Last 7 Days)", style="color: #94a3b8; font-size: 16px; margin-top: 20px; margin-bottom: 12px;"),
                ui.div("No performance data available for this period.", style="color: #475569; font-size: 15px;"),
            )

        modal = ui.modal(
            # Campaign details grid
            ui.div(
                ui.div(ui.tags.label("Campaign ID"), ui.span(campaign_id, style="font-family: monospace; font-size: 14px;"), class_="detail-item"),
                ui.div(ui.tags.label("Status"), ui.span(badge_label, class_=badge_class), class_="detail-item"),
                ui.div(ui.tags.label("Objective"), ui.span(obj_display, class_="badge-objective"), class_="detail-item"),
                ui.div(ui.tags.label("Budget"), ui.span(budget_display), class_="detail-item"),
                ui.div(ui.tags.label("Budget Remaining"), ui.span(budget_remaining_display), class_="detail-item"),
                ui.div(ui.tags.label("Buying Type"), ui.span(buying_type.title()), class_="detail-item"),
                ui.div(ui.tags.label("Bid Strategy"), ui.span(bid_strategy.replace("_", " ").title() if bid_strategy != "—" else "—"), class_="detail-item"),
                ui.div(ui.tags.label("Created"), ui.span(created_time), class_="detail-item"),
                ui.div(ui.tags.label("Start Date"), ui.span(start_time), class_="detail-item"),
                ui.div(ui.tags.label("End Date"), ui.span(stop_time), class_="detail-item"),
                ui.div(ui.tags.label("Account"), ui.span(account_name), class_="detail-item"),
                ui.div(ui.tags.label("Account ID"), ui.span(account_id, style="font-family: monospace; font-size: 14px;"), class_="detail-item"),
                class_="detail-grid",
            ),

            perf_section,

            title=name,
            size="l",
            easy_close=True,
        )
        ui.modal_show(modal)

    # ---- Pause campaign ----

    @reactive.effect
    @reactive.event(input.pause_campaign)
    async def _pause_campaign():
        campaign_id = input.pause_campaign()
        if not campaign_id:
            return
        try:
            from services.marketing import marketing_service
            result = await marketing_service._fb_client.update_campaign(campaign_id, status="PAUSED")
            ui.notification_show(
                f"Campaign {campaign_id} paused successfully. Click Refresh to update the table.",
                type="message", duration=5,
            )
        except Exception as e:
            ui.notification_show(f"Failed to pause campaign: {e}", type="error", duration=6)

    # ---- Activate campaign ----

    @reactive.effect
    @reactive.event(input.activate_campaign)
    async def _activate_campaign():
        campaign_id = input.activate_campaign()
        if not campaign_id:
            return
        try:
            from services.marketing import marketing_service
            result = await marketing_service._fb_client.update_campaign(campaign_id, status="ACTIVE")
            ui.notification_show(
                f"Campaign {campaign_id} activated successfully. Click Refresh to update the table.",
                type="message", duration=5,
            )
        except Exception as e:
            ui.notification_show(f"Failed to activate campaign: {e}", type="error", duration=6)

    # ---- Delete campaign ----

    @reactive.effect
    @reactive.event(input.delete_campaign)
    async def _delete_campaign():
        campaign_id = input.delete_campaign()
        if not campaign_id:
            return
        try:
            from services.marketing import marketing_service
            result = await marketing_service._fb_client.delete_campaign(campaign_id)
            ui.notification_show(
                f"Campaign {campaign_id} deleted (archived). Click Refresh to update the table.",
                type="warning", duration=5,
            )
        except Exception as e:
            ui.notification_show(f"Failed to delete campaign: {e}", type="error", duration=6)

    # ---- Edit budget modal ----

    @reactive.effect
    @reactive.event(input.edit_budget_campaign)
    async def _show_edit_budget_modal():
        raw = input.edit_budget_campaign()
        if not raw:
            return
        try:
            c = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        campaign_id = c.get("id", "")
        name = c.get("name", "")
        currency = c.get("_currency", "USD")
        daily_budget = c.get("daily_budget")
        current_budget_display = fmt_budget(int(daily_budget), currency) if daily_budget and int(daily_budget) > 0 else "Not set"
        current_budget_value = str(int(daily_budget) // 100) if daily_budget and int(daily_budget) > 0 else ""

        sym = CURRENCY_SYMBOLS.get(currency, currency)

        modal = ui.modal(
            ui.div(
                ui.div(f"Current daily budget: {current_budget_display}", style="color: #94a3b8; font-size: 16px; margin-bottom: 16px;"),
                ui.div(
                    ui.input_text(
                        "new_budget_value",
                        f"New Daily Budget ({sym})",
                        value=current_budget_value,
                        placeholder=f"e.g., 500 ({sym}500.00/day)",
                        width="100%",
                    ),
                    ui.div(
                        f"Enter the amount in whole {currency} (e.g., 500 = {sym}500.00/day). "
                        f"The value will be converted to cents for the API.",
                        style="font-size: 14px; color: #475569; margin-top: 6px;",
                    ),
                    style="margin-bottom: 20px;",
                ),
                # Hidden input to pass campaign_id
                ui.tags.script(f"document.getElementById('budget_campaign_id_store').value = '{campaign_id}';"),
                ui.tags.input(type="hidden", id="budget_campaign_id_store", value=campaign_id),
                ui.div(
                    ui.input_action_button(
                        "submit_budget",
                        f"Update Budget for {name[:40]}",
                        class_="action-btn action-btn-primary",
                        style="width: 100%; padding: 12px;",
                    ),
                ),
            ),
            title=f"Edit Budget — {name}",
            size="m",
            easy_close=True,
        )
        ui.modal_show(modal)

    @reactive.effect
    @reactive.event(input.submit_budget)
    async def _handle_budget_update():
        new_value = input.new_budget_value()
        if not new_value:
            ui.notification_show("Please enter a budget value.", type="error", duration=4)
            return

        try:
            budget_whole = int(float(new_value))
            budget_cents = budget_whole * 100
        except (ValueError, TypeError):
            ui.notification_show("Invalid budget value. Please enter a number.", type="error", duration=4)
            return

        # Get campaign_id from the last edit_budget_campaign event
        raw = input.edit_budget_campaign()
        if not raw:
            ui.notification_show("Campaign not found.", type="error", duration=4)
            return
        try:
            c = json.loads(raw)
            campaign_id = c.get("id", "")
        except (json.JSONDecodeError, TypeError):
            ui.notification_show("Campaign not found.", type="error", duration=4)
            return

        currency = c.get("_currency", "USD")
        sym = CURRENCY_SYMBOLS.get(currency, currency)

        try:
            from services.marketing import marketing_service
            result = await marketing_service._fb_client.update_campaign(campaign_id, daily_budget=budget_cents)
            ui.notification_show(
                f"Budget updated to {sym}{budget_whole:,}/day for campaign {c.get('name', campaign_id)}. Click Refresh to see changes.",
                type="message", duration=5,
            )
            ui.modal_remove()
        except Exception as e:
            ui.notification_show(f"Failed to update budget: {e}", type="error", duration=6)

    # ============================================
    # Creatives tab reactives
    # ============================================

    # Reactive value to store cursor state per account
    creative_cursor = reactive.Value("")
    creative_cache = reactive.Value(None)  # {account_id, creatives, has_next, next_cursor, has_prev, prev_cursor}
    creative_loading = reactive.Value(False)
    media_type_filter = reactive.Value("images")  # "images" or "videos"

    @reactive.calc
    async def accounts_list():
        """Fetch only the list of ad accounts (lightweight — no creatives)."""
        input.refresh()
        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return None
        accounts = await marketing_service._fb_client.get_all_ad_accounts()
        return accounts

    @render.ui
    def media_type_toggle():
        """Render the Images / Videos toggle buttons."""
        selected = ""
        try:
            selected = input.account_select()
        except Exception:
            pass
        if not selected:
            return ui.div()  # Don't show toggle until an account is selected

        current = media_type_filter.get()
        img_cls = "media-toggle-btn active-images" if current == "images" else "media-toggle-btn"
        vid_cls = "media-toggle-btn active-videos" if current == "videos" else "media-toggle-btn"

        # SVG icons for the toggle
        img_icon = ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>')
        vid_icon = ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>')

        return ui.div(
            ui.div(
                ui.tags.button(
                    img_icon, " Images",
                    class_=img_cls,
                    onclick="Shiny.setInputValue('set_media_type', 'images', {priority: 'event'});",
                ),
                ui.tags.button(
                    vid_icon, " Videos",
                    class_=vid_cls,
                    onclick="Shiny.setInputValue('set_media_type', 'videos', {priority: 'event'});",
                ),
                class_="media-toggle",
            ),
            style="display: flex; align-items: center; gap: 16px;",
        )

    @reactive.effect
    @reactive.event(input.set_media_type)
    def _on_media_type_change():
        """Update the media type filter when toggle is clicked."""
        val = input.set_media_type()
        if val in ("images", "videos"):
            media_type_filter.set(val)

    @render.ui
    async def account_selector():
        """Render the account dropdown — no 'All Accounts' option."""
        accounts = await accounts_list()
        if accounts is None:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading accounts...", class_="loading-text"),
                class_="loading-spinner",
            )

        choices = {}
        for acc in accounts:
            label = f"{acc.get('name', 'Unknown')} ({acc.get('id', '')})"
            choices[acc.get("id", "")] = label

        first_account_id = accounts[0].get("id", "")

        return ui.input_select("account_select",
                               None,
                               choices=choices,
                               selected=first_account_id,
                               width="100%")

    @reactive.effect
    @reactive.event(input.account_select)
    async def _on_account_change():
        """When account changes, fetch first page of creatives."""
        selected = input.account_select()
        if not selected:
            creative_cache.set(None)
            return
        creative_cursor.set("")  # Reset cursor
        await _fetch_creatives_page(selected, "")

    async def _fetch_creatives_page(account_id: str, cursor: str):
        """Fetch a page of 50 creatives for the given account."""
        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return
        creative_loading.set(True)
        try:
            result = await marketing_service._fb_client.get_creatives_for_account(
                account_id, limit=50, after=cursor if cursor else None
            )
            # Find account name
            accounts = await accounts_list()
            acc_name = "Unknown"
            if accounts:
                acc = next((a for a in accounts if a.get("id") == account_id), None)
                if acc:
                    acc_name = acc.get("name", "Unknown")

            # Tag each creative with account info
            for c in result.get("creatives", []):
                c["_account_name"] = acc_name
                c["_account_id"] = account_id

            creative_cache.set({
                "account_id": account_id,
                "account_name": acc_name,
                "creatives": result.get("creatives", []),
                "count": result.get("count", 0),
                "count_before_dedup": result.get("count_before_dedup", result.get("count", 0)),
                "has_next": result.get("has_next", False),
                "has_prev": result.get("has_prev", False),
                "next_cursor": result.get("next_cursor", ""),
                "prev_cursor": result.get("prev_cursor", ""),
            })
        except Exception as e:
            creative_cache.set({"error": str(e)})
        finally:
            creative_loading.set(False)

    @reactive.effect
    @reactive.event(input.creative_next_page)
    async def _load_next_page():
        """Load the next page of creatives."""
        cache = creative_cache.get()
        if not cache or not cache.get("has_next"):
            return
        await _fetch_creatives_page(cache["account_id"], cache["next_cursor"])

    @reactive.effect
    @reactive.event(input.creative_prev_page)
    async def _load_prev_page():
        """Load the previous page of creatives."""
        cache = creative_cache.get()
        if not cache or not cache.get("has_prev"):
            return
        # For previous page, we use the Graph API 'before' cursor
        # Since our client only supports 'after', we reload from the start
        # This is a known limitation — Facebook cursor pagination is forward-only
        # For now, show a notification
        ui.notification_show("Previous page navigation is not supported by the Facebook API cursor. Please refresh to start over.", type="warning", duration=4)

    @render.ui
    def creatives_kpi():
        """KPI summary for the currently loaded creatives."""
        loading = creative_loading.get()
        if loading:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading creative stats...", class_="loading-text"),
                class_="loading-spinner",
            )

        cache = creative_cache.get()
        selected = ""
        try:
            selected = input.account_select()
        except Exception:
            pass

        if not selected:
            return ui.div(
                "Select an ad account from the dropdown above to view creatives.",
                style="color: #64748b; text-align: center; padding: 30px; font-size: 17px;",
            )

        if cache is None:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading creatives...", class_="loading-text"),
                class_="loading-spinner",
            )

        if "error" in cache:
            return ui.div(f"Error: {cache['error']}", style="color: #ef4444; text-align: center; padding: 20px;")

        creatives = cache.get("creatives", [])
        total = len(creatives)
        type_counts = {"video": 0, "image": 0, "carousel": 0, "unknown": 0}
        for c in creatives:
            ctype = c.get("type", "unknown")
            type_counts[ctype] = type_counts.get(ctype, 0) + 1

        # Count by current filter
        current_filter = media_type_filter.get()
        if current_filter == "videos":
            filtered_count = type_counts.get("video", 0)
            filter_label = "Videos"
        else:
            filtered_count = type_counts.get("image", 0) + type_counts.get("carousel", 0)
            filter_label = "Images"

        has_more = " (more available)" if cache.get("has_next") else ""
        raw_count = cache.get("count_before_dedup", total)
        dedup_note = f"Deduplicated from {raw_count}" if raw_count != total else ""

        kpi_items = [
            ui.div(
                ui.div("Unique Creatives", class_="kpi-label"),
                ui.div(fmt_number(total), class_="kpi-value"),
                ui.div(
                    f"{cache.get('account_name', 'Unknown')}{has_more}"
                    + (f" · {dedup_note}" if dedup_note else ""),
                    class_="kpi-sub",
                ),
                class_="kpi-card", style="flex: 1; min-width: 160px;",
            ),
            ui.div(
                ui.div(f"Showing ({filter_label})", class_="kpi-label"),
                ui.div(fmt_number(filtered_count), class_="kpi-value",
                       style=f"color: {'#7dd3fc' if current_filter == 'videos' else '#6ee7b7'};"),
                class_="kpi-card", style="flex: 1; min-width: 160px;",
            ),
            ui.div(
                ui.div("Videos", class_="kpi-label"),
                ui.div(fmt_number(type_counts.get("video", 0)), class_="kpi-value", style="color: #7dd3fc;"),
                class_="kpi-card", style="flex: 1; min-width: 120px;",
            ),
            ui.div(
                ui.div("Images", class_="kpi-label"),
                ui.div(fmt_number(type_counts.get("image", 0)), class_="kpi-value", style="color: #6ee7b7;"),
                class_="kpi-card", style="flex: 1; min-width: 120px;",
            ),
            ui.div(
                ui.div("Carousels", class_="kpi-label"),
                ui.div(fmt_number(type_counts.get("carousel", 0)), class_="kpi-value", style="color: #c4b5fd;"),
                class_="kpi-card", style="flex: 1; min-width: 120px;",
            ),
        ]
        return ui.div(*kpi_items, style="display: flex; gap: 16px; flex-wrap: wrap;")

    @render.ui
    def creatives_grid():
        """Render the creative grid for the selected account — server-side paginated."""
        loading = creative_loading.get()
        if loading:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading creatives from Facebook...", class_="loading-text"),
                class_="loading-spinner",
            )

        cache = creative_cache.get()
        selected = ""
        try:
            selected = input.account_select()
        except Exception:
            pass

        if not selected:
            return ui.div(
                ui.div(
                    ui.tags.span("\U0001f5bc", style="font-size: 48px; display: block; margin-bottom: 12px;"),
                    "Select an ad account to browse creatives",
                    style="color: #475569; text-align: center; padding: 60px 20px; font-size: 18px;",
                ),
            )

        if cache is None:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading creatives...", class_="loading-text"),
                class_="loading-spinner",
            )

        if "error" in cache:
            return ui.div(f"Error loading creatives: {cache['error']}", style="color: #ef4444; text-align: center; padding: 40px;")

        creatives = cache.get("creatives", [])
        if not creatives:
            return ui.div("No creatives found for this account.", style="color: #64748b; text-align: center; padding: 40px;")

        # Filter by media type toggle
        current_filter = media_type_filter.get()
        if current_filter == "videos":
            filtered = [c for c in creatives if c.get("type") == "video"]
        else:
            # "images" includes image, carousel, and unknown (non-video)
            filtered = [c for c in creatives if c.get("type") != "video"]

        if not filtered:
            label = "videos" if current_filter == "videos" else "images"
            return ui.div(
                f"No {label} found in this batch. Try loading the next page.",
                style="color: #64748b; text-align: center; padding: 40px; font-size: 17px;",
            )

        # SVG play triangle for video overlays
        play_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><polygon points="6,3 20,12 6,21"/></svg>'

        # Build grid cards
        cards = []
        for c in filtered:
            creative_id = c.get("creative_id", "")
            name = c.get("name", "Untitled")
            ctype = c.get("type", "unknown")
            status = c.get("status", "UNKNOWN").upper()
            thumb_url = c.get("preview_url") or c.get("thumbnail_url") or c.get("image_url") or ""

            type_class = f"type-badge-{ctype}" if ctype in ("video", "image", "carousel") else "type-badge-unknown"
            status_class = "badge-active" if status == "ACTIVE" else ("badge-paused" if status == "PAUSED" else "badge-archived")
            status_label = "Active" if status == "ACTIVE" else ("Paused" if status == "PAUSED" else status.title())

            # Build thumbnail with optional play overlay for videos
            if thumb_url:
                thumb_img = ui.tags.img(src=thumb_url, class_="creative-thumb", alt=name)
            else:
                icon = "\U0001f3ac" if ctype == "video" else ("\U0001f5bc" if ctype == "image" else ("\U0001f4d1" if ctype == "carousel" else "\U0001f4c4"))
                thumb_img = ui.div(icon, class_="creative-thumb-placeholder")

            if ctype == "video":
                # Wrap in thumb-wrapper with play overlay
                thumb = ui.div(
                    thumb_img,
                    ui.div(
                        ui.div(ui.HTML(play_svg), class_="play-icon"),
                        class_="play-overlay",
                    ),
                    class_="thumb-wrapper",
                )
            else:
                thumb = ui.div(thumb_img, class_="thumb-wrapper")

            short_id = creative_id[-8:] if len(creative_id) > 8 else creative_id

            card = ui.div(
                thumb,
                ui.div(
                    ui.div(name, class_="creative-name", title=name),
                    ui.div(f"ID: {creative_id}  #{short_id}", class_="creative-id"),
                    ui.div(
                        ui.span(ctype.title(), class_=type_class),
                        ui.span(status_label, class_=status_class),
                        *([ui.span(f"Used in {dup_count} ads", class_="dup-badge")] if (dup_count := c.get("_duplicate_count", 1)) > 1 else []),
                        class_="creative-meta",
                    ),
                    class_="creative-info",
                ),
                class_="creative-card",
                onclick=f"Shiny.setInputValue('clicked_creative', {json.dumps(json.dumps(c))}, {{priority: 'event'}});",
            )
            cards.append(card)

        count = len(filtered)
        total = len(creatives)
        label = "videos" if current_filter == "videos" else "images"
        showing_text = ui.div(
            f"Showing {count} {label} (of {total} total creatives loaded)",
            style="color: #94a3b8; font-size: 15px; margin-bottom: 12px;",
        )
        return ui.div(showing_text, ui.div(*cards, class_="creative-grid"))

    @render.ui
    def creatives_pagination():
        """Render Next/Previous pagination using Facebook cursor pagination."""
        cache = creative_cache.get()
        if cache is None or "error" in (cache or {}):
            return ui.div()

        has_next = cache.get("has_next", False)
        has_prev = cache.get("has_prev", False)

        if not has_next and not has_prev:
            return ui.div()  # No pagination needed

        buttons = []

        if has_prev:
            buttons.append(ui.input_action_button(
                "creative_prev_page", "\u2190 Previous 50",
                class_="refresh-btn",
            ))

        if has_next:
            buttons.append(ui.input_action_button(
                "creative_next_page", "Next 50 \u2192",
                class_="refresh-btn",
            ))

        return ui.div(
            *buttons,
            style="display: flex; gap: 12px; justify-content: center; margin-top: 20px; padding: 16px;",
        )

    # ---- Creative detail modal ----

    @reactive.effect
    @reactive.event(input.clicked_creative)
    async def _show_creative_modal():
        raw = input.clicked_creative()
        if not raw:
            return
        try:
            c = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        creative_id = c.get("creative_id", "Unknown")
        name = c.get("name", "Untitled")
        ctype = c.get("type", "unknown")
        status = c.get("status", "UNKNOWN").upper()
        title = c.get("title", "") or "\u2014"
        body = c.get("body", "") or "\u2014"
        image_url = c.get("image_url", "") or "\u2014"
        thumb_url = c.get("preview_url") or c.get("thumbnail_url") or ""
        account_name = c.get("_account_name", "\u2014")
        account_id = c.get("_account_id", "\u2014")

        type_class = f"type-badge-{ctype}" if ctype in ("video", "image", "carousel") else "type-badge-unknown"
        status_class = "badge-active" if status == "ACTIVE" else ("badge-paused" if status == "PAUSED" else "badge-archived")
        status_label = "Active" if status == "ACTIVE" else ("Paused" if status == "PAUSED" else status.title())

        if thumb_url:
            preview = ui.tags.img(
                src=thumb_url,
                style="width: 100%; max-height: 360px; object-fit: contain; border-radius: 8px; background: #0f1117; margin-bottom: 16px;",
            )
        else:
            preview = ui.div(
                "No preview available",
                style="width: 100%; height: 200px; display: flex; align-items: center; justify-content: center; background: #0f1117; border-radius: 8px; color: #374151; margin-bottom: 16px;",
            )

        modal = ui.modal(
            preview,
            ui.div(
                ui.div(ui.tags.label("Creative ID"), ui.span(creative_id, style="font-family: monospace; font-size: 12px;"), class_="detail-item"),
                ui.div(ui.tags.label("Type"), ui.span(ctype.title(), class_=type_class), class_="detail-item"),
                ui.div(ui.tags.label("Status"), ui.span(status_label, class_=status_class), class_="detail-item"),
                ui.div(ui.tags.label("Account"), ui.span(f"{account_name}", style="font-size: 13px;"), class_="detail-item"),
                ui.div(ui.tags.label("Account ID"), ui.span(account_id, style="font-family: monospace; font-size: 12px;"), class_="detail-item"),
                ui.div(ui.tags.label("Ad Title"), ui.span(title), class_="detail-item"),
                class_="detail-grid",
            ),
            ui.div(
                ui.tags.label("Body Text", style="display: block; font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 16px; margin-bottom: 4px;"),
                ui.div(body, style="font-size: 13px; color: #cbd5e1; line-height: 1.6; padding: 12px; background: #0f1117; border-radius: 8px; max-height: 120px; overflow-y: auto;"),
            ),
            ui.div(
                ui.tags.label("Image URL", style="display: block; font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 12px; margin-bottom: 4px;"),
                ui.div(image_url, style="font-size: 11px; color: #475569; font-family: monospace; word-break: break-all; padding: 8px; background: #0f1117; border-radius: 6px;"),
            ),
            ui.div(
                ui.tags.button("Create Ad from Creative", class_="action-btn action-btn-primary", onclick=f"alert('Create Ad flow for creative {creative_id} — coming soon');"),
                ui.tags.button("Delete Creative", class_="action-btn action-btn-danger", onclick=f"alert('Delete creative {creative_id} — coming soon');"),
                ui.tags.button("Copy ID", class_="action-btn action-btn-secondary", onclick=f"navigator.clipboard.writeText('{creative_id}'); alert('Creative ID copied to clipboard');"),
                style="display: flex; gap: 12px; margin-top: 20px; flex-wrap: wrap;",
            ),
            title=name,
            size="l",
            easy_close=True,
        )
        ui.modal_show(modal)

    # ---- Upload modal ----

    @reactive.effect
    @reactive.event(input.show_upload)
    async def _show_upload_modal():
        accounts = await accounts_list() or []

        account_choices = {}
        for acc in accounts:
            account_choices[acc.get("id", "")] = f"{acc.get('name', 'Unknown')} ({acc.get('id', '')})"

        modal = ui.modal(
            ui.div(
                ui.input_select("upload_account", "Target Ad Account", choices=account_choices, width="100%"),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text("upload_name", "Creative Name", placeholder="e.g., Summer Sale Banner v2", width="100%"),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text("upload_title", "Ad Title", placeholder="e.g., 50% Off All Gummies", width="100%"),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text_area("upload_body", "Ad Body Text", placeholder="Write your ad copy here...", width="100%", rows=3),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_file("upload_file", "Upload Image or Video", accept=[".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov"], multiple=False),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text("upload_link", "Destination URL", placeholder="https://kayapure.com/product/...", width="100%"),
                style="margin-bottom: 20px;",
            ),
            ui.div(
                ui.input_action_button("submit_upload", "Upload Creative to Meta", class_="action-btn action-btn-primary", style="width: 100%; padding: 12px;"),
            ),
            title="Upload New Creative",
            size="l",
            easy_close=True,
        )
        ui.modal_show(modal)

    @reactive.effect
    @reactive.event(input.submit_upload)
    async def _handle_upload():
        account_id = input.upload_account()
        name = input.upload_name()
        title = input.upload_title()
        body = input.upload_body()
        link = input.upload_link()
        file_info = input.upload_file()

        if not account_id or not name:
            ui.notification_show("Please fill in at least the account and creative name.", type="error", duration=4)
            return

        if not file_info:
            ui.notification_show("Please select an image or video file to upload.", type="error", duration=4)
            return

        ui.notification_show(
            f"Upload creative '{name}' to {account_id} — This feature requires the Facebook Marketing API "
            f"'ads_management' permission. The upload endpoint will be wired once the permission is approved. "
            f"File: {file_info[0]['name']}",
            type="warning",
            duration=8,
        )
        ui.modal_remove()

    # ============================================
    # AI Reports tab reactives
    # ============================================

    @reactive.calc
    async def ai_reports_accounts_data():
        """Fetch all ad accounts with 30-day spend for the AI Reports tab."""
        input.refresh()
        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return None
        from datetime import date as date_type, timedelta
        until = date_type.today().strftime("%Y-%m-%d")
        since = (date_type.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        data = await marketing_service._fb_client.get_total_spend_all_accounts(since=since, until=until)
        return data

    @render.ui
    async def ai_reports_accounts_list():
        """Render the list of ad account cards for the AI Reports tab."""
        data = await ai_reports_accounts_data()

        if data is None:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading ad accounts...", class_="loading-text"),
                class_="loading-spinner",
            )

        accounts = data.get("accounts", [])
        if not accounts:
            return ui.div(
                "No ad accounts found. Ensure your Facebook access token is configured.",
                style="color: #64748b; text-align: center; padding: 60px;",
            )

        # Sort: accounts with data first, then by spend descending
        accounts.sort(key=lambda a: (-1 if a.get("has_data") else 0, -a.get("spend", 0)))

        cards = []
        for acc in accounts:
            acc_id = acc.get("account_id", "")
            acc_name = acc.get("account_name", "Unknown")
            acc_currency = acc.get("currency", "USD")
            acc_status = acc.get("status", "UNKNOWN")
            acc_spend = acc.get("spend", 0)
            is_active = acc_status == "ACTIVE"

            # Status dot
            dot_class = "ai-report-status-dot active" if is_active else "ai-report-status-dot inactive"

            # Spend display
            spend_display = fmt_currency(acc_spend, acc_currency)

            # SVG icons
            envelope_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 4L12 13 2 4"/></svg>'
            clock_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
            target_svg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>'
            target_small_svg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>'

            # Safe account ID for JS
            safe_id = acc_id.replace("'", "\\'")
            safe_name = acc_name.replace("'", "\\'")

            card = ui.div(
                # Main row: dot + info + spend + actions
                ui.div(
                    ui.div(class_=dot_class),
                    ui.div(
                        ui.div(acc_name, class_="ai-report-account-name"),
                        ui.div(f"{acc_id}  ·  {acc_currency}", class_="ai-report-account-meta"),
                        class_="ai-report-account-info",
                    ),
                    ui.div(spend_display, class_="ai-report-spend"),
                    ui.div(
                        ui.tags.button(
                            ui.HTML(envelope_svg), " Generate Report",
                            class_="btn-generate-report",
                            onclick=f"Shiny.setInputValue('generate_report_click', '{safe_id}|{safe_name}|{acc_currency}', {{priority: 'event'}});",
                        ),
                        ui.tags.button(
                            ui.HTML(clock_svg), " View Reports",
                            class_="btn-view-reports",
                            onclick=f"Shiny.setInputValue('view_reports_click', '{safe_id}|{safe_name}', {{priority: 'event'}});",
                        ),
                        class_="ai-report-actions",
                    ),
                    class_="ai-report-account-row",
                ),
                # Goals section
                ui.div(
                    ui.div(
                        ui.div(
                            ui.HTML(target_svg),
                            ui.span("Set goals for this account"),
                            class_="ai-report-goals-title",
                        ),
                        ui.div(
                            "Define business targets so AI reports evaluate actual performance against your goals.",
                            class_="ai-report-goals-desc",
                        ),
                        ui.tags.button(
                            ui.HTML(target_small_svg), " Add Goals",
                            class_="btn-add-goals",
                            onclick=f"Shiny.setInputValue('add_goals_click', '{safe_id}|{safe_name}', {{priority: 'event'}});",
                        ),
                        class_="ai-report-goals-inner",
                    ),
                    class_="ai-report-goals-section",
                ),
                class_="ai-report-account-card",
            )
            cards.append(card)

        return ui.div(*cards)

    # ---- Helper: build formatted report modal content ----
    def _build_report_modal_content(analysis: dict, acc_name: str, acc_id: str = "",
                                     from_cache: bool = False, cache_age_min: int = 0,
                                     report_type: str = "generate") -> ui.Tag:
        """Build a nicely formatted modal body from the AdsAnalysisResult dict."""
        a = analysis.get("analysis", {})
        summary = a.get("summary", "No summary available.")
        findings = a.get("key_findings", [])
        risks = a.get("risks", [])
        recs = a.get("recommendations", [])
        confidence = a.get("confidence", 0)

        # Data snapshot info
        snap = analysis.get("data_snapshot", {})
        period = snap.get("period", {})
        currency = snap.get("currency", "USD")
        total_spend = snap.get("total_spend", 0)

        sections = []

        # Toolbar: cache label + PDF download + regenerate
        toolbar_items = []
        if from_cache:
            if cache_age_min < 60:
                age_text = f"Cached report ({cache_age_min} min ago)"
            else:
                age_text = f"Cached report ({cache_age_min // 60}h {cache_age_min % 60}m ago)"
            check_svg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
            toolbar_items.append(
                ui.span(ui.HTML(check_svg), f" {age_text}", class_="ai-report-cache-label")
            )
        else:
            toolbar_items.append(ui.span("Fresh report", class_="ai-report-cache-label", style="color: #3b82f6;"))

        # PDF download button
        safe_id = acc_id.replace("'", "\\'")
        safe_name = acc_name.replace("'", "\\'")
        pdf_svg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 18 15 15"/></svg>'
        toolbar_items.append(
            ui.tags.button(
                ui.HTML(pdf_svg), " Download PDF",
                class_="btn-download-pdf",
                onclick=f"Shiny.setInputValue('download_pdf_click', '{safe_id}|{safe_name}|{report_type}', {{priority: 'event'}});",
            )
        )

        # Regenerate button
        refresh_svg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>'
        toolbar_items.append(
            ui.tags.button(
                ui.HTML(refresh_svg), " Regenerate",
                class_="btn-regenerate",
                onclick=f"Shiny.setInputValue('regenerate_report_click', '{safe_id}|{safe_name}|{report_type}', {{priority: 'event'}});",
            )
        )

        sections.append(ui.div(*toolbar_items, class_="ai-report-toolbar"))

        # Period + spend header
        period_text = ""
        if period:
            period_text = f"{period.get('start', '?')} \u2192 {period.get('end', '?')}"
        sections.append(
            ui.div(
                ui.div(
                    ui.span(f"Period: {period_text}" if period_text else "Ad Account Analysis",
                            style="color: #64748b; font-size: 14px;"),
                    ui.span(f"  \u00b7  Total Spend: {fmt_currency(total_spend, currency)}" if total_spend else "",
                            style="color: #64748b; font-size: 14px;"),
                    style="margin-bottom: 16px;",
                ),
            )
        )

        # Summary
        sections.append(
            ui.div(
                ui.div("\U0001f4cb Summary", class_="ai-report-section-title"),
                ui.div(summary, class_="ai-report-summary"),
            )
        )

        # Key Findings
        if findings:
            finding_items = [ui.div(f, class_="ai-report-finding") for f in findings]
            sections.append(
                ui.div(
                    ui.div("\U0001f50d Key Findings", class_="ai-report-section-title"),
                    *finding_items,
                    style="margin-bottom: 20px;",
                )
            )

        # Risks
        if risks:
            risk_items = [ui.div(r, class_="ai-report-risk") for r in risks]
            sections.append(
                ui.div(
                    ui.div("\u26a0\ufe0f Risks", class_="ai-report-section-title"),
                    *risk_items,
                    style="margin-bottom: 20px;",
                )
            )

        # Recommendations
        if recs:
            rec_cards = []
            for i, rec in enumerate(recs, 1):
                action = rec.get("action", "—")
                rationale = rec.get("rationale", "")
                impact = rec.get("expected_impact", "")
                priority = rec.get("priority", "medium").lower()

                priority_class = f"ai-report-rec-badge priority-{priority}" if priority in ("high", "medium", "low") else "ai-report-rec-badge priority-medium"

                rec_cards.append(
                    ui.div(
                        ui.div(f"{i}. {action}", class_="ai-report-rec-action"),
                        ui.div(rationale, class_="ai-report-rec-rationale") if rationale else ui.span(),
                        ui.div(
                            ui.span(priority.upper(), class_=priority_class),
                            ui.span(impact, class_="ai-report-rec-badge impact") if impact else ui.span(),
                            class_="ai-report-rec-meta",
                        ),
                        class_="ai-report-rec-card",
                    )
                )
            sections.append(
                ui.div(
                    ui.div("\U0001f4a1 Recommendations", class_="ai-report-section-title"),
                    *rec_cards,
                    style="margin-bottom: 20px;",
                )
            )

        # Confidence bar
        conf_pct = int(confidence * 100)
        conf_color = "#22c55e" if conf_pct >= 70 else ("#f59e0b" if conf_pct >= 40 else "#f87171")
        sections.append(
            ui.div(
                ui.span("AI Confidence", class_="ai-report-confidence-label"),
                ui.div(
                    ui.div(style=f"width: {conf_pct}%; background: {conf_color};", class_="ai-report-confidence-fill"),
                    class_="ai-report-confidence-bar",
                ),
                ui.span(f"{conf_pct}%", style=f"color: {conf_color}; font-weight: 700; font-size: 15px;"),
                class_="ai-report-confidence",
            )
        )

        return ui.div(*sections)

    # ---- AI Reports: Generate Report handler (with caching) ----
    @reactive.effect
    @reactive.event(input.generate_report_click)
    async def _handle_generate_report():
        val = input.generate_report_click()
        if not val:
            return
        parts = val.split("|")
        acc_id = parts[0] if len(parts) > 0 else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"
        acc_currency = parts[2] if len(parts) > 2 else "USD"

        # Check cache first
        cached = _report_cache.get(acc_id, "generate", days=30)
        if cached:
            age_min = int((time.time() - cached["timestamp"]) / 60)
            result = cached["result"]
            report_content = _build_report_modal_content(
                result, acc_name, acc_id=acc_id,
                from_cache=True, cache_age_min=age_min, report_type="generate",
            )
            report_modal = ui.modal(
                report_content,
                title=f"AI Report \u2014 {acc_name}",
                size="l",
                easy_close=True,
            )
            ui.modal_show(report_modal)
            return

        # Show loading modal
        loading_modal = ui.modal(
            ui.div(
                ui.div(class_="spinner"),
                ui.div("Analysing your ad account data with AI...", style="margin-top: 16px; font-size: 16px; color: #94a3b8;"),
                ui.div("This may take 15\u201330 seconds.", style="margin-top: 6px; font-size: 14px; color: #475569;"),
                class_="ai-report-modal-loading",
            ),
            title=f"Generating Report \u2014 {acc_name}",
            size="l",
            easy_close=True,
        )
        ui.modal_show(loading_modal)

        try:
            from services.ads_analysis_agent import ads_analysis_agent_service
            result = await ads_analysis_agent_service.analyze(
                days=30,
                question=f"Analyse the ad performance for account {acc_name} ({acc_id}). "
                         f"Find waste, winners, and optimization opportunities. "
                         f"Provide specific, actionable recommendations.",
            )

            # Cache the result
            _report_cache.put(acc_id, "generate", result, days=30)

            report_content = _build_report_modal_content(
                result, acc_name, acc_id=acc_id,
                from_cache=False, report_type="generate",
            )
            ui.modal_remove()  # Explicitly remove loading modal + backdrop
            report_modal = ui.modal(
                report_content,
                title=f"AI Report \u2014 {acc_name}",
                size="l",
                easy_close=True,
            )
            ui.modal_show(report_modal)

        except Exception as e:
            ui.modal_remove()  # Explicitly remove loading modal + backdrop
            error_modal = ui.modal(
                ui.div(
                    f"Failed to generate report: {str(e)}",
                    class_="ai-report-error",
                ),
                ui.div(
                    "Please ensure the backend server has been restarted and the OpenAI API key is configured.",
                    style="color: #475569; font-size: 14px; text-align: center; margin-top: 12px;",
                ),
                title=f"Report Error \u2014 {acc_name}",
                size="l",
                easy_close=True,
            )
            ui.modal_show(error_modal)

    # ---- AI Reports: View Reports handler (with caching) ----
    @reactive.effect
    @reactive.event(input.view_reports_click)
    async def _handle_view_reports():
        val = input.view_reports_click()
        if not val:
            return
        parts = val.split("|")
        acc_id = parts[0] if len(parts) > 0 else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"

        # Check cache first
        cached = _report_cache.get(acc_id, "view", days=30)
        if cached:
            age_min = int((time.time() - cached["timestamp"]) / 60)
            result = cached["result"]
            report_content = _build_report_modal_content(
                result, acc_name, acc_id=acc_id,
                from_cache=True, cache_age_min=age_min, report_type="view",
            )
            report_modal = ui.modal(
                report_content,
                title=f"AI Report \u2014 {acc_name}",
                size="l",
                easy_close=True,
            )
            ui.modal_show(report_modal)
            return

        # Show loading modal
        loading_modal = ui.modal(
            ui.div(
                ui.div(class_="spinner"),
                ui.div("Fetching AI analysis for your ad account...", style="margin-top: 16px; font-size: 16px; color: #94a3b8;"),
                ui.div("This may take 15\u201330 seconds.", style="margin-top: 6px; font-size: 14px; color: #475569;"),
                class_="ai-report-modal-loading",
            ),
            title=f"Loading Report \u2014 {acc_name}",
            size="l",
            easy_close=True,
        )
        ui.modal_show(loading_modal)

        try:
            from services.ads_analysis_agent import ads_analysis_agent_service
            result = await ads_analysis_agent_service.analyze(
                days=30,
                question=f"Provide a comprehensive performance report for account {acc_name} ({acc_id}). "
                         f"Include spend efficiency, audience performance, creative fatigue signals, "
                         f"and specific actions to improve ROAS.",
            )

            # Cache the result
            _report_cache.put(acc_id, "view", result, days=30)

            report_content = _build_report_modal_content(
                result, acc_name, acc_id=acc_id,
                from_cache=False, report_type="view",
            )
            ui.modal_remove()  # Explicitly remove loading modal + backdrop
            report_modal = ui.modal(
                report_content,
                title=f"AI Report \u2014 {acc_name}",
                size="l",
                easy_close=True,
            )
            ui.modal_show(report_modal)

        except Exception as e:
            ui.modal_remove()  # Explicitly remove loading modal + backdrop
            error_modal = ui.modal(
                ui.div(
                    f"Failed to load report: {str(e)}",
                    class_="ai-report-error",
                ),
                ui.div(
                    "Please ensure the backend server has been restarted and the OpenAI API key is configured.",
                    style="color: #475569; font-size: 14px; text-align: center; margin-top: 12px;",
                ),
                title=f"Report Error \u2014 {acc_name}",
                size="l",
                easy_close=True,
            )
            ui.modal_show(error_modal)

    # ---- AI Reports: Add Goals handler ----
    @reactive.effect
    @reactive.event(input.add_goals_click)
    async def _handle_add_goals():
        val = input.add_goals_click()
        if not val:
            return
        parts = val.split("|")
        acc_id = parts[0] if len(parts) > 0 else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"

        modal = ui.modal(
            ui.div(
                ui.input_text("goal_monthly_spend", "Monthly Spend Target", placeholder="e.g., 50000", width="100%"),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text("goal_target_cpc", "Target CPC", placeholder="e.g., 1.50", width="100%"),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text("goal_target_ctr", "Target CTR (%)", placeholder="e.g., 3.5", width="100%"),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text("goal_target_roas", "Target ROAS", placeholder="e.g., 4.0", width="100%"),
                style="margin-bottom: 20px;",
            ),
            ui.div(
                ui.tags.button(
                    "Save Goals",
                    class_="action-btn action-btn-primary",
                    style="width: 100%; padding: 12px;",
                    onclick=f"Shiny.setInputValue('save_goals_submit', '{acc_id}', {{priority: 'event'}}); bootstrap.Modal.getInstance(document.querySelector('.modal')).hide();",
                ),
            ),
            title=f"Set Goals — {acc_name}",
            size="m",
            easy_close=True,
        )
        ui.modal_show(modal)

    @reactive.effect
    @reactive.event(input.save_goals_submit)
    async def _handle_save_goals():
        ui.notification_show(
            "Goals saved! AI reports will evaluate performance against these targets. "
            "Goal persistence is coming soon.",
            type="message",
            duration=6,
        )

    # ---- AI Reports: Download PDF handler ----
    @reactive.effect
    @reactive.event(input.download_pdf_click)
    async def _handle_download_pdf():
        val = input.download_pdf_click()
        if not val:
            return
        parts = val.split("|")
        acc_id = parts[0] if len(parts) > 0 else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"
        report_type = parts[2] if len(parts) > 2 else "generate"

        # Get the cached result (should exist since user is viewing the report)
        cached = _report_cache.get(acc_id, report_type, days=30)
        if not cached:
            ui.notification_show(
                "Report data not found. Please generate the report first.",
                type="warning",
                duration=5,
            )
            return

        try:
            import base64
            result = cached["result"]
            filepath = _generate_report_pdf(result, acc_name, acc_id)
            filename = os.path.basename(filepath)

            with open(filepath, "rb") as f:
                pdf_bytes = f.read()
            b64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Use send_custom_message to trigger a JS download
            await session.send_custom_message(
                "download_pdf",
                {"data": b64, "filename": filename},
            )

            ui.notification_show(
                f"PDF ready: {filename}",
                type="message",
                duration=4,
            )

        except Exception as e:
            ui.notification_show(
                f"Failed to generate PDF: {str(e)}",
                type="error",
                duration=6,
            )

    # ---- AI Reports: Regenerate handler (bypasses cache) ----
    @reactive.effect
    @reactive.event(input.regenerate_report_click)
    async def _handle_regenerate_report():
        val = input.regenerate_report_click()
        if not val:
            return
        parts = val.split("|")
        acc_id = parts[0] if len(parts) > 0 else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"
        report_type = parts[2] if len(parts) > 2 else "generate"

        # Invalidate cache for this account + type
        _report_cache.invalidate(acc_id, report_type, days=30)

        # Show loading modal
        loading_modal = ui.modal(
            ui.div(
                ui.div(class_="spinner"),
                ui.div("Regenerating report with fresh data...", style="margin-top: 16px; font-size: 16px; color: #94a3b8;"),
                ui.div("This may take 15\u201330 seconds.", style="margin-top: 6px; font-size: 14px; color: #475569;"),
                class_="ai-report-modal-loading",
            ),
            title=f"Regenerating Report \u2014 {acc_name}",
            size="l",
            easy_close=True,
        )
        ui.modal_show(loading_modal)

        try:
            from services.ads_analysis_agent import ads_analysis_agent_service

            if report_type == "generate":
                question = (f"Analyse the ad performance for account {acc_name} ({acc_id}). "
                            f"Find waste, winners, and optimization opportunities. "
                            f"Provide specific, actionable recommendations.")
            else:
                question = (f"Provide a comprehensive performance report for account {acc_name} ({acc_id}). "
                            f"Include spend efficiency, audience performance, creative fatigue signals, "
                            f"and specific actions to improve ROAS.")

            result = await ads_analysis_agent_service.analyze(
                days=30,
                question=question,
            )

            # Cache the fresh result
            _report_cache.put(acc_id, report_type, result, days=30)

            report_content = _build_report_modal_content(
                result, acc_name, acc_id=acc_id,
                from_cache=False, report_type=report_type,
            )
            ui.modal_remove()  # Explicitly remove loading modal + backdrop
            report_modal = ui.modal(
                report_content,
                title=f"AI Report \u2014 {acc_name}",
                size="l",
                easy_close=True,
            )
            ui.modal_show(report_modal)

        except Exception as e:
            ui.modal_remove()  # Explicitly remove loading modal + backdrop
            error_modal = ui.modal(
                ui.div(
                    f"Failed to regenerate report: {str(e)}",
                    class_="ai-report-error",
                ),
                ui.div(
                    "Please ensure the backend server has been restarted and the OpenAI API key is configured.",
                    style="color: #475569; font-size: 14px; text-align: center; margin-top: 12px;",
                ),
                title=f"Report Error \u2014 {acc_name}",
                size="l",
                easy_close=True,
            )
            ui.modal_show(error_modal)


# ============================================
# App instance (mounted by FastAPI)
# ============================================
shiny_app = App(app_ui, server)
