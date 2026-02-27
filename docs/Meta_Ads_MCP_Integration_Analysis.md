# Meta Ads MCP Server — Integration Analysis for KayaPure Commerce OS

**Author:** Manus AI
**Date:** February 27, 2026
**Status:** Analysis only — no code changes made

---

## Executive Summary

The [pipeboard-co/meta-ads-mcp](https://github.com/pipeboard-co/meta-ads-mcp) server is a mature, production-ready MCP server with 535 stars, 393 commits, and 93 releases [1]. It provides 29 tools covering the full Meta Ads lifecycle — from campaign creation to performance insights to audience targeting. Integrating it into KayaPure's existing backend is a **low-complexity task** that can be completed in approximately **4–6 hours of focused development**, primarily because the server offers a hosted remote endpoint that eliminates the need for self-hosting, and the `langchain-mcp-adapters` library provides a drop-in bridge to LangGraph.

This document maps every integration point, identifies the exact files that need to change, and provides a step-by-step implementation plan with effort estimates.

---

## 1. What the Meta Ads MCP Server Provides

The server is built in Python (99.7%) on the FastMCP framework and exposes 29 tools organized into seven functional categories [1]. The table below maps each category to the specific tools and their relevance to KayaPure's operations.

| Category | Tools | KayaPure Relevance |
|---|---|---|
| **Account Management** | `get_ad_accounts`, `get_account_info`, `get_account_pages` | Needed at setup time to discover and configure the ad account |
| **Campaign CRUD** | `get_campaigns`, `get_campaign_details`, `create_campaign` | Strategy Agent can create campaigns; Sensor Node reads campaign status |
| **Ad Set CRUD** | `get_adsets`, `get_adset_details`, `create_adset`, `update_adset` | Firecracker executor adjusts budgets and targeting on ad sets |
| **Ad & Creative CRUD** | `get_ads`, `create_ad`, `get_ad_details`, `get_ad_creatives`, `create_ad_creative`, `update_ad_creative`, `upload_ad_image`, `get_ad_image`, `update_ad` | Full creative management for automated ad optimization |
| **Performance Insights** | `get_insights` | **Critical** — replaces the mock `get_ad_spend_summary()` in the Sensor Node |
| **Targeting & Audience** | `search_interests`, `get_interest_suggestions`, `validate_interests`, `search_behaviors`, `search_demographics`, `search_geo_locations` | Enables the Strategy Agent to propose audience expansion actions |
| **Budget & Scheduling** | `create_budget_schedule` | Enables automated budget scheduling for promotional periods |
| **Search & Auth** | `search`, `get_login_link` | Generic search across entities; authentication management |

### Authentication Options

The server supports two authentication paths [2]:

**Option A — Pipeboard Hosted (Recommended for speed).** Connect to `https://mcp.pipeboard.co/meta-ads-mcp` with a Pipeboard API token. No infrastructure to manage. The token is obtained from [pipeboard.co/api-tokens](https://pipeboard.co/api-tokens) after connecting a Facebook Ads account.

**Option B — Self-Hosted.** Clone the repository, install dependencies, and run `python -m meta_ads_mcp --transport streamable-http --host 0.0.0.0 --port 9000`. This requires creating a Meta Developer App with the `ads_management` and `ads_read` permissions. This option gives full control but requires maintaining the server.

### Transport Protocol

The server uses **Streamable HTTP** transport, which means it exposes a standard HTTP endpoint at `/mcp` that accepts JSON-RPC 2.0 requests [2]. This is important because it means KayaPure's backend can connect to it as a standard HTTP client — no special IPC, stdio pipes, or sidecar processes are needed.

### Licensing

The server uses the Business Source License 1.1 [1]. This means it is free to use for individual and business purposes, free to modify and redistribute, but cannot be offered as a competing hosted MCP service. It converts to Apache 2.0 on January 1, 2029. This license is fully compatible with KayaPure's use case.

---

## 2. Current KayaPure Code That Gets Replaced

The integration touches **four files** in the existing backend. No other files need to change. The table below maps each file to the specific changes required.

| File | Current State | What Changes | Lines Affected |
|---|---|---|---|
| `backend/services/marketing.py` | 128 lines of mock data with hardcoded campaigns and random number generation | **Replaced entirely** by MCP client calls. The `MarketingService` class becomes a thin wrapper around MCP tools, or is removed altogether if the LangGraph agent calls MCP tools directly. | All 128 lines |
| `backend/graph/workflow.py` (line 91) | `ad_spend_data = await marketing_service.get_ad_spend_summary()` | Changes to an MCP tool call: `mcp_meta_ads_get_insights(object_id=account_id, time_range={"since":"today","until":"today"})` | ~5 lines in `sensor_node()` |
| `backend/graph/workflow.py` (lines 252-256) | Strategy Agent proposes `budget_reduction` sub-actions with mock parameters | Sub-actions now reference real MCP tools: `mcp_meta_ads_update_adset(adset_id=X, daily_budget=Y)` | ~10 lines in `strategy_agent()` |
| `backend/requirements.txt` | Does not include MCP dependencies | Add `langchain-mcp-adapters>=0.1.0` and `mcp[cli]>=1.12.0` | 2 new lines |

### What Does NOT Change

The following components remain completely untouched:

The **P&L Analyzer node** (`p_and_l_analyzer`) does not change because it operates on the state dictionary, not on the marketing service directly. As long as `ad_spend_data` is populated in the state (which the Sensor Node does), the P&L calculations work identically regardless of whether the data came from mock or MCP.

The **Human Approval Gate** and **Firecracker Executor** nodes do not change because they operate on `proposed_actions` and `current_action` state fields, which are action descriptions — not API calls. The executor would gain the ability to call real MCP tools instead of mock functions, but the node structure remains the same.

The **database models, API routes, and frontend** are completely unaffected.

---

## 3. Integration Architecture

There are two architectural approaches for connecting the Meta Ads MCP server to KayaPure's LangGraph workflow. The choice depends on how much autonomy you want the agent to have.

### Approach A — MCP Tools as LangGraph Tools (Recommended)

In this approach, the MCP tools are loaded at startup via `langchain-mcp-adapters` and injected into the LangGraph agent as callable tools. The Strategy Agent node can then reason about which Meta Ads tools to call and with what parameters.

```
KayaPure Backend (FastAPI)
    │
    ├── startup: MultiServerMCPClient connects to Meta Ads MCP
    │             ↓
    │         load_mcp_tools() → List[BaseTool]
    │             ↓
    │         Inject tools into LangGraph StateGraph
    │
    ├── sensor_node: calls mcp_meta_ads_get_insights(account_id, time_range)
    │                calls mcp_meta_ads_get_campaigns(account_id)
    │                → populates state["ad_spend_data"]
    │
    ├── strategy_agent: LLM has access to all 29 MCP tools
    │                   Can propose: "call mcp_meta_ads_update_adset to reduce budget"
    │                   → populates state["proposed_actions"]
    │
    └── firecracker_executor: calls the actual MCP tool inside the VM
                              e.g., mcp_meta_ads_update_adset(adset_id, daily_budget)
```

The key code pattern uses `langchain-mcp-adapters` [3]:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

async with MultiServerMCPClient({
    "meta-ads": {
        "url": "https://mcp.pipeboard.co/meta-ads-mcp",
        "transport": "streamable_http",
        "headers": {"Authorization": f"Bearer {PIPEBOARD_TOKEN}"}
    }
}) as client:
    tools = client.get_tools()  # Returns 29 LangChain-compatible tools
    # Inject into LangGraph agent
```

### Approach B — MCP as a Service Layer (Simpler)

In this approach, the existing `MarketingService` class is refactored to call MCP tools internally, preserving the current interface. The rest of the codebase does not change at all.

```python
class MarketingService:
    async def get_ad_spend_summary(self):
        # Instead of mock data, call MCP
        result = await self.mcp_client.call_tool(
            "mcp_meta_ads_get_insights",
            {"object_id": self.account_id, "level": "account", "time_range": {"since": "today", "until": "today"}}
        )
        return self._transform_insights_to_spend_summary(result)
```

**Recommendation:** Start with **Approach B** for the fastest integration (2–3 hours), then migrate to **Approach A** when you want the LLM agent to have direct access to all 29 tools for autonomous decision-making.

---

## 4. Step-by-Step Implementation Plan

| Step | Task | Effort | Dependencies |
|---|---|---|---|
| **1** | Create a Pipeboard account and connect your Facebook Ads account at [pipeboard.co](https://pipeboard.co). Obtain your API token from [pipeboard.co/api-tokens](https://pipeboard.co/api-tokens). | 15 min | Facebook Ads account with active campaigns |
| **2** | Add `PIPEBOARD_API_TOKEN` to `backend/.env` and update `config.py` to read it. | 5 min | Step 1 |
| **3** | Add `langchain-mcp-adapters>=0.1.0` and `mcp[cli]>=1.12.0` to `requirements.txt` and install. | 5 min | None |
| **4** | Create `backend/services/mcp_client.py` — a singleton that initializes `MultiServerMCPClient` at startup and provides a `get_tools()` method. | 30 min | Step 3 |
| **5** | Refactor `backend/services/marketing.py` — replace mock methods with MCP tool calls. Map `get_insights` response format to the existing `ad_spend_data` schema expected by the P&L Analyzer. | 1–2 hours | Step 4 |
| **6** | Update `sensor_node()` in `workflow.py` — replace `marketing_service.get_ad_spend_summary()` with the refactored MCP-backed method. | 15 min | Step 5 |
| **7** | Update `strategy_agent()` — modify the Inventory Shield sub-actions to reference real MCP tool names (`mcp_meta_ads_update_adset`) instead of generic `budget_reduction`. | 30 min | Step 5 |
| **8** | Update `firecracker_executor_node()` — when executing a `budget_reduction` sub-action, call the actual `mcp_meta_ads_update_adset` tool via the MCP client. | 30 min | Step 4 |
| **9** | Test end-to-end: run agent cycle → verify real Meta Ads data flows through P&L → verify budget adjustment proposals contain real adset IDs → approve and verify the budget change in Meta Ads Manager. | 1 hour | Steps 1–8 |
| **10** | Update the frontend API client if the response schema changed (likely minimal or no changes needed). | 15 min | Step 9 |

**Total estimated effort: 4–6 hours** for a developer familiar with the codebase.

---

## 5. Data Mapping — Meta Ads Insights to KayaPure Schema

The most critical integration point is mapping the `mcp_meta_ads_get_insights` response to the `ad_spend_data` dictionary that the P&L Analyzer expects. The table below shows the field mapping.

| KayaPure Field (`ad_spend_data`) | Meta Ads Insights Field | Notes |
|---|---|---|
| `total_spend` | `spend` | Direct mapping; Meta returns as string, convert to float |
| `campaigns[].spend` | `spend` (at campaign level) | Use `level: "campaign"` in the insights call |
| `campaigns[].clicks` | `clicks` | Direct mapping |
| `campaigns[].impressions` | `impressions` | Direct mapping |
| `campaigns[].conversions` | `actions[type="offsite_conversion"]` | Filter the `actions` array by action type |
| `campaigns[].cpc` | `cpc` | Direct mapping |
| `campaigns[].ctr` | `ctr` | Direct mapping; Meta returns as percentage string |
| `campaigns[].roas` | `purchase_roas[0].value` | From the `purchase_roas` action breakdown |
| `platform_breakdown.meta` | Sum of all campaign `spend` | Aggregate from campaign-level data |

The `mcp_meta_ads_get_insights` tool accepts an `action_attribution_windows` parameter [1] that controls how conversions are attributed (e.g., `1d_click`, `7d_click`, `1d_view`). For KayaPure's P&L calculations, `7d_click` (the default) is appropriate.

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Pipeboard service downtime** | Low | High — Sensor Node fails to collect ad data | Implement fallback to cached data; add retry logic with exponential backoff |
| **Meta API rate limits** | Medium | Medium — Insights calls throttled during high-frequency agent cycles | Cache insights data for 15 minutes; Meta allows 200 calls per hour per ad account |
| **Token expiration** | Low | Medium — Auth fails silently | Pipeboard handles token refresh automatically for hosted mode; monitor for 401 responses |
| **Response schema changes** | Low | Medium — Data mapping breaks | Pin to a specific MCP server version; add schema validation in the transformation layer |
| **BSL license conflict** | Very Low | Low — Only restricts competing hosted services | KayaPure is a commerce platform, not a competing MCP hosting service |

---

## 7. What You Gain Beyond Replacing Mocks

Integrating the Meta Ads MCP server does not just replace mock data with real data. It unlocks capabilities that the current architecture cannot support:

**Autonomous campaign creation.** The Strategy Agent can propose creating entirely new campaigns (e.g., "Launch a retargeting campaign for cart abandoners from the last 7 days") using `mcp_meta_ads_create_campaign`, `create_adset`, and `create_ad`. The human gate approves, and the Firecracker executor creates the campaign in Meta.

**Audience intelligence.** The targeting tools (`search_interests`, `search_behaviors`, `search_demographics`, `search_geo_locations`) allow the Strategy Agent to discover new audience segments. For example, if the agent notices high ROAS on a particular demographic, it can propose expanding targeting to similar audiences.

**Creative optimization.** The creative tools (`create_ad_creative`, `update_ad_creative`, `upload_ad_image`) enable the agent to propose A/B tests with different headlines and descriptions, then monitor performance via `get_insights` and recommend winners.

**Budget scheduling.** The `create_budget_schedule` tool enables the agent to automatically increase budgets during high-demand periods (e.g., supplement sales spikes in January) and reduce them during slow periods.

---

## 8. Conclusion

The Meta Ads MCP server is the most mature and feature-complete MCP server relevant to KayaPure's stack. Its hosted option eliminates infrastructure overhead, its 29 tools cover the full Meta Ads lifecycle, and the `langchain-mcp-adapters` library provides a clean bridge to LangGraph. The integration is a 4–6 hour task that transforms the marketing service from a mock data generator into a live connection to your actual ad campaigns — and unlocks autonomous campaign management capabilities that go far beyond what the current architecture supports.

The recommended path is to start with Approach B (MCP as a service layer behind the existing interface) for a quick win, then evolve to Approach A (MCP tools as first-class LangGraph tools) when you are ready to give the Strategy Agent direct access to all 29 Meta Ads tools.

---

## References

[1]: https://github.com/pipeboard-co/meta-ads-mcp "pipeboard-co/meta-ads-mcp — GitHub Repository"
[2]: https://github.com/pipeboard-co/meta-ads-mcp/blob/main/STREAMABLE_HTTP_SETUP.md "Meta Ads MCP — Streamable HTTP Transport Setup Guide"
[3]: https://github.com/langchain-ai/langchain-mcp-adapters "langchain-ai/langchain-mcp-adapters — LangChain MCP Adapters"
