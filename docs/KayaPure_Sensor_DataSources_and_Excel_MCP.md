# KayaPure Commerce OS — Sensor Node Data Sources & Excel/Sheets MCP Integration

**Author:** Manus AI  
**Date:** February 27, 2026  
**Status:** Research Document (No Code Changes)

---

## 1. Executive Summary

This document addresses two questions: (1) where does all the data feeding into the Sensor Node actually come from, mapped to exact API endpoints and fields, and (2) how can the system connect to Excel spreadsheets for warehouse inventory data and WhatsApp/sales data parsing via MCP.

The Sensor Node aggregates data from **seven distinct source categories** across **30+ individual data streams**. Each stream maps to a specific API endpoint, GraphQL query, or database table. The complete inventory is documented in Section 3.

For Excel integration, **yes — mature open-source MCP servers exist for both Excel and Google Sheets**. The most prominent is `haris-musa/excel-mcp-server` with 3,400 GitHub stars, which can read, write, and manipulate `.xlsx` files without requiring Microsoft Excel to be installed. For Google Sheets, `xing5/mcp-google-sheets` provides 15+ tools for full read/write access. Both integrate directly into the existing `MultiServerMCPClient` architecture proposed in the previous MCP design document.

---

## 2. Sensor Node Data Sources — Complete Map

The following diagram shows every data source that feeds into the Sensor Node, organized by service:

![Sensor Node Data Sources](/home/ubuntu/sensor-data-sources.png)

The Sensor Node is the first node in the LangGraph workflow. Its job is to gather a comprehensive snapshot of the current state of the business — products, inventory, orders, ad performance, payment flows, shipments, and warehouse data — and pass that context to the P&L Analyzer and Strategy nodes for reasoning.

---

## 3. Detailed Data Source Inventory

### 3.1 Shopify Storefront (Commerce Data)

Shopify is the primary storefront and the richest data source. Since October 2024, Shopify has deprecated the REST Admin API in favor of GraphQL [1]. All new integrations must use the GraphQL Admin API.

| Data Stream | API | Endpoint / Query | Key Fields Retrieved | Use in KayaPure |
|---|---|---|---|---|
| **Products & Variants** | GraphQL Admin | `query { products(first: 50) { edges { node { id title variants { edges { node { price inventoryQuantity sku } } } } } } }` | Product title, SKU, price, compare-at price, variant count, status | SKU catalog, pricing analysis, competitor comparison |
| **Inventory Levels** | GraphQL Admin | `query { inventoryLevels(first: 100) { edges { node { available incoming quantities { name quantity } location { name } } } } }` | Available qty, incoming qty, committed qty, on-hand qty, location | Stock-out risk detection, reorder triggers |
| **Orders & Fulfillments** | GraphQL Admin | `query { orders(first: 50, sortKey: CREATED_AT) { edges { node { totalPriceSet { shopMoney { amount } } lineItems { edges { node { sku quantity } } } fulfillments { status } } } } }` | Order total, line items, SKU, quantity, fulfillment status, shipping | Revenue calculation, order velocity, fulfillment rate |
| **Customers** | GraphQL Admin | `query { customers(first: 50) { edges { node { email ordersCount totalSpentV2 { amount } } } } }` | Customer count, total spend, order frequency, email | Customer LTV analysis, cohort segmentation |
| **Collections** | GraphQL Admin | `query { collections(first: 20) { edges { node { title productsCount } } } }` | Collection names, product counts | Category-level performance analysis |
| **Discounts** | GraphQL Admin | `query { discountNodes(first: 20) { edges { node { discount { ... on DiscountCodeBasic { title status startsAt endsAt } } } } } }` | Active discounts, codes, start/end dates, usage count | Promotion impact analysis, margin erosion tracking |

The **Shopify Storefront MCP** (official) and **Shopify Admin MCP** (community, 22 tools) both expose these data streams as MCP tools, so the agent can call them dynamically without hardcoding GraphQL queries [2] [3].

---

### 3.2 Meta Ads — Facebook & Instagram (Marketing Data)

Meta's Marketing API provides advertising performance data through the Insights edge [4]. The `pipeboard-co/meta-ads-mcp` server wraps all of these into 29 MCP tools [5].

| Data Stream | API | Endpoint | Key Fields Retrieved | Use in KayaPure |
|---|---|---|---|---|
| **Campaign Insights** | Marketing API v21.0 | `GET /act_{ad_account_id}/insights?fields=spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions,action_values,purchase_roas&date_preset=last_7d` | Spend, impressions, clicks, CTR, CPC, CPM, reach, frequency, conversions, ROAS | Campaign-level P&L, budget efficiency |
| **Ad Set Performance** | Marketing API v21.0 | `GET /{adset_id}/insights?fields=spend,impressions,clicks,conversions,cost_per_action_type,actions&breakdowns=age,gender` | Per-audience spend, demographic breakdown, cost per conversion | Audience optimization, targeting recommendations |
| **Ad Creative Data** | Marketing API v21.0 | `GET /{ad_id}/insights?fields=spend,impressions,clicks,actions,video_avg_time_watched_actions,video_p75_watched_actions` | Per-creative performance, video watch rates, engagement | Creative fatigue detection, A/B test analysis |
| **Audience Targeting** | Marketing API v21.0 | `GET /act_{id}/targetingsearch?q={query}&type=adinterest` | Interest categories, audience sizes, demographics | New audience discovery, expansion recommendations |
| **Budget & Schedule** | Marketing API v21.0 | `GET /{campaign_id}?fields=daily_budget,lifetime_budget,budget_remaining,start_time,stop_time,status` | Daily budget, lifetime budget, remaining budget, schedule | Budget pacing, overspend alerts |

**Key metrics available from Meta Ads:**

| Metric | Field Name | Description |
|---|---|---|
| Return on Ad Spend | `purchase_roas` | Revenue generated per dollar spent |
| Cost Per Purchase | `cost_per_action_type` (filtered for `purchase`) | Average cost to acquire one purchase |
| Click-Through Rate | `ctr` | Percentage of impressions that resulted in clicks |
| Cost Per Mille | `cpm` | Cost per 1,000 impressions |
| Frequency | `frequency` | Average times each person saw the ad |
| Video Watch Rate | `video_p75_watched_actions` | Percentage who watched 75% of video |

---

### 3.3 Google Ads (Marketing Data)

Google Ads data is accessed through the Google Ads Query Language (GAQL), which allows SQL-like queries against the Google Ads API [6]. The official Google Ads MCP server provides a `search` tool that accepts GAQL queries [7].

| Data Stream | API | GAQL Query | Key Fields Retrieved | Use in KayaPure |
|---|---|---|---|---|
| **Campaign Metrics** | Google Ads API v18 | `SELECT campaign.name, campaign.status, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM campaign WHERE segments.date DURING LAST_7_DAYS` | Campaign name, status, impressions, clicks, cost, conversions, conversion value | Campaign-level performance, cross-channel comparison with Meta |
| **Ad Group Performance** | Google Ads API v18 | `SELECT ad_group.name, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.average_cpc, metrics.ctr FROM ad_group WHERE segments.date DURING LAST_7_DAYS` | Ad group metrics, average CPC, CTR | Ad group optimization recommendations |
| **Keyword Data** | Google Ads API v18 | `SELECT keyword_view.resource_name, ad_group_criterion.keyword.text, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.average_cpc FROM keyword_view WHERE segments.date DURING LAST_30_DAYS` | Keyword text, impressions, clicks, cost, CPC | Keyword bid optimization, negative keyword suggestions |
| **Budget Data** | Google Ads API v18 | `SELECT campaign_budget.amount_micros, campaign_budget.total_amount_micros, campaign_budget.status FROM campaign_budget` | Budget amount, total budget, status | Budget pacing, allocation recommendations |

**Important limitation:** The official Google Ads MCP server is currently **read-only** [7]. It can retrieve all the data above but cannot modify campaigns, adjust bids, or change budgets. Write operations would require a custom MCP server wrapping the Google Ads API mutate endpoints.

---

### 3.4 Stripe (Payment & Financial Data)

Stripe provides the financial layer — all payment processing, subscription management, and revenue data [8]. The official Stripe MCP server at `mcp.stripe.com` exposes 25 tools covering the full API surface [9].

| Data Stream | API | Endpoint | Key Fields Retrieved | Use in KayaPure |
|---|---|---|---|---|
| **Balance** | Stripe API | `GET /v1/balance` | Available balance (by currency), pending balance, connect reserved | Current cash position, liquidity analysis |
| **Balance Transactions** | Stripe API | `GET /v1/balance_transactions?limit=100&created[gte]={timestamp}` | Amount, fee, net, type (charge/refund/payout), created date | Revenue tracking, fee analysis, net income calculation |
| **Charges** | Stripe API | `GET /v1/charges?limit=100` | Amount, currency, status, payment method, customer, refunded | Payment success rate, average order value |
| **Subscriptions** | Stripe API | `GET /v1/subscriptions?status=active` | Plan, amount, interval, current period, cancel at period end | MRR/ARR calculation, churn prediction |
| **Invoices** | Stripe API | `GET /v1/invoices?status=paid&limit=100` | Amount paid, subtotal, tax, discount, line items | Revenue recognition, tax reporting |
| **Disputes** | Stripe API | `GET /v1/disputes?limit=50` | Amount, reason, status, evidence due by | Chargeback monitoring, fraud detection |
| **Payouts** | Stripe API | `GET /v1/payouts?limit=50` | Amount, arrival date, status, method | Cash flow forecasting |
| **Revenue Recognition** | Stripe Reporting API | `GET /v1/reporting/report_runs` | Deferred revenue, recognized revenue, waterfall | Accrual accounting, financial reporting |

---

### 3.5 Flexport (Logistics & Supply Chain Data)

Flexport provides end-to-end logistics data through its REST API [10]. No official MCP server exists, so a custom one must be built using FastMCP.

| Data Stream | API | Endpoint | Key Fields Retrieved | Use in KayaPure |
|---|---|---|---|---|
| **Shipments** | Flexport API v3 | `GET /shipments?page=1&per=20&sort=updated_at` | Shipment ID, status, origin, destination, cargo ready date, estimated arrival | In-transit inventory tracking, ETA monitoring |
| **Shipment Details** | Flexport API v3 | `GET /shipments/{id}` | Milestones (departed, arrived, customs cleared), container info, tracking events | Delivery timeline, delay detection |
| **Freight Invoices** | Flexport API v3 | `GET /invoices?page=1&per=20` | Invoice amount, currency, due date, shipment reference, line items | Logistics cost tracking, landed cost calculation |
| **Commercial Invoices** | Flexport API v3 | `GET /commercial_invoices/{id}` | Product descriptions, quantities, unit values, HS codes, country of origin | Customs compliance, duty cost estimation |
| **Products/Inventory** | Flexport Logistics API | `GET /products?page=1&per=50` | Product name, SKU, weight, dimensions, warehouse location | Warehouse inventory levels, storage cost |
| **Documents** | Flexport API v3 | `GET /documents?shipment_id={id}` | Document type (BOL, packing list, customs), file URL | Compliance documentation, audit trail |

---

### 3.6 PostgreSQL Data Warehouse (Internal Analytics)

The internal data warehouse stores historical aggregated data and serves as the foundation for trend analysis and P&L computation.

| Data Stream | Query Type | Query Pattern | Key Fields Retrieved | Use in KayaPure |
|---|---|---|---|---|
| **Daily Metrics** | Direct SQL | `SELECT date, revenue, ad_spend, cogs, shipping_cost, refunds, net_profit FROM daily_metrics WHERE date >= NOW() - INTERVAL '30 days' ORDER BY date` | Revenue, ad spend, COGS, shipping, refunds, net profit by day | P&L trend analysis, daily performance tracking |
| **SKU Performance** | Direct SQL | `SELECT s.sku, s.product_name, dm.revenue, dm.units_sold, dm.ad_spend, dm.margin FROM skus s JOIN daily_metrics dm ON s.id = dm.sku_id WHERE dm.date >= NOW() - INTERVAL '7 days'` | Per-SKU revenue, units, ad spend, margin | SKU-level profitability, portfolio optimization |
| **Inventory Risk** | Direct SQL | `SELECT sku, product_name, current_stock, daily_velocity, (current_stock / NULLIF(daily_velocity, 0)) as days_of_supply FROM skus WHERE (current_stock / NULLIF(daily_velocity, 0)) < 14` | Stock level, velocity, days of supply | Stock-out risk alerts, reorder recommendations |
| **Channel Performance** | Direct SQL | `SELECT channel, SUM(revenue) as revenue, SUM(ad_spend) as spend, SUM(revenue)/NULLIF(SUM(ad_spend),0) as roas FROM daily_metrics GROUP BY channel` | Revenue, spend, ROAS by channel | Cross-channel comparison, budget allocation |

---

### 3.7 Excel / Google Sheets (Warehouse & Sales Data) — NEW

This is the new data source category for connecting to spreadsheets maintained by the warehousing team and for parsing WhatsApp numbers and sales data.

| Data Stream | Source | MCP Tool | Key Fields Retrieved | Use in KayaPure |
|---|---|---|---|---|
| **Warehouse Inventory** | Excel (.xlsx) or Google Sheets | `read_data_from_excel` or `get_sheet_data` | SKU, product name, current stock, location, last updated, reorder point | Real-time inventory sync from warehouse team |
| **WhatsApp Contacts** | Excel (.xlsx) or Google Sheets | `read_data_from_excel` or `get_sheet_data` | Phone number, customer name, order reference, communication date | Customer outreach, order follow-up |
| **Sales Data** | Excel (.xlsx) or Google Sheets | `read_data_from_excel` or `get_sheet_data` | Date, product, quantity, amount, channel, payment method | Offline/manual sales tracking, reconciliation with Shopify |

---

## 4. Excel & Google Sheets MCP Integration

### 4.1 The Problem

Your warehousing team updates inventory data in Excel spreadsheets. You also need to parse WhatsApp numbers and sales data from spreadsheets. The question is: how does the LangGraph agent access this data through MCP?

### 4.2 Available MCP Servers

The following diagram shows the three integration options:

![Excel Integration Options](/home/ubuntu/excel-integration.png)

There are three viable approaches, each with a mature open-source MCP server:

### Option A: Local Excel Files — `haris-musa/excel-mcp-server`

| Attribute | Details |
|---|---|
| **Repository** | [github.com/haris-musa/excel-mcp-server](https://github.com/haris-musa/excel-mcp-server) |
| **Stars / Forks** | 3,400 / 376 |
| **License** | MIT |
| **Version** | v0.1.7 |
| **Transport** | stdio, SSE, Streamable HTTP |
| **Language** | Python (openpyxl) |
| **Key Tools** | `read_data_from_excel`, `write_data_to_excel`, `get_workbook_metadata`, `create_workbook`, `create_worksheet`, `apply_formula`, `create_chart`, `create_pivot_table`, `create_table`, `format_range`, `merge_cells`, `copy_range`, `insert_rows`, `insert_columns`, `delete_rows`, `delete_columns` |

This server works with local `.xlsx` files and does not require Microsoft Excel to be installed. The warehouse team would save their updated Excel files to a shared directory (or sync via Dropbox/OneDrive), and the MCP server reads from that directory. The `EXCEL_FILES_PATH` environment variable controls where the server looks for files.

**How it would work for your use cases:**

For **inventory data**: The warehouse team updates `inventory.xlsx` with columns like SKU, Product Name, Current Stock, Location, Last Updated. The Sensor Node calls `read_data_from_excel(filepath="inventory.xlsx", sheet_name="Stock Levels")` to pull the latest data.

For **WhatsApp numbers**: The team maintains `whatsapp-contacts.xlsx` with columns like Phone Number, Customer Name, Order Ref, Last Contact Date. The agent calls `read_data_from_excel(filepath="whatsapp-contacts.xlsx", sheet_name="Contacts")` to parse the numbers.

For **sales data**: Manual or offline sales are logged in `sales-data.xlsx`. The agent reads this to reconcile with Shopify order data.

**Limitation:** This approach requires the Excel files to be accessible on the server's filesystem. If the warehouse team works on their own machines, you need a file sync mechanism (Dropbox, OneDrive sync, rsync, or a shared network drive).

---

### Option B: Google Sheets (Recommended) — `xing5/mcp-google-sheets`

| Attribute | Details |
|---|---|
| **Repository** | [github.com/xing5/mcp-google-sheets](https://github.com/xing5/mcp-google-sheets) |
| **Stars / Forks** | 704 / 179 |
| **License** | MIT |
| **Version** | v0.6.0 |
| **Transport** | stdio, Docker |
| **Language** | Python |
| **Auth** | Google Service Account or OAuth 2.0 |
| **Key Tools** | `list_spreadsheets`, `create_spreadsheet`, `get_sheet_data`, `update_cells`, `batch_update_cells`, `add_rows`, `list_sheets`, `create_sheet`, `get_multiple_sheet_data`, `get_multiple_spreadsheet_summary`, `share_spreadsheet`, `add_columns`, `copy_sheet`, `rename_sheet` |

This is the **recommended approach** for the following reasons:

**Real-time access.** Google Sheets is cloud-native. The moment the warehouse team updates a cell, the MCP server can read the new value. There is no file sync delay.

**Multi-user editing.** Multiple warehouse team members can update the same spreadsheet simultaneously without file locking conflicts, which is a common problem with shared Excel files.

**Mobile access.** The warehouse team can update inventory from their phones using the Google Sheets app, which is particularly useful for on-the-floor stock counts.

**Version history.** Google Sheets automatically tracks every change with timestamps and user attribution, providing a built-in audit trail.

**No file system dependency.** The MCP server connects to Google Sheets via API, so the KayaPure backend does not need filesystem access to the warehouse team's machines.

**How it would work for your use cases:**

For **inventory data**: Create a Google Sheet called "KayaPure Inventory" shared with the warehouse team. The Sensor Node calls `get_sheet_data(spreadsheet_id="abc123", sheet="Stock Levels", range="A1:F500")` to pull the latest inventory.

For **WhatsApp numbers**: Create a "WhatsApp Contacts" sheet. The agent calls `get_sheet_data(spreadsheet_id="xyz789", sheet="Contacts")` to parse phone numbers and customer data.

For **sales data**: Create a "Manual Sales Log" sheet. The agent reads this and cross-references with Shopify orders to identify discrepancies.

---

### Option C: Cloud Excel via OneDrive/SharePoint — `Softeria/ms-365-mcp-server`

| Attribute | Details |
|---|---|
| **Repository** | [github.com/Softeria/ms-365-mcp-server](https://github.com/Softeria/ms-365-mcp-server) |
| **Auth** | Microsoft Graph API (Azure AD) |
| **Transport** | stdio |
| **Key Tools** | Read files, list drives, search, access Excel Online workbooks |

If your organization already uses Microsoft 365, this option allows the warehouse team to continue using Excel Online (via OneDrive or SharePoint) while the MCP server reads the files through the Microsoft Graph API. Microsoft also offers an official **SharePoint and OneDrive MCP Server** as part of their Agent 365 platform [11].

This option is best if the team is already deeply embedded in the Microsoft ecosystem and switching to Google Sheets would cause friction.

---

### 4.3 Recommendation

For KayaPure, **Option B (Google Sheets)** is the strongest choice because:

1. The warehouse team gets real-time, multi-user, mobile-friendly editing with zero setup cost.
2. The MCP server is mature (704 stars, 15+ tools, active development).
3. No file sync infrastructure is needed — everything is cloud-native.
4. The agent can both read and write to sheets, enabling it to update inventory records or flag issues directly.
5. Google Sheets can be connected to WhatsApp Business API via Google Apps Script for automated data capture, reducing manual entry.

If the team insists on using local Excel files, **Option A** works well and is the most popular Excel MCP server in the ecosystem (3,400 stars). The two options are not mutually exclusive — you can connect both MCP servers simultaneously via `MultiServerMCPClient` and let the agent access whichever data source is relevant.

---

## 5. Complete Sensor Node Data Source Summary

| Source Category | # of Data Streams | MCP Server | Status |
|---|---|---|---|
| Shopify Storefront | 6 | Shopify Storefront MCP (Official) + Shopify Admin MCP (Community) | Ready to use |
| Meta Ads | 5 | pipeboard-co/meta-ads-mcp (Community) | Ready to use |
| Google Ads | 4 | Google Ads MCP (Official) | Ready (read-only) |
| Stripe Payments | 8 | Stripe MCP (Official) | Ready to use |
| Flexport Logistics | 6 | Must build custom (FastMCP) | Needs development |
| PostgreSQL DWH | 4 | Must build custom (FastMCP) | Needs development |
| Excel / Google Sheets | 3 | haris-musa/excel-mcp-server or xing5/mcp-google-sheets | Ready to use |
| **Total** | **36** | | |

The Sensor Node aggregates **36 distinct data streams** from 7 source categories. Of these, 26 streams have production-ready MCP servers available today. Only 10 streams (Flexport + DWH) require custom MCP server development.

---

## 6. References

[1] Shopify, "REST Admin API Deprecation — GraphQL Migration Guide," https://shopify.dev/docs/api/admin-rest

[2] Shopify, "Shopify Storefront MCP," https://shopify.dev/docs/apps/build/storefront-mcp

[3] antoineschaller, "MCP Shopify — Shopify Admin API MCP Server (22 tools)," https://github.com/antoineschaller/shopify-mcp-server

[4] Meta, "Insights API — Marketing API," https://developers.facebook.com/docs/marketing-api/insights/

[5] pipeboard-co, "Meta Ads MCP Server (29 tools)," https://github.com/pipeboard-co/meta-ads-mcp

[6] Google, "Google Ads Query Language Overview," https://developers.google.com/google-ads/api/docs/query/overview

[7] Google, "Google Ads MCP Server," https://developers.google.com/google-ads/api/docs/developer-toolkit/mcp-server

[8] Stripe, "Stripe API Reference," https://docs.stripe.com/api

[9] Stripe, "Model Context Protocol (MCP) — Stripe Documentation," https://docs.stripe.com/mcp

[10] Flexport, "Supply Chain & Logistics APIs — Developer Portal," https://developers.flexport.com/

[11] Microsoft, "SharePoint and OneDrive MCP Server Reference," https://learn.microsoft.com/en-us/microsoft-agent-365/mcp-server-reference/odspremoteserver

[12] haris-musa, "Excel MCP Server (3.4k stars)," https://github.com/haris-musa/excel-mcp-server

[13] xing5, "MCP Google Sheets (704 stars)," https://github.com/xing5/mcp-google-sheets
