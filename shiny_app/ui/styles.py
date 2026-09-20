"""Global dashboard CSS for the Shiny Meta Ads UI."""

APP_CSS = """
/* ========== KayaPure theme tokens (storefront-aligned) ========== */
:root,
[data-theme="light"] {
  --kp-kaya: #09594D;
  --kp-pure: #00A38C;
  --kp-cta: #0A584C;
  --kp-ink: #17352F;
  --kp-mint: #D9F6F1;
  --kp-mint-soft: #EFFBF8;
  --kp-page: #F7F7F7;
  --bg: #F7F7F7;
  --surface: #FFFFFF;
  --surface-2: #F3F7F6;
  --surface-3: #EFFBF8;
  --border: #E5EFED;
  --border-strong: #CDE4DF;
  --text: #17352F;
  --text-strong: #0B2E28;
  --text-muted: #5F746F;
  --text-subtle: #7A8F8A;
  --accent: #00A38C;
  --accent-soft: rgba(0, 163, 140, 0.12);
  --brand-kaya: #09594D;
  --brand-pure: #00A38C;
  --primary-btn: #0A584C;
  --primary-btn-hover: #084840;
  --danger: #DC2626;
  --warning: #D97706;
  --success: #059669;
  --shadow: 0 10px 30px rgba(9, 89, 77, 0.08);
  --rail-width: 248px;
  --topbar-height: 72px;
  --close-filter: none;
}
[data-theme="dark"] {
  --kp-kaya: #0E7A6A;
  --kp-pure: #00A38C;
  --kp-cta: #00A38C;
  --kp-ink: #E2E8F0;
  --kp-mint: #14352F;
  --kp-mint-soft: #102820;
  --kp-page: #0F1117;
  --bg: #0F1117;
  --surface: #1A1D27;
  --surface-2: #161924;
  --surface-3: #12151F;
  --border: #2D3348;
  --border-strong: #3B455F;
  --text: #E2E8F0;
  --text-strong: #F1F5F9;
  --text-muted: #94A3B8;
  --text-subtle: #64748B;
  --accent: #00A38C;
  --accent-soft: rgba(0, 163, 140, 0.18);
  --brand-kaya: #7DD3C0;
  --brand-pure: #00A38C;
  --primary-btn: #0A584C;
  --primary-btn-hover: #00A38C;
  --danger: #F87171;
  --warning: #FCD34D;
  --success: #6EE7B7;
  --shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
  --close-filter: invert(1);
}

/* Shiny busy pulse overlay */
.shiny-busy { opacity: 0.6; transition: opacity 0.3s; }
.recalculating { opacity: 0.4; }
html, body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 16px;
}
body { margin: 0; }
.container-fluid { padding: 0 !important; max-width: none !important; }

/* ========== App shell / CRM drawer ========== */
.app-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
}
.app-nav-rail {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1040;
  width: var(--rail-width);
  height: 100vh;
  background: var(--surface);
  border-right: 1px solid var(--border);
  box-shadow: none;
  transform: translateX(0);
  transition: transform 0.24s ease, box-shadow 0.24s ease;
}
.app-nav-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px 16px;
}
.app-nav-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.app-nav-top-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.app-nav-brand {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
}
.brand-kaya { color: var(--brand-kaya); }
.brand-pure { color: var(--brand-pure); }
.brand-suffix { color: var(--text-muted); font-weight: 700; }
.app-nav-kicker {
  margin: 6px 0 18px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-subtle);
}
.app-nav-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  overflow-y: auto;
  max-height: calc(100vh - 220px);
  padding-right: 4px;
}
.app-nav-item {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text);
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.app-nav-item:hover {
  background: var(--kp-mint);
  color: var(--kp-kaya);
}
.app-nav-item[data-nav="profit_leak_scanner"] {
  font-weight: 700;
}
/* Highlight by stable button IDs — Shiny rewrites action-button classes on click */
.app-nav-item.is-active,
body[data-active-nav="profit_leak_scanner"] #nav_profit_leak_scanner,
body[data-active-nav="daily_diagnosis"] #nav_daily_diagnosis,
body[data-active-nav="creative_intelligence"] #nav_creative_intelligence,
body[data-active-nav="funnel_reconciliation"] #nav_funnel_reconciliation,
body[data-active-nav="supplement_economics"] #nav_supplement_economics,
body[data-active-nav="ai_reports"] #nav_ai_reports,
body[data-active-nav="saleor_mcp"] #nav_saleor_mcp,
body[data-active-nav="postex"] #nav_postex {
  background: var(--kp-mint) !important;
  color: var(--kp-kaya) !important;
  border-color: var(--border-strong) !important;
  box-shadow: inset 3px 0 0 var(--brand-pure) !important;
}
.app-nav-footer { margin-top: auto; padding-top: 16px; }
.app-nav-footnote {
  margin: 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-subtle);
}
.app-content {
  flex: 1;
  min-width: 0;
  margin-left: var(--rail-width);
  display: flex;
  flex-direction: column;
  transition: margin-left 0.24s ease;
}
.app-nav-collapse-btn {
  display: inline-flex;
  min-width: 36px;
  padding: 8px;
  font-size: 16px;
}
.app-nav-close-btn { display: none; }
.app-nav-open-btn {
  display: inline-flex;
  font-size: 18px;
  min-width: 40px;
  padding: 8px;
}
.app-nav-backdrop {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 1035;
  background: rgba(9, 89, 77, 0.28);
}
.app-topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  min-height: var(--topbar-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 24px;
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
}
.header-left { display: flex; align-items: center; gap: 12px; min-width: 0; }
.header-copy { min-width: 0; }
.header-title { font-size: 22px; font-weight: 700; color: var(--text-strong); }
.header-sub { font-size: 16px; color: var(--text-muted); margin-top: 4px; line-height: 1.45; }
.header-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.app-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--kp-kaya);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.app-icon-btn:hover {
  background: var(--kp-mint);
  border-color: var(--border-strong);
  color: var(--brand-pure);
}
.theme-toggle-btn { min-width: 88px; }
.refresh-btn {
  background: var(--primary-btn);
  color: #fff;
  border: none;
  padding: 10px 16px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
}
.refresh-btn:hover { background: var(--primary-btn-hover); }
.app-main { padding: 24px; }
.tab-content { padding-top: 0; }

/* Desktop: slide rail away for full-width canvas */
body.nav-collapsed .app-nav-rail {
  transform: translateX(calc(-1 * var(--rail-width) - 8px));
  box-shadow: none;
  pointer-events: none;
}
body.nav-collapsed .app-content {
  margin-left: 0;
}

@media (max-width: 960px) {
  .app-nav-rail {
    transform: translateX(-105%);
    box-shadow: var(--shadow);
    pointer-events: auto;
  }
  body.nav-collapsed .app-nav-rail {
    transform: translateX(-105%);
  }
  body.nav-drawer-open .app-nav-rail {
    transform: translateX(0);
    pointer-events: auto;
    box-shadow: var(--shadow);
  }
  body.nav-drawer-open .app-nav-backdrop { display: block; }
  .app-content,
  body.nav-collapsed .app-content { margin-left: 0; }
  .app-nav-collapse-btn { display: none; }
  .app-nav-close-btn { display: inline-flex; }
  .app-main { padding: 16px; }
  .theme-toggle-label { display: none; }
  .theme-toggle-btn { min-width: 40px; }
}

.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow); }
.card-header { border-bottom: 1px solid var(--border); padding: 14px 18px; font-weight: 600; font-size: 16px; color: var(--text-muted); background: var(--surface-2); }
.card-body { padding: 16px; }
.kpi-value { font-size: 34px; font-weight: 700; color: var(--text-strong); letter-spacing: -0.5px; }
.kpi-label { font-size: 16px; color: var(--text-subtle); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.kpi-sub { font-size: 15px; color: var(--text-muted); margin-top: 2px; }
.kpi-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.badge-active { background: #065f46; color: #6ee7b7; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
.badge-paused { background: #78350f; color: #fcd34d; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
.badge-archived { background: #7f1d1d; color: #fca5a5; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
.badge-deleted { background: #4a1d1d; color: #f87171; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
table { width: 100%; border-collapse: collapse; font-size: 17px; }
th { text-align: left; padding: 12px 14px; color: var(--text-subtle); font-weight: 600; font-size: 15px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }
td { padding: 12px 14px; border-bottom: 1px solid var(--surface-2); color: var(--text); }
.metric-label-wrap {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    max-width: 100%;
    overflow: visible !important;
}
.metric-tip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 15px;
    height: 15px;
    border-radius: 9999px;
    border: 1px solid var(--text-subtle);
    color: var(--text-muted);
    font-size: 10px;
    font-weight: 700;
    line-height: 1;
    cursor: help;
    flex-shrink: 0;
    text-transform: none;
    letter-spacing: 0;
    position: relative;
    z-index: 2;
}
.metric-tip:hover,
.metric-tip:focus {
    border-color: var(--text-muted);
    color: var(--text);
    background: var(--surface-2);
    outline: none;
}
.metric-floating-tip {
    position: fixed;
    z-index: 10000;
    max-width: 280px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--border-strong);
    background: var(--surface-3);
    color: var(--text);
    font-size: 12px;
    font-weight: 500;
    line-height: 1.35;
    letter-spacing: 0;
    text-transform: none;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
    pointer-events: none;
    white-space: normal;
}
.table-scroll-wrap thead th {
    overflow: visible;
}
tr:hover td { background: var(--surface-2); }
.table-scroll-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin-top: 8px;
}
.table-scroll-wrap table {
    width: max-content;
    min-width: 100%;
}
.table-scroll-wrap th,
.table-scroll-wrap td {
    white-space: nowrap;
}
.header-bar { background: linear-gradient(135deg, var(--surface) 0%, var(--bg) 100%); border-bottom: 1px solid var(--border); padding: 20px 24px; margin: -16px -16px 24px -16px; border-radius: 0; }
.header-title { font-size: 26px; font-weight: 700; color: var(--text-strong); }
.header-sub { font-size: 17px; color: var(--text-subtle); margin-top: 4px; }
.source-badge { background: var(--accent-soft); color: var(--accent); padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
.refresh-btn { background: var(--primary-btn); color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 17px; font-weight: 600; }
.refresh-btn:hover { background: var(--primary-btn-hover); }
.period-info { font-size: 16px; color: var(--text-subtle); }
/* Tab styling */
.nav-tabs { border-bottom: 1px solid var(--border); }
.nav-tabs .nav-link { color: var(--text-subtle); border: none; padding: 14px 24px; font-weight: 600; font-size: 18px; }
.nav-tabs .nav-link:hover { color: var(--text); border: none; background: var(--surface); }
.nav-tabs .nav-link.active { color: var(--accent); border: none; border-bottom: 2px solid var(--accent); background: transparent; }
.tab-content { padding-top: 24px; }
/* Creative grid */
.creative-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
.creative-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    overflow: hidden; cursor: pointer; transition: all 0.2s ease;
}
.creative-card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
.creative-thumb {
    width: 100%; height: 200px; object-fit: cover; display: block;
    background: var(--bg);
}
.creative-thumb-placeholder {
    width: 100%; height: 200px; display: flex; align-items: center; justify-content: center;
    background: var(--bg); color: #374151; font-size: 48px;
}
.creative-info { padding: 14px; }
.creative-name { font-size: 17px; font-weight: 600; color: var(--text); margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.creative-id { font-size: 14px; color: var(--text-subtle); font-family: monospace; margin-bottom: 8px; }
.creative-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.type-badge-video { background: var(--accent-soft); color: var(--accent); padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
.type-badge-image { background: #1a3a2a; color: #6ee7b7; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
.type-badge-carousel { background: #3b1f5e; color: #c4b5fd; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
.type-badge-unknown { background: #374151; color: #9ca3af; padding: 3px 10px; border-radius: 9999px; font-size: 14px; font-weight: 600; }
/* Toolbar */
.toolbar {
    display: flex; align-items: center; gap: 16px; margin-bottom: 24px;
    padding: 16px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
}
.toolbar label { color: var(--text-muted); font-size: 17px; font-weight: 600; }
.toolbar select {
    background: var(--bg); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 10px 14px; font-size: 17px; min-width: 300px;
}
.toolbar select:focus { border-color: var(--accent); outline: none; }
/* Upload area */
.upload-area {
    border: 2px dashed var(--border); border-radius: 12px; padding: 32px;
    text-align: center; background: var(--bg); margin-bottom: 24px;
    transition: border-color 0.2s;
}
.upload-area:hover { border-color: var(--accent); }
.upload-icon { font-size: 36px; color: #374151; margin-bottom: 8px; }
.upload-text { color: var(--text-subtle); font-size: 17px; }
/* Loading spinner */
.shiny-output-error { color: #f87171; padding: 20px; }
.loading-spinner {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 60px 20px; color: var(--text-subtle);
}
.spinner {
    width: 48px; height: 48px; border: 4px solid var(--border); border-top: 4px solid var(--accent);
    border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 16px;
}
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.loading-text { font-size: 16px; color: var(--text-subtle); }
/* Pagination */
.pagination-bar {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    padding: 20px 0; margin-top: 16px;
}
.pagination-bar .page-info { color: var(--text-muted); font-size: 16px; margin: 0 16px; }
.pagination-bar button {
    background: var(--surface); color: var(--text); border: 1px solid var(--border);
    padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 15px; font-weight: 600;
    transition: all 0.2s;
}
.pagination-bar button:hover { background: var(--border); border-color: var(--accent); }
.pagination-bar button:disabled { opacity: 0.3; cursor: not-allowed; }
.pagination-bar button.active-page { background: var(--primary-btn); border-color: var(--primary-btn); color: white; }
/* Modal overrides */
.modal-content { background: var(--surface) !important; border: 1px solid var(--border) !important; color: var(--text) !important; }
.modal-header { border-bottom: 1px solid var(--border) !important; }
.modal-footer { border-top: 1px solid var(--border) !important; }
.modal-title { color: var(--text-strong) !important; }
.btn-close { filter: invert(1); }
/* Action buttons */
.action-btn {
    padding: 10px 20px; border-radius: 6px; font-size: 17px; font-weight: 600;
    border: none; cursor: pointer; transition: background 0.2s;
}
.action-btn-primary { background: var(--primary-btn); color: white; }
.action-btn-primary:hover { background: var(--primary-btn-hover); }
.action-btn-danger { background: #dc2626; color: white; }
.action-btn-danger:hover { background: #b91c1c; }
.action-btn-warning { background: #d97706; color: white; }
.action-btn-warning:hover { background: #b45309; }
.action-btn-success { background: #059669; color: white; }
.action-btn-success:hover { background: #047857; }
.action-btn-secondary { background: #374151; color: var(--text); }
.action-btn-secondary:hover { background: #4b5563; }
/* Detail grid in modal */
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
.detail-grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 16px; }
.detail-item label { display: block; font-size: 15px; color: var(--text-subtle); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
.detail-item span { font-size: 18px; color: var(--text); }
.campaign-thumb-cell {
  width: 72px;
  padding-right: 8px !important;
  vertical-align: middle;
}
.campaign-thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  display: block;
}
.campaign-thumb-placeholder {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  border: 1px dashed var(--border);
  background: var(--surface-2);
  color: var(--text-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}
.campaign-modal-preview {
  width: 100%;
  max-height: 280px;
  object-fit: contain;
  border-radius: 10px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  margin-bottom: 16px;
}
.creative-engagement {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-muted);
}
.creative-engagement span {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 9999px;
  padding: 2px 8px;
  font-weight: 600;
}
.creative-date {
  font-size: 12px;
  color: var(--text-subtle);
  margin-top: 4px;
}
.creatives-sort-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.creatives-sort-bar label {
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 600;
  margin: 0;
  white-space: nowrap;
}
.creatives-sort-bar select,
.creatives-sort-bar .form-select {
  min-width: 180px;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
}
/* Campaign action buttons in table */
.campaign-name {
  font-weight: 600;
  margin-bottom: 2px;
}
.campaign-name-link {
  color: var(--brand-kaya);
  text-decoration: none;
}
.campaign-name-link:hover {
  text-decoration: underline;
  color: var(--accent);
}
.campaign-id {
  font-size: 12px;
  color: #475569;
  font-family: monospace;
}
.campaigns-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.campaigns-table-wrap table {
  width: max-content;
  min-width: 100%;
}
.campaigns-table-wrap th:last-child,
.campaigns-table-wrap td:last-child {
  position: sticky;
  right: 0;
  z-index: 2;
  background: var(--surface);
  min-width: 340px;
  width: 340px;
  box-shadow: -6px 0 12px rgba(9, 89, 77, 0.08);
}
.campaigns-table-wrap tr:hover td:last-child {
  background: var(--surface-2);
}
.campaign-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.campaign-actions button,
.campaign-actions .btn-view,
.campaign-actions .btn-ai-report,
.campaign-actions .btn-pause,
.campaign-actions .btn-activate,
.campaign-actions .btn-edit,
.campaign-actions .btn-delete {
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  padding: 6px 12px !important;
  border-radius: 6px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  line-height: 1.2 !important;
  border: 1px solid transparent !important;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  white-space: nowrap;
  opacity: 1 !important;
  visibility: visible !important;
  min-height: 28px;
  box-shadow: none !important;
}
.btn-view {
  background: var(--kp-mint-soft) !important;
  color: var(--kp-kaya) !important;
  border-color: var(--border-strong) !important;
}
.btn-view:hover { background: var(--kp-mint) !important; color: var(--brand-pure) !important; }
.btn-ai-report {
  background: rgba(0, 163, 140, 0.14) !important;
  color: var(--kp-kaya) !important;
  border-color: var(--accent) !important;
  font-weight: 700 !important;
}
.btn-ai-report:hover {
  background: var(--kp-mint) !important;
  color: var(--brand-pure) !important;
}
.btn-pause { background: #FEF3C7 !important; color: #92400E !important; border-color: #FCD34D !important; }
.btn-pause:hover { background: #FDE68A !important; }
.btn-activate { background: #D1FAE5 !important; color: #065F46 !important; border-color: #6EE7B7 !important; }
.btn-activate:hover { background: #A7F3D0 !important; }
.btn-edit { background: var(--kp-kaya) !important; color: #FFFFFF !important; border-color: var(--kp-kaya) !important; }
.btn-edit:hover { background: var(--brand-pure) !important; border-color: var(--brand-pure) !important; color: #FFFFFF !important; }
.btn-delete { background: #FEE2E2 !important; color: #991B1B !important; border-color: #FCA5A5 !important; }
.btn-delete:hover { background: #FECACA !important; }
[data-theme="dark"] .campaigns-table-wrap th:last-child,
[data-theme="dark"] .campaigns-table-wrap td:last-child {
  background: var(--surface);
  box-shadow: -6px 0 12px rgba(0, 0, 0, 0.35);
}
[data-theme="dark"] .btn-view {
  background: rgba(0, 163, 140, 0.18) !important;
  color: #7DD3C0 !important;
  border-color: rgba(0, 163, 140, 0.35) !important;
}
[data-theme="dark"] .btn-pause { background: #78350F !important; color: #FCD34D !important; border-color: #92400E !important; }
[data-theme="dark"] .btn-activate { background: #065F46 !important; color: #6EE7B7 !important; border-color: #047857 !important; }
[data-theme="dark"] .btn-edit { background: #334155 !important; color: #F1F5F9 !important; border-color: #475569 !important; }
[data-theme="dark"] .btn-delete { background: #7F1D1D !important; color: #FCA5A5 !important; border-color: #991B1B !important; }
/* Objective badge */
.badge-objective { background: var(--surface-2); color: var(--text-muted); padding: 3px 10px; border-radius: 9999px; font-size: 13px; font-weight: 600; }
/* Media type toggle */
.media-toggle {
    display: flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
}
.media-toggle-btn {
    padding: 8px 20px; font-size: 15px; font-weight: 600; cursor: pointer;
    border: none; background: transparent; color: var(--text-subtle);
    transition: all 0.2s ease; display: flex; align-items: center; gap: 6px;
}
.media-toggle-btn:hover { color: var(--text); background: var(--surface-2); }
.media-toggle-btn.active-images {
    background: #1a3a2a; color: #6ee7b7; box-shadow: inset 0 0 0 1px #6ee7b7;
}
.media-toggle-btn.active-videos {
    background: var(--accent-soft); color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent);
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
    background: var(--surface-2); color: var(--text-muted); padding: 3px 10px; border-radius: 9999px;
    font-size: 13px; font-weight: 600; white-space: nowrap;
}
/* AI Reports tab */
.ai-reports-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
    margin-bottom: 20px;
}
.ai-reports-header h3 { color: var(--text-strong); font-size: 28px; font-weight: 700; margin: 0; line-height: 1.25; }
.ai-reports-header .subtitle { color: var(--text-subtle); font-size: 18px; margin-top: 8px; line-height: 1.6; max-width: 720px; }
.ai-reports-featured-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 9999px;
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.18), rgba(234, 88, 12, 0.18));
    color: #ea580c;
    border: 1px solid rgba(245, 158, 11, 0.45);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.ai-reports-filter-bar {
    display: flex;
    align-items: flex-end;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 16px;
    padding: 14px 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
}
.ai-reports-custom-dates {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: flex-end;
}
.ai-reports-custom-field label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    margin-bottom: 4px;
}
.ai-reports-custom-field input[type="date"],
.ai-reports-custom-field .form-control {
    min-width: 160px;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 12px;
}
.ai-reports-sort-note {
    color: var(--text-subtle);
    font-size: 13px;
    margin: 0 0 12px 4px;
}
.ai-report-account-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    margin-bottom: 20px; overflow: hidden;
}
.account-campaigns {
    margin: 0 20px 16px 48px;
    border: 1px solid var(--border);
    border-left: 3px solid var(--brand-pure);
    border-radius: 10px;
    background: var(--surface-2);
    overflow: hidden;
}
.btn-account-campaigns-toggle {
    width: 100%;
    display: flex !important;
    align-items: center;
    justify-content: flex-start !important;
    gap: 14px;
    background: var(--surface-2) !important;
    color: var(--text-strong) !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 14px 16px !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    text-align: left;
    cursor: pointer;
    box-shadow: none !important;
    min-height: 56px;
}
.account-campaigns-chevron {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    border-radius: 8px;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--kp-kaya);
}
.account-campaigns-chevron-icon {
    display: block;
    transition: transform 0.15s ease;
}
.account-campaigns.is-open .account-campaigns-chevron-icon {
    transform: rotate(180deg);
}
.account-campaigns-toggle-copy {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    min-width: 0;
}
.account-campaigns-toggle-title {
    font-size: 15px;
    font-weight: 800;
    color: var(--text-strong);
    letter-spacing: 0.01em;
}
.account-campaigns-toggle-sub {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
}
.btn-account-campaigns-toggle:hover {
    background: color-mix(in srgb, var(--surface-2) 55%, var(--kp-mint)) !important;
}
.account-campaigns-body {
    max-height: 520px;
    overflow: auto;
    border-top: 1px solid var(--border);
    padding: 12px 14px 16px;
    background: var(--bg);
}
.account-campaigns-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 10px;
}
.account-campaigns-note {
    color: var(--text-subtle);
    font-size: 13px;
    margin: 0;
}
.account-campaigns-sort {
    display: flex;
    align-items: center;
    gap: 8px;
}
.account-campaigns-sort-label {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.account-campaigns-sort-chip {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 9999px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
}
.account-campaigns-sort-chip:hover {
    border-color: var(--border-strong);
}
.account-campaigns-sort-chip.is-active {
    background: var(--kp-mint);
    color: var(--kp-kaya);
    border-color: var(--border-strong);
}
.account-campaigns-empty {
    color: var(--text-muted);
    text-align: center;
    padding: 32px 16px;
    font-size: 14px;
}
.account-campaigns-body .campaigns-table-wrap th:last-child,
.account-campaigns-body .campaigns-table-wrap td:last-child {
    background: var(--bg);
}
.account-campaigns-body.loading-spinner {
    min-height: 120px;
    padding: 24px 16px;
}
.campaign-goal-cell {
    min-width: 140px;
}
.campaign-goal-primary {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-strong);
}
.campaign-goal-secondary {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
}
.ai-report-account-row {
    display: flex; align-items: center; padding: 24px 28px; gap: 24px;
}
.ai-report-status-dot {
    width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0;
}
.ai-report-status-dot.active { background: #22c55e; }
.ai-report-status-dot.inactive { background: var(--text-subtle); }
.ai-report-account-info { flex: 1; min-width: 0; }
.ai-report-account-name { font-size: 20px; font-weight: 700; color: var(--text-strong); margin-bottom: 4px; }
.ai-report-account-meta { font-size: 14px; color: var(--text-subtle); font-family: monospace; }
.ai-report-spend {
    font-size: 26px; font-weight: 700; color: var(--text-strong); white-space: nowrap;
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
    background: transparent; color: var(--text); border: 1px solid var(--text-subtle);
    padding: 12px 24px; border-radius: 8px; font-size: 16px; font-weight: 600;
    cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s;
}
.btn-view-reports:hover { border-color: var(--text-muted); background: var(--surface-2); }
.ai-report-goals-section {
    border-top: 1px solid var(--border); padding: 20px 28px;
    background: rgba(30, 34, 53, 0.5);
}
.ai-report-goals-inner {
    border: 1px solid var(--border); border-radius: 10px; padding: 20px 24px;
    background: var(--surface-2);
}
.ai-report-goals-title {
    display: flex; align-items: center; gap: 12px; margin-bottom: 6px;
}
.ai-report-goals-title span { font-size: 17px; font-weight: 600; color: var(--text); }
.ai-report-goals-desc { font-size: 15px; color: var(--text-subtle); margin-bottom: 14px; }
.btn-add-goals {
    background: transparent; color: #f59e0b; border: 1px solid #f59e0b;
    padding: 8px 20px; border-radius: 20px; font-size: 15px; font-weight: 600;
    cursor: pointer; display: inline-flex; align-items: center; gap: 6px; transition: all 0.2s;
}
.btn-add-goals:hover { background: rgba(245, 158, 11, 0.1); }
.ai-report-table-header {
    display: flex; padding: 12px 28px; border-bottom: 1px solid var(--border);
    background: var(--surface-2); border-radius: 10px 10px 0 0;
}
.ai-report-col-header {
    font-size: 13px; font-weight: 600; color: var(--text-subtle);
    text-transform: uppercase; letter-spacing: 0.5px;
}
/* AI Report modal */
.ai-report-modal-loading {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 60px 20px; color: var(--text-subtle);
}
.ai-report-summary {
    font-size: 16px; color: var(--text); line-height: 1.7; padding: 16px 20px;
    background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px;
    margin-bottom: 20px;
}
.ai-report-section-title {
    font-size: 15px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 10px; margin-top: 4px;
    display: flex; align-items: center; gap: 8px;
}
.ai-report-finding {
    padding: 10px 16px; background: var(--surface-2); border-left: 3px solid var(--accent);
    border-radius: 0 8px 8px 0; margin-bottom: 8px; font-size: 15px;
    color: var(--text); line-height: 1.5;
}
.ai-report-risk {
    padding: 10px 16px; background: #1c1520; border-left: 3px solid #f87171;
    border-radius: 0 8px 8px 0; margin-bottom: 8px; font-size: 15px;
    color: #fca5a5; line-height: 1.5;
}
.ai-report-rec-card {
    background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px;
    padding: 16px 20px; margin-bottom: 12px;
}
.ai-report-rec-action {
    font-size: 16px; font-weight: 700; color: var(--text-strong); margin-bottom: 6px;
}
.ai-report-rec-rationale {
    font-size: 14px; color: var(--text-muted); line-height: 1.5; margin-bottom: 8px;
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
.ai-report-rec-badge.impact { background: var(--accent-soft); color: var(--accent); }
.ai-report-confidence {
    display: flex; align-items: center; gap: 10px; margin-top: 16px;
    padding: 12px 16px; background: var(--surface-2); border-radius: 8px;
}
.ai-report-confidence-bar {
    flex: 1; height: 8px; background: var(--border); border-radius: 4px; overflow: hidden;
}
.ai-report-confidence-fill {
    height: 100%; border-radius: 4px;
    transition: width 0.5s ease;
}
.ai-report-confidence-label {
    font-size: 14px; color: var(--text-muted); font-weight: 600; white-space: nowrap;
}
.ai-report-error {
    padding: 20px; background: #1c1520; border: 1px solid #7f1d1d; border-radius: 10px;
    color: #fca5a5; font-size: 15px; text-align: center;
}
.ai-report-toolbar {
    display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
    padding: 12px 16px; background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 10px; flex-wrap: wrap;
}
.ai-report-cache-label {
    font-size: 13px; color: #22c55e; font-weight: 600;
    display: flex; align-items: center; gap: 6px; flex: 1;
}
.btn-download-pdf {
    background: linear-gradient(135deg, #3b82f6 0%, var(--primary-btn-hover) 100%);
    color: white; border: none; padding: 8px 20px; border-radius: 8px;
    font-size: 14px; font-weight: 700; cursor: pointer;
    display: flex; align-items: center; gap: 6px; transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}
.btn-download-pdf:hover { filter: brightness(1.08); }
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
.date-range-bar label { color: var(--text-muted); font-size: 15px; font-weight: 600; white-space: nowrap; }
.date-range-bar select {
    background: var(--bg); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 8px 14px; font-size: 15px; min-width: 180px;
}
.date-range-bar select:focus { border-color: var(--accent); outline: none; }

/* ========== Dashboard overview ========== */
.dash-overview {
    max-width: 1120px;
}
.dash-toolbar {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
    margin-bottom: 28px;
}
.dash-kicker {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--brand-pure);
    margin-bottom: 6px;
}
.dash-title {
    margin: 0;
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.04em;
    color: var(--text-strong);
    line-height: 1.15;
}
.dash-filter {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    flex-wrap: wrap;
}
.dash-filter-select,
.dash-filter-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.dash-filter-select .shiny-input-container,
.dash-filter-select .form-group,
.dash-filter-field .shiny-input-container,
.dash-filter-field .form-group {
    margin: 0;
    width: auto;
}
.dash-filter-select .control-label,
.dash-filter-field .control-label {
    display: none;
}
.dash-filter-select > label,
.dash-filter-field > label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-subtle);
    margin: 0;
}
.dash-filter-select select,
.dash-filter-select .form-select,
.dash-filter-field input[type="date"],
.dash-filter-field .form-control {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 9px 14px;
    font-size: 14px;
    font-weight: 600;
    min-width: 176px;
    box-shadow: 0 1px 0 rgba(9, 89, 77, 0.04);
}
.dash-filter-select select:focus,
.dash-filter-select .form-select:focus,
.dash-filter-field input[type="date"]:focus,
.dash-filter-field .form-control:focus {
    border-color: var(--accent);
    outline: none;
    box-shadow: 0 0 0 3px var(--accent-soft);
}
.dash-filter-custom {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    flex-wrap: wrap;
}
.dash-hero {
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(1200px 240px at -10% -40%, rgba(0, 163, 140, 0.18), transparent 55%),
        linear-gradient(180deg, var(--kp-mint-soft) 0%, var(--surface) 72%);
    border: 1px solid var(--border);
    border-radius: 24px;
    padding: 36px 40px 32px;
    margin-bottom: 28px;
    box-shadow: var(--shadow);
}
.dash-hero::before {
    content: "";
    position: absolute;
    left: 0;
    top: 18px;
    bottom: 18px;
    width: 4px;
    border-radius: 999px;
    background: var(--brand-pure);
}
.dash-hero-label {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
}
.dash-hero .metric-tip {
    width: 16px;
    height: 16px;
    font-size: 10px;
}
.dash-hero-value {
    margin-top: 10px;
    font-size: 64px;
    font-weight: 800;
    letter-spacing: -0.06em;
    line-height: 1.02;
    color: var(--text-strong);
    font-variant-numeric: tabular-nums;
}
.dash-hero-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 14px;
}
.dash-hero-chip {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 999px;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 13px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}
.dash-hero-period {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
    color: var(--text-muted);
    font-size: 14px;
    font-weight: 600;
}
.dash-hero-dot { color: var(--text-subtle); }
.dash-group {
    margin-bottom: 24px;
}
.dash-group-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-subtle);
    margin: 0 0 12px 4px;
}
.dash-metrics {
    display: grid;
    gap: 14px;
}
.dash-metrics-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.dash-metrics-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.dash-metric {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 22px 22px 20px;
    min-height: 124px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 18px;
    transition: border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.dash-metric:hover {
    border-color: var(--border-strong);
    box-shadow: 0 10px 24px rgba(9, 89, 77, 0.06);
    transform: translateY(-1px);
}
.dash-metric-label {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
}
.dash-metric .metric-tip {
    width: 15px;
    height: 15px;
    font-size: 10px;
}
.dash-metric-value {
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -0.045em;
    line-height: 1.1;
    color: var(--text-strong);
    font-variant-numeric: tabular-nums;
    word-break: break-word;
}
.dash-empty {
    color: var(--text-subtle);
    text-align: center;
    padding: 64px 16px;
    font-size: 16px;
    background: var(--surface);
    border: 1px dashed var(--border-strong);
    border-radius: 18px;
}
@media (max-width: 1100px) {
    .dash-metrics-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .dash-metrics-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .dash-hero-value { font-size: 52px; }
}
@media (max-width: 760px) {
    .dash-toolbar { align-items: flex-start; }
    .dash-hero { padding: 28px 22px 24px; }
    .dash-hero-value { font-size: 42px; }
    .dash-metrics-3,
    .dash-metrics-4 { grid-template-columns: 1fr 1fr; }
    .dash-metric { min-height: 0; }
    .dash-metric-value { font-size: 26px; }
}
@media (max-width: 520px) {
    .dash-metrics-3,
    .dash-metrics-4 { grid-template-columns: 1fr; }
}

.amazon-help {
    color: var(--text-muted);
    font-size: 14px;
    line-height: 1.5;
    margin: -8px 0 20px;
    max-width: 52rem;
}
.amazon-toolbar-filters {
    align-items: flex-end;
    margin-bottom: 14px;
}
.amazon-job-fields {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: flex-end;
}
.amazon-url-field,
.amazon-run-field {
    min-width: min(420px, 100%);
}
.amazon-run-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
}
.amazon-run-chip {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 6px 12px;
}
.amazon-product-heading {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--text-strong);
    margin: 8px 0 16px;
}
.amazon-kpi-row { margin-bottom: 20px; }
.amazon-review-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 24px;
}
.amazon-review-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 16px 18px;
}
.amazon-review-title {
    font-weight: 700;
    color: var(--text-strong);
}
.amazon-review-body {
    margin-top: 8px;
    color: var(--text);
    font-size: 14px;
    line-height: 1.55;
    white-space: pre-wrap;
}
.amazon-run-select {
    min-width: min(420px, 100%);
}
.amazon-analysis {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 20px 22px;
    margin-bottom: 24px;
}
.amazon-analysis-loading {
    min-height: 80px;
}
.amazon-status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    min-height: 40px;
}
.amazon-status-dot {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.amazon-status-on { color: var(--success); }
.amazon-status-off { color: var(--warning); }
.amazon-status-id {
    font-size: 12px;
    color: var(--text-subtle);
    font-weight: 600;
}
.amazon-search-field .shiny-input-container,
.amazon-search-field .form-group {
    margin: 0;
    width: auto;
}
.amazon-search-field .control-label { display: none; }
.amazon-search-field input[type="text"],
.amazon-search-field input[type="number"],
.amazon-search-field .form-control {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 9px 14px;
    font-size: 14px;
    font-weight: 600;
    min-width: 160px;
}
.amazon-search-field input[type="text"]:focus,
.amazon-search-field input[type="number"]:focus,
.amazon-search-field .form-control:focus {
    border-color: var(--accent);
    outline: none;
    box-shadow: 0 0 0 3px var(--accent-soft);
}
.amazon-search-btn {
    background: var(--primary-btn);
    color: #fff;
    border: none;
    border-radius: 999px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 700;
    min-height: 40px;
    cursor: pointer;
}
.amazon-search-btn:hover { background: var(--primary-btn-hover); }
.amazon-pager {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin: 4px 0 14px;
}
.amazon-page-meta {
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 600;
    margin-right: auto;
}
.amazon-page-btn {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
}
.amazon-page-btn:hover {
    border-color: var(--accent);
    color: var(--kp-kaya);
}
.amazon-table-wrap {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 4px 8px 8px;
    box-shadow: var(--shadow);
}
.amazon-table { width: 100%; border-collapse: collapse; }
.amazon-table th {
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-subtle);
    padding: 14px 12px;
}
.amazon-table td {
    padding: 14px 12px;
    vertical-align: middle;
    color: var(--text);
}
.amazon-title {
    font-weight: 700;
    color: var(--text-strong);
    max-width: 320px;
    white-space: normal;
    line-height: 1.35;
}
.amazon-meta {
    font-size: 12px;
    color: var(--text-subtle);
    margin-top: 4px;
}
.amazon-num { font-variant-numeric: tabular-nums; font-weight: 600; }
.amazon-thumb {
    width: 48px;
    height: 48px;
    object-fit: cover;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--surface-2);
}
.amazon-thumb-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-subtle);
    font-size: 12px;
}
@media (max-width: 760px) {
    .amazon-toolbar-filters { width: 100%; }
}

/* Amazon Compliance workflow */
.ac-page { max-width: 1100px; }
.ac-product-select { min-width: 280px; }
.ac-product-card {
    margin: 16px 0 20px;
    padding: 16px 18px;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--surface);
}
.ac-version-note {
    margin-top: 10px;
    font-size: 12px;
    color: var(--text-subtle);
    line-height: 1.45;
}
.ac-progress-block { margin-bottom: 18px; }
.ac-progress-metric { margin-bottom: 12px; }
.ac-stage-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.ac-stage-chip {
    border: 1px solid var(--border);
    background: var(--surface-2);
    color: var(--text-muted);
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 12px;
    cursor: pointer;
}
.ac-stage-chip.is-active {
    border-color: var(--accent);
    color: var(--text-strong);
    background: var(--accent-soft);
}
.ac-stage-chip.is-complete {
    border-color: var(--success);
    color: var(--success);
}
.ac-stepper {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 8px;
    margin: 8px 0 18px;
}
.ac-step-btn {
    display: flex;
    flex-direction: column;
    gap: 4px;
    align-items: flex-start;
    text-align: left;
    padding: 12px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
}
.ac-step-btn:hover { border-color: var(--border-strong); }
.ac-step-btn.is-active {
    border-color: var(--accent);
    box-shadow: inset 3px 0 0 var(--brand-pure);
    background: var(--kp-mint-soft);
}
.ac-step-num {
    font-size: 11px;
    font-weight: 700;
    color: var(--text-subtle);
}
.ac-step-label {
    font-size: 13px;
    font-weight: 600;
    line-height: 1.3;
}
.ac-stage-panel {
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--surface);
    padding: 18px;
}
.ac-stage-header { margin-bottom: 16px; }
.ac-stage-title {
    margin: 4px 0 8px;
    font-size: 22px;
    color: var(--text-strong);
}
.ac-item-list { display: flex; flex-direction: column; gap: 12px; }
.ac-item-card {
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px;
    background: var(--surface-2);
}
.ac-item-card.status-done { border-left: 3px solid var(--success); }
.ac-item-card.status-doing { border-left: 3px solid var(--accent); }
.ac-item-card.status-blocked { border-left: 3px solid var(--warning); }
.ac-item-card.status-na { opacity: 0.72; }
.ac-item-title {
    font-weight: 700;
    color: var(--text-strong);
    margin-bottom: 6px;
}
.ac-item-detail,
.ac-item-why,
.ac-item-evidence {
    font-size: 13px;
    line-height: 1.45;
    color: var(--text-muted);
    margin-top: 6px;
}
.ac-item-label { font-weight: 600; color: var(--text); }
.ac-status-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 12px;
}
.ac-status-btn {
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-muted);
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 12px;
    cursor: pointer;
}
.ac-status-btn.is-active {
    border-color: var(--accent);
    color: var(--text-strong);
    background: var(--accent-soft);
    font-weight: 600;
}
@media (max-width: 900px) {
    .ac-stepper { grid-template-columns: 1fr 1fr; }
}

[data-theme="dark"] .dash-hero {
    background:
        radial-gradient(900px 220px at -8% -30%, rgba(0, 163, 140, 0.22), transparent 58%),
        linear-gradient(180deg, var(--kp-mint-soft) 0%, var(--surface) 78%);
    box-shadow: none;
}
[data-theme="dark"] .dash-metric:hover {
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
}
[data-theme="dark"] .dash-filter-select select,
[data-theme="dark"] .dash-filter-select .form-select,
[data-theme="dark"] .dash-filter-field input[type="date"],
[data-theme="dark"] .dash-filter-field .form-control {
    box-shadow: none;
}

.btn-close { filter: var(--close-filter); }
.source-badge { background: var(--accent-soft); color: var(--brand-kaya); padding: 3px 10px; border-radius: 9999px; font-size: 13px; font-weight: 700; }
.header-bar { display: none; } /* legacy */
.nav-tabs { display: none !important; }
.toolbar {
  background: var(--surface);
  border: 1px solid var(--border);
}
.toolbar label { color: var(--text-muted); }
.toolbar select {
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
}
.toolbar select:focus { border-color: var(--accent); }
table { color: var(--text); }
th { color: var(--text-subtle); border-bottom: 1px solid var(--border); }
td { border-bottom: 1px solid var(--border); color: var(--text); }
tr:hover td { background: var(--surface-2); }
.metric-tip {
  border-color: var(--border-strong);
  color: var(--text-muted);
}
.metric-tip:hover, .metric-tip:focus {
  border-color: var(--accent);
  color: var(--text-strong);
  background: var(--surface-2);
}
.metric-floating-tip {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow);
}
.modal-content { background: var(--surface) !important; border: 1px solid var(--border) !important; color: var(--text) !important; }
.modal-header { border-bottom: 1px solid var(--border) !important; }
.modal-footer { border-top: 1px solid var(--border) !important; }
.modal-title { color: var(--text-strong) !important; }
.loading-spinner, .loading-text { color: var(--text-subtle); }
.spinner { border-color: var(--border); border-top-color: var(--accent); }

/* Profit Leak Scanner */
.pls-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
    margin-bottom: 20px;
}
.pls-header h3 { color: var(--text-strong); font-size: 28px; font-weight: 700; margin: 0; line-height: 1.25; }
.pls-header .subtitle { color: var(--text-subtle); font-size: 18px; margin-top: 8px; max-width: 720px; line-height: 1.6; }
.pls-featured-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 9999px;
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.16), rgba(5, 150, 105, 0.16));
    color: #059669;
    border: 1px solid rgba(16, 185, 129, 0.4);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.pls-controls {
    display: flex;
    align-items: flex-end;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 20px;
    padding: 14px 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
}
.pls-scan-btn { min-width: 120px; }
.pls-summary-card {
    display: flex;
    align-items: stretch;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
    padding: 24px;
    margin-bottom: 24px;
    border-radius: 14px;
    border: 1px solid var(--border);
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
}
.pls-summary-card.pls-summary-empty { border-style: dashed; }
.pls-summary-card.pls-summary-error { border-color: rgba(248, 113, 113, 0.45); }
.pls-summary-kicker {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-subtle);
    margin-bottom: 8px;
}
.pls-summary-amount {
    font-size: 32px;
    font-weight: 800;
    color: var(--text-strong);
    line-height: 1.1;
}
.pls-summary-title { font-size: 20px; font-weight: 700; color: var(--text-strong); margin-bottom: 6px; }
.pls-summary-sub { font-size: 17px; color: var(--text-subtle); line-height: 1.55; }
.pls-summary-aside {
    flex: 1;
    min-width: 220px;
    max-width: 360px;
    padding: 12px 14px;
    border-radius: 10px;
    background: var(--surface);
    border: 1px solid var(--border);
}
.pls-summary-note-heading {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}
.pls-summary-note-title {
    font-size: 20px;
    font-weight: 800;
    color: var(--text-strong);
    line-height: 1.2;
}
.pls-diagnosis-info-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 9999px;
    border: 1px solid var(--border-strong);
    background: var(--surface-2);
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 800;
    line-height: 1;
    cursor: pointer;
    padding: 0;
    flex-shrink: 0;
}
.pls-diagnosis-info-btn:hover,
.pls-diagnosis-info-btn:focus {
    border-color: #059669;
    color: #059669;
    background: rgba(16, 185, 129, 0.1);
    outline: none;
}
.pls-diagnosis-info-btn-disabled {
    opacity: 0.45;
    cursor: not-allowed;
}
.pls-diagnosis-details-link {
    background: none;
    border: none;
    padding: 0;
    color: #059669;
    font-size: 13px;
    font-weight: 600;
    text-decoration: underline;
    cursor: pointer;
}
.pls-diagnosis-details-link:hover,
.pls-diagnosis-details-link:focus {
    color: #047857;
    outline: none;
}
.pls-diagnosis-modal-intro {
    font-size: 14px;
    color: var(--text-muted);
    line-height: 1.55;
    margin-bottom: 16px;
}
.pls-diagnosis-modal-context {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 10px;
    margin-bottom: 18px;
}
.pls-diagnosis-context-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--surface-2);
}
.pls-diagnosis-context-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-subtle);
}
.pls-diagnosis-context-value {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-strong);
}
.pls-diagnosis-modal-section-title {
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 10px;
}
.pls-diagnosis-modal-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 52vh;
    overflow-y: auto;
    padding-right: 4px;
}
.pls-diagnosis-reason-item {
    padding: 14px 16px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--surface);
}
.pls-diagnosis-reason-top {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 8px;
}
.pls-diagnosis-rank {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 9999px;
    background: var(--kp-mint);
    color: var(--kp-kaya);
    font-size: 12px;
    font-weight: 800;
    flex-shrink: 0;
}
.pls-diagnosis-reason-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-strong);
    line-height: 1.35;
}
.pls-diagnosis-reason-meta {
    font-size: 12px;
    color: var(--text-subtle);
    margin-top: 2px;
}
.pls-diagnosis-reason-text {
    font-size: 14px;
    color: var(--text);
    line-height: 1.5;
    margin-bottom: 10px;
}
.pls-diagnosis-evidence-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-subtle);
    margin-bottom: 4px;
}
.pls-diagnosis-evidence-list {
    margin: 0;
    padding-left: 18px;
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.45;
}
.pls-diagnosis-evidence-block { margin-top: 8px; }
.pls-diagnosis-empty {
    font-size: 14px;
    color: var(--text-subtle);
    line-height: 1.5;
    padding: 12px;
    border-radius: 8px;
    border: 1px dashed var(--border);
}
.pls-summary-note { font-size: 17px; color: var(--text-subtle); line-height: 1.55; }
.pls-board-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-strong);
    margin-bottom: 14px;
}
.pls-board { display: flex; flex-direction: column; gap: 14px; }
.pls-finding-card {
    padding: 18px 20px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
}
.pls-finding-card[data-severity="critical"] { border-left: 4px solid #f87171; }
.pls-finding-card[data-severity="high"] { border-left: 4px solid #fb923c; }
.pls-finding-card[data-severity="medium"] { border-left: 4px solid #fbbf24; }
.pls-finding-card[data-severity="low"] { border-left: 4px solid #94a3b8; }
.pls-finding-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}
.pls-rank {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 9999px;
    background: var(--kp-mint);
    color: var(--kp-kaya);
    font-size: 13px;
    font-weight: 800;
    flex-shrink: 0;
}
.pls-finding-head { flex: 1; min-width: 200px; }
.pls-finding-title { font-size: 17px; font-weight: 700; color: var(--text-strong); margin-bottom: 6px; }
.pls-finding-meta { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; color: var(--text-subtle); }
.pls-finding-account { font-weight: 600; color: var(--text-muted); }
.pls-finding-category {
    padding: 2px 8px;
    border-radius: 9999px;
    background: var(--surface-2);
    border: 1px solid var(--border);
}
.pls-impact { text-align: right; min-width: 180px; }
.pls-impact-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-subtle); }
.pls-impact-value { font-size: 18px; font-weight: 800; color: #059669; margin-top: 4px; }
.pls-diagnosis { font-size: 17px; color: var(--text); line-height: 1.55; margin-bottom: 10px; }
.pls-recommendation {
    font-size: 17px;
    color: var(--text-muted);
    line-height: 1.5;
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    margin-bottom: 12px;
}
.pls-evidence {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 8px;
    margin-bottom: 10px;
}
.pls-evidence-row {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 10px;
    border-radius: 8px;
    background: var(--surface-2);
    border: 1px solid var(--border);
}
.pls-evidence-label { font-size: 11px; font-weight: 700; color: var(--text-subtle); text-transform: uppercase; letter-spacing: 0.04em; }
.pls-evidence-value { font-size: 13px; color: var(--text); }
.pls-empty-state {
    text-align: center;
    padding: 48px 24px;
    border: 1px dashed var(--border);
    border-radius: 12px;
    background: var(--surface);
}
.pls-empty-title { font-size: 20px; font-weight: 700; color: var(--text-strong); margin-bottom: 8px; }
.pls-empty-sub { font-size: 17px; color: var(--text-subtle); max-width: 520px; margin: 0 auto; line-height: 1.55; }
.pls-summary-saved { font-size: 14px; color: #059669; margin-top: 8px; font-weight: 600; }
.pls-summary-meta { font-size: 15px; color: var(--text-subtle); margin-top: 8px; line-height: 1.5; }
.pls-llm-block {
    margin: 12px 0;
    padding: 14px 16px;
    border-radius: 10px;
    border: 1px solid rgba(16, 185, 129, 0.35);
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(5, 150, 105, 0.04));
}
.pls-llm-label {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #059669;
    margin-bottom: 8px;
}
.pls-llm-text { font-size: 14px; line-height: 1.55; color: var(--text); margin-bottom: 10px; }
.pls-llm-sublabel { font-size: 11px; font-weight: 700; color: var(--text-muted); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
.pls-llm-list { margin: 0 0 10px 18px; padding: 0; font-size: 13px; color: var(--text-muted); line-height: 1.45; }
.pls-llm-caveats { color: var(--text-subtle); font-style: italic; }
.pls-llm-action-row { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; }
.pls-llm-action { font-size: 14px; color: var(--text); font-weight: 600; }
.pls-finding-footer {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 8px;
    padding-top: 10px;
    border-top: 1px solid var(--border);
}
.pls-finding-status {
    padding: 2px 8px;
    border-radius: 9999px;
    background: var(--surface-2);
    border: 1px solid var(--border);
}

/* Growth feature tabs (B–E) */
.gf-card {
    padding: 20px 22px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
    margin-bottom: 20px;
}
.gf-card-empty { border-style: dashed; }
.gf-card-error { border-color: rgba(248, 113, 113, 0.45); }
.gf-card-title { font-size: 22px; font-weight: 700; color: var(--text-strong); margin-bottom: 8px; }
.gf-card-sub { font-size: 17px; color: var(--text-subtle); line-height: 1.6; }
.gf-hero-card {
    padding: 22px 24px;
    border-radius: 14px;
    border: 1px solid var(--border);
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
    margin-bottom: 20px;
}
.gf-hero-title { font-size: 24px; font-weight: 800; color: var(--text-strong); margin-bottom: 12px; }
.gf-hero-text { font-size: 18px; line-height: 1.65; color: var(--text); }
.gf-hero-meta { font-size: 15px; color: var(--text-subtle); margin-top: 10px; line-height: 1.5; }
.gf-hero-split { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
.gf-hero-main { flex: 2; min-width: 260px; }
.gf-measurement-card {
    flex: 1;
    min-width: 220px;
    padding: 16px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
}
.gf-section-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
.gf-section-card {
    padding: 14px 16px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--surface);
}
.gf-section-label {
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 6px;
}
.gf-section-text { font-size: 17px; line-height: 1.6; color: var(--text); }
.gf-board-title { font-size: 20px; font-weight: 700; color: var(--text-strong); margin-bottom: 12px; }
.gf-board-section { margin-bottom: 24px; }
.gf-pattern-row, .gf-list-card, .gf-test-card {
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--surface);
}
.gf-pattern-list, .gf-list-grid, .gf-test-grid { display: flex; flex-direction: column; gap: 10px; }
.gf-tag {
    font-weight: 700;
    color: var(--text-strong);
    margin-right: 8px;
}
.gf-metric-pill {
    display: inline-block;
    font-size: 14px;
    padding: 2px 8px;
    border-radius: 9999px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    margin-right: 6px;
    color: var(--text-muted);
}
.gf-list-title { font-size: 17px; font-weight: 700; color: var(--text-strong); }
.gf-list-sub { font-size: 15px; color: var(--text-subtle); margin-top: 4px; line-height: 1.5; }
.gf-list-body { font-size: 16px; color: var(--text-muted); margin-top: 6px; line-height: 1.5; }
.gf-test-meta-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
.gf-test-meta { font-size: 15px; color: var(--text-subtle); }
.gf-test-rule { font-size: 16px; color: var(--text-muted); font-style: italic; line-height: 1.5; }
.gf-funnel-table { display: flex; flex-direction: column; gap: 8px; }
.gf-funnel-row {
    display: grid;
    grid-template-columns: 1.5fr 1fr 1fr;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--surface-2);
    border: 1px solid var(--border);
}
.gf-funnel-label { font-weight: 600; color: var(--text-strong); }
.gf-funnel-count { font-size: 18px; font-weight: 800; color: #059669; }
.gf-funnel-rate { font-size: 16px; color: var(--text-subtle); }
.gf-health-score { font-size: 36px; font-weight: 800; color: #059669; margin-bottom: 8px; }
.gf-measurement-line { font-size: 15px; font-weight: 700; margin-bottom: 8px; }
.gf-status-ok { color: #059669; }
.gf-status-warn { color: #f59e0b; }
.gf-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}
.gf-kpi-card {
    padding: 16px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
}
.gf-kpi-label { font-size: 13px; font-weight: 700; color: var(--text-subtle); text-transform: uppercase; }
.gf-kpi-value { font-size: 24px; font-weight: 800; color: var(--text-strong); margin: 6px 0; }
.gf-kpi-sub { font-size: 15px; color: var(--text-muted); line-height: 1.45; }
.gf-assumptions-panel {
    padding: 16px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
    margin-bottom: 20px;
}
.supp-econ-inputs {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin-top: 10px;
}
.gf-data-table { width: 100%; border-collapse: collapse; font-size: 16px; }
.gf-data-table th {
    text-align: left;
    padding: 10px 12px;
    font-size: 13px;
    text-transform: uppercase;
    color: var(--text-subtle);
    border-bottom: 1px solid var(--border);
}
.gf-data-table td { padding: 10px 12px; border-bottom: 1px solid var(--surface-2); }
.loading-text { font-size: 17px; color: var(--text-subtle); line-height: 1.5; }

/* Tab pane typography — titles + descriptive sub-text */
.app-main h3 {
    font-size: 28px;
    font-weight: 700;
    line-height: 1.25;
    color: var(--text-strong);
}
.app-main .subtitle {
    font-size: 18px;
    line-height: 1.6;
    color: var(--text-subtle);
}

/* Saleor MCP tab */
.saleor-mcp-controls { align-items: flex-end; }
.saleor-mcp-controls .shiny-input-container { min-width: 180px; max-width: 420px; }
.saleor-mcp-status-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
}
.saleor-mcp-chip {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 8px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
}
.saleor-mcp-chip.muted { font-weight: 500; color: var(--text-subtle); }
.saleor-mcp-results { display: grid; gap: 16px; }
.saleor-mcp-card { margin-bottom: 0; }
.saleor-mcp-raw {
    margin: 0;
    padding: 12px 14px;
    max-height: 420px;
    overflow: auto;
    font-size: 13px;
    line-height: 1.45;
    background: var(--surface-2);
    border-radius: 10px;
    border: 1px solid var(--border);
    white-space: pre-wrap;
    word-break: break-word;
}
.saleor-mcp-table { margin-top: 8px; }

/* PostEx shipping tab */
.postex-section { padding: 8px 4px 16px; display: grid; gap: 14px; }
.postex-form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px 16px;
}
.postex-inline-controls { align-items: flex-end; }
.postex-inline-controls .shiny-input-container { min-width: 160px; }
.postex-results { display: grid; gap: 16px; }
.postex-card { margin-bottom: 0; }
.postex-success { color: var(--kp-kaya); font-weight: 600; }
.postex-history { margin: 8px 0 0; padding-left: 18px; line-height: 1.55; }
.postex-raw {
    margin: 0;
    padding: 12px 14px;
    max-height: 360px;
    overflow: auto;
    font-size: 13px;
    line-height: 1.45;
    background: var(--surface-2);
    border-radius: 10px;
    border: 1px solid var(--border);
    white-space: pre-wrap;
    word-break: break-word;
}
.postex-kv-table table,
.postex-orders-table table { width: 100%; border-collapse: collapse; }
.postex-kv-table th {
    text-align: left;
    width: 200px;
    padding: 8px 10px;
    color: var(--text-subtle);
    border-bottom: 1px solid var(--border);
    font-weight: 600;
}
.postex-kv-table td,
.postex-orders-table th,
.postex-orders-table td {
    padding: 8px 10px;
    border-bottom: 1px solid var(--surface-2);
    text-align: left;
}
.postex-card-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 4px;
}
.postex-card-heading .gf-card-title { margin-bottom: 0; }
.postex-cpr-list {
    display: grid;
    gap: 10px;
    margin-top: 12px;
}
.postex-cpr-item {
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface);
    overflow: hidden;
}
.postex-cpr-item[open] {
    border-color: var(--border-strong);
    box-shadow: var(--shadow);
}
.postex-cpr-summary {
    list-style: none;
    cursor: pointer;
    padding: 14px 16px;
    font-weight: 600;
    font-size: 15px;
    color: var(--text-strong);
    background: var(--surface-2);
    display: flex;
    align-items: center;
    gap: 10px;
}
.postex-cpr-summary::-webkit-details-marker { display: none; }
.postex-cpr-summary::before {
    content: "▸";
    color: var(--kp-kaya);
    font-size: 12px;
    flex-shrink: 0;
}
.postex-cpr-item[open] > .postex-cpr-summary::before {
    content: "▾";
}
.postex-cpr-summary-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.postex-cpr-panel {
    padding: 14px 16px 16px;
    display: grid;
    gap: 14px;
    border-top: 1px solid var(--border);
}
.postex-cpr-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
}
.postex-cpr-pdf-btn {
    border: none;
    cursor: pointer;
}
.postex-cpr-totals {
    display: grid;
    gap: 4px;
    margin-top: 10px;
    font-size: 14px;
    color: var(--text);
    text-align: right;
}
.postex-cpr-net {
    font-weight: 700;
    font-size: 15px;
    color: var(--text-strong);
    margin-top: 4px;
}
.postex-ext-link {
    color: var(--kp-kaya);
    font-weight: 600;
    font-size: 14px;
    text-decoration: none;
    white-space: nowrap;
}
.postex-ext-link:hover { text-decoration: underline; }

/* PostEx subnav tabs must stay visible (global .nav-tabs { display:none } for legacy chrome) */
#postex_subnav > .card-header .nav,
#postex_subnav .nav.nav-underline,
#postex_subnav .nav-tabs {
  display: flex !important;
  flex-wrap: wrap;
  gap: 0;
}

/* Keep PostEx datepickers fully visible above sticky topbar / card chrome */
body[data-active-nav="postex"] .app-main,
body[data-active-nav="postex"] .tab-content,
#postex_subnav.card,
#postex_subnav .card-body,
#postex_subnav .tab-content,
#postex_subnav .tab-pane,
#postex_subnav .card-header,
.postex-section,
.postex-inline-controls,
.postex-inline-controls .shiny-input-container,
.postex-inline-controls .form-group {
  overflow: visible !important;
}
/* Picker is moved to body via JS; keep it above sticky topbar (z-index 30) */
.datepicker,
.datepicker-dropdown,
.dropdown-menu.datepicker,
body > .datepicker.datepicker-dropdown {
  z-index: 10050 !important;
}
"""
