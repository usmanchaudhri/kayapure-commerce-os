"""PostEx shipping nav panel — create, track, list, CPR, AWB, load sheet."""

from datetime import date, timedelta

from shiny import ui

from shiny_app.lib.postex_client import ORDER_STATUS_CHOICES


def nav_panel():
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    status_choices = ORDER_STATUS_CHOICES
    return ui.nav_panel(
        "PostEx",
        ui.div(
            ui.div(
                ui.span("Shipping", class_="pls-featured-badge"),
                ui.tags.h3("PostEx"),
                ui.div(
                    "Create COD shipments, track parcels, list orders by date, "
                    "view cash payment receipts (CPR), and download airway bills "
                    "or load sheets via the PostEx merchant API.",
                    class_="subtitle",
                ),
                style="flex: 1;",
            ),
            class_="pls-header",
        ),
        ui.navset_card_underline(
            ui.nav_panel(
                "Sales",
                ui.div(
                    ui.div(
                        "Synced PostEx orders consolidated into Gross COD, Delivered, "
                        "Settled, and Unsettled delivered. First sync backfills from "
                        "POSTEX_SYNC_SINCE to today (empty months are skipped quickly); "
                        "later clicks refresh the lookback window. Watch the status line "
                        "and browser notification after Sync now.",
                        class_="gf-card-sub",
                    ),
                    ui.div(
                        ui.input_text(
                            "postex_sales_from",
                            "From date (YYYY-MM-DD, optional)",
                            placeholder="Leave blank for lifetime",
                            width="200px",
                        ),
                        ui.input_text(
                            "postex_sales_to",
                            "To date (YYYY-MM-DD, optional)",
                            placeholder="Leave blank for lifetime",
                            width="200px",
                        ),
                        ui.input_action_button(
                            "postex_sales_sync_btn",
                            "Sync now",
                            class_="btn-primary pls-scan-btn",
                        ),
                        ui.input_action_button(
                            "postex_sales_refresh_btn",
                            "Refresh summary",
                            class_="btn-secondary pls-scan-btn",
                        ),
                        class_="pls-controls postex-inline-controls",
                    ),
                    ui.output_ui("postex_sales_status"),
                    ui.output_ui("postex_sales_kpis"),
                    ui.output_ui("postex_sales_orders"),
                    class_="postex-section",
                ),
            ),
            ui.nav_panel(
                "Create order",
                ui.div(
                    ui.div(
                        ui.input_text(
                            "postex_create_ref",
                            "Order reference",
                            placeholder="Your order / invoice number",
                            width="100%",
                        ),
                        ui.input_text(
                            "postex_create_payment",
                            "COD amount (invoicePayment)",
                            placeholder="e.g. 2500",
                            width="100%",
                        ),
                        ui.input_text(
                            "postex_create_customer",
                            "Customer name",
                            width="100%",
                        ),
                        ui.input_text(
                            "postex_create_phone",
                            "Customer phone",
                            placeholder="03xxxxxxxxx",
                            width="100%",
                        ),
                        class_="postex-form-grid",
                    ),
                    ui.div(
                        ui.input_text(
                            "postex_create_city",
                            "City",
                            placeholder="Must match PostEx operational city",
                            width="100%",
                        ),
                        ui.input_text(
                            "postex_create_address",
                            "Delivery address",
                            width="100%",
                        ),
                        ui.input_numeric(
                            "postex_create_items",
                            "Items (pieces)",
                            value=1,
                            min=1,
                            width="100%",
                        ),
                        ui.input_numeric(
                            "postex_create_division",
                            "Invoice division (AWB copies)",
                            value=1,
                            min=1,
                            width="100%",
                        ),
                        class_="postex-form-grid",
                    ),
                    ui.input_text_area(
                        "postex_create_detail",
                        "Order detail (SKU / qty)",
                        placeholder="Optional product description",
                        rows=2,
                        width="100%",
                    ),
                    ui.input_text_area(
                        "postex_create_notes",
                        "Transaction notes",
                        placeholder="Optional",
                        rows=2,
                        width="100%",
                    ),
                    ui.input_action_button(
                        "postex_create_btn",
                        "Create order",
                        class_="btn-primary pls-scan-btn",
                    ),
                    ui.output_ui("postex_create_status"),
                    ui.output_ui("postex_create_result"),
                    class_="postex-section",
                ),
            ),
            ui.nav_panel(
                "Track",
                ui.div(
                    ui.div(
                        ui.input_text(
                            "postex_track_id",
                            "Tracking number",
                            placeholder="CX-XXXXXXXXXXX",
                            width="100%",
                        ),
                        ui.input_action_button(
                            "postex_track_btn",
                            "Check status",
                            class_="btn-primary pls-scan-btn",
                        ),
                        class_="pls-controls postex-inline-controls",
                    ),
                    ui.output_ui("postex_track_status"),
                    ui.output_ui("postex_track_result"),
                    class_="postex-section",
                ),
            ),
            ui.nav_panel(
                "Orders by date",
                ui.div(
                    ui.div(
                        ui.input_date(
                            "postex_list_from",
                            "From date",
                            value=week_ago,
                            width="160px",
                        ),
                        ui.input_date(
                            "postex_list_to",
                            "To date",
                            value=today,
                            width="160px",
                        ),
                        ui.input_select(
                            "postex_list_order_status",
                            "Status",
                            choices=status_choices,
                            selected="0",
                            width="220px",
                        ),
                        ui.input_action_button(
                            "postex_list_btn",
                            "Load orders",
                            class_="btn-primary pls-scan-btn",
                        ),
                        class_="pls-controls postex-inline-controls",
                    ),
                    ui.output_ui("postex_list_feedback"),
                    ui.output_ui("postex_list_result"),
                    class_="postex-section",
                ),
            ),
            ui.nav_panel(
                "Cash Payment Receipts",
                ui.div(
                    ui.div(
                        "Load Cash Payment Receipts (CPR) for orders in a date range. "
                        "Each receipt expands to show full details and a CPR PDF download. "
                        "Uses PostEx Payment Status per tracking number; newest first.",
                        class_="gf-card-sub",
                    ),
                    ui.div(
                        ui.input_date(
                            "postex_cpr_from",
                            "From date",
                            value=month_ago,
                            width="160px",
                        ),
                        ui.input_date(
                            "postex_cpr_to",
                            "To date",
                            value=today,
                            width="160px",
                        ),
                        ui.input_select(
                            "postex_cpr_order_status",
                            "Order status",
                            choices=status_choices,
                            selected="5",
                            width="220px",
                        ),
                        ui.input_action_button(
                            "postex_cpr_btn",
                            "Load CPR receipts",
                            class_="btn-primary pls-scan-btn",
                        ),
                        class_="pls-controls postex-inline-controls",
                    ),
                    ui.output_ui("postex_cpr_feedback"),
                    ui.output_ui("postex_cpr_result"),
                    class_="postex-section",
                ),
            ),
            ui.nav_panel(
                "Airway bill",
                ui.div(
                    ui.div(
                        "Print airway bills for up to 10 tracking numbers "
                        "(comma or newline separated).",
                        class_="gf-card-sub",
                    ),
                    ui.input_text_area(
                        "postex_awb_tracking",
                        "Tracking numbers",
                        placeholder="CX-111, CX-222",
                        rows=3,
                        width="100%",
                    ),
                    ui.input_action_button(
                        "postex_awb_btn",
                        "Download airway bill PDF",
                        class_="btn-primary pls-scan-btn",
                    ),
                    ui.output_ui("postex_awb_status"),
                    class_="postex-section",
                ),
            ),
            ui.nav_panel(
                "Load sheet",
                ui.div(
                    ui.div(
                        "Generate a pickup load sheet PDF for booked tracking numbers.",
                        class_="gf-card-sub",
                    ),
                    ui.input_text_area(
                        "postex_ls_tracking",
                        "Tracking numbers",
                        placeholder="CX-111\nCX-222",
                        rows=3,
                        width="100%",
                    ),
                    ui.div(
                        ui.input_text(
                            "postex_ls_address",
                            "Pickup address",
                            width="100%",
                        ),
                        ui.input_text(
                            "postex_ls_city",
                            "Pickup city",
                            width="100%",
                        ),
                        ui.input_text(
                            "postex_ls_contact",
                            "Contact number / person",
                            width="100%",
                        ),
                        class_="postex-form-grid",
                    ),
                    ui.input_action_button(
                        "postex_ls_btn",
                        "Download load sheet PDF",
                        class_="btn-primary pls-scan-btn",
                    ),
                    ui.output_ui("postex_ls_status"),
                    class_="postex-section",
                ),
            ),
            id="postex_subnav",
        ),
        value="postex",
    )
