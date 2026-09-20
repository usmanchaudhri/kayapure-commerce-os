"""Shiny UI composition for the Meta Ads dashboard."""

from shiny import ui

from shiny_app.ui.styles import APP_CSS
from shiny_app.ui.tabs import ai_reports as ai_reports_tab
from shiny_app.ui.tabs import creative_intelligence as creative_intel_tab
from shiny_app.ui.tabs import daily_diagnosis as daily_diagnosis_tab
from shiny_app.ui.tabs import funnel_reconciliation as funnel_rec_tab
from shiny_app.ui.tabs import postex as postex_tab
from shiny_app.ui.tabs import profit_leak_scanner as profit_leak_tab
from shiny_app.ui.tabs import saleor_mcp as saleor_mcp_tab
from shiny_app.ui.tabs import supplement_economics as supp_econ_tab

_PDF_DOWNLOAD_SCRIPT = """
        $(document).on('shiny:connected', function() {
            Shiny.addCustomMessageHandler('download_pdf', function(msg) {
                if (!msg || !msg.url) return;
                // Navigate to a real FastAPI FileResponse with Content-Disposition: attachment.
                // Chrome keeps this page open and saves the file instead of treating it as a failed blob download.
                window.location.assign(msg.url);
            });
        });
    """

_METRIC_TOOLTIP_SCRIPT = """
(function() {
  var tipEl = null;

  function ensureTip() {
    if (!tipEl) {
      tipEl = document.createElement('div');
      tipEl.className = 'metric-floating-tip';
      tipEl.style.display = 'none';
      document.body.appendChild(tipEl);
    }
    return tipEl;
  }

  function placeTip(anchor) {
    var tip = ensureTip();
    var text = anchor.getAttribute('data-tip') || '';
    if (!text) {
      tip.style.display = 'none';
      return;
    }
    tip.textContent = text;
    tip.style.display = 'block';
    tip.style.left = '0px';
    tip.style.top = '0px';
    var rect = anchor.getBoundingClientRect();
    var tipRect = tip.getBoundingClientRect();
    var left = rect.left + (rect.width / 2) - (tipRect.width / 2);
    var top = rect.top - tipRect.height - 8;
    if (top < 8) {
      top = rect.bottom + 8;
    }
    left = Math.max(8, Math.min(left, window.innerWidth - tipRect.width - 8));
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }

  function hideTip() {
    if (tipEl) {
      tipEl.style.display = 'none';
    }
  }

  document.addEventListener('mouseover', function(e) {
    var anchor = e.target && e.target.closest ? e.target.closest('.metric-tip') : null;
    if (anchor) placeTip(anchor);
  });

  document.addEventListener('mouseout', function(e) {
    var anchor = e.target && e.target.closest ? e.target.closest('.metric-tip') : null;
    if (!anchor) return;
    var related = e.relatedTarget;
    if (related && anchor.contains(related)) return;
    hideTip();
  });

  document.addEventListener('focusin', function(e) {
    var anchor = e.target && e.target.closest ? e.target.closest('.metric-tip') : null;
    if (anchor) placeTip(anchor);
  });

  document.addEventListener('focusout', function(e) {
    var anchor = e.target && e.target.closest ? e.target.closest('.metric-tip') : null;
    if (anchor) hideTip();
  });

  window.addEventListener('scroll', hideTip, true);
  window.addEventListener('resize', hideTip);
})();
"""

_THEME_AND_NAV_SCRIPT = """
(function() {
  var THEME_KEY = 'kayapure-ads-theme';
  var NAV_KEY = 'kayapure-ads-nav-collapsed';

  function applyTheme(theme) {
    var next = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    var btn = document.getElementById('theme_toggle');
    if (btn) {
      btn.setAttribute('aria-pressed', next === 'dark' ? 'true' : 'false');
      btn.setAttribute('title', next === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      var label = btn.querySelector('.theme-toggle-label');
      if (label) label.textContent = next === 'dark' ? 'Light' : 'Dark';
      var icon = btn.querySelector('.theme-toggle-icon');
      if (icon) icon.textContent = next === 'dark' ? '☀' : '☾';
    }
  }

  function currentTheme() {
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
    applyTheme(saved === 'dark' ? 'dark' : 'light');
  }

  function isMobileNav() {
    return window.matchMedia('(max-width: 960px)').matches;
  }

  function syncNavButtons() {
    var collapsed = document.body.classList.contains('nav-collapsed');
    var overlay = document.body.classList.contains('nav-drawer-open');
    var open = isMobileNav() ? overlay : !collapsed;
    var toggle = document.getElementById('nav_drawer_toggle');
    if (toggle) {
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('title', open ? 'Hide navigation' : 'Show navigation');
      toggle.setAttribute('aria-label', open ? 'Hide navigation' : 'Show navigation');
      var icon = toggle.querySelector('.nav-toggle-icon');
      if (icon) icon.innerHTML = open ? '&#10094;' : '&#9776;';
    }
    var collapseBtn = document.getElementById('nav_rail_collapse');
    if (collapseBtn) {
      collapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      collapseBtn.setAttribute('title', 'Hide navigation');
    }
  }

  function setNavCollapsed(collapsed) {
    document.body.classList.toggle('nav-collapsed', !!collapsed);
    document.body.classList.remove('nav-drawer-open');
    try { localStorage.setItem(NAV_KEY, collapsed ? '1' : '0'); } catch (e) {}
    syncNavButtons();
  }

  function setNavOverlay(open) {
    document.body.classList.toggle('nav-drawer-open', !!open);
    syncNavButtons();
  }

  function initNav() {
    var saved = null;
    try { saved = localStorage.getItem(NAV_KEY); } catch (e) {}
    if (!isMobileNav() && saved === '1') {
      document.body.classList.add('nav-collapsed');
    }
    document.body.classList.remove('nav-drawer-open');
    syncNavButtons();
  }

  var NAV_ACTIVE_KEY = 'kayapure-ads-active-nav';
  var DEFAULT_NAV = 'profit_leak_scanner';
  var NAV_IDS = {
    profit_leak_scanner: 'nav_profit_leak_scanner',
    daily_diagnosis: 'nav_daily_diagnosis',
    creative_intelligence: 'nav_creative_intelligence',
    funnel_reconciliation: 'nav_funnel_reconciliation',
    supplement_economics: 'nav_supplement_economics',
    ai_reports: 'nav_ai_reports',
    saleor_mcp: 'nav_saleor_mcp',
    postex: 'nav_postex'
  };
  var NAV_TITLES = {
    profit_leak_scanner: 'Profit Leak Scanner',
    daily_diagnosis: 'Daily Diagnosis',
    creative_intelligence: 'Creative Intelligence',
    funnel_reconciliation: 'Funnel Reconciliation',
    supplement_economics: 'Unit Economics',
    ai_reports: 'Ads Performance',
    saleor_mcp: 'Saleor MCP',
    postex: 'PostEx'
  };
  var NAV_SUBTITLES = {
    profit_leak_scanner: 'Find wasted spend and ranked fixes for supplement ads',
    daily_diagnosis: 'Plain-English account health in five sentences',
    creative_intelligence: 'Message patterns, fatigue, and creative test backlog',
    funnel_reconciliation: 'Funnel drop-off and Meta vs store reconciliation',
    supplement_economics: 'First-order CAC, break-even, and LTV contribution',
    ai_reports: 'Generate reports to analyse and improve ad spend',
    saleor_mcp: 'Query products, orders, and stock via Saleor MCP',
    postex: 'Create shipments, track orders, CPR receipts, AWB and load sheets'
  };

  function setActiveNav(panel) {
    if (!panel || !NAV_IDS[panel]) return;
    document.body.setAttribute('data-active-nav', panel);
    try { localStorage.setItem(NAV_ACTIVE_KEY, panel); } catch (e) {}
    Object.keys(NAV_IDS).forEach(function(key) {
      var el = document.getElementById(NAV_IDS[key]);
      if (!el) return;
      var isActive = key === panel;
      el.classList.toggle('is-active', isActive);
      el.setAttribute('aria-current', isActive ? 'page' : 'false');
    });
    var title = document.getElementById('app_panel_title');
    if (title) title.textContent = NAV_TITLES[panel] || NAV_TITLES[DEFAULT_NAV];
    var sub = document.getElementById('app_panel_sub');
    if (sub) sub.textContent = NAV_SUBTITLES[panel] || '';
  }

  function panelFromNavButton(el) {
    if (!el || !el.id) return null;
    for (var key in NAV_IDS) {
      if (NAV_IDS[key] === el.id) return key;
    }
    return el.getAttribute('data-nav') || null;
  }

  function closeNavForViewport() {
    if (isMobileNav()) {
      setNavOverlay(false);
    } else {
      // Keep docked/collapsed preference; only close overlay if any
      setNavOverlay(false);
    }
  }

  document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    initNav();
    setActiveNav(DEFAULT_NAV);
  });
  setTimeout(function() {
    initTheme();
    initNav();
    setActiveNav(DEFAULT_NAV);
  }, 0);

  document.addEventListener('click', function(e) {
    var navItem = e.target && e.target.closest ? e.target.closest('.app-nav-item') : null;
    if (navItem) {
      var panel = panelFromNavButton(navItem);
      if (panel) setActiveNav(panel);
    }

    var themeBtn = e.target && e.target.closest ? e.target.closest('#theme_toggle') : null;
    if (themeBtn) {
      e.preventDefault();
      applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
      return;
    }

    var openBtn = e.target && e.target.closest ? e.target.closest('#nav_drawer_toggle') : null;
    if (openBtn) {
      e.preventDefault();
      if (isMobileNav()) {
        setNavOverlay(!document.body.classList.contains('nav-drawer-open'));
      } else if (document.body.classList.contains('nav-collapsed')) {
        setNavCollapsed(false); // pop docked rail back out
      } else {
        setNavCollapsed(true); // slide away for full canvas
      }
      return;
    }

    var collapseBtn = e.target && e.target.closest ? e.target.closest('#nav_rail_collapse') : null;
    if (collapseBtn) {
      e.preventDefault();
      setNavCollapsed(true);
      return;
    }

    var backdrop = e.target && e.target.closest ? e.target.closest('.app-nav-backdrop') : null;
    if (backdrop) {
      closeNavForViewport();
      return;
    }

    var closeBtn = e.target && e.target.closest ? e.target.closest('#nav_drawer_close') : null;
    if (closeBtn) {
      e.preventDefault();
      if (isMobileNav()) {
        setNavOverlay(false);
      } else {
        setNavCollapsed(true);
      }
    }
  });

  window.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeNavForViewport();
  });

  window.addEventListener('resize', function() {
    if (!isMobileNav()) {
      document.body.classList.remove('nav-drawer-open');
    }
    syncNavButtons();
  });

  $(document).on('shiny:connected', function() {
    initTheme();
    initNav();
    var current = document.body.getAttribute('data-active-nav');
    setActiveNav(NAV_IDS[current] ? current : DEFAULT_NAV);
    Shiny.addCustomMessageHandler('nav_activated', function(msg) {
      if (msg && msg.id) {
        setActiveNav(msg.id);
        // Re-apply after Shiny finishes patching action-button DOM
        setTimeout(function() { setActiveNav(msg.id); }, 0);
        setTimeout(function() { setActiveNav(msg.id); }, 50);
        setTimeout(function() { setActiveNav(msg.id); }, 200);
        if (isMobileNav()) setNavOverlay(false);
      }
    });
  });
  $(document).on('shiny:idle', function() {
    var panel = document.body.getAttribute('data-active-nav');
    if (panel) setActiveNav(panel);
  });
})();
"""

_POSTEX_DATEPICKER_SCRIPT = """
(function() {
  var POSTEX_DATE_IDS = [
    'postex_cpr_from', 'postex_cpr_to',
    'postex_list_from', 'postex_list_to'
  ];

  function patchInput(el) {
    if (!el || !window.jQuery) return;
    var $el = window.jQuery(el);
    el.setAttribute('data-date-orientation', 'bottom');
    var dp = $el.data('datepicker');
    if (!dp) return;
    // Always open below the field so the sticky PostEx topbar does not cover it.
    dp.o.orientation = { x: 'auto', y: 'bottom' };
    if (dp.picker && dp.picker.length && dp.picker.parent()[0] !== document.body) {
      dp.picker.appendTo(document.body);
    }
  }

  function patchAll() {
    POSTEX_DATE_IDS.forEach(function(id) {
      patchInput(document.getElementById(id));
    });
  }

  function bindShowHandlers() {
    if (!window.jQuery) return;
    POSTEX_DATE_IDS.forEach(function(id) {
      var el = document.getElementById(id);
      if (!el || el.getAttribute('data-kp-dp-bound') === '1') return;
      el.setAttribute('data-kp-dp-bound', '1');
      window.jQuery(el).on('show', function() {
        patchInput(el);
      });
    });
  }

  function init() {
    patchAll();
    bindShowHandlers();
  }

  document.addEventListener('DOMContentLoaded', init);
  // Shiny may init datepickers after first paint / tab switch.
  setTimeout(init, 0);
  setTimeout(init, 500);
  setTimeout(init, 1500);
  document.addEventListener('click', function(e) {
    var t = e.target && e.target.closest
      ? e.target.closest('#postex_cpr_from, #postex_cpr_to, #postex_list_from, #postex_list_to')
      : null;
    if (t) {
      setTimeout(function() { patchInput(t); }, 0);
    }
    // Re-bind when switching into PostEx / CPR subtab.
    if (e.target && e.target.closest && (
      e.target.closest('#nav_postex') ||
      e.target.closest('#postex_subnav')
    )) {
      setTimeout(init, 50);
    }
  });
})();
"""


def _nav_item(button_id: str, panel: str, label: str, *, active: bool = False):
    # Active styling is driven by body[data-active-nav] + #nav_* IDs (Shiny rewrites button classes).
    return ui.input_action_button(
        button_id,
        label,
        class_="app-nav-item",
        **{
            "data-nav": panel,
            "aria-current": "page" if active else "false",
        },
    )


def _nav_rail():
    """Single navigation source — desktop rail + mobile drawer (no duplicate input IDs)."""
    return ui.tags.aside(
        ui.div(
            ui.div(
                ui.div(
                    ui.span("Kaya", class_="brand-kaya"),
                    ui.span("Pure", class_="brand-pure"),
                    ui.span(" Ads", class_="brand-suffix"),
                    class_="app-nav-brand",
                ),
                ui.div(
                    ui.tags.button(
                        ui.HTML("&#10094;"),
                        type="button",
                        id="nav_rail_collapse",
                        class_="app-icon-btn app-nav-collapse-btn",
                        **{"aria-label": "Hide navigation", "title": "Hide navigation"},
                    ),
                    ui.tags.button(
                        "✕",
                        type="button",
                        id="nav_drawer_close",
                        class_="app-icon-btn app-nav-close-btn",
                        **{"aria-label": "Close navigation"},
                    ),
                    class_="app-nav-top-actions",
                ),
                class_="app-nav-top",
            ),
            ui.p("Commerce OS", class_="app-nav-kicker"),
            ui.tags.nav(
                _nav_item("nav_profit_leak_scanner", "profit_leak_scanner", "Profit Leak Scanner", active=True),
                _nav_item("nav_daily_diagnosis", "daily_diagnosis", "Daily Diagnosis"),
                _nav_item("nav_creative_intelligence", "creative_intelligence", "Creative Intelligence"),
                _nav_item("nav_funnel_reconciliation", "funnel_reconciliation", "Funnel Reconciliation"),
                _nav_item("nav_supplement_economics", "supplement_economics", "Unit Economics"),
                _nav_item("nav_ai_reports", "ai_reports", "Ads Performance"),
                _nav_item("nav_saleor_mcp", "saleor_mcp", "Saleor MCP"),
                _nav_item("nav_postex", "postex", "PostEx"),
                class_="app-nav-list",
                **{"aria-label": "Main"},
            ),
            ui.div(
                ui.p("Filters & tools stay on each page.", class_="app-nav-footnote"),
                class_="app-nav-footer",
            ),
            class_="app-nav-inner",
        ),
        class_="app-nav-rail",
        id="app-nav-rail",
        **{"aria-label": "Main"},
    )


def build_app_ui():
    return ui.page_fluid(
        ui.busy_indicators.use(spinners=False, pulse=True),
        ui.tags.script(_PDF_DOWNLOAD_SCRIPT),
        ui.tags.script(_METRIC_TOOLTIP_SCRIPT),
        ui.tags.script(_THEME_AND_NAV_SCRIPT),
        ui.tags.script(_POSTEX_DATEPICKER_SCRIPT),
        ui.tags.style(APP_CSS),
        ui.div(class_="app-nav-backdrop", **{"aria-hidden": "true"}),
        ui.div(
            _nav_rail(),
            ui.div(
                ui.tags.header(
                    ui.div(
                        ui.tags.button(
                            ui.span(ui.HTML("&#9776;"), class_="nav-toggle-icon"),
                            type="button",
                            id="nav_drawer_toggle",
                            class_="app-icon-btn app-nav-open-btn",
                            **{
                                "aria-expanded": "true",
                                "aria-controls": "app-nav-rail",
                                "aria-label": "Hide navigation",
                                "title": "Hide navigation",
                            },
                        ),
                        ui.div(
                            ui.div(
                                "Profit Leak Scanner",
                                id="app_panel_title",
                                class_="header-title",
                            ),
                            ui.div(
                                "Find wasted spend and ranked fixes for supplement ads",
                                id="app_panel_sub",
                                class_="header-sub",
                            ),
                            class_="header-copy",
                        ),
                        class_="header-left",
                    ),
                    ui.div(
                        ui.tags.button(
                            ui.span("☾", class_="theme-toggle-icon"),
                            ui.span("Dark", class_="theme-toggle-label"),
                            type="button",
                            id="theme_toggle",
                            class_="app-icon-btn theme-toggle-btn",
                            **{"aria-pressed": "false", "title": "Switch to dark mode"},
                        ),
                        ui.input_action_button("refresh", "↻ Refresh", class_="refresh-btn"),
                        class_="header-actions",
                    ),
                    class_="app-topbar",
                ),
                ui.tags.main(
                    ui.navset_hidden(
                        profit_leak_tab.nav_panel(),
                        daily_diagnosis_tab.nav_panel(),
                        creative_intel_tab.nav_panel(),
                        funnel_rec_tab.nav_panel(),
                        supp_econ_tab.nav_panel(),
                        ai_reports_tab.nav_panel(),
                        saleor_mcp_tab.nav_panel(),
                        postex_tab.nav_panel(),
                        id="main_nav",
                        selected="profit_leak_scanner",
                    ),
                    class_="app-main",
                ),
                class_="app-content",
            ),
            class_="app-shell",
        ),
    )
