# KayaPure Commerce OS — MCP Architecture Research and Design

**Author:** Manus AI  
**Date:** February 27, 2026  
**Status:** Architecture Proposal (No Code Changes)

---

## 1. Executive Summary

The KayaPure Autonomous Commerce OS currently connects to external services (Shopify, Meta Ads, Google Ads, Flexport) through direct REST API integrations — each with its own authentication handling, data mapping, and error logic baked into Python service classes. While this approach works for the current prototype with four or five integrations, the stated goal is for the integration list to grow over time. This document evaluates the **Model Context Protocol (MCP)** as the standardized integration layer for the system, catalogs the open-source MCP servers available for each service in the KayaPure stack, and presents a complete architecture design for adopting MCP.

The core finding is that **MCP adoption is not only feasible but strategically advantageous** for KayaPure. Official MCP servers already exist from Shopify, Google, and Stripe. A mature community server exists for Meta Ads. For services without existing MCP servers (such as Flexport), the **FastMCP** Python framework makes it straightforward to build custom wrappers around REST APIs. The **langchain-mcp-adapters** library provides a production-ready bridge between MCP servers and LangGraph agents, meaning the existing 5-node workflow can be upgraded without a fundamental rewrite.

---

## 2. What is MCP and Why It Matters

The **Model Context Protocol** is an open standard created by Anthropic that provides a uniform interface for LLM-based agents to discover and invoke external tools [1]. Instead of hardcoding each API integration, services are exposed as MCP servers — each one declares what tools it offers, what parameters they accept, and what data they return. An agent connects to these servers as a client and can dynamically discover and call any tool across all connected services.

The protocol supports three core primitives: **Tools** (executable functions the agent can invoke), **Resources** (data the agent can read), and **Prompts** (reusable templates for common interactions) [2]. Communication happens over two transport mechanisms: **stdio** (local subprocess communication) and **HTTP/Streamable HTTP** (remote server communication) [3].

For KayaPure, the critical distinction is this: the current direct integration approach requires writing and maintaining custom "glue code" for every API — authentication, request formatting, response parsing, error handling, and retry logic. With MCP, each integration becomes a self-contained server that the LangGraph agent discovers and uses through a standardized interface. Adding a new channel becomes deploying a server, not modifying core orchestration code.

---

## 3. Open-Source MCP Server Inventory

The following table catalogs every MCP server relevant to the KayaPure Commerce OS stack, organized by domain. Each entry has been individually verified through direct examination of the source repository or official documentation.

### 3.1 Commerce and Storefront

| MCP Server | Source | Tools | Transport | License | Maturity |
|---|---|---|---|---|---|
| **Shopify Storefront MCP** | Official (Shopify) [4] | Product discovery, cart management, store info, checkout, order tracking | stdio / HTTP | Shopify Terms | Production-ready |
| **Shopify Admin MCP** (antoineschaller) | Community [5] | 22 tools: product CRUD, order management, customer management, inventory, analytics, collections, discounts | stdio | MIT | Stable (v1.0.0) |
| **Shopify Dev MCP** | Official (Shopify) | Search docs, explore API schemas, developer tooling | stdio | Shopify Terms | Production-ready |
| **commercetools Commerce MCP** | Vendor (commercetools) [6] | Cart operations, discounts, inventory checks, order placement | HTTP | Commercial | Production-ready |

The **Shopify Storefront MCP** is the recommended choice for KayaPure because it is maintained by Shopify directly and covers the full storefront lifecycle — from product discovery through checkout. The community **Shopify Admin MCP** complements it with 22 administrative tools for back-office operations like inventory updates, discount creation, and analytics retrieval [5].

### 3.2 Advertising — Meta (Facebook/Instagram)

| MCP Server | Source | Tools | Transport | License | Maturity |
|---|---|---|---|---|---|
| **Meta Ads MCP** (pipeboard-co) | Community [7] | 29 tools: campaigns, ad sets, ads, creatives, insights, targeting, budget schedules, interest/behavior/geo search | stdio / HTTP | BSL 1.1 (Apache 2.0 in 2029) | Very active (527 stars, 393 commits, v1.0.46) |
| **gomarble-ai/facebook-ads-mcp-server** | Community | Meta Ads data interface | stdio | Open source | Early |
| **brijr/meta-mcp** | Community | Meta Marketing API | stdio | Open source | Early |

The **pipeboard-co/meta-ads-mcp** server is the clear winner here. With 527 GitHub stars, 130 forks, and 393 commits as of February 2026, it is one of the most actively maintained MCP servers in the entire ecosystem [7]. It exposes 29 tools covering the full Meta Ads lifecycle — from creating campaigns and ad sets to uploading creatives, retrieving performance insights, and searching targeting options (interests, behaviors, demographics, geo-locations). It supports both stdio and Streamable HTTP transports, and includes OAuth authentication handling.

### 3.3 Advertising — Google

| MCP Server | Source | Tools | Transport | License | Maturity |
|---|---|---|---|---|---|
| **Google Ads MCP** | Official (Google) [8] | `list_accessible_customers`, `search` (GAQL queries for campaign metrics, budgets, status) | stdio | Open source | Production-ready (read-only) |

The **official Google Ads MCP server** is maintained by Google's marketing solutions team and provides a standardized bridge to the Google Ads API [8]. It is currently **read-only**, meaning it can retrieve campaign performance data, budgets, and account information, but cannot modify campaigns. For KayaPure's sensor and P&L analysis nodes, this is sufficient. For the executor node (which would need to adjust bids or budgets), you would either need to wait for Google to add write capabilities or build a custom MCP server that wraps the Google Ads API's mutate endpoints.

### 3.4 Payments

| MCP Server | Source | Tools | Transport | License | Maturity |
|---|---|---|---|---|---|
| **Stripe MCP** | Official (Stripe) [9] | 25 tools: account info, balance, customers, products, prices, invoices, payment links, subscriptions, refunds, disputes, search | HTTP | Stripe Terms | Production-ready |

The **official Stripe MCP server** is hosted at `https://mcp.stripe.com` and provides 25 tools covering the full Stripe API surface [9]. Unlike most MCP servers that run locally, Stripe's server is a remote HTTP endpoint — you connect to it directly, and authentication is handled through Stripe's dashboard. The tools include both read operations (`retrieve_balance`, `list_customers`, `list_invoices`) and write operations (`create_product`, `create_price`, `create_payment_link`, `create_refund`), making it fully suitable for both the sensor/analysis and executor nodes in the KayaPure workflow.

### 3.5 Order Management and Logistics

| MCP Server | Source | Tools | Transport | License | Maturity |
|---|---|---|---|---|---|
| **Pipe17 MCP** | Vendor (Pipe17) [10] | Query, retrieve, and manage omnichannel commerce operations — orders, inventory, fulfillment | HTTP | Commercial | Production-ready |
| **Fluent Commerce MCP** | Vendor (Fluent Commerce) [11] | Order management for retail AI agents | HTTP | Commercial | Production-ready |
| **Flexport MCP** | **Does not exist** | — | — | — | Must be built custom |

Pipe17 is particularly relevant because it positions itself as an "AI-native order management" platform with a dedicated MCP server [10]. For logistics specifically, **no open-source Flexport MCP server exists**. Flexport provides a REST API at `developers.flexport.com`, but the MCP wrapper would need to be built as a custom server using FastMCP.

### 3.6 Data Warehouse and Database

| MCP Server | Source | Tools | Transport | License | Maturity |
|---|---|---|---|---|---|
| **PostgreSQL MCP** (call518) | Community | Professional PostgreSQL 12–17 monitoring and management | stdio | Open source | Stable |
| **Google MCP Toolbox for Databases** | Official (Google) | PostgreSQL support, query execution | HTTP | Apache 2.0 | Production-ready |
| **Anthropic Reference PostgreSQL MCP** | Official (Anthropic) | Reference implementation for database access | stdio | MIT | Reference |

For the KayaPure data warehouse, a custom MCP server wrapping the existing PostgreSQL database is recommended over using a generic PostgreSQL MCP server. This allows you to expose domain-specific tools like `query_pnl_summary`, `get_sku_metrics`, and `get_inventory_risk` rather than raw SQL access, which is both safer and more useful for the LLM agent.

---

## 4. System Architecture Design

The following diagram shows the complete MCP-based architecture for KayaPure Commerce OS:

![KayaPure MCP Architecture](/home/ubuntu/mcp-architecture.png)

The architecture is organized into four layers:

**Presentation Layer** — The React dashboard (Control Tower) communicates with the backend via REST and WebSocket connections, unchanged from the current implementation.

**Orchestration Layer** — The FastAPI gateway receives requests and delegates to the LangGraph agent. The critical change is that the agent's tool nodes now use **MultiServerMCPClient** from `langchain-mcp-adapters` instead of direct service calls. This client manages connections to all MCP servers and converts MCP tools into LangChain-compatible tools that the LangGraph state graph can invoke [3].

**MCP Server Layer** — This is the new integration layer. It contains three categories of servers: official vendor servers (Shopify, Google, Stripe), community servers (Meta Ads, Pipe17), and custom servers built with FastMCP (Flexport, Data Warehouse, Inventory). Each server is a self-contained process that handles its own authentication, API communication, and error handling.

**Execution Layer** — Approved actions are executed inside Firecracker microVMs with hardware-signed audit trails, unchanged from the current implementation.

---

## 5. LangGraph Workflow with MCP Tools

The following diagram shows how MCP tools map to each node in the existing 5-node LangGraph workflow:

![LangGraph MCP Workflow](/home/ubuntu/mcp-langgraph-flow.png)

Each node in the workflow uses specific MCP tools:

**Node 1 — Sensor:** Gathers real-time data from all connected channels. Uses `shopify.list_products` for storefront data, `meta_ads.get_insights` for advertising performance, `google_ads.search` for Google campaign metrics, and `dwh.query_metrics` for warehouse data.

**Node 2 — P&L Analyzer:** Computes profitability analysis. Uses `dwh.query_pnl` for historical financial data, `stripe.retrieve_balance` for current payment balances, and `pipe17.get_orders` for order fulfillment costs.

**Node 3 — Strategy:** The LLM reasoning node. It receives the structured context from Nodes 1 and 2, then uses its reasoning capability to propose actions. This node does not call MCP tools directly — it consumes the data gathered by previous nodes and generates action proposals.

**Node 4 — Human Gate:** Presents proposed actions on the dashboard for owner approval. No MCP tools are used here — this is a WebSocket-driven UI interaction.

**Node 5 — Executor:** Carries out approved actions. Uses `shopify.update_product` for price changes, `meta_ads.update_adset` for ad budget adjustments, `stripe.create_price` for new pricing, and `pipe17.create_order` for reorder placement. All executions happen inside Firecracker microVMs.

---

## 6. Integration Pattern: langchain-mcp-adapters

The `langchain-mcp-adapters` library is the official LangChain integration for MCP [3]. It provides the `MultiServerMCPClient` class, which manages connections to multiple MCP servers simultaneously and converts their tools into LangChain-compatible tools. The integration with LangGraph is straightforward because LangGraph agents already consume LangChain tools.

The key code pattern for KayaPure would be:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "shopify": {
        "transport": "stdio",
        "command": "npx",
        "args": ["@shopify/storefront-mcp"],
        "env": {"SHOPIFY_ACCESS_TOKEN": "..."}
    },
    "meta_ads": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["meta-ads-mcp"],
        "env": {"META_ACCESS_TOKEN": "..."}
    },
    "google_ads": {
        "transport": "stdio",
        "command": "pipx",
        "args": ["run", "--spec", "git+https://github.com/googleads/google-ads-mcp.git", "google-ads-mcp"],
        "env": {"GOOGLE_ADS_DEVELOPER_TOKEN": "..."}
    },
    "stripe": {
        "transport": "http",
        "url": "https://mcp.stripe.com",
        "headers": {"Authorization": "Bearer sk_..."}
    },
    "data_warehouse": {
        "transport": "stdio",
        "command": "python",
        "args": ["mcp_servers/dwh_server.py"]
    },
    "flexport": {
        "transport": "stdio",
        "command": "python",
        "args": ["mcp_servers/flexport_server.py"]
    }
})

# Get all tools from all servers
tools = await client.get_tools()

# These tools are now directly usable in the LangGraph workflow
# The agent can discover and invoke any tool from any server
```

The `MultiServerMCPClient` is **stateless by default** — each tool invocation creates a fresh MCP session, executes the tool, and cleans up. For servers that need persistent state (such as maintaining an authenticated session), stateful sessions can be created explicitly using `client.session("server_name")` [3].

---

## 7. Custom MCP Servers to Build

Three custom MCP servers need to be built using the **FastMCP** Python framework [2]. FastMCP provides decorators to declare tools, resources, and prompts, making it straightforward to wrap existing REST APIs.

### 7.1 Flexport MCP Server

Since no open-source Flexport MCP server exists, this must be built from scratch. The server would wrap Flexport's REST API and expose tools such as:

| Tool | Description | Flexport API Endpoint |
|---|---|---|
| `get_shipments` | List active shipments with status | `GET /shipments` |
| `get_shipment_details` | Get tracking and milestone data for a shipment | `GET /shipments/{id}` |
| `create_booking` | Create a new freight booking | `POST /bookings` |
| `get_invoices` | Retrieve logistics invoices | `GET /invoices` |
| `get_products` | List products in Flexport inventory | `GET /products` |

### 7.2 Data Warehouse MCP Server

Rather than exposing raw SQL access, this server would provide domain-specific tools that encapsulate common analytical queries:

| Tool | Description | Underlying Query |
|---|---|---|
| `query_pnl_summary` | Get P&L summary for a date range | Aggregation over daily_metrics |
| `get_sku_metrics` | Get performance metrics for a specific SKU | Join skus + daily_metrics |
| `get_inventory_risk` | Identify SKUs at risk of stockout | WHERE days_of_supply < threshold |
| `get_channel_performance` | Compare performance across sales channels | GROUP BY channel |
| `get_trend_analysis` | Revenue/margin trends over time | Time-series aggregation |

### 7.3 Inventory MCP Server

This server would provide real-time inventory management tools:

| Tool | Description |
|---|---|
| `get_stock_levels` | Current stock levels across all warehouses |
| `get_reorder_recommendations` | AI-suggested reorder quantities based on velocity |
| `update_safety_stock` | Adjust safety stock thresholds |
| `get_fulfillment_status` | Track fulfillment pipeline status |

Each of these servers can be built in approximately 100–200 lines of Python using FastMCP, since the framework handles all MCP protocol compliance, transport negotiation, and tool discovery automatically [2].

---

## 8. How This Differs from the Current Architecture

The following table summarizes the concrete changes between the current direct integration approach and the proposed MCP architecture:

| Aspect | Current (Direct REST) | Proposed (MCP) |
|---|---|---|
| **Adding a new integration** | Write a new Python service class with auth, request/response mapping, error handling | Deploy an MCP server (often pre-built) and add one entry to the MultiServerMCPClient config |
| **Agent tool discovery** | Hardcoded — the agent only knows about tools explicitly wired into the graph | Dynamic — the agent discovers available tools at runtime from all connected MCP servers |
| **Authentication** | Each service class manages its own auth tokens | Each MCP server manages its own auth; the orchestrator only needs server connection config |
| **Error isolation** | A bug in one service class can crash the entire backend | Each MCP server runs as a separate process; a crash in one does not affect others |
| **Testing** | Must mock each API individually | Each MCP server can be tested independently; the orchestrator tests against the MCP interface |
| **Community leverage** | Every integration is custom code | Can adopt open-source MCP servers maintained by vendors and community |
| **LLM context** | Agent receives pre-formatted data from hardcoded service calls | Agent receives structured tool results with metadata, enabling richer reasoning |

---

## 9. Implementation Roadmap

The migration to MCP can be done incrementally without disrupting the existing system. The recommended phased approach is:

**Phase 1 — Foundation (1–2 weeks).** Install `langchain-mcp-adapters` and `fastmcp`. Build the Data Warehouse MCP server as the first custom server, since it wraps the existing PostgreSQL database and can be tested entirely locally. Modify the Sensor node in the LangGraph workflow to use the MCP tool instead of the direct database query. Validate that the existing functionality is preserved.

**Phase 2 — Adopt Official Servers (1–2 weeks).** Connect the Shopify Storefront MCP (official), Google Ads MCP (official), and Stripe MCP (official) servers. These are production-ready and require only configuration, not code. Update the corresponding LangGraph nodes to use MCP tools instead of direct service calls. Remove the old service classes as each is replaced.

**Phase 3 — Community Servers (1 week).** Connect the Meta Ads MCP server (pipeboard-co). This is the most feature-rich community server and covers all 29 Meta Ads operations currently needed. Optionally connect the Pipe17 MCP server for order management.

**Phase 4 — Custom Servers (1–2 weeks).** Build the Flexport MCP server and Inventory MCP server using FastMCP. These are the only integrations that require new code, and each is approximately 100–200 lines of Python.

**Phase 5 — Dynamic Discovery (Optional).** Implement a server registry that allows new MCP servers to be added via configuration without code changes. This enables the "plug-in a new channel" vision described in the original requirements.

---

## 10. Risks and Considerations

**Latency overhead.** MCP adds a protocol layer between the agent and the external API. For stdio-based servers, this overhead is negligible (subprocess communication). For HTTP-based servers like Stripe's hosted MCP, latency depends on network conditions. The current direct REST approach has lower latency per call, but the difference is typically under 100ms and is unlikely to be noticeable in an agent workflow that already involves LLM inference.

**Google Ads write limitations.** The official Google Ads MCP server is currently read-only [8]. If the executor node needs to modify Google Ads campaigns (adjust bids, change budgets), you would need to either build a custom MCP server wrapping the Google Ads API's mutate endpoints, or wait for Google to add write capabilities.

**Meta Ads licensing.** The pipeboard-co/meta-ads-mcp server uses the Business Source License 1.1, which is free for individual and business use but prohibits offering it as a competing hosted service [7]. This is not a concern for KayaPure since you are using it as an internal tool, not reselling it as a service.

**Operational complexity.** Running multiple MCP server processes adds operational overhead compared to a monolithic backend. This can be mitigated with Docker Compose (one container per MCP server) and health monitoring. The `MultiServerMCPClient` handles connection management and reconnection automatically.

---

## 11. References

[1] Anthropic, "Model Context Protocol Specification," https://modelcontextprotocol.io/

[2] FastMCP, "Welcome to FastMCP — the best way to build MCP servers in Python," https://gofastmcp.com/

[3] LangChain, "Model Context Protocol (MCP) — langchain-mcp-adapters," https://docs.langchain.com/oss/python/langchain/mcp

[4] Shopify, "Shopify Storefront MCP," https://shopify.dev/docs/apps/build/storefront-mcp

[5] antoineschaller, "MCP Shopify — Shopify Admin API MCP Server," https://github.com/antoineschaller/shopify-mcp-server

[6] commercetools, "Commerce MCP: AI for Your Enterprise," https://commercetools.com/commerce-platform/commerce-mcp

[7] pipeboard-co, "Meta Ads MCP Server," https://github.com/pipeboard-co/meta-ads-mcp

[8] Google, "Google Ads MCP Server: Developer Integration Guide," https://developers.google.com/google-ads/api/docs/developer-toolkit/mcp-server

[9] Stripe, "Model Context Protocol (MCP) — Stripe Documentation," https://docs.stripe.com/mcp

[10] Pipe17, "Introducing the Pipe17 MCP Server: AI Order Management," https://pipe17.com/ai/mcp/

[11] Fluent Commerce, "Fluent Commerce Launches Order Management MCP Server," https://fluentcommerce.com/resources/news/fluent-commerce-launches-order-management-mcp-server-to-power-ai-agent-interactions/
