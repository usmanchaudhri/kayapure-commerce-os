"""
KayaPure Commerce OS - Marketing Service
Meta Ads integration via MCP (Model Context Protocol).

Architecture: Approach B — MCP as a Service Layer
This service wraps MCP tool calls behind the same interface that the rest of
the codebase already uses (get_ad_spend_summary, adjust_campaign_budget, etc.).
The LangGraph workflow and API routes require zero changes.

When the MCP connection is unavailable (no token configured, server down, etc.),
the service falls back to mock data so the system remains functional during
development and testing.
"""

import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kayapure.marketing")


class MarketingService:
    """
    Meta Ads integration via the Pipeboard-hosted MCP server.
    Preserves the original interface so workflow.py and main.py need no changes.
    """

    def __init__(self):
        self._mcp_client = None  # Set during app startup via configure()
        self._meta_account_id: Optional[str] = None
        self._use_mcp = False

        # Fallback mock campaigns (used when MCP is not available)
        self._mock_campaigns = {
            "meta_brand_awareness": {
                "platform": "meta",
                "name": "KayaPure Brand Awareness",
                "daily_budget": 200.0,
                "status": "active",
                "cpc": 1.20,
                "ctr": 2.8,
                "roas": 3.5,
            },
            "meta_retargeting": {
                "platform": "meta",
                "name": "KayaPure Retargeting",
                "daily_budget": 150.0,
                "status": "active",
                "cpc": 0.85,
                "ctr": 4.2,
                "roas": 5.1,
            },
            "google_search_turmeric": {
                "platform": "google",
                "name": "Turmeric Supplements - Search",
                "daily_budget": 180.0,
                "status": "active",
                "cpc": 2.10,
                "ctr": 3.5,
                "roas": 4.2,
            },
            "google_shopping": {
                "platform": "google",
                "name": "KayaPure Shopping Ads",
                "daily_budget": 250.0,
                "status": "active",
                "cpc": 0.95,
                "ctr": 5.1,
                "roas": 4.8,
            },
            "meta_lookalike": {
                "platform": "meta",
                "name": "Lookalike - Health Enthusiasts",
                "daily_budget": 120.0,
                "status": "active",
                "cpc": 1.45,
                "ctr": 2.1,
                "roas": 2.9,
            },
        }

    def configure(self, mcp_client, meta_account_id: Optional[str] = None) -> None:
        """
        Configure the service with an MCP client instance.
        Called during FastAPI app startup after the MCP manager is initialized.
        """
        self._mcp_client = mcp_client
        self._meta_account_id = meta_account_id
        self._use_mcp = mcp_client is not None and meta_account_id is not None
        mode = "MCP (live Meta Ads)" if self._use_mcp else "MOCK (fallback data)"
        logger.info(f"MarketingService configured in {mode} mode")

    # ================================================================
    # Primary Interface — called by workflow.py sensor_node and main.py
    # ================================================================

    async def get_ad_spend_summary(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get total ad spend across all platforms.
        Interface is identical to the original mock version.
        """
        if self._use_mcp:
            try:
                return await self._mcp_get_ad_spend_summary(date)
            except Exception as e:
                logger.warning(f"MCP call failed, falling back to mock: {e}")
                return await self._mock_get_ad_spend_summary(date)
        else:
            return await self._mock_get_ad_spend_summary(date)

    async def adjust_campaign_budget(
        self, campaign_id: str, new_budget: float
    ) -> Dict[str, Any]:
        """
        Adjust campaign daily budget.
        In MCP mode, calls mcp_meta_ads_update_adset to change the budget.
        """
        if self._use_mcp:
            try:
                return await self._mcp_adjust_campaign_budget(campaign_id, new_budget)
            except Exception as e:
                logger.warning(f"MCP budget adjustment failed, falling back to mock: {e}")
                return await self._mock_adjust_campaign_budget(campaign_id, new_budget)
        else:
            return await self._mock_adjust_campaign_budget(campaign_id, new_budget)

    async def get_total_daily_spend(self) -> float:
        """Get total daily ad spend across all campaigns."""
        summary = await self.get_ad_spend_summary()
        return summary.get("total_spend", 0.0)

    # ================================================================
    # Additional MCP-powered methods (new capabilities)
    # ================================================================

    async def get_campaigns(self) -> List[Dict[str, Any]]:
        """
        Fetch all campaigns from Meta Ads via MCP.
        New capability not available in the mock version.
        """
        if not self._use_mcp:
            return [
                {"id": k, "name": v["name"], "status": v["status"], "daily_budget": v["daily_budget"]}
                for k, v in self._mock_campaigns.items()
                if v["platform"] == "meta"
            ]

        try:
            result = await self._mcp_client.call_tool(
                "get_campaigns",
                {"account_id": self._meta_account_id},
            )
            return self._normalize_campaigns_response(result)
        except Exception as e:
            logger.warning(f"MCP get_campaigns failed: {e}")
            return []

    async def get_campaign_insights(
        self,
        campaign_id: str,
        time_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get detailed insights for a specific campaign via MCP.
        New capability not available in the mock version.
        """
        if not self._use_mcp:
            return {"error": "MCP not configured, insights unavailable"}

        if time_range is None:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            time_range = {"since": today, "until": today}

        try:
            result = await self._mcp_client.call_tool(
                "get_insights",
                {
                    "object_id": campaign_id,
                    "time_range": time_range,
                    "level": "campaign",
                    "fields": "spend,impressions,clicks,cpc,ctr,actions,purchase_roas",
                },
            )
            return result
        except Exception as e:
            logger.warning(f"MCP get_campaign_insights failed: {e}")
            return {"error": str(e)}

    async def get_adsets(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Fetch ad sets for a campaign via MCP."""
        if not self._use_mcp:
            return []

        try:
            result = await self._mcp_client.call_tool(
                "get_adsets",
                {"campaign_id": campaign_id},
            )
            return result if isinstance(result, list) else [result]
        except Exception as e:
            logger.warning(f"MCP get_adsets failed: {e}")
            return []

    async def update_adset(
        self, adset_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an ad set via MCP (budget, targeting, status, etc.)."""
        if not self._use_mcp:
            return {"success": False, "error": "MCP not configured"}

        try:
            result = await self._mcp_client.call_tool(
                "update_adset",
                {"adset_id": adset_id, **updates},
            )
            return {"success": True, "result": result}
        except Exception as e:
            logger.warning(f"MCP update_adset failed: {e}")
            return {"success": False, "error": str(e)}

    # ================================================================
    # MCP Implementation — real Meta Ads data via Pipeboard
    # ================================================================

    async def _mcp_get_ad_spend_summary(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Fetch real ad spend data from Meta Ads via MCP get_insights tool.
        Transforms the Meta Ads response into the same schema the P&L Analyzer expects.
        """
        if date is None:
            date = datetime.utcnow()

        date_str = date.strftime("%Y-%m-%d")

        # Step 1: Get account-level insights for total spend
        account_insights = await self._mcp_client.call_tool(
            "get_insights",
            {
                "object_id": self._meta_account_id,
                "time_range": {"since": date_str, "until": date_str},
                "level": "account",
                "fields": "spend,impressions,clicks,cpc,ctr,actions,purchase_roas",
            },
        )

        # Step 2: Get campaign-level breakdown
        campaign_insights = await self._mcp_client.call_tool(
            "get_insights",
            {
                "object_id": self._meta_account_id,
                "time_range": {"since": date_str, "until": date_str},
                "level": "campaign",
                "fields": "campaign_id,campaign_name,spend,impressions,clicks,cpc,ctr,actions,purchase_roas",
            },
        )

        # Step 3: Transform into KayaPure's ad_spend_data schema
        return self._transform_insights_to_spend_summary(
            account_insights, campaign_insights, date
        )

    def _transform_insights_to_spend_summary(
        self,
        account_insights: Any,
        campaign_insights: Any,
        date: datetime,
    ) -> Dict[str, Any]:
        """
        Map Meta Ads Insights API response to KayaPure's ad_spend_data schema.

        Meta Ads fields → KayaPure fields:
            spend → total_spend / campaigns[].spend
            clicks → campaigns[].clicks
            impressions → campaigns[].impressions
            actions[type=offsite_conversion.*] → campaigns[].conversions
            cpc → campaigns[].cpc
            ctr → campaigns[].ctr
            purchase_roas[0].value → campaigns[].roas
        """
        # Parse account-level totals
        account_data = self._extract_insights_data(account_insights)
        total_spend = self._safe_float(account_data.get("spend", 0))

        # Parse campaign-level data
        campaign_list = self._extract_insights_list(campaign_insights)
        campaign_data = []

        for camp in campaign_list:
            spend = self._safe_float(camp.get("spend", 0))
            clicks = self._safe_int(camp.get("clicks", 0))
            impressions = self._safe_int(camp.get("impressions", 0))
            cpc = self._safe_float(camp.get("cpc", 0))
            ctr = self._safe_float(camp.get("ctr", 0))

            # Extract conversions from actions array
            conversions = 0
            actions = camp.get("actions", [])
            if isinstance(actions, list):
                for action in actions:
                    action_type = action.get("action_type", "")
                    if "offsite_conversion" in action_type or action_type == "purchase":
                        conversions += self._safe_int(action.get("value", 0))

            # Extract ROAS from purchase_roas
            roas = 0.0
            purchase_roas = camp.get("purchase_roas", [])
            if isinstance(purchase_roas, list) and purchase_roas:
                roas = self._safe_float(purchase_roas[0].get("value", 0))

            campaign_data.append({
                "campaign_id": camp.get("campaign_id", "unknown"),
                "name": camp.get("campaign_name", "Unknown Campaign"),
                "platform": "meta",
                "spend": spend,
                "clicks": clicks,
                "impressions": impressions,
                "conversions": conversions,
                "cpc": cpc,
                "ctr": ctr,
                "roas": roas,
            })

        # Build platform breakdown (Meta only for now; Google added separately)
        meta_spend = sum(c["spend"] for c in campaign_data)

        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_spend": round(total_spend if total_spend > 0 else meta_spend, 2),
            "platform_breakdown": {
                "meta": round(meta_spend, 2),
                "google": 0,  # Google Ads MCP not yet integrated
            },
            "campaigns": campaign_data,
            "source": "meta_ads_mcp",
        }

    async def _mcp_adjust_campaign_budget(
        self, campaign_id: str, new_budget: float
    ) -> Dict[str, Any]:
        """
        Adjust a Meta Ads campaign budget via MCP.
        First fetches ad sets for the campaign, then updates each ad set's daily budget.
        (Meta Ads budgets are set at the ad set level, not campaign level.)
        """
        # Get ad sets for this campaign
        adsets = await self._mcp_client.call_tool(
            "get_adsets",
            {"campaign_id": campaign_id},
        )

        adset_list = adsets if isinstance(adsets, list) else [adsets]
        results = []

        for adset in adset_list:
            adset_id = adset.get("id", adset.get("adset_id"))
            if not adset_id:
                continue

            old_budget = self._safe_float(adset.get("daily_budget", 0)) / 100  # Meta returns in cents
            result = await self._mcp_client.call_tool(
                "update_adset",
                {
                    "adset_id": str(adset_id),
                    "daily_budget": int(new_budget * 100),  # Meta expects cents
                },
            )
            results.append({
                "adset_id": adset_id,
                "old_budget": old_budget,
                "new_budget": new_budget,
                "result": result,
            })

        return {
            "success": len(results) > 0,
            "campaign_id": campaign_id,
            "campaign_name": campaign_id,
            "old_budget": results[0]["old_budget"] if results else 0,
            "new_budget": new_budget,
            "change_percent": round(
                ((new_budget - (results[0]["old_budget"] if results else new_budget))
                 / max(results[0]["old_budget"] if results else 1, 1)) * 100, 2
            ),
            "adsets_updated": len(results),
            "details": results,
            "updated_at": datetime.utcnow().isoformat(),
            "source": "meta_ads_mcp",
        }

    # ================================================================
    # Mock Implementation — fallback when MCP is unavailable
    # ================================================================

    async def _mock_get_ad_spend_summary(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Original mock implementation preserved as fallback."""
        if date is None:
            date = datetime.utcnow()

        total_spend = 0
        platform_breakdown = {"meta": 0, "google": 0}
        campaign_data = []

        for campaign_id, campaign in self._mock_campaigns.items():
            variance = random.uniform(0.85, 1.15)
            spend = round(campaign["daily_budget"] * variance, 2)
            total_spend += spend
            platform_breakdown[campaign["platform"]] += spend

            clicks = int(spend / campaign["cpc"])
            impressions = int(clicks / (campaign["ctr"] / 100))
            conversions = int(clicks * random.uniform(0.02, 0.08))

            campaign_data.append({
                "campaign_id": campaign_id,
                "name": campaign["name"],
                "platform": campaign["platform"],
                "spend": spend,
                "clicks": clicks,
                "impressions": impressions,
                "conversions": conversions,
                "cpc": round(campaign["cpc"] * variance, 2),
                "ctr": round(campaign["ctr"] * random.uniform(0.9, 1.1), 2),
                "roas": round(campaign["roas"] * random.uniform(0.8, 1.2), 2),
            })

        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_spend": round(total_spend, 2),
            "platform_breakdown": {k: round(v, 2) for k, v in platform_breakdown.items()},
            "campaigns": campaign_data,
            "source": "mock",
        }

    async def _mock_adjust_campaign_budget(
        self, campaign_id: str, new_budget: float
    ) -> Dict[str, Any]:
        """Original mock implementation preserved as fallback."""
        if campaign_id not in self._mock_campaigns:
            return {"success": False, "error": f"Campaign {campaign_id} not found"}

        old_budget = self._mock_campaigns[campaign_id]["daily_budget"]
        self._mock_campaigns[campaign_id]["daily_budget"] = new_budget

        return {
            "success": True,
            "campaign_id": campaign_id,
            "campaign_name": self._mock_campaigns[campaign_id]["name"],
            "old_budget": old_budget,
            "new_budget": new_budget,
            "change_percent": round(((new_budget - old_budget) / old_budget) * 100, 2),
            "updated_at": datetime.utcnow().isoformat(),
            "source": "mock",
        }

    # ================================================================
    # Utility Methods
    # ================================================================

    @staticmethod
    def _extract_insights_data(raw: Any) -> Dict[str, Any]:
        """Extract the first data row from a Meta Ads insights response."""
        if isinstance(raw, dict):
            data = raw.get("data", [raw])
            return data[0] if data else {}
        if isinstance(raw, list):
            return raw[0] if raw else {}
        return {}

    @staticmethod
    def _extract_insights_list(raw: Any) -> List[Dict[str, Any]]:
        """Extract all data rows from a Meta Ads insights response."""
        if isinstance(raw, dict):
            return raw.get("data", [raw])
        if isinstance(raw, list):
            return raw
        return []

    @staticmethod
    def _safe_float(value: Any) -> float:
        """Safely convert a value to float (Meta often returns strings)."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> int:
        """Safely convert a value to int."""
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def _normalize_campaigns_response(self, raw: Any) -> List[Dict[str, Any]]:
        """Normalize the MCP campaigns response into a consistent format."""
        if isinstance(raw, dict):
            campaigns = raw.get("data", [raw])
        elif isinstance(raw, list):
            campaigns = raw
        else:
            return []

        result = []
        for camp in campaigns:
            result.append({
                "id": camp.get("id", ""),
                "name": camp.get("name", "Unknown"),
                "status": camp.get("status", "UNKNOWN").lower(),
                "daily_budget": self._safe_float(camp.get("daily_budget", 0)) / 100,
                "objective": camp.get("objective", ""),
            })
        return result


# Singleton — configure() is called during app startup
marketing_service = MarketingService()
