"""
KayaPure Commerce OS - Marketing Service
Meta Ads integration via the Facebook Marketing API (Graph API v21.0).

This service wraps Facebook Graph API calls behind the same interface that
the rest of the codebase uses (get_ad_spend_summary, adjust_campaign_budget,
etc.). The LangGraph workflow and API routes require zero changes.

When the Facebook connection is unavailable (no token configured, API down,
etc.), the service falls back to mock data so the system remains functional
during development and testing.
"""

import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logging_config import get_logger

logger = get_logger("marketing")

CAMPAIGN_INSIGHT_FIELDS = (
    "campaign_id,campaign_name,spend,impressions,clicks,cpc,ctr,cpm,"
    "reach,frequency,inline_link_clicks,actions,purchase_roas"
)

_WHATSAPP_DESTINATION_TYPES = frozenset({
    "WHATSAPP",
    "MESSAGING_MESSENGER_WHATSAPP",
    "MESSAGING_INSTAGRAM_DIRECT_WHATSAPP",
    "MESSAGING_INSTAGRAM_DIRECT_MESSENGER_WHATSAPP",
})

_DESTINATION_TYPE_LABELS = {
    "WEBSITE": "Website",
    "APP": "App",
    "MESSENGER": "Messenger",
    "WHATSAPP": "WhatsApp",
    "INSTAGRAM_DIRECT": "Instagram",
    "INSTAGRAM_PROFILE": "Instagram Profile",
    "FACEBOOK": "Facebook",
    "FACEBOOK_PAGE": "Facebook Page",
    "FACEBOOK_LIVE": "Facebook Live",
    "INSTAGRAM_LIVE": "Instagram Live",
    "PHONE_CALL": "Phone Call",
    "SHOP_AUTOMATIC": "Shop",
    "ON_PAGE": "Facebook Page",
    "ON_POST": "Facebook Post",
    "ON_EVENT": "Facebook Event",
    "ON_VIDEO": "Facebook Video",
    "ON_AD": "On Ad",
    "MESSAGING_MESSENGER_WHATSAPP": "WhatsApp & Messenger",
    "MESSAGING_INSTAGRAM_DIRECT_MESSENGER": "Instagram & Messenger",
    "MESSAGING_INSTAGRAM_DIRECT_WHATSAPP": "Instagram & WhatsApp",
    "MESSAGING_INSTAGRAM_DIRECT_MESSENGER_WHATSAPP": "Instagram, Messenger & WhatsApp",
    "INSTAGRAM_PROFILE_AND_FACEBOOK_PAGE": "Instagram & Facebook",
    "APPLINKS_AUTOMATIC": "App Links",
    "UNDEFINED": "",
}


def _destination_label_from_adset(destination_type: str, promoted_object: Any) -> tuple[str, str]:
    """Map ad set destination metadata to a display label and optional detail."""
    promoted = promoted_object if isinstance(promoted_object, dict) else {}
    dest_type = (destination_type or "").upper()

    if promoted.get("product_set_id"):
        return "Product Catalog", ""

    if dest_type in _WHATSAPP_DESTINATION_TYPES or promoted.get("whatsapp_phone_number"):
        phone = str(promoted.get("whatsapp_phone_number", "")).strip()
        return "WhatsApp", phone

    if dest_type == "APP" or promoted.get("application_id"):
        store_url = str(promoted.get("object_store_url", "")).strip()
        return "App", store_url

    if dest_type == "WEBSITE":
        return "Website", ""

    if dest_type == "PHONE_CALL":
        return "Phone Call", ""

    if dest_type in _DESTINATION_TYPE_LABELS and _DESTINATION_TYPE_LABELS[dest_type]:
        return _DESTINATION_TYPE_LABELS[dest_type], ""

    if promoted.get("page_id") and not dest_type:
        return "Facebook Page", ""

    return "", ""


def _summarize_campaign_destinations(adsets: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """Group ad sets by campaign and summarize unique destinations."""
    by_campaign: Dict[str, List[Dict[str, Any]]] = {}
    for adset in adsets:
        campaign_id = adset.get("campaign_id", "")
        if not campaign_id:
            continue
        by_campaign.setdefault(campaign_id, []).append(adset)

    summaries: Dict[str, Dict[str, str]] = {}
    for campaign_id, campaign_adsets in by_campaign.items():
        labels: List[str] = []
        details: List[str] = []
        for adset in campaign_adsets:
            label, detail = _destination_label_from_adset(
                adset.get("destination_type", ""),
                adset.get("promoted_object"),
            )
            if label and label not in labels:
                labels.append(label)
            if detail and detail not in details:
                details.append(detail)

        summaries[campaign_id] = {
            "destination": ", ".join(labels),
            "destination_detail": "; ".join(details[:2]),
        }
    return summaries


class MarketingService:
    """
    Meta Ads integration via the Facebook Marketing API.
    Preserves the original interface so workflow.py and main.py need no changes.
    """

    def __init__(self):
        self._fb_client = None  # Set during app startup via configure()
        self._meta_account_id: Optional[str] = None
        self._use_facebook = False
        self._currency: str = "USD"  # Account currency (PKR, USD, GBP, etc.)

        # Fallback mock campaigns (used when Facebook API is not available)
        self._mock_campaigns = {
            "meta_brand_awareness": {
                "platform": "meta",
                "name": "KayaPure Brand Awareness",
                "daily_budget": 200.0,
                "status": "active",
                "cpc": 1.20,
                "ctr": 2.8,
                "roas": 3.5,
                "objective": "OUTCOME_AWARENESS",
                "destination": "Website",
                "destination_detail": "",
            },
            "meta_retargeting": {
                "platform": "meta",
                "name": "KayaPure Retargeting",
                "daily_budget": 150.0,
                "status": "active",
                "cpc": 0.85,
                "ctr": 4.2,
                "roas": 5.1,
                "objective": "OUTCOME_SALES",
                "destination": "Website",
                "destination_detail": "kayapure.com",
            },
            "google_search_turmeric": {
                "platform": "google",
                "name": "Turmeric Supplements - Search",
                "daily_budget": 180.0,
                "status": "active",
                "cpc": 2.10,
                "ctr": 3.5,
                "roas": 4.2,
                "objective": "OUTCOME_SALES",
                "destination": "Website",
                "destination_detail": "",
            },
            "google_shopping": {
                "platform": "google",
                "name": "KayaPure Shopping Ads",
                "daily_budget": 250.0,
                "status": "active",
                "cpc": 0.95,
                "ctr": 5.1,
                "roas": 4.8,
                "objective": "OUTCOME_SALES",
                "destination": "Product Catalog",
                "destination_detail": "",
            },
            "meta_lookalike": {
                "platform": "meta",
                "name": "Lookalike - Health Enthusiasts",
                "daily_budget": 120.0,
                "status": "active",
                "cpc": 1.45,
                "ctr": 2.1,
                "roas": 2.9,
                "objective": "OUTCOME_ENGAGEMENT",
                "destination": "WhatsApp",
                "destination_detail": "923001234567",
            },
        }

    def configure(self, fb_client, meta_account_id: Optional[str] = None) -> None:
        """
        Configure the service with a FacebookAdsClient instance.
        Called during FastAPI app startup after the client is initialized.
        """
        self._fb_client = fb_client
        self._meta_account_id = meta_account_id
        self._use_facebook = fb_client is not None and meta_account_id is not None
        # Read currency from the Facebook client (set during initialize())
        if fb_client is not None and hasattr(fb_client, 'currency'):
            self._currency = fb_client.currency
        mode = "FACEBOOK API (live Meta Ads)" if self._use_facebook else "MOCK (fallback data)"
        logger.info(
            f"MarketingService configured in {mode} mode",
            extra={"mode": mode, "account_id": meta_account_id or "none"},
        )

    # ================================================================
    # Primary Interface — called by workflow.py sensor_node and main.py
    # ================================================================

    async def get_ad_spend_summary(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get total ad spend across all platforms for a single day.
        Interface is identical to the original mock version.
        """
        start_time = time.perf_counter()
        if self._use_facebook:
            try:
                result = await self._fb_get_ad_spend_summary(date)
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.info(
                    f"Ad spend summary fetched via Facebook API in {elapsed:.1f}ms: "
                    f"${result.get('total_spend', 0):.2f} total spend, "
                    f"{len(result.get('campaigns', []))} campaigns",
                    extra={
                        "source": "facebook_api",
                        "total_spend": result.get("total_spend", 0),
                        "campaign_count": len(result.get("campaigns", [])),
                        "duration_ms": round(elapsed, 1),
                    },
                )
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"Facebook API call failed after {elapsed:.1f}ms, falling back to mock: {e}",
                    extra={"error": str(e), "duration_ms": round(elapsed, 1), "fallback": True},
                )
                return await self._mock_get_ad_spend_summary(date)
        else:
            result = await self._mock_get_ad_spend_summary(date)
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"Ad spend summary fetched via MOCK in {elapsed:.1f}ms",
                extra={"source": "mock", "duration_ms": round(elapsed, 1)},
            )
            return result

    async def adjust_campaign_budget(
        self, campaign_id: str, new_budget: float
    ) -> Dict[str, Any]:
        """
        Adjust campaign daily budget.
        In Facebook API mode, updates ad set budgets for the campaign.
        """
        if self._use_facebook:
            try:
                return await self._fb_adjust_campaign_budget(campaign_id, new_budget)
            except Exception as e:
                logger.warning(f"Facebook API budget adjustment failed, falling back to mock: {e}")
                return await self._mock_adjust_campaign_budget(campaign_id, new_budget)
        else:
            return await self._mock_adjust_campaign_budget(campaign_id, new_budget)

    async def get_total_daily_spend(self) -> float:
        """Get total daily ad spend across all campaigns."""
        summary = await self.get_ad_spend_summary()
        return summary.get("total_spend", 0.0)

    async def get_ad_spend_history(
        self, days: int = 7, account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get ad spend data for the last N days with daily breakdown.
        Returns both per-day summaries and aggregate totals.

        When account_id is set, Graph calls are scoped to that ad account only.
        """
        start_time = time.perf_counter()
        if self._use_facebook:
            try:
                result = await self._fb_get_ad_spend_history(days, account_id=account_id)
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.info(
                    f"Ad spend history ({days} days) fetched via Facebook API in {elapsed:.1f}ms: "
                    f"${result.get('total_spend', 0):.2f} total spend, "
                    f"{len(result.get('daily_breakdown', []))} days",
                    extra={
                        "source": "facebook_api",
                        "days": days,
                        "account_id": account_id or "all",
                        "total_spend": result.get("total_spend", 0),
                        "daily_count": len(result.get("daily_breakdown", [])),
                        "duration_ms": round(elapsed, 1),
                    },
                )
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"Facebook API history call failed after {elapsed:.1f}ms, falling back to mock: {e}",
                    extra={"error": str(e), "duration_ms": round(elapsed, 1), "fallback": True},
                )
                return await self._mock_get_ad_spend_history(days)
        else:
            result = await self._mock_get_ad_spend_history(days)
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"Ad spend history ({days} days) fetched via MOCK in {elapsed:.1f}ms",
                extra={"source": "mock", "days": days, "duration_ms": round(elapsed, 1)},
            )
            return result

    # ================================================================
    # Additional Facebook API methods (new capabilities)
    # ================================================================

    async def get_campaigns(self) -> List[Dict[str, Any]]:
        """Fetch all campaigns from Meta Ads via the Graph API."""
        if not self._use_facebook:
            return [
                {"id": k, "name": v["name"], "status": v["status"], "daily_budget": v["daily_budget"]}
                for k, v in self._mock_campaigns.items()
                if v["platform"] == "meta"
            ]

        try:
            result = await self._fb_client.get_campaigns()
            campaigns = result.get("data", [])
            return [
                {
                    "id": c.get("id", ""),
                    "name": c.get("name", "Unknown"),
                    "status": c.get("status", "UNKNOWN").lower(),
                    "daily_budget": self._safe_float(c.get("daily_budget", 0)) / 100,
                    "objective": c.get("objective", ""),
                }
                for c in campaigns
            ]
        except Exception as e:
            logger.warning(f"Facebook API get_campaigns failed: {e}")
            return []

    async def get_campaign_insights(
        self,
        campaign_id: str,
        time_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Get detailed insights for a specific campaign."""
        if not self._use_facebook:
            return {"error": "Facebook API not configured, insights unavailable"}

        if time_range is None:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            time_range = {"since": today, "until": today}

        try:
            result = await self._fb_client.get_insights(
                object_id=campaign_id,
                time_range=time_range,
                level="campaign",
                fields="spend,impressions,clicks,cpc,ctr,actions,purchase_roas",
            )
            return result
        except Exception as e:
            logger.warning(f"Facebook API get_campaign_insights failed: {e}")
            return {"error": str(e)}

    async def get_adsets(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Fetch ad sets for a campaign."""
        if not self._use_facebook:
            return []

        try:
            result = await self._fb_client.get_adsets(campaign_id)
            return result.get("data", [])
        except Exception as e:
            logger.warning(f"Facebook API get_adsets failed: {e}")
            return []

    async def update_adset(
        self, adset_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an ad set (budget, targeting, status, etc.)."""
        if not self._use_facebook:
            return {"success": False, "error": "Facebook API not configured"}

        try:
            result = await self._fb_client.update_adset(
                adset_id=adset_id,
                daily_budget=updates.get("daily_budget"),
                status=updates.get("status"),
            )
            return {"success": True, "result": result}
        except Exception as e:
            logger.warning(f"Facebook API update_adset failed: {e}")
            return {"success": False, "error": str(e)}

    # ================================================================
    # Facebook Graph API Implementation — live Meta Ads data
    # ================================================================

    async def _fb_get_ad_spend_summary(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Fetch real ad spend data from Meta Ads via the Facebook Graph API.
        Transforms the response into the same schema the P&L Analyzer expects.
        """
        if date is None:
            date = datetime.utcnow()

        date_str = date.strftime("%Y-%m-%d")
        time_range = {"since": date_str, "until": date_str}

        # Step 1: Get account-level insights for total spend
        account_response = await self._fb_client.get_insights(
            time_range=time_range,
            level="account",
            fields="spend,impressions,clicks,cpc,ctr,actions,purchase_roas",
        )

        # Step 2: Get campaign-level breakdown
        campaign_response = await self._fb_client.get_insights(
            time_range=time_range,
            level="campaign",
            fields="campaign_id,campaign_name,spend,impressions,clicks,cpc,ctr,actions,purchase_roas",
        )

        # Step 3: Transform into KayaPure's ad_spend_data schema
        return self._transform_insights_to_spend_summary(
            account_response, campaign_response, date
        )

    def _transform_insights_to_spend_summary(
        self,
        account_response: Dict[str, Any],
        campaign_response: Dict[str, Any],
        date: datetime,
    ) -> Dict[str, Any]:
        """
        Map Facebook Insights API response to KayaPure's ad_spend_data schema.

        Facebook fields → KayaPure fields:
            spend → total_spend / campaigns[].spend
            clicks → campaigns[].clicks
            impressions → campaigns[].impressions
            actions[type=offsite_conversion.*] → campaigns[].conversions
            cpc → campaigns[].cpc
            ctr → campaigns[].ctr
            purchase_roas[0].value → campaigns[].roas
        """
        # Parse account-level totals
        account_data = self._extract_first_row(account_response)
        total_spend = self._safe_float(account_data.get("spend", 0))

        # Parse campaign-level data
        campaign_list = self._extract_data_rows(campaign_response)
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
            "currency": self._currency,
            "total_spend": round(total_spend if total_spend > 0 else meta_spend, 2),
            "platform_breakdown": {
                "meta": round(meta_spend, 2),
                "google": 0,  # Google Ads not yet integrated
            },
            "campaigns": campaign_data,
            "source": "facebook_api",
        }

    async def _fb_adjust_campaign_budget(
        self, campaign_id: str, new_budget: float
    ) -> Dict[str, Any]:
        """
        Adjust a Meta Ads campaign budget via the Graph API.
        Fetches ad sets for the campaign, then updates each ad set's daily budget.
        (Meta Ads budgets are set at the ad set level, not campaign level.)
        """
        adsets_response = await self._fb_client.get_adsets(campaign_id)
        adset_list = adsets_response.get("data", [])
        results = []

        for adset in adset_list:
            adset_id = adset.get("id")
            if not adset_id:
                continue

            old_budget = self._safe_float(adset.get("daily_budget", 0)) / 100  # Meta returns cents
            result = await self._fb_client.update_adset(
                adset_id=str(adset_id),
                daily_budget=int(new_budget * 100),  # Meta expects cents
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
            "source": "facebook_api",
        }

    async def _fb_get_ad_spend_history(
        self, days: int = 7, account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch N days of ad spend data from Meta Ads via the Graph API.
        Uses time_increment=1 for daily granularity in a single API call
        (unlike the MCP approach which required parallel single-day calls).

        When account_id is provided, only that ad account is queried.
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days - 1)

        since_str = start_date.strftime("%Y-%m-%d")
        until_str = end_date.strftime("%Y-%m-%d")
        time_range = {"since": since_str, "until": until_str}

        insight_object_id = account_id or self._meta_account_id

        # Single call with time_increment=1 returns one row per day
        daily_response = await self._fb_client.get_insights(
            object_id=insight_object_id,
            time_range=time_range,
            level="account",
            fields="spend,impressions,clicks,cpc,ctr,cpm,reach,frequency",
            time_increment=1,
        )

        # Campaign-level totals — scoped to one account when requested
        campaigns_summary = await self._fb_fetch_campaigns_all_accounts(
            time_range, account_id=account_id
        )
        daily_rows = self._extract_data_rows(daily_response)
        daily_breakdown = []
        total_spend = 0.0
        total_impressions = 0
        total_clicks = 0

        for row in daily_rows:
            day_spend = round(self._safe_float(row.get("spend", 0)), 2)
            day_impressions = self._safe_int(row.get("impressions", 0))
            day_clicks = self._safe_int(row.get("clicks", 0))

            total_spend += day_spend
            total_impressions += day_impressions
            total_clicks += day_clicks

            # date_start is the date field returned by the API with time_increment
            day_date = row.get("date_start", row.get("date_stop", ""))

            daily_breakdown.append({
                "date": day_date,
                "spend": day_spend,
                "impressions": day_impressions,
                "clicks": day_clicks,
                "cpc": round(self._safe_float(row.get("cpc", 0)), 2),
                "ctr": round(self._safe_float(row.get("ctr", 0)), 2),
                "cpm": round(self._safe_float(row.get("cpm", 0)), 2),
                "reach": self._safe_int(row.get("reach", 0)),
                "frequency": round(self._safe_float(row.get("frequency", 0)), 2),
            })

        # Calculate averages
        num_days = max(len(daily_breakdown), 1)
        avg_daily_spend = round(total_spend / num_days, 2)

        return {
            "period": {
                "start": since_str,
                "end": until_str,
                "days": days,
            },
            "currency": self._currency,
            "total_spend": round(total_spend, 2),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "avg_daily_spend": avg_daily_spend,
            "avg_cpc": round(total_spend / max(total_clicks, 1), 2),
            "avg_ctr": round((total_clicks / max(total_impressions, 1)) * 100, 2),
            "daily_breakdown": daily_breakdown,
            "campaigns": campaigns_summary,
            "campaigns_daily": [],  # Per-campaign daily available via separate calls if needed
            "platform_breakdown": {
                "meta": round(total_spend, 2),
                "google": 0,
            },
            "source": "facebook_api",
            "scoped_account_id": account_id,
        }

    async def _fb_fetch_campaigns_all_accounts(
        self,
        time_range: Dict[str, str],
        account_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch campaign insights for every accessible ad account (or one if scoped)."""
        import asyncio

        if account_id:
            accounts = [{"id": account_id, "name": account_id, "currency": self._currency}]
            # Prefer display name/currency from cached account list when available
            try:
                all_accounts = await self._fb_client.get_all_ad_accounts()
                match = next((a for a in all_accounts if a.get("id") == account_id), None)
                if match:
                    accounts = [match]
            except Exception:
                pass
        else:
            accounts = await self._fb_client.get_all_ad_accounts()
        if not accounts:
            return []

        async def fetch_for_account(account: Dict[str, Any]) -> List[Dict[str, Any]]:
            acc_id = account.get("id", "")
            account_name = account.get("name", "Unknown")
            account_currency = account.get("currency", self._currency)

            try:
                campaign_response = await self._fb_client.get_insights(
                    object_id=acc_id,
                    time_range=time_range,
                    level="campaign",
                    fields=CAMPAIGN_INSIGHT_FIELDS,
                    limit=500,
                )
                campaign_rows = await self._fb_client._paginate_data(campaign_response)
                campaign_meta_response = await self._fb_client.get_campaigns(account_id=acc_id)
                # Skip adsets on AI report path — destinations are optional and costly
                adsets: List[Dict[str, Any]] = []
            except Exception as e:
                logger.warning(
                    f"Failed to fetch campaign insights for {account_name} ({acc_id}): {e}",
                    extra={"account_id": acc_id, "error": str(e)},
                )
                return []

            campaign_meta_map = {
                cm.get("id", ""): {
                    "status": cm.get("status", "UNKNOWN"),
                    "objective": cm.get("objective", ""),
                    "start_time": cm.get("start_time", ""),
                    "stop_time": cm.get("stop_time", ""),
                }
                for cm in campaign_meta_response.get("data", [])
            }
            destination_map = _summarize_campaign_destinations(adsets)

            summaries = []
            for camp in campaign_rows:
                camp_id = camp.get("campaign_id", "unknown")
                meta_info = campaign_meta_map.get(camp_id, {})
                dest_info = destination_map.get(camp_id, {})
                summaries.append(
                    self._build_campaign_summary(
                        camp,
                        meta_info,
                        account_id=acc_id,
                        account_name=account_name,
                        currency=account_currency,
                        destination=dest_info.get("destination", ""),
                        destination_detail=dest_info.get("destination_detail", ""),
                    )
                )
            return summaries

        nested = await asyncio.gather(*(fetch_for_account(acc) for acc in accounts))
        return [campaign for account_campaigns in nested for campaign in account_campaigns]

    def _extract_conversions(self, actions: Any) -> int:
        if not isinstance(actions, list):
            return 0
        total = 0
        for action in actions:
            action_type = action.get("action_type", "")
            if "offsite_conversion" in action_type or action_type in ("purchase", "omni_purchase"):
                total += self._safe_int(action.get("value", 0))
        return total

    def _extract_roas(self, purchase_roas: Any) -> float:
        if isinstance(purchase_roas, list) and purchase_roas:
            return self._safe_float(purchase_roas[0].get("value", 0))
        return 0.0

    def _build_campaign_summary(
        self,
        camp: Dict[str, Any],
        meta_info: Dict[str, Any],
        *,
        account_id: str,
        account_name: str,
        currency: str,
        destination: str = "",
        destination_detail: str = "",
    ) -> Dict[str, Any]:
        spend = self._safe_float(camp.get("spend", 0))
        clicks = self._safe_int(camp.get("clicks", 0))
        impressions = self._safe_int(camp.get("impressions", 0))

        return {
            "campaign_id": camp.get("campaign_id", "unknown"),
            "name": camp.get("campaign_name", "Unknown Campaign"),
            "platform": "meta",
            "account_id": account_id,
            "account_name": account_name,
            "currency": currency,
            "status": meta_info.get("status", "UNKNOWN"),
            "objective": meta_info.get("objective", ""),
            "destination": destination,
            "destination_detail": destination_detail,
            "start_time": meta_info.get("start_time", ""),
            "stop_time": meta_info.get("stop_time", ""),
            "date_start": camp.get("date_start", ""),
            "date_stop": camp.get("date_stop", ""),
            "spend": round(spend, 2),
            "clicks": clicks,
            "impressions": impressions,
            "reach": self._safe_int(camp.get("reach", 0)),
            "frequency": round(self._safe_float(camp.get("frequency", 0)), 2),
            "cpm": round(self._safe_float(camp.get("cpm", 0)), 2),
            "link_clicks": self._safe_int(camp.get("inline_link_clicks")),
            "conversions": self._extract_conversions(camp.get("actions")),
            "cpc": round(self._safe_float(camp.get("cpc", 0)), 2),
            "ctr": round(self._safe_float(camp.get("ctr", 0)), 2),
            "roas": round(self._extract_roas(camp.get("purchase_roas")), 2),
        }

    # ================================================================
    # Mock Implementation — fallback when Facebook API is unavailable
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

    async def _mock_get_ad_spend_history(self, days: int = 7) -> Dict[str, Any]:
        """Mock implementation for multi-day ad spend history."""
        end_date = datetime.utcnow()
        daily_breakdown = []
        total_spend = 0.0
        total_impressions = 0
        total_clicks = 0

        for i in range(days - 1, -1, -1):
            day = end_date - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")

            base_spend = 780.0
            day_of_week = day.weekday()
            if day_of_week >= 5:
                base_spend *= 0.7
            variance = random.uniform(0.8, 1.2)
            day_spend = round(base_spend * variance, 2)
            day_impressions = int(day_spend * random.uniform(80, 120))
            day_clicks = int(day_impressions * random.uniform(0.015, 0.04))

            total_spend += day_spend
            total_impressions += day_impressions
            total_clicks += day_clicks

            daily_breakdown.append({
                "date": day_str,
                "spend": day_spend,
                "impressions": day_impressions,
                "clicks": day_clicks,
                "cpc": round(day_spend / max(day_clicks, 1), 2),
                "ctr": round((day_clicks / max(day_impressions, 1)) * 100, 2),
                "cpm": round((day_spend / max(day_impressions, 1)) * 1000, 2),
                "reach": int(day_impressions * 0.85),
                "frequency": round(day_impressions / max(int(day_impressions * 0.85), 1), 2),
            })

        campaigns_summary = []
        campaigns_daily = []
        mock_statuses = ["ACTIVE", "ACTIVE", "PAUSED", "ARCHIVED", "ACTIVE"]
        for idx, (cid, camp) in enumerate(self._mock_campaigns.items()):
            camp_spend = round(total_spend * random.uniform(0.15, 0.25), 2)
            camp_clicks = int(camp_spend / camp["cpc"])
            camp_impressions = int(camp_clicks / (camp["ctr"] / 100))
            status = mock_statuses[idx % len(mock_statuses)]
            start_date = end_date - timedelta(days=(idx + 1) * 12)
            stop_date = end_date - timedelta(days=idx * 3) if status != "ACTIVE" else None
            campaigns_summary.append({
                "campaign_id": cid,
                "name": camp["name"],
                "platform": camp["platform"],
                "account_id": "act_mock_kayapure",
                "account_name": "KayaPure Mock Account",
                "currency": "USD",
                "status": status,
                "objective": camp.get("objective", ""),
                "destination": camp.get("destination", ""),
                "destination_detail": camp.get("destination_detail", ""),
                "start_time": start_date.isoformat(),
                "stop_time": stop_date.isoformat() if stop_date else "",
                "date_start": daily_breakdown[0]["date"] if daily_breakdown else "",
                "date_stop": daily_breakdown[-1]["date"] if daily_breakdown else "",
                "spend": camp_spend,
                "clicks": camp_clicks,
                "impressions": camp_impressions,
                "reach": int(camp_impressions * 0.85),
                "frequency": round(camp_impressions / max(int(camp_impressions * 0.85), 1), 2),
                "cpm": round(camp_spend / max(camp_impressions, 1) * 1000, 2),
                "link_clicks": int(camp_clicks * 0.82),
                "conversions": int(camp_clicks * random.uniform(0.02, 0.08)),
                "cpc": round(camp["cpc"] * random.uniform(0.9, 1.1), 2),
                "ctr": round(camp["ctr"] * random.uniform(0.9, 1.1), 2),
                "roas": round(camp["roas"] * random.uniform(0.8, 1.2), 2),
            })

            camp_daily = []
            for db in daily_breakdown:
                camp_day_spend = round(db["spend"] * random.uniform(0.15, 0.25), 2)
                camp_day_clicks = int(camp_day_spend / max(camp["cpc"], 0.01))
                camp_day_impressions = int(camp_day_clicks / max(camp["ctr"] / 100, 0.001))
                camp_daily.append({
                    "date": db["date"],
                    "spend": camp_day_spend,
                    "impressions": camp_day_impressions,
                    "clicks": camp_day_clicks,
                    "cpc": round(camp_day_spend / max(camp_day_clicks, 1), 2),
                    "ctr": round((camp_day_clicks / max(camp_day_impressions, 1)) * 100, 2),
                })
            campaigns_daily.append({
                "campaign_id": cid,
                "name": camp["name"],
                "daily": camp_daily,
            })

        num_days = max(len(daily_breakdown), 1)

        return {
            "period": {
                "start": daily_breakdown[0]["date"] if daily_breakdown else "",
                "end": daily_breakdown[-1]["date"] if daily_breakdown else "",
                "days": days,
            },
            "total_spend": round(total_spend, 2),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "avg_daily_spend": round(total_spend / num_days, 2),
            "avg_cpc": round(total_spend / max(total_clicks, 1), 2),
            "avg_ctr": round((total_clicks / max(total_impressions, 1)) * 100, 2),
            "daily_breakdown": daily_breakdown,
            "campaigns": campaigns_summary,
            "campaigns_daily": campaigns_daily,
            "platform_breakdown": {
                "meta": round(total_spend * 0.6, 2),
                "google": round(total_spend * 0.4, 2),
            },
            "source": "mock",
        }

    # ================================================================
    # Utility Methods
    # ================================================================

    @staticmethod
    def _extract_first_row(response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the first data row from a Facebook Insights API response."""
        data = response.get("data", [])
        return data[0] if data else {}

    @staticmethod
    def _extract_data_rows(response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all data rows from a Facebook Insights API response."""
        return response.get("data", [])

    @staticmethod
    def _safe_float(value: Any) -> float:
        """Safely convert a value to float (Facebook often returns strings)."""
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


# Singleton — configure() is called during app startup
marketing_service = MarketingService()
