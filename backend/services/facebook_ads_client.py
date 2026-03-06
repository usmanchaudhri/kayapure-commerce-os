"""
KayaPure Commerce OS - Facebook Ads Client
Direct integration with the Facebook Marketing API (Graph API v21.0).

This module provides a lightweight, async client for querying Facebook Ads
data. It replaces the previous MCP-based transport with direct HTTPS calls
to graph.facebook.com.

Authentication: Long-Lived User Access Token (60-day validity).
Refresh the token before expiry via the Facebook token exchange endpoint.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from utils.logging_config import get_logger

logger = get_logger("facebook_ads")

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class FacebookAdsError(Exception):
    """Raised when a Facebook Graph API call fails."""
    pass


class FacebookAdsClient:
    """
    Async client for the Facebook Marketing API.

    Handles authentication, request formatting, pagination, error handling,
    and rate-limit awareness. All methods return parsed JSON dicts/lists.

    Usage:
        client = FacebookAdsClient(access_token="...", account_id="act_123")
        await client.initialize()
        insights = await client.get_insights(level="account", fields="spend,clicks", ...)
        await client.close()
    """

    def __init__(self, access_token: str, account_id: str):
        self._access_token = access_token
        self._account_id = account_id
        self._http_client: Optional[httpx.AsyncClient] = None
        self._initialized = False
        self.currency: str = "USD"  # Set during initialize() from account info

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def initialize(self) -> Dict[str, Any]:
        """
        Verify the access token and account ID are valid by making a
        lightweight call to the Graph API. Returns account info on success.
        """
        if self._initialized:
            return {"status": "already_initialized"}

        client = await self._get_client()
        url = f"{GRAPH_API_BASE}/{self._account_id}"
        params = {
            "access_token": self._access_token,
            "fields": "name,account_id,account_status,currency,timezone_name",
        }

        start = time.perf_counter()
        try:
            response = await client.get(url, params=params)
            elapsed = (time.perf_counter() - start) * 1000

            if response.status_code != 200:
                error_body = response.text[:500]
                logger.error(
                    f"Facebook API auth check failed: HTTP {response.status_code}: {error_body}",
                    extra={"status_code": response.status_code, "error": error_body},
                )
                raise FacebookAdsError(
                    f"Auth check failed (HTTP {response.status_code}): {error_body}"
                )

            data = response.json()
            self._initialized = True
            self.currency = data.get("currency", "USD")
            logger.info(
                f"Facebook Ads client initialized in {elapsed:.1f}ms — "
                f"account: {data.get('name', 'unknown')} ({self._account_id}), "
                f"currency: {data.get('currency', '?')}, "
                f"timezone: {data.get('timezone_name', '?')}",
                extra={
                    "account_name": data.get("name"),
                    "account_id": self._account_id,
                    "currency": data.get("currency"),
                    "timezone": data.get("timezone_name"),
                    "latency_ms": round(elapsed, 1),
                },
            )
            return data

        except httpx.HTTPError as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                f"Facebook API connection failed after {elapsed:.1f}ms: {e}",
                extra={"error": str(e), "latency_ms": round(elapsed, 1)},
            )
            raise FacebookAdsError(f"Connection failed: {e}")

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Make an authenticated request to the Facebook Graph API.
        Handles error parsing and logging.
        """
        client = await self._get_client()
        url = f"{GRAPH_API_BASE}/{path.lstrip('/')}"

        # Inject access token
        if params is None:
            params = {}
        params["access_token"] = self._access_token

        start = time.perf_counter()
        logger.info(
            f"Facebook API {method} /{path}",
            extra={"method": method, "path": path},
        )

        try:
            if method == "GET":
                response = await client.get(url, params=params)
            elif method == "POST":
                response = await client.post(url, params=params, data=data)
            else:
                raise FacebookAdsError(f"Unsupported HTTP method: {method}")

            elapsed = (time.perf_counter() - start) * 1000

            if response.status_code != 200:
                error_body = response.text[:500]
                logger.error(
                    f"Facebook API error: HTTP {response.status_code} on {method} /{path}: {error_body}",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                        "error": error_body,
                        "latency_ms": round(elapsed, 1),
                    },
                )
                # Try to parse structured error
                try:
                    err = response.json().get("error", {})
                    msg = err.get("message", error_body)
                    code = err.get("code", response.status_code)
                    raise FacebookAdsError(f"[{code}] {msg}")
                except (json.JSONDecodeError, AttributeError):
                    raise FacebookAdsError(
                        f"HTTP {response.status_code}: {error_body}"
                    )

            result = response.json()
            logger.info(
                f"Facebook API {method} /{path} completed in {elapsed:.1f}ms",
                extra={
                    "method": method,
                    "path": path,
                    "latency_ms": round(elapsed, 1),
                },
            )
            return result

        except httpx.HTTPError as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                f"Facebook API request failed after {elapsed:.1f}ms: {e}",
                extra={
                    "method": method,
                    "path": path,
                    "error": str(e),
                    "latency_ms": round(elapsed, 1),
                },
            )
            raise FacebookAdsError(f"Request failed: {e}")

    # ================================================================
    # Public API — mirrors the operations marketing.py needs
    # ================================================================

    async def get_insights(
        self,
        object_id: Optional[str] = None,
        time_range: Optional[Dict[str, str]] = None,
        level: str = "account",
        fields: str = "spend,impressions,clicks,cpc,ctr",
        time_increment: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Fetch insights from the Facebook Marketing API.

        Args:
            object_id: The ad account, campaign, or ad set ID. Defaults to account ID.
            time_range: Dict with 'since' and 'until' date strings (YYYY-MM-DD).
            level: Aggregation level — 'account', 'campaign', 'adset', or 'ad'.
            fields: Comma-separated list of metrics to retrieve.
            time_increment: If set to 1, returns daily granularity rows.

        Returns:
            Raw Graph API response dict (contains 'data' array).
        """
        target_id = object_id or self._account_id
        path = f"{target_id}/insights"

        params: Dict[str, Any] = {
            "level": level,
            "fields": fields,
        }

        if time_range:
            params["time_range"] = json.dumps(time_range)

        if time_increment is not None:
            params["time_increment"] = str(time_increment)

        return await self._request("GET", path, params=params)

    async def get_campaigns(
        self,
        fields: str = "id,name,status,daily_budget,objective,start_time,stop_time",
    ) -> Dict[str, Any]:
        """
        Fetch all campaigns for the ad account.

        Returns:
            Raw Graph API response dict (contains 'data' array).
        """
        path = f"{self._account_id}/campaigns"
        params = {"fields": fields}
        return await self._request("GET", path, params=params)

    async def get_adsets(
        self,
        campaign_id: str,
        fields: str = "id,name,daily_budget,status,targeting",
    ) -> Dict[str, Any]:
        """
        Fetch ad sets for a specific campaign.

        Returns:
            Raw Graph API response dict (contains 'data' array).
        """
        path = f"{campaign_id}/adsets"
        params = {"fields": fields}
        return await self._request("GET", path, params=params)

    async def update_adset(
        self,
        adset_id: str,
        daily_budget: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an ad set's properties (budget, status, etc.).

        Args:
            adset_id: The ad set ID to update.
            daily_budget: New daily budget in cents (e.g., 5000 = $50.00).
            status: New status ('ACTIVE', 'PAUSED', etc.).

        Returns:
            Graph API response (typically {"success": true}).
        """
        path = adset_id
        data: Dict[str, Any] = {}
        if daily_budget is not None:
            data["daily_budget"] = str(daily_budget)
        if status is not None:
            data["status"] = status

        params = {"access_token": self._access_token}
        return await self._request("POST", path, data=data)

    async def get_all_ad_accounts(
        self,
        fields: str = "id,name,currency,account_status,amount_spent,timezone_name",
    ) -> List[Dict[str, Any]]:
        """
        Fetch all ad accounts accessible by the current access token.

        Returns:
            List of ad account dicts with id, name, currency, status, etc.
        """
        path = "me/adaccounts"
        params = {"fields": fields, "limit": "100"}
        result = await self._request("GET", path, params=params)
        accounts = result.get("data", [])

        # Handle pagination if there are more than 100 accounts
        while result.get("paging", {}).get("next"):
            next_url = result["paging"]["next"]
            client = await self._get_client()
            response = await client.get(next_url)
            if response.status_code == 200:
                result = response.json()
                accounts.extend(result.get("data", []))
            else:
                break

        logger.info(
            f"Found {len(accounts)} ad accounts",
            extra={"account_count": len(accounts)},
        )
        return accounts

    async def get_total_spend_all_accounts(
        self,
        since: str = "2025-01-01",
        until: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch total ad spend across ALL ad accounts from `since` to `until`.

        Args:
            since: Start date (YYYY-MM-DD). Defaults to Jan 1, 2025.
            until: End date (YYYY-MM-DD). Defaults to today.

        Returns:
            Dict with grand_total_spend, per-account breakdown, and metadata.
        """
        from datetime import date as date_type

        if until is None:
            until = date_type.today().strftime("%Y-%m-%d")

        time_range = {"since": since, "until": until}

        # Step 1: Discover all ad accounts
        accounts = await self.get_all_ad_accounts()

        # Step 2: Fetch insights for each account in parallel
        async def fetch_account_spend(account: Dict) -> Dict[str, Any]:
            account_id = account["id"]
            account_name = account.get("name", "Unknown")
            account_currency = account.get("currency", "USD")
            account_status = account.get("account_status", 0)

            # Status codes: 1=ACTIVE, 2=DISABLED, 3=UNSETTLED, 7=PENDING_RISK_REVIEW, etc.
            status_map = {
                1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED",
                7: "PENDING_RISK_REVIEW", 8: "PENDING_SETTLEMENT",
                9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE",
                101: "CLOSED", 201: "ANY_ACTIVE", 202: "ANY_CLOSED",
            }
            status_label = status_map.get(account_status, f"UNKNOWN({account_status})")

            try:
                insights = await self.get_insights(
                    object_id=account_id,
                    time_range=time_range,
                    level="account",
                    fields="spend,impressions,clicks,cpc,ctr,cpm",
                )
                rows = insights.get("data", [])
                if rows:
                    row = rows[0]
                    return {
                        "account_id": account_id,
                        "account_name": account_name,
                        "currency": account_currency,
                        "status": status_label,
                        "spend": float(row.get("spend", 0)),
                        "impressions": int(row.get("impressions", 0)),
                        "clicks": int(row.get("clicks", 0)),
                        "cpc": float(row.get("cpc", 0)),
                        "ctr": float(row.get("ctr", 0)),
                        "cpm": float(row.get("cpm", 0)),
                        "has_data": True,
                    }
                else:
                    return {
                        "account_id": account_id,
                        "account_name": account_name,
                        "currency": account_currency,
                        "status": status_label,
                        "spend": 0.0,
                        "impressions": 0,
                        "clicks": 0,
                        "cpc": 0.0,
                        "ctr": 0.0,
                        "cpm": 0.0,
                        "has_data": False,
                    }
            except Exception as e:
                logger.warning(
                    f"Failed to fetch insights for {account_name} ({account_id}): {e}",
                    extra={"account_id": account_id, "error": str(e)},
                )
                return {
                    "account_id": account_id,
                    "account_name": account_name,
                    "currency": account_currency,
                    "status": status_label,
                    "spend": 0.0,
                    "impressions": 0,
                    "clicks": 0,
                    "cpc": 0.0,
                    "ctr": 0.0,
                    "cpm": 0.0,
                    "has_data": False,
                    "error": str(e),
                }

        import asyncio
        account_results = await asyncio.gather(
            *[fetch_account_spend(acc) for acc in accounts]
        )

        # Step 3: Aggregate totals (grouped by currency)
        grand_total_spend = sum(a["spend"] for a in account_results)
        grand_total_impressions = sum(a["impressions"] for a in account_results)
        grand_total_clicks = sum(a["clicks"] for a in account_results)
        accounts_with_data = [a for a in account_results if a["has_data"]]

        # Group by currency for proper reporting
        currency_totals: Dict[str, float] = {}
        for a in account_results:
            cur = a["currency"]
            currency_totals[cur] = currency_totals.get(cur, 0) + a["spend"]

        logger.info(
            f"Total spend across {len(accounts)} accounts: {grand_total_spend:,.2f} "
            f"({len(accounts_with_data)} with data) from {since} to {until}",
            extra={
                "total_spend": grand_total_spend,
                "account_count": len(accounts),
                "accounts_with_data": len(accounts_with_data),
                "since": since,
                "until": until,
            },
        )

        return {
            "period": {"since": since, "until": until},
            "total_accounts": len(accounts),
            "accounts_with_data": len(accounts_with_data),
            "grand_total_spend": grand_total_spend,
            "grand_total_impressions": grand_total_impressions,
            "grand_total_clicks": grand_total_clicks,
            "currency_totals": currency_totals,
            "accounts": account_results,
        }

    async def get_creatives_for_account(
        self,
        account_id: str,
        fields: str = "id,name,title,body,image_url,thumbnail_url,object_story_spec,status,effective_object_story_id",
        limit: int = 50,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch ad creatives for a specific ad account with server-side pagination.

        Args:
            account_id: The ad account ID (e.g., act_123456).
            fields: Comma-separated fields to retrieve.
            limit: Max creatives per page (default 50).
            after: Cursor for the next page of results.

        Returns:
            Dict with 'data' (list of creatives), 'paging' (cursor info), and 'total_count'.
        """
        path = f"{account_id}/adcreatives"
        params = {"fields": fields, "limit": str(limit)}
        if after:
            params["after"] = after

        result = await self._request("GET", path, params=params)
        creatives = result.get("data", [])

        # Extract pagination cursors
        paging = result.get("paging", {})
        cursors = paging.get("cursors", {})
        has_next = bool(paging.get("next"))
        has_prev = bool(paging.get("previous"))
        next_cursor = cursors.get("after", "") if has_next else ""
        prev_cursor = cursors.get("before", "") if has_prev else ""

        # Normalize creatives
        normalized = []
        for c in creatives:
            story_spec = c.get("object_story_spec", {}) or {}
            creative_type = "unknown"
            preview_url = c.get("image_url") or c.get("thumbnail_url") or ""

            if story_spec.get("video_data"):
                creative_type = "video"
                video_data = story_spec["video_data"]
                preview_url = preview_url or video_data.get("image_url", "")
            elif story_spec.get("link_data"):
                creative_type = "image"
                link_data = story_spec["link_data"]
                preview_url = preview_url or link_data.get("image_hash", "")
                if link_data.get("child_attachments"):
                    creative_type = "carousel"
            elif story_spec.get("photo_data"):
                creative_type = "image"

            normalized.append({
                "creative_id": c.get("id", ""),
                "name": c.get("name", "Untitled"),
                "title": c.get("title", ""),
                "body": c.get("body", ""),
                "type": creative_type,
                "status": c.get("status", "UNKNOWN"),
                "image_url": c.get("image_url", ""),
                "thumbnail_url": c.get("thumbnail_url", ""),
                "preview_url": preview_url,
            })

        # ----------------------------------------------------------
        # Deduplicate: by image_url for images/carousels,
        #              by preview_url (video thumbnail) for videos.
        # Keep the first occurrence (most recent creative ID) and
        # track how many duplicates were collapsed.
        # ----------------------------------------------------------
        seen_keys: dict[str, int] = {}  # dedup_key -> index in deduped list
        deduped: list[dict] = []

        for c in normalized:
            ctype = c.get("type", "unknown")
            if ctype == "video":
                dedup_key = c.get("preview_url") or c.get("thumbnail_url") or ""
            else:
                dedup_key = c.get("image_url") or c.get("preview_url") or ""

            # If no usable key, keep the creative as-is (can't deduplicate)
            if not dedup_key:
                c["_duplicate_count"] = 1
                deduped.append(c)
                continue

            if dedup_key in seen_keys:
                # Increment the duplicate counter on the first occurrence
                idx = seen_keys[dedup_key]
                deduped[idx]["_duplicate_count"] = deduped[idx].get("_duplicate_count", 1) + 1
            else:
                c["_duplicate_count"] = 1
                seen_keys[dedup_key] = len(deduped)
                deduped.append(c)

        logger.info(
            f"Fetched {len(normalized)} creatives for {account_id} "
            f"(page, has_next={has_next}), deduplicated to {len(deduped)}",
            extra={
                "account_id": account_id,
                "creative_count_raw": len(normalized),
                "creative_count_deduped": len(deduped),
                "has_next": has_next,
            },
        )

        return {
            "creatives": deduped,
            "count": len(deduped),
            "count_before_dedup": len(normalized),
            "has_next": has_next,
            "has_prev": has_prev,
            "next_cursor": next_cursor,
            "prev_cursor": prev_cursor,
        }

    async def get_all_creatives(self) -> Dict[str, Any]:
        """
        Fetch all ad creatives across ALL ad accounts accessible by the token.

        Returns:
            Dict with total_creatives count and per-account creative lists.
        """
        # Step 1: Discover all ad accounts
        accounts = await self.get_all_ad_accounts()

        # Step 2: Fetch creatives for each account in parallel
        async def fetch_account_creatives(account: Dict) -> Dict[str, Any]:
            account_id = account["id"]
            account_name = account.get("name", "Unknown")
            account_currency = account.get("currency", "USD")

            try:
                creatives = await self.get_creatives_for_account(account_id)

                # Normalize each creative into a clean structure
                normalized = []
                for c in creatives:
                    # Determine creative type from object_story_spec
                    story_spec = c.get("object_story_spec", {}) or {}
                    creative_type = "unknown"
                    preview_url = c.get("image_url") or c.get("thumbnail_url") or ""

                    if story_spec.get("video_data"):
                        creative_type = "video"
                        video_data = story_spec["video_data"]
                        preview_url = preview_url or video_data.get("image_url", "")
                    elif story_spec.get("link_data"):
                        creative_type = "image"
                        link_data = story_spec["link_data"]
                        preview_url = preview_url or link_data.get("image_hash", "")
                        # If link_data has child_attachments, it's a carousel
                        if link_data.get("child_attachments"):
                            creative_type = "carousel"
                    elif story_spec.get("photo_data"):
                        creative_type = "image"

                    normalized.append({
                        "creative_id": c.get("id", ""),
                        "name": c.get("name", "Untitled"),
                        "title": c.get("title", ""),
                        "body": c.get("body", ""),
                        "type": creative_type,
                        "status": c.get("status", "UNKNOWN"),
                        "image_url": c.get("image_url", ""),
                        "thumbnail_url": c.get("thumbnail_url", ""),
                        "preview_url": preview_url,
                    })

                return {
                    "account_id": account_id,
                    "account_name": account_name,
                    "currency": account_currency,
                    "creative_count": len(normalized),
                    "creatives": normalized,
                }
            except Exception as e:
                logger.warning(
                    f"Failed to fetch creatives for {account_name} ({account_id}): {e}",
                    extra={"account_id": account_id, "error": str(e)},
                )
                return {
                    "account_id": account_id,
                    "account_name": account_name,
                    "currency": account_currency,
                    "creative_count": 0,
                    "creatives": [],
                    "error": str(e),
                }

        import asyncio
        account_results = await asyncio.gather(
            *[fetch_account_creatives(acc) for acc in accounts]
        )

        total_creatives = sum(a["creative_count"] for a in account_results)
        accounts_with_creatives = sum(1 for a in account_results if a["creative_count"] > 0)

        logger.info(
            f"Fetched {total_creatives} creatives across {len(accounts)} accounts "
            f"({accounts_with_creatives} with creatives)",
            extra={
                "total_creatives": total_creatives,
                "account_count": len(accounts),
                "accounts_with_creatives": accounts_with_creatives,
            },
        )

        return {
            "total_accounts": len(accounts),
            "accounts_with_creatives": accounts_with_creatives,
            "total_creatives": total_creatives,
            "accounts": account_results,
        }

    async def get_campaigns_detailed(
        self,
        account_id: Optional[str] = None,
        fields: str = "id,name,status,objective,daily_budget,lifetime_budget,budget_remaining,start_time,stop_time,created_time,updated_time,buying_type,bid_strategy,special_ad_categories",
    ) -> List[Dict[str, Any]]:
        """
        Fetch all campaigns for an ad account with detailed fields.

        Args:
            account_id: The ad account ID. Defaults to primary account.
            fields: Comma-separated fields to retrieve.

        Returns:
            List of campaign dicts with full metadata.
        """
        target = account_id or self._account_id
        path = f"{target}/campaigns"
        params = {"fields": fields, "limit": "500"}
        result = await self._request("GET", path, params=params)
        campaigns = result.get("data", [])

        # Handle pagination
        while result.get("paging", {}).get("next"):
            next_url = result["paging"]["next"]
            client = await self._get_client()
            response = await client.get(next_url)
            if response.status_code == 200:
                result = response.json()
                campaigns.extend(result.get("data", []))
            else:
                break

        logger.info(
            f"Fetched {len(campaigns)} campaigns for {target}",
            extra={"account_id": target, "campaign_count": len(campaigns)},
        )
        return campaigns

    async def get_campaign_insights(
        self,
        campaign_id: str,
        time_range: Optional[Dict[str, str]] = None,
        fields: str = "spend,impressions,clicks,cpc,ctr,cpm,reach,frequency,actions,cost_per_action_type",
    ) -> Dict[str, Any]:
        """
        Fetch performance insights for a specific campaign.

        Returns:
            Dict with campaign performance metrics.
        """
        path = f"{campaign_id}/insights"
        params: Dict[str, Any] = {"fields": fields}
        if time_range:
            params["time_range"] = json.dumps(time_range)
        return await self._request("GET", path, params=params)

    async def update_campaign(
        self,
        campaign_id: str,
        status: Optional[str] = None,
        daily_budget: Optional[int] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update a campaign's properties.

        Args:
            campaign_id: The campaign ID.
            status: New status ('ACTIVE', 'PAUSED', 'ARCHIVED').
            daily_budget: New daily budget in cents (e.g., 5000 = 50.00 in account currency).
            name: New campaign name.

        Returns:
            Graph API response (typically {"success": true}).
        """
        data: Dict[str, Any] = {}
        if status is not None:
            data["status"] = status
        if daily_budget is not None:
            data["daily_budget"] = str(daily_budget)
        if name is not None:
            data["name"] = name

        if not data:
            raise FacebookAdsError("No update fields provided")

        logger.info(
            f"Updating campaign {campaign_id}: {data}",
            extra={"campaign_id": campaign_id, "updates": data},
        )
        return await self._request("POST", campaign_id, data=data)

    async def delete_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """
        Delete (archive) a campaign. Facebook doesn't truly delete campaigns;
        this sets the status to DELETED which effectively archives it.

        Returns:
            Graph API response.
        """
        logger.info(
            f"Deleting (archiving) campaign {campaign_id}",
            extra={"campaign_id": campaign_id},
        )
        return await self._request("POST", campaign_id, data={"status": "DELETED"})

    async def get_all_campaigns(
        self,
        include_insights: bool = True,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Fetch all campaigns across ALL ad accounts with optional performance insights.

        Args:
            include_insights: Whether to fetch spend/clicks/impressions for each campaign.
            days: Number of days for the insights time range.

        Returns:
            Dict with total_campaigns count and per-account campaign lists.
        """
        from datetime import date as date_type, timedelta

        accounts = await self.get_all_ad_accounts()
        end_date = date_type.today()
        start_date = end_date - timedelta(days=days)
        time_range = {
            "since": start_date.strftime("%Y-%m-%d"),
            "until": end_date.strftime("%Y-%m-%d"),
        }

        async def fetch_account_campaigns(account: Dict) -> Dict[str, Any]:
            account_id = account["id"]
            account_name = account.get("name", "Unknown")
            account_currency = account.get("currency", "USD")

            try:
                campaigns = await self.get_campaigns_detailed(account_id)

                # Optionally fetch insights for each campaign in parallel
                if include_insights and campaigns:
                    async def enrich_campaign(c: Dict) -> Dict:
                        try:
                            insights = await self.get_campaign_insights(
                                c["id"], time_range=time_range
                            )
                            rows = insights.get("data", [])
                            if rows:
                                perf = rows[0]
                                c["performance"] = {
                                    "spend": float(perf.get("spend", 0)),
                                    "impressions": int(perf.get("impressions", 0)),
                                    "clicks": int(perf.get("clicks", 0)),
                                    "cpc": float(perf.get("cpc", 0)),
                                    "ctr": float(perf.get("ctr", 0)),
                                    "cpm": float(perf.get("cpm", 0)),
                                    "reach": int(perf.get("reach", 0)),
                                    "frequency": float(perf.get("frequency", 0)),
                                }
                            else:
                                c["performance"] = None
                        except Exception as e:
                            logger.warning(f"Failed to get insights for campaign {c['id']}: {e}")
                            c["performance"] = None
                        return c

                    campaigns = await asyncio.gather(
                        *[enrich_campaign(c) for c in campaigns]
                    )
                else:
                    for c in campaigns:
                        c["performance"] = None

                return {
                    "account_id": account_id,
                    "account_name": account_name,
                    "currency": account_currency,
                    "campaign_count": len(campaigns),
                    "campaigns": list(campaigns),
                }
            except Exception as e:
                logger.warning(
                    f"Failed to fetch campaigns for {account_name} ({account_id}): {e}",
                    extra={"account_id": account_id, "error": str(e)},
                )
                return {
                    "account_id": account_id,
                    "account_name": account_name,
                    "currency": account_currency,
                    "campaign_count": 0,
                    "campaigns": [],
                    "error": str(e),
                }

        account_results = await asyncio.gather(
            *[fetch_account_campaigns(acc) for acc in accounts]
        )

        total_campaigns = sum(a["campaign_count"] for a in account_results)
        accounts_with_campaigns = sum(1 for a in account_results if a["campaign_count"] > 0)

        logger.info(
            f"Fetched {total_campaigns} campaigns across {len(accounts)} accounts",
            extra={
                "total_campaigns": total_campaigns,
                "account_count": len(accounts),
                "insights_period": f"{start_date} to {end_date}" if include_insights else "none",
            },
        )

        return {
            "total_accounts": len(accounts),
            "accounts_with_campaigns": accounts_with_campaigns,
            "total_campaigns": total_campaigns,
            "insights_period": time_range if include_insights else None,
            "accounts": account_results,
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
        self._initialized = False
        logger.info("Facebook Ads client closed")
