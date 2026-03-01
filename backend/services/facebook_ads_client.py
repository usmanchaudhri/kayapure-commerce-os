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
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all ad creatives for a specific ad account.

        Args:
            account_id: The ad account ID (e.g., act_123456).
            fields: Comma-separated fields to retrieve.
            limit: Max creatives per page.

        Returns:
            List of creative dicts.
        """
        path = f"{account_id}/adcreatives"
        params = {"fields": fields, "limit": str(limit)}
        result = await self._request("GET", path, params=params)
        creatives = result.get("data", [])

        # Handle pagination
        while result.get("paging", {}).get("next"):
            next_url = result["paging"]["next"]
            client = await self._get_client()
            response = await client.get(next_url)
            if response.status_code == 200:
                result = response.json()
                creatives.extend(result.get("data", []))
            else:
                break

        logger.info(
            f"Fetched {len(creatives)} creatives for {account_id}",
            extra={"account_id": account_id, "creative_count": len(creatives)},
        )
        return creatives

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

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
        self._initialized = False
        logger.info("Facebook Ads client closed")
