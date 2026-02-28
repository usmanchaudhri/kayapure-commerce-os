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

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
        self._initialized = False
        logger.info("Facebook Ads client closed")
