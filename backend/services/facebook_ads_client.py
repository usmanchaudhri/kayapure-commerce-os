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

from services.meta_api_cache import (
    ACCOUNT_LIST_CACHE,
    ACCOUNT_SPEND_CACHE,
    CAMPAIGN_PAYLOAD_CACHE,
)
from utils.logging_config import get_logger

logger = get_logger("facebook_ads")

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

ACCOUNT_INSIGHT_FIELDS = (
    "spend,impressions,clicks,cpc,ctr,cpm,reach,frequency,"
    "inline_link_clicks,actions,purchase_roas"
)

# Slim list fields for campaign tables (modal-only fields fetched on View).
CAMPAIGN_LIST_FIELDS = (
    "id,name,status,objective,daily_budget,lifetime_budget,"
    "start_time,stop_time,created_time,updated_time"
)
CAMPAIGN_DETAIL_FIELDS = (
    "id,name,status,objective,daily_budget,lifetime_budget,budget_remaining,"
    "start_time,stop_time,created_time,updated_time,buying_type,bid_strategy,"
    "special_ad_categories"
)
CAMPAIGN_INSIGHT_BATCH_FIELDS = (
    "campaign_id,spend,impressions,clicks,cpc,ctr,cpm,reach,frequency,"
    "inline_link_clicks,actions,purchase_roas"
)
AD_INSIGHT_BATCH_FIELDS = (
    "ad_id,ad_name,campaign_id,spend,impressions,clicks,cpc,ctr,cpm,reach,frequency,"
    "inline_link_clicks,actions,purchase_roas"
)

# Meta rate-limit / throttle error codes (Graph + Marketing API).
_RATE_LIMIT_CODES = {4, 17, 32, 613, 80000, 80003, 80004}
_RATE_LIMIT_SUBCODES = {2446079, 1487742, 1996}
_MAX_RATE_LIMIT_RETRIES = 3
_DEFAULT_RATE_LIMIT_WAIT_SECONDS = 60.0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _extract_conversions(actions: Any) -> int:
    if not isinstance(actions, list):
        return 0
    total = 0
    for action in actions:
        action_type = action.get("action_type", "")
        if "offsite_conversion" in action_type or action_type in ("purchase", "omni_purchase"):
            total += _safe_int(action.get("value", 0))
    return total


def _extract_roas(purchase_roas: Any) -> float:
    if isinstance(purchase_roas, list) and purchase_roas:
        return _safe_float(purchase_roas[0].get("value", 0))
    return 0.0


def _extract_action_value(actions: Any, action_type: str) -> int:
    if not isinstance(actions, list):
        return 0
    for action in actions:
        if action.get("action_type") == action_type:
            return _safe_int(action.get("value", 0))
    return 0


def _creative_preview_from_payload(creative: Optional[Dict[str, Any]]) -> str:
    """Best-effort image/thumbnail URL from a nested ad creative payload."""
    if not creative or not isinstance(creative, dict):
        return ""
    preview = creative.get("thumbnail_url") or creative.get("image_url") or ""
    if preview:
        return preview
    story_spec = creative.get("object_story_spec") or {}
    if not isinstance(story_spec, dict):
        return ""
    video_data = story_spec.get("video_data") or {}
    if isinstance(video_data, dict) and video_data.get("image_url"):
        return video_data.get("image_url", "")
    link_data = story_spec.get("link_data") or {}
    if isinstance(link_data, dict) and link_data.get("picture"):
        return link_data.get("picture", "")
    photo_data = story_spec.get("photo_data") or {}
    if isinstance(photo_data, dict) and photo_data.get("url"):
        return photo_data.get("url", "")
    return ""


def _empty_account_metrics() -> Dict[str, Any]:
    return {
        "spend": 0.0,
        "impressions": 0,
        "clicks": 0,
        "cpc": 0.0,
        "ctr": 0.0,
        "cpm": 0.0,
        "reach": 0,
        "frequency": 0.0,
        "link_clicks": 0,
        "conversions": 0,
        "roas": 0.0,
        "has_data": False,
    }


def _parse_account_insight_row(row: Dict[str, Any]) -> Dict[str, Any]:
    spend = _safe_float(row.get("spend"))
    impressions = _safe_int(row.get("impressions"))
    clicks = _safe_int(row.get("clicks"))
    metrics = {
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "cpc": _safe_float(row.get("cpc")),
        "ctr": _safe_float(row.get("ctr")),
        "cpm": _safe_float(row.get("cpm")),
        "reach": _safe_int(row.get("reach")),
        "frequency": round(_safe_float(row.get("frequency")), 2),
        "link_clicks": _safe_int(row.get("inline_link_clicks")),
        "conversions": _extract_conversions(row.get("actions")),
        "roas": round(_extract_roas(row.get("purchase_roas")), 2),
        "has_data": spend > 0 or impressions > 0 or clicks > 0,
    }
    return metrics


def _aggregate_account_metrics(accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    spend = sum(a.get("spend", 0) for a in accounts)
    impressions = sum(a.get("impressions", 0) for a in accounts)
    clicks = sum(a.get("clicks", 0) for a in accounts)
    reach = sum(a.get("reach", 0) for a in accounts)
    link_clicks = sum(a.get("link_clicks", 0) for a in accounts)
    conversions = sum(a.get("conversions", 0) for a in accounts)
    spend_for_roas = sum(a.get("spend", 0) for a in accounts if a.get("spend", 0) > 0)
    roas_weighted = sum(a.get("roas", 0) * a.get("spend", 0) for a in accounts if a.get("spend", 0) > 0)

    return {
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "reach": reach,
        "link_clicks": link_clicks,
        "conversions": conversions,
        "cpc": round(spend / max(clicks, 1), 2),
        "ctr": round(clicks / max(impressions, 1) * 100, 2),
        "cpm": round(spend / max(impressions, 1) * 1000, 2),
        "roas": round(roas_weighted / spend_for_roas, 2) if spend_for_roas else 0.0,
    }


class FacebookAdsError(Exception):
    """Raised when a Facebook Graph API call fails."""

    def __init__(self, message: str, *, code: Optional[int] = None, subcode: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


class FacebookAdsRateLimitError(FacebookAdsError):
    """Raised when Meta throttles the app or ad account."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[int] = None,
        subcode: Optional[int] = None,
        wait_seconds: float = _DEFAULT_RATE_LIMIT_WAIT_SECONDS,
    ):
        super().__init__(message, code=code, subcode=subcode)
        self.wait_seconds = max(1.0, float(wait_seconds))


def _parse_rate_limit_wait(headers: httpx.Headers, err: Dict[str, Any]) -> float:
    """Best-effort wait time from Meta usage headers or error payload."""
    for header_name in (
        "x-business-use-case-usage",
        "x-ad-account-usage",
        "x-fb-ads-insights-throttle",
    ):
        raw = headers.get(header_name)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        # Headers are often {"act_123":[{"estimated_time_to_regain_access":2, ...}]}
        if isinstance(payload, dict):
            for value in payload.values():
                entries = value if isinstance(value, list) else [value]
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    eta = entry.get("estimated_time_to_regain_access")
                    if eta is not None:
                        try:
                            minutes = float(eta)
                            if minutes > 0:
                                return minutes * 60.0
                        except (TypeError, ValueError):
                            pass
                    reset_duration = entry.get("reset_time_duration")
                    if reset_duration is not None:
                        try:
                            return float(reset_duration)
                        except (TypeError, ValueError):
                            pass
                    util = entry.get("acc_id_util_pct")
                    if util is not None:
                        try:
                            if float(util) >= 100:
                                return _DEFAULT_RATE_LIMIT_WAIT_SECONDS
                        except (TypeError, ValueError):
                            pass
    # Fall back to error body hints
    for key in ("estimated_time_to_regain_access", "error_user_msg"):
        val = err.get(key)
        if isinstance(val, (int, float)) and val > 0:
            # Meta sometimes returns minutes in BUC headers; body ints are treated as seconds if large
            return float(val) if float(val) > 10 else float(val) * 60.0
    return _DEFAULT_RATE_LIMIT_WAIT_SECONDS


def _is_rate_limit_error(code: Any, subcode: Any) -> bool:
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    try:
        sub_i = int(subcode) if subcode is not None else None
    except (TypeError, ValueError):
        sub_i = None
    if code_i in _RATE_LIMIT_CODES:
        return True
    if sub_i in _RATE_LIMIT_SUBCODES:
        return True
    return False


def _performance_from_insight_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "spend": _safe_float(row.get("spend")),
        "impressions": _safe_int(row.get("impressions")),
        "clicks": _safe_int(row.get("clicks")),
        "cpc": _safe_float(row.get("cpc")),
        "ctr": _safe_float(row.get("ctr")),
        "cpm": _safe_float(row.get("cpm")),
        "reach": _safe_int(row.get("reach")),
        "frequency": _safe_float(row.get("frequency")),
    }


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
        Handles error parsing, rate-limit backoff, and logging.
        """
        client = await self._get_client()
        url = f"{GRAPH_API_BASE}/{path.lstrip('/')}"

        # Inject access token
        if params is None:
            params = {}
        else:
            params = dict(params)
        params["access_token"] = self._access_token

        last_error: Optional[Exception] = None
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            start = time.perf_counter()
            logger.info(
                f"Facebook API {method} /{path}",
                extra={"method": method, "path": path, "attempt": attempt + 1},
            )
            try:
                if method == "GET":
                    response = await client.get(url, params=params)
                elif method == "POST":
                    response = await client.post(url, params=params, data=data)
                else:
                    raise FacebookAdsError(f"Unsupported HTTP method: {method}")

                elapsed = (time.perf_counter() - start) * 1000
                self._log_usage_headers(response.headers, path=path)

                if response.status_code != 200:
                    error_body = response.text[:500]
                    err: Dict[str, Any] = {}
                    try:
                        err = response.json().get("error", {}) or {}
                    except (json.JSONDecodeError, AttributeError):
                        err = {}
                    msg = err.get("message", error_body)
                    code = err.get("code", response.status_code)
                    subcode = err.get("error_subcode")

                    if _is_rate_limit_error(code, subcode) and attempt < _MAX_RATE_LIMIT_RETRIES:
                        wait_s = _parse_rate_limit_wait(response.headers, err)
                        # Cap single wait so the UI does not hang forever
                        wait_s = min(wait_s, 120.0)
                        logger.warning(
                            f"Facebook rate limit on {method} /{path}; "
                            f"backing off {wait_s:.0f}s (attempt {attempt + 1}/"
                            f"{_MAX_RATE_LIMIT_RETRIES})",
                            extra={
                                "path": path,
                                "code": code,
                                "subcode": subcode,
                                "wait_seconds": wait_s,
                            },
                        )
                        await asyncio.sleep(wait_s)
                        last_error = FacebookAdsRateLimitError(
                            f"[{code}] {msg}",
                            code=int(code) if str(code).isdigit() else None,
                            subcode=int(subcode) if subcode is not None and str(subcode).isdigit() else None,
                            wait_seconds=wait_s,
                        )
                        continue

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
                    if _is_rate_limit_error(code, subcode):
                        wait_s = _parse_rate_limit_wait(response.headers, err)
                        raise FacebookAdsRateLimitError(
                            f"[{code}] {msg}",
                            code=int(code) if str(code).isdigit() else None,
                            subcode=int(subcode) if subcode is not None and str(subcode).isdigit() else None,
                            wait_seconds=wait_s,
                        )
                    raise FacebookAdsError(
                        f"[{code}] {msg}",
                        code=int(code) if str(code).isdigit() else None,
                        subcode=int(subcode) if subcode is not None and str(subcode).isdigit() else None,
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

            except FacebookAdsRateLimitError:
                raise
            except FacebookAdsError:
                raise
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

        if last_error:
            raise last_error
        raise FacebookAdsError(f"Request failed after retries: {method} /{path}")

    def _log_usage_headers(self, headers: httpx.Headers, *, path: str) -> None:
        for header_name in (
            "x-business-use-case-usage",
            "x-ad-account-usage",
            "x-fb-ads-insights-throttle",
        ):
            raw = headers.get(header_name)
            if raw:
                logger.debug(
                    f"Meta usage header {header_name} on /{path}: {raw[:500]}",
                    extra={"path": path, "header": header_name},
                )

    async def _get_json_url(self, next_url: str) -> Dict[str, Any]:
        """Follow an absolute paging URL with the same rate-limit handling."""
        client = await self._get_client()
        last_error: Optional[Exception] = None
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            start = time.perf_counter()
            try:
                response = await client.get(next_url)
                elapsed = (time.perf_counter() - start) * 1000
                self._log_usage_headers(response.headers, path="paging")
                if response.status_code != 200:
                    err: Dict[str, Any] = {}
                    try:
                        err = response.json().get("error", {}) or {}
                    except (json.JSONDecodeError, AttributeError):
                        err = {}
                    msg = err.get("message", response.text[:300])
                    code = err.get("code", response.status_code)
                    subcode = err.get("error_subcode")
                    if _is_rate_limit_error(code, subcode) and attempt < _MAX_RATE_LIMIT_RETRIES:
                        wait_s = min(_parse_rate_limit_wait(response.headers, err), 120.0)
                        logger.warning(
                            f"Facebook rate limit on paging URL; backing off {wait_s:.0f}s",
                            extra={"wait_seconds": wait_s, "attempt": attempt + 1},
                        )
                        await asyncio.sleep(wait_s)
                        last_error = FacebookAdsRateLimitError(
                            f"[{code}] {msg}",
                            wait_seconds=wait_s,
                        )
                        continue
                    raise FacebookAdsError(f"[{code}] {msg}")
                logger.info(
                    f"Facebook API paging completed in {elapsed:.1f}ms",
                    extra={"latency_ms": round(elapsed, 1)},
                )
                return response.json()
            except FacebookAdsError:
                raise
            except httpx.HTTPError as e:
                raise FacebookAdsError(f"Paging request failed: {e}")
        if last_error:
            raise last_error
        raise FacebookAdsError("Paging request failed after retries")

    async def _paginate_data(
        self,
        first_page: Dict[str, Any],
        *,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        rows = list(first_page.get("data") or [])
        page = first_page
        pages = 1
        while page.get("paging", {}).get("next"):
            if max_pages is not None and pages >= max_pages:
                break
            page = await self._get_json_url(page["paging"]["next"])
            rows.extend(page.get("data") or [])
            pages += 1
        return rows

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
        limit: Optional[int] = None,
        filtering: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Fetch insights from the Facebook Marketing API.

        Args:
            object_id: The ad account, campaign, or ad set ID. Defaults to account ID.
            time_range: Dict with 'since' and 'until' date strings (YYYY-MM-DD).
            level: Aggregation level — 'account', 'campaign', 'adset', or 'ad'.
            fields: Comma-separated list of metrics to retrieve.
            time_increment: If set to 1, returns daily granularity rows.
            limit: Page size for multi-row insights (e.g. level=campaign).
            filtering: Optional Meta filtering list/dict (JSON-serialized).

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

        if limit is not None:
            params["limit"] = str(limit)

        if filtering is not None:
            params["filtering"] = (
                filtering if isinstance(filtering, str) else json.dumps(filtering)
            )

        return await self._request("GET", path, params=params)

    async def get_campaigns(
        self,
        account_id: Optional[str] = None,
        fields: str = "id,name,status,daily_budget,objective,start_time,stop_time",
    ) -> Dict[str, Any]:
        """
        Fetch all campaigns for an ad account.

        Returns:
            Raw Graph API response dict (contains 'data' array).
        """
        path = f"{account_id or self._account_id}/campaigns"
        params = {"fields": fields, "limit": "500"}
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

    async def get_adsets_for_account(
        self,
        account_id: Optional[str] = None,
        fields: str = "id,campaign_id,destination_type,promoted_object,optimization_goal",
    ) -> List[Dict[str, Any]]:
        """
        Fetch all ad sets for an ad account (used to resolve campaign destinations).

        Returns:
            List of ad set dicts with campaign_id and destination metadata.
        """
        target = account_id or self._account_id
        path = f"{target}/adsets"
        params = {"fields": fields, "limit": "500"}
        result = await self._request("GET", path, params=params)
        adsets = await self._paginate_data(result)

        logger.info(
            f"Fetched {len(adsets)} ad sets for {target}",
            extra={"account_id": target, "adset_count": len(adsets)},
        )
        return adsets

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
        fields: str = "id,name,currency,account_status,amount_spent,timezone_name,created_time",
        *,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all ad accounts accessible by the current access token.

        Returns:
            List of ad account dicts with id, name, currency, status, etc.
        """
        cache_key = f"adaccounts:{fields}"
        if not force_refresh:
            cached = ACCOUNT_LIST_CACHE.get(cache_key)
            if cached is not None:
                logger.info(
                    f"Ad accounts cache hit ({len(cached)} accounts)",
                    extra={"account_count": len(cached), "cache": True},
                )
                return list(cached)

        path = "me/adaccounts"
        params = {"fields": fields, "limit": "100"}
        result = await self._request("GET", path, params=params)
        accounts = await self._paginate_data(result)

        logger.info(
            f"Found {len(accounts)} ad accounts",
            extra={"account_count": len(accounts)},
        )
        ACCOUNT_LIST_CACHE.set(cache_key, accounts)
        return accounts

    async def get_total_spend_all_accounts(
        self,
        since: str = "2025-01-01",
        until: Optional[str] = None,
        *,
        force_refresh: bool = False,
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

        cache_key = f"spend:{since}:{until}"
        if not force_refresh:
            cached = ACCOUNT_SPEND_CACHE.get(cache_key)
            if cached is not None:
                logger.info(
                    "Account spend cache hit",
                    extra={"since": since, "until": until, "cache": True},
                )
                return cached

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
                    fields=ACCOUNT_INSIGHT_FIELDS,
                )
                rows = insights.get("data", [])
                base = {
                    "account_id": account_id,
                    "account_name": account_name,
                    "currency": account_currency,
                    "status": status_label,
                    "created_time": account.get("created_time", "") or "",
                    "lifetime_spend": _safe_float(account.get("amount_spent", 0)) / 100,
                }
                if rows:
                    return {**base, **_parse_account_insight_row(rows[0])}
                return {**base, **_empty_account_metrics()}
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
                    "created_time": account.get("created_time", "") or "",
                    "lifetime_spend": _safe_float(account.get("amount_spent", 0)) / 100,
                    **_empty_account_metrics(),
                    "error": str(e),
                }

        import asyncio
        account_results = await asyncio.gather(
            *[fetch_account_spend(acc) for acc in accounts]
        )

        # Step 3: Aggregate totals (grouped by currency)
        grand_totals = _aggregate_account_metrics(account_results)
        grand_total_spend = grand_totals["spend"]
        grand_total_impressions = grand_totals["impressions"]
        grand_total_clicks = grand_totals["clicks"]
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

        payload = {
            "period": {"since": since, "until": until},
            "total_accounts": len(accounts),
            "accounts_with_data": len(accounts_with_data),
            "grand_total_spend": grand_total_spend,
            "grand_total_impressions": grand_total_impressions,
            "grand_total_clicks": grand_total_clicks,
            "grand_totals": grand_totals,
            "currency_totals": currency_totals,
            "accounts": account_results,
        }
        ACCOUNT_SPEND_CACHE.set(cache_key, payload)
        return payload

    async def get_creatives_for_account(
        self,
        account_id: str,
        fields: str = (
            "id,name,title,body,image_url,thumbnail_url,object_story_spec,"
            "status,effective_object_story_id,created_time"
        ),
        limit: int = 50,
        after: Optional[str] = None,
        include_engagement: bool = True,
        engagement_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Fetch ad creatives for a specific ad account with server-side pagination.

        Args:
            account_id: The ad account ID (e.g., act_123456).
            fields: Comma-separated fields to retrieve.
            limit: Max creatives per page (default 50).
            after: Cursor for the next page of results.
            include_engagement: Attach ad-level insights aggregated by creative.
            engagement_days: Lookback window for creative engagement metrics.

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
                preview_url = preview_url or link_data.get("picture") or link_data.get("image_hash", "")
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
                "created_time": c.get("created_time", "") or "",
                "image_url": c.get("image_url", ""),
                "thumbnail_url": c.get("thumbnail_url", ""),
                "preview_url": preview_url,
            })

        # ----------------------------------------------------------
        # Deduplicate: by image_url for images/carousels,
        #              by preview_url (video thumbnail) for videos.
        # Keep the newest created_time when collapsing duplicates.
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
                idx = seen_keys[dedup_key]
                kept = deduped[idx]
                kept["_duplicate_count"] = kept.get("_duplicate_count", 1) + 1
                # Prefer the newer creative when collapsing duplicates
                if (c.get("created_time") or "") > (kept.get("created_time") or ""):
                    dup_count = kept["_duplicate_count"]
                    c["_duplicate_count"] = dup_count
                    deduped[idx] = c
            else:
                c["_duplicate_count"] = 1
                seen_keys[dedup_key] = len(deduped)
                deduped.append(c)

        if include_engagement and deduped:
            try:
                engagement_map = await self.get_creative_engagement_for_account(
                    account_id, days=engagement_days
                )
                for c in deduped:
                    metrics = engagement_map.get(c.get("creative_id", ""))
                    if metrics:
                        c["engagement"] = metrics
                    else:
                        c["engagement"] = None
            except Exception as e:
                logger.warning(
                    f"Failed to attach creative engagement for {account_id}: {e}",
                    extra={"account_id": account_id, "error": str(e)},
                )
                for c in deduped:
                    c.setdefault("engagement", None)

        # Newest first within the page (Graph order is not guaranteed after dedup)
        deduped.sort(key=lambda item: item.get("created_time") or "", reverse=True)

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

    async def get_campaign_ad_previews(
        self,
        account_id: str,
        max_pages: int = 3,
        page_size: int = 100,
    ) -> Dict[str, Dict[str, str]]:
        """
        Map campaign_id -> preview metadata from the first usable ad creative.

        Prefers ACTIVE ads when available; falls back to any ad with a thumbnail.
        """
        fields = (
            "campaign_id,name,effective_status,"
            "creative{id,thumbnail_url,image_url,object_story_spec}"
        )
        path = f"{account_id}/ads"
        params = {"fields": fields, "limit": str(page_size)}
        previews: Dict[str, Dict[str, str]] = {}
        pages = 0
        result = await self._request("GET", path, params=params)

        while True:
            pages += 1
            for ad in result.get("data", []):
                campaign_id = ad.get("campaign_id") or ""
                if not campaign_id:
                    continue
                creative = ad.get("creative") if isinstance(ad.get("creative"), dict) else {}
                preview_url = _creative_preview_from_payload(creative)
                if not preview_url:
                    continue
                status = (ad.get("effective_status") or "").upper()
                candidate = {
                    "thumbnail_url": preview_url,
                    "ad_name": ad.get("name", "") or "",
                    "ad_status": status,
                    "creative_id": creative.get("id", ""),
                }
                existing = previews.get(campaign_id)
                if not existing:
                    previews[campaign_id] = candidate
                elif existing.get("ad_status") != "ACTIVE" and status == "ACTIVE":
                    previews[campaign_id] = candidate

            next_url = (result.get("paging") or {}).get("next")
            if not next_url or pages >= max_pages:
                break
            result = await self._get_json_url(next_url)

        logger.info(
            f"Mapped ad previews for {len(previews)} campaigns on {account_id}",
            extra={"account_id": account_id, "campaign_preview_count": len(previews)},
        )
        return previews

    async def get_single_campaign_ad_preview(
        self,
        account_id: str,
        campaign_id: str,
    ) -> Dict[str, str]:
        """Fetch one campaign's ad thumbnail without scanning the whole account."""
        fields = (
            "campaign_id,name,effective_status,"
            "creative{id,thumbnail_url,image_url,object_story_spec}"
        )
        filtering = json.dumps(
            [{"field": "campaign.id", "operator": "IN", "value": [str(campaign_id)]}]
        )
        path = f"{account_id}/ads"
        params = {"fields": fields, "limit": "5", "filtering": filtering}
        result = await self._request("GET", path, params=params)
        best: Dict[str, str] = {}
        for ad in result.get("data", []):
            creative = ad.get("creative") if isinstance(ad.get("creative"), dict) else {}
            preview_url = _creative_preview_from_payload(creative)
            if not preview_url:
                continue
            status = (ad.get("effective_status") or "").upper()
            candidate = {
                "thumbnail_url": preview_url,
                "ad_name": ad.get("name", "") or "",
                "ad_status": status,
            }
            if not best or (best.get("ad_status") != "ACTIVE" and status == "ACTIVE"):
                best = candidate
        return best

    async def get_creative_engagement_for_account(
        self,
        account_id: str,
        days: int = 30,
        max_pages: int = 3,
        page_size: int = 100,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate ad insights by creative_id for engagement ranking.

        Returns:
            Map of creative_id -> impressions/clicks/ctr/link_clicks/post_engagement/score.
        """
        fields = (
            "creative{id},"
            "insights.date_preset(last_30d){impressions,clicks,ctr,inline_link_clicks,actions}"
        )
        path = f"{account_id}/ads"
        params = {"fields": fields, "limit": str(page_size)}
        totals: Dict[str, Dict[str, Any]] = {}
        pages = 0
        client = await self._get_client()
        result = await self._request("GET", path, params=params)

        while True:
            pages += 1
            for ad in result.get("data", []):
                creative = ad.get("creative") if isinstance(ad.get("creative"), dict) else {}
                creative_id = creative.get("id", "")
                if not creative_id:
                    continue
                insights = ad.get("insights") if isinstance(ad.get("insights"), dict) else {}
                insight_rows = insights.get("data", []) if insights else []
                if not insight_rows:
                    continue
                row = insight_rows[0]
                bucket = totals.setdefault(
                    creative_id,
                    {
                        "impressions": 0,
                        "clicks": 0,
                        "link_clicks": 0,
                        "post_engagement": 0,
                    },
                )
                bucket["impressions"] += _safe_int(row.get("impressions"))
                bucket["clicks"] += _safe_int(row.get("clicks"))
                bucket["link_clicks"] += _safe_int(row.get("inline_link_clicks"))
                bucket["post_engagement"] += _extract_action_value(
                    row.get("actions"), "post_engagement"
                )

            next_url = (result.get("paging") or {}).get("next")
            if not next_url or pages >= max_pages:
                break
            response = await client.get(next_url)
            if response.status_code != 200:
                break
            result = response.json()

        engagement_map: Dict[str, Dict[str, Any]] = {}
        for creative_id, bucket in totals.items():
            impressions = bucket["impressions"]
            clicks = bucket["clicks"]
            link_clicks = bucket["link_clicks"]
            post_engagement = bucket["post_engagement"]
            ctr = round((clicks / impressions) * 100, 2) if impressions > 0 else 0.0
            score = post_engagement or clicks or link_clicks
            engagement_map[creative_id] = {
                "impressions": impressions,
                "clicks": clicks,
                "link_clicks": link_clicks,
                "post_engagement": post_engagement,
                "ctr": ctr,
                "score": score,
                "days": days,
            }

        logger.info(
            f"Aggregated engagement for {len(engagement_map)} creatives on {account_id}",
            extra={
                "account_id": account_id,
                "creative_engagement_count": len(engagement_map),
                "days": days,
            },
        )
        return engagement_map


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
        fields: str = CAMPAIGN_LIST_FIELDS,
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
        campaigns = await self._paginate_data(result)

        logger.info(
            f"Fetched {len(campaigns)} campaigns for {target}",
            extra={"account_id": target, "campaign_count": len(campaigns)},
        )
        return campaigns

    async def get_campaign_insights_batch(
        self,
        account_id: str,
        time_range: Optional[Dict[str, str]] = None,
        fields: str = CAMPAIGN_INSIGHT_BATCH_FIELDS,
    ) -> Dict[str, Dict[str, Any]]:
        """One account-level insights call at level=campaign, keyed by campaign_id."""
        first = await self.get_insights(
            object_id=account_id,
            time_range=time_range,
            level="campaign",
            fields=fields,
            limit=500,
        )
        rows = await self._paginate_data(first)
        by_id: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            cid = row.get("campaign_id") or ""
            if cid:
                by_id[cid] = _performance_from_insight_row(row)
        return by_id

    async def get_insights_raw_batch(
        self,
        account_id: str,
        *,
        time_range: Optional[Dict[str, str]] = None,
        level: str = "campaign",
        fields: str = CAMPAIGN_INSIGHT_BATCH_FIELDS,
        id_field: str = "campaign_id",
    ) -> Dict[str, Dict[str, Any]]:
        """Raw Graph insight rows keyed by campaign_id or ad_id (for profit leak scanner)."""
        first = await self.get_insights(
            object_id=account_id,
            time_range=time_range,
            level=level,
            fields=fields,
            limit=500,
        )
        rows = await self._paginate_data(first)
        by_id: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            entity_id = row.get(id_field) or ""
            if entity_id:
                by_id[entity_id] = row
        return by_id

    async def get_ad_insights_batch(
        self,
        account_id: str,
        time_range: Optional[Dict[str, str]] = None,
        fields: str = AD_INSIGHT_BATCH_FIELDS,
    ) -> Dict[str, Dict[str, Any]]:
        """Raw insight rows at level=ad, keyed by ad_id."""
        return await self.get_insights_raw_batch(
            account_id,
            time_range=time_range,
            level="ad",
            fields=fields,
            id_field="ad_id",
        )

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

    async def get_campaign_by_id(
        self,
        campaign_id: str,
        fields: str = CAMPAIGN_DETAIL_FIELDS,
    ) -> Dict[str, Any]:
        """Fetch a single campaign object (used for View-modal detail fields)."""
        result = await self._request("GET", campaign_id, params={"fields": fields})
        return result if isinstance(result, dict) else {}

    async def enrich_account_campaigns(
        self,
        account_id: str,
        campaigns: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Phase 2: attach ad previews and ad-set goal/destination metadata."""
        enriched = [dict(c) for c in campaigns]
        try:
            previews = await self.get_campaign_ad_previews(account_id)
        except Exception as e:
            logger.warning(
                f"Failed to fetch campaign ad previews for {account_id}: {e}",
                extra={"account_id": account_id, "error": str(e)},
            )
            previews = {}

        try:
            adsets = await self.get_adsets_for_account(account_id)
            goal_map = _summarize_campaign_goals(adsets)
        except Exception as e:
            logger.warning(
                f"Failed to fetch campaign goals for {account_id}: {e}",
                extra={"account_id": account_id, "error": str(e)},
            )
            goal_map = {}

        for c in enriched:
            cid = c.get("id", "")
            preview = previews.get(cid) or {}
            c["thumbnail_url"] = preview.get("thumbnail_url", "") or c.get("thumbnail_url", "")
            c["ad_preview_name"] = preview.get("ad_name", "") or c.get("ad_preview_name", "")
            info = goal_map.get(cid, {})
            c["optimization_goal"] = info.get("optimization_goal", "") or c.get("optimization_goal", "")
            c["optimization_goals"] = info.get("optimization_goals", "") or c.get("optimization_goals", "")
            c["destination_type"] = info.get("destination_type", "") or c.get("destination_type", "")
        return enriched

    async def get_campaign_modal_details(
        self,
        account_id: str,
        campaign_id: str,
    ) -> Dict[str, Any]:
        """
        Lazy View-modal extras: full campaign fields + best-effort ad preview.
        Avoids loading these for every row in the table.
        """
        details = await self.get_campaign_by_id(campaign_id)
        thumbnail_url = ""
        ad_preview_name = ""
        try:
            preview = await self.get_single_campaign_ad_preview(account_id, campaign_id)
            thumbnail_url = preview.get("thumbnail_url", "") or ""
            ad_preview_name = preview.get("ad_name", "") or ""
        except Exception as e:
            logger.warning(
                f"Failed to fetch preview for campaign {campaign_id}: {e}",
                extra={"campaign_id": campaign_id, "error": str(e)},
            )
        return {
            **details,
            "thumbnail_url": thumbnail_url,
            "ad_preview_name": ad_preview_name,
        }

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
        CAMPAIGN_PAYLOAD_CACHE.invalidate(prefix="campaigns:")
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
        CAMPAIGN_PAYLOAD_CACHE.invalidate(prefix="campaigns:")
        return await self._request("POST", campaign_id, data={"status": "DELETED"})

    async def get_account_campaigns(
        self,
        account_id: str,
        *,
        since: str,
        until: str,
        account_name: str = "Unknown",
        currency: str = "USD",
        include_insights: bool = True,
        include_enrichment: bool = False,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch campaigns for one ad account.

        Phase 1 (default): campaign list + one batched level=campaign insights call.
        Phase 2 (include_enrichment=True): also attach ad previews + ad-set goals.
        """
        time_range = {"since": since, "until": until}
        cache_key = (
            f"campaigns:{account_id}:{since}:{until}:"
            f"insights={include_insights}:enrich={include_enrichment}"
        )
        if not force_refresh:
            cached = CAMPAIGN_PAYLOAD_CACHE.get(cache_key)
            if cached is not None:
                logger.info(
                    f"Campaign payload cache hit for {account_id}",
                    extra={"account_id": account_id, "cache": True},
                )
                return cached

        try:
            campaigns = await self.get_campaigns_detailed(
                account_id, fields=CAMPAIGN_LIST_FIELDS
            )

            if include_insights and campaigns:
                try:
                    perf_by_id = await self.get_campaign_insights_batch(
                        account_id, time_range=time_range
                    )
                    for c in campaigns:
                        c["performance"] = perf_by_id.get(c.get("id", ""))
                except Exception as e:
                    logger.warning(
                        f"Failed batched campaign insights for {account_id}: {e}",
                        extra={"account_id": account_id, "error": str(e)},
                    )
                    for c in campaigns:
                        c["performance"] = None
            else:
                for c in campaigns:
                    c["performance"] = None

            for c in campaigns:
                c.setdefault("thumbnail_url", "")
                c.setdefault("ad_preview_name", "")
                c.setdefault("optimization_goal", "")
                c.setdefault("optimization_goals", "")
                c.setdefault("destination_type", "")

            enrichment_loaded = False
            if include_enrichment and campaigns:
                campaigns = await self.enrich_account_campaigns(account_id, list(campaigns))
                enrichment_loaded = True

            payload = {
                "account_id": account_id,
                "account_name": account_name,
                "currency": currency,
                "campaign_count": len(campaigns),
                "campaigns": list(campaigns),
                "insights_period": time_range if include_insights else None,
                "enrichment_loaded": enrichment_loaded,
            }
            CAMPAIGN_PAYLOAD_CACHE.set(cache_key, payload)
            return payload
        except Exception as e:
            logger.warning(
                f"Failed to fetch campaigns for {account_name} ({account_id}): {e}",
                extra={"account_id": account_id, "error": str(e)},
            )
            return {
                "account_id": account_id,
                "account_name": account_name,
                "currency": currency,
                "campaign_count": 0,
                "campaigns": [],
                "insights_period": time_range if include_insights else None,
                "enrichment_loaded": False,
                "error": str(e),
            }

    async def get_campaign_deep_dataset(
        self,
        account_id: str,
        campaign_id: str,
        *,
        since: str,
        until: str,
        account_name: str = "",
        campaign_name: str = "",
        currency: str = "USD",
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Deep forensic dataset for one campaign: totals, daily trend, ad sets, ads, creatives.

        Uses filtered account insights (level=adset / level=ad) to avoid per-object fan-out.
        """
        cache_key = f"deep:{account_id}:{campaign_id}:{since}:{until}"
        if not force_refresh:
            cached = CAMPAIGN_PAYLOAD_CACHE.get(cache_key)
            if cached is not None:
                logger.info(
                    f"Deep campaign dataset cache hit for {campaign_id}",
                    extra={"campaign_id": campaign_id, "cache": True},
                )
                return cached

        time_range = {"since": since, "until": until}
        campaign_filter = [
            {"field": "campaign.id", "operator": "IN", "value": [str(campaign_id)]}
        ]
        insight_fields = (
            "spend,impressions,clicks,cpc,ctr,cpm,reach,frequency,"
            "inline_link_clicks,actions,purchase_roas"
        )
        adset_insight_fields = (
            "adset_id,adset_name,spend,impressions,clicks,cpc,ctr,cpm,"
            "reach,frequency,inline_link_clicks,actions,purchase_roas"
        )
        ad_insight_fields = (
            "ad_id,ad_name,spend,impressions,clicks,cpc,ctr,cpm,"
            "reach,frequency,inline_link_clicks,actions,purchase_roas"
        )

        # Campaign meta
        try:
            campaign_meta = await self.get_campaign_by_id(campaign_id)
        except Exception as e:
            campaign_meta = {"id": campaign_id, "name": campaign_name or campaign_id}
            logger.warning(
                f"Failed to fetch campaign meta {campaign_id}: {e}",
                extra={"campaign_id": campaign_id, "error": str(e)},
            )
        if campaign_name and not campaign_meta.get("name"):
            campaign_meta["name"] = campaign_name

        # Campaign totals + daily trend
        totals_row: Dict[str, Any] = {}
        daily_rows: List[Dict[str, Any]] = []
        try:
            totals_resp = await self.get_insights(
                object_id=campaign_id,
                time_range=time_range,
                level="campaign",
                fields=insight_fields,
            )
            totals_data = totals_resp.get("data") or []
            if totals_data:
                totals_row = totals_data[0]
        except Exception as e:
            logger.warning(
                f"Failed campaign totals for {campaign_id}: {e}",
                extra={"campaign_id": campaign_id, "error": str(e)},
            )
        try:
            daily_resp = await self.get_insights(
                object_id=campaign_id,
                time_range=time_range,
                level="campaign",
                fields=insight_fields,
                time_increment=1,
                limit=100,
            )
            daily_rows = await self._paginate_data(daily_resp)
        except Exception as e:
            logger.warning(
                f"Failed campaign daily insights for {campaign_id}: {e}",
                extra={"campaign_id": campaign_id, "error": str(e)},
            )

        # Ad set objects (structure / goals)
        adset_meta: Dict[str, Dict[str, Any]] = {}
        try:
            adsets_resp = await self.get_adsets(
                campaign_id,
                fields=(
                    "id,name,status,effective_status,daily_budget,lifetime_budget,"
                    "optimization_goal,billing_event,destination_type,targeting,"
                    "start_time,end_time"
                ),
            )
            for row in adsets_resp.get("data") or []:
                adset_meta[row.get("id", "")] = row
        except Exception as e:
            logger.warning(
                f"Failed ad sets for campaign {campaign_id}: {e}",
                extra={"campaign_id": campaign_id, "error": str(e)},
            )

        # Ad set insights (filtered)
        adset_insights: List[Dict[str, Any]] = []
        try:
            adset_ins_resp = await self.get_insights(
                object_id=account_id,
                time_range=time_range,
                level="adset",
                fields=adset_insight_fields,
                filtering=campaign_filter,
                limit=200,
            )
            adset_insights = await self._paginate_data(adset_ins_resp)
        except Exception as e:
            logger.warning(
                f"Failed ad set insights for campaign {campaign_id}: {e}",
                extra={"campaign_id": campaign_id, "error": str(e)},
            )

        # Ads + creatives (filtered list)
        ads_meta: List[Dict[str, Any]] = []
        try:
            ads_fields = (
                "id,name,effective_status,status,adset_id,"
                "creative{id,name,title,body,thumbnail_url,image_url,object_story_spec}"
            )
            ads_resp = await self._request(
                "GET",
                f"{account_id}/ads",
                params={
                    "fields": ads_fields,
                    "limit": "100",
                    "filtering": json.dumps(campaign_filter),
                },
            )
            ads_meta = await self._paginate_data(ads_resp, max_pages=3)
        except Exception as e:
            logger.warning(
                f"Failed ads list for campaign {campaign_id}: {e}",
                extra={"campaign_id": campaign_id, "error": str(e)},
            )

        # Ad insights (filtered)
        ad_insights: List[Dict[str, Any]] = []
        try:
            ad_ins_resp = await self.get_insights(
                object_id=account_id,
                time_range=time_range,
                level="ad",
                fields=ad_insight_fields,
                filtering=campaign_filter,
                limit=200,
            )
            ad_insights = await self._paginate_data(ad_ins_resp)
        except Exception as e:
            logger.warning(
                f"Failed ad insights for campaign {campaign_id}: {e}",
                extra={"campaign_id": campaign_id, "error": str(e)},
            )

        def _row_metrics(row: Dict[str, Any]) -> Dict[str, Any]:
            spend = _safe_float(row.get("spend"))
            clicks = _safe_int(row.get("clicks"))
            impressions = _safe_int(row.get("impressions"))
            return {
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "cpc": _safe_float(row.get("cpc")),
                "ctr": _safe_float(row.get("ctr")),
                "cpm": _safe_float(row.get("cpm")),
                "reach": _safe_int(row.get("reach")),
                "frequency": round(_safe_float(row.get("frequency")), 2),
                "link_clicks": _safe_int(row.get("inline_link_clicks")),
                "conversions": _extract_conversions(row.get("actions")),
                "roas": round(_extract_roas(row.get("purchase_roas")), 2),
            }

        campaign_totals = _row_metrics(totals_row) if totals_row else _empty_account_metrics()
        daily_breakdown = []
        for row in daily_rows:
            metrics = _row_metrics(row)
            daily_breakdown.append({
                "date": row.get("date_start", row.get("date_stop", "")),
                **metrics,
            })

        # Merge ad set meta + insights
        adset_perf_by_id = {
            r.get("adset_id", ""): _row_metrics(r) for r in adset_insights if r.get("adset_id")
        }
        adsets_out = []
        seen_adsets = set()
        for aid, meta in adset_meta.items():
            if not aid:
                continue
            seen_adsets.add(aid)
            targeting = meta.get("targeting") if isinstance(meta.get("targeting"), dict) else {}
            age_min = (targeting.get("age_min") if targeting else None)
            age_max = (targeting.get("age_max") if targeting else None)
            countries = []
            geos = targeting.get("geo_locations") if targeting else None
            if isinstance(geos, dict):
                countries = geos.get("countries") or []
            adsets_out.append({
                "id": aid,
                "name": meta.get("name", aid),
                "status": meta.get("effective_status") or meta.get("status") or "",
                "optimization_goal": meta.get("optimization_goal") or "",
                "destination_type": meta.get("destination_type") or "",
                "daily_budget": meta.get("daily_budget"),
                "targeting_summary": {
                    "age_min": age_min,
                    "age_max": age_max,
                    "countries": countries,
                },
                "performance": adset_perf_by_id.get(aid),
            })
        for aid, perf in adset_perf_by_id.items():
            if aid in seen_adsets:
                continue
            name = next(
                (r.get("adset_name") for r in adset_insights if r.get("adset_id") == aid),
                aid,
            )
            adsets_out.append({
                "id": aid,
                "name": name,
                "status": "",
                "optimization_goal": "",
                "destination_type": "",
                "daily_budget": None,
                "targeting_summary": {},
                "performance": perf,
            })
        adsets_out.sort(
            key=lambda a: float((a.get("performance") or {}).get("spend") or 0),
            reverse=True,
        )

        # Merge ads + creatives + insights
        ad_perf_by_id = {
            r.get("ad_id", ""): _row_metrics(r) for r in ad_insights if r.get("ad_id")
        }
        ads_out = []
        for ad in ads_meta:
            ad_id = ad.get("id", "")
            if not ad_id:
                continue
            creative = ad.get("creative") if isinstance(ad.get("creative"), dict) else {}
            story = creative.get("object_story_spec") if isinstance(creative.get("object_story_spec"), dict) else {}
            link_data = story.get("link_data") if isinstance(story.get("link_data"), dict) else {}
            video_data = story.get("video_data") if isinstance(story.get("video_data"), dict) else {}
            body = (
                creative.get("body")
                or link_data.get("message")
                or video_data.get("message")
                or ""
            )
            title = (
                creative.get("title")
                or link_data.get("name")
                or video_data.get("title")
                or ""
            )
            ads_out.append({
                "id": ad_id,
                "name": ad.get("name", ad_id),
                "status": ad.get("effective_status") or ad.get("status") or "",
                "adset_id": ad.get("adset_id") or "",
                "creative": {
                    "id": creative.get("id") or "",
                    "title": (title or "")[:180],
                    "body": (body or "")[:280],
                    "thumbnail_url": _creative_preview_from_payload(creative),
                },
                "performance": ad_perf_by_id.get(ad_id),
            })
        # Include insight-only ads missing from list
        listed_ids = {a["id"] for a in ads_out}
        for row in ad_insights:
            ad_id = row.get("ad_id", "")
            if not ad_id or ad_id in listed_ids:
                continue
            ads_out.append({
                "id": ad_id,
                "name": row.get("ad_name") or ad_id,
                "status": "",
                "adset_id": "",
                "creative": {"id": "", "title": "", "body": "", "thumbnail_url": ""},
                "performance": ad_perf_by_id.get(ad_id),
            })
        ads_out.sort(
            key=lambda a: float((a.get("performance") or {}).get("spend") or 0),
            reverse=True,
        )

        # Trim for LLM: top spenders + weakest CTR among those with spend
        top_adsets = adsets_out[:10]
        top_ads = ads_out[:10]
        weak_ads = sorted(
            [a for a in ads_out if (a.get("performance") or {}).get("spend", 0) > 0],
            key=lambda a: float((a.get("performance") or {}).get("ctr") or 0),
        )[:5]

        payload = {
            "scope": "campaign",
            "period": {"start": since, "end": until},
            "currency": currency,
            "account_id": account_id,
            "account_name": account_name,
            "campaign": {
                "id": campaign_id,
                "name": campaign_meta.get("name") or campaign_name or campaign_id,
                "status": campaign_meta.get("status") or "",
                "objective": campaign_meta.get("objective") or "",
                "daily_budget": campaign_meta.get("daily_budget"),
                "lifetime_budget": campaign_meta.get("lifetime_budget"),
                "buying_type": campaign_meta.get("buying_type") or "",
                "bid_strategy": campaign_meta.get("bid_strategy") or "",
                "created_time": campaign_meta.get("created_time") or "",
                "start_time": campaign_meta.get("start_time") or "",
                "stop_time": campaign_meta.get("stop_time") or "",
            },
            "campaign_totals": campaign_totals,
            "total_spend": campaign_totals.get("spend", 0),
            "avg_ctr": campaign_totals.get("ctr", 0),
            "avg_cpc": campaign_totals.get("cpc", 0),
            "daily_breakdown": daily_breakdown,
            "adsets": top_adsets,
            "adsets_count": len(adsets_out),
            "ads": top_ads,
            "weak_ads_by_ctr": weak_ads,
            "ads_count": len(ads_out),
            "source": "facebook_api",
        }
        CAMPAIGN_PAYLOAD_CACHE.set(cache_key, payload)
        logger.info(
            f"Built deep campaign dataset for {campaign_id}: "
            f"{len(adsets_out)} adsets, {len(ads_out)} ads, {len(daily_breakdown)} days",
            extra={
                "campaign_id": campaign_id,
                "adset_count": len(adsets_out),
                "ad_count": len(ads_out),
            },
        )
        return payload

    async def get_all_campaigns(
        self,
        include_insights: bool = True,
        days: int = 7,
        *,
        include_enrichment: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch all campaigns across ALL ad accounts with optional performance insights.

        Prefer lazy per-account loading in the UI; this remains for bulk/admin use.
        """
        from datetime import date as date_type, timedelta

        accounts = await self.get_all_ad_accounts()
        end_date = date_type.today()
        start_date = end_date - timedelta(days=days)
        since = start_date.strftime("%Y-%m-%d")
        until = end_date.strftime("%Y-%m-%d")
        time_range = {"since": since, "until": until}

        account_results = await asyncio.gather(
            *[
                self.get_account_campaigns(
                    acc["id"],
                    since=since,
                    until=until,
                    account_name=acc.get("name", "Unknown"),
                    currency=acc.get("currency", "USD"),
                    include_insights=include_insights,
                    include_enrichment=include_enrichment,
                )
                for acc in accounts
            ]
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



def _summarize_campaign_goals(adsets: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """Pick a representative optimization goal and destination per campaign."""
    by_campaign: Dict[str, List[Dict[str, Any]]] = {}
    for adset in adsets:
        campaign_id = adset.get("campaign_id") or ""
        if not campaign_id:
            continue
        by_campaign.setdefault(campaign_id, []).append(adset)

    summaries: Dict[str, Dict[str, str]] = {}
    for campaign_id, campaign_adsets in by_campaign.items():
        goals: List[str] = []
        destinations: List[str] = []
        for adset in campaign_adsets:
            goal = (adset.get("optimization_goal") or "").strip()
            if goal and goal not in goals:
                goals.append(goal)
            dest = (adset.get("destination_type") or "").strip()
            if dest and dest not in destinations:
                destinations.append(dest)
        summaries[campaign_id] = {
            "optimization_goal": goals[0] if goals else "",
            "optimization_goals": ", ".join(goals),
            "destination_type": destinations[0] if destinations else "",
        }
    return summaries
