"""HTTP client for PostEx COD Merchant API (v4.1.9).

Docs: PostEx Merchant API Integration Guide
Base: https://api.postex.pk/services/integration/api/order/v1
Auth: request header ``token`` (merchant API token).
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.postex.pk/services/integration/api/order/v1"

# List Orders API orderStatusID values (0 = all)
ORDER_STATUS_CHOICES: dict[str, str] = {
    "0": "All orders",
    "1": "Unbooked",
    "2": "Booked",
    "3": "PostEx Warehouse",
    "4": "Out For Delivery",
    "5": "Delivered",
    "6": "Returned",
    "7": "Un-Assigned By Me",
    "8": "Expired",
    "9": "Delivery Under Review",
    "15": "Picked By PostEx",
    "16": "Out For Return",
    "17": "Attempted",
    "18": "En-Route to PostEx warehouse",
}

_SHINY_ROOT = Path(__file__).resolve().parent.parent
POSTEX_PDF_DIR = _SHINY_ROOT / "postex_pdfs"
POSTEX_PDF_DIR.mkdir(parents=True, exist_ok=True)
_SAFE_PDF_NAME = re.compile(r"^postex_[A-Za-z0-9_-]+\.pdf$")

# Header printed on official PostEx CPR PDFs (from merchant portal export).
POSTEX_CPR_HEADER_ADDRESS = "CCA, 14, Sector C Phase 5 D.H.A,"
POSTEX_CPR_HEADER_PHONE = "(042) 32157777"
WH_TAX_RATE = 0.02


class PostExError(RuntimeError):
    """Raised when PostEx API returns an error or is unreachable."""


def is_safe_postex_pdf_filename(filename: str) -> bool:
    return bool(filename and _SAFE_PDF_NAME.fullmatch(filename))


def resolve_postex_pdf_path(filename: str) -> Path | None:
    if not is_safe_postex_pdf_filename(filename):
        return None
    root = POSTEX_PDF_DIR.resolve()
    filepath = (POSTEX_PDF_DIR / filename).resolve()
    try:
        filepath.relative_to(root)
    except ValueError:
        return None
    if not filepath.is_file():
        return None
    return filepath


def save_postex_pdf(content: bytes, stem: str) -> str:
    """Write PDF bytes and return a safe download filename."""
    from datetime import datetime

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", (stem or "doc").strip())[:48] or "doc"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"postex_{safe}_{stamp}.pdf"
    path = POSTEX_PDF_DIR / filename
    path.write_bytes(content)
    return filename


def _cpr_rows_from_payment_status(*args, **kwargs):
    from shiny_app.lib.cpr_document import cpr_rows_from_payment_status

    return cpr_rows_from_payment_status(*args, **kwargs)


def cpr_detail_fields(*args, **kwargs):
    from shiny_app.lib.cpr_document import cpr_detail_fields as _fn

    return _fn(*args, **kwargs)


def generate_cpr_pdf_bytes(*args, **kwargs):
    from shiny_app.lib.cpr_document import generate_cpr_pdf_bytes as _fn

    return _fn(*args, **kwargs)


def save_cpr_pdf(*args, **kwargs):
    from shiny_app.lib.cpr_document import save_cpr_pdf as _fn

    return _fn(*args, **kwargs)


def sort_cpr_rows_by_date_desc(*args, **kwargs):
    from shiny_app.lib.cpr_document import sort_cpr_rows_by_date_desc as _fn

    return _fn(*args, **kwargs)


def group_cpr_documents(*args, **kwargs):
    from shiny_app.lib.cpr_document import group_cpr_documents as _fn

    return _fn(*args, **kwargs)


def pick_default_merchant_address(*args, **kwargs):
    from shiny_app.lib.cpr_document import pick_default_merchant_address as _fn

    return _fn(*args, **kwargs)



class PostExClient:
    """Thin async client for PostEx merchant order APIs."""

    def __init__(
        self,
        *,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        self.token = token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "token": self.token,
            "Accept": "application/json, application/pdf, */*",
            "Content-Type": "application/json",
        }

    def _raise_for_api(self, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        code = str(payload.get("statusCode") or "")
        if code and code not in {"200", "201"}:
            msg = payload.get("statusMessage") or payload.get("message") or code
            raise PostExError(str(msg))
        return payload

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json_body,
            )

        if response.status_code >= 400:
            raise PostExError(
                f"PostEx HTTP {response.status_code}: {response.text[:400]}"
            )

        content_type = (response.headers.get("content-type") or "").lower()
        if "application/json" in content_type or response.text.strip().startswith("{"):
            try:
                data = response.json()
            except Exception as exc:
                raise PostExError(f"Invalid JSON from PostEx: {exc}") from exc
            return self._raise_for_api(data)

        raise PostExError(
            f"Unexpected PostEx response ({content_type}): {response.text[:300]}"
        )

    async def _request_pdf(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> bytes:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json_body,
            )

        if response.status_code >= 400:
            raise PostExError(
                f"PostEx HTTP {response.status_code}: {response.text[:400]}"
            )

        content_type = (response.headers.get("content-type") or "").lower()
        body = response.content
        if "pdf" in content_type or (body[:4] == b"%PDF"):
            return body

        # Some gateways return JSON error with 200
        text = response.text[:400]
        if text.strip().startswith("{"):
            try:
                self._raise_for_api(response.json())
            except PostExError:
                raise
        raise PostExError(f"Expected PDF from PostEx, got: {text}")

    async def get_operational_cities(self) -> list[dict[str, Any]]:
        data = await self._request_json("GET", "get-operational-city")
        dist = data.get("dist") if isinstance(data, dict) else None
        return dist if isinstance(dist, list) else []

    async def get_merchant_addresses(self) -> list[dict[str, Any]]:
        data = await self._request_json("GET", "get-merchant-address")
        dist = data.get("dist") if isinstance(data, dict) else None
        return dist if isinstance(dist, list) else []

    async def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request_json("POST", "create-order", json_body=payload)
        dist = data.get("dist") if isinstance(data, dict) else None
        if isinstance(dist, dict):
            return dist
        return data if isinstance(data, dict) else {"raw": data}

    async def track_order(self, tracking_number: str) -> dict[str, Any]:
        tn = quote(tracking_number.strip(), safe="")
        data = await self._request_json("GET", f"track-order/{tn}")
        dist = data.get("dist") if isinstance(data, dict) else None
        if isinstance(dist, dict):
            return dist
        return data if isinstance(data, dict) else {"raw": data}

    async def get_payment_status(self, tracking_number: str) -> dict[str, Any]:
        """Payment Status API — settlement flag and CPR numbers for one tracking number."""
        tn = quote(tracking_number.strip(), safe="")
        data = await self._request_json("GET", f"payment-status/{tn}")
        dist = data.get("dist") if isinstance(data, dict) else None
        if isinstance(dist, dict):
            return dist
        return data if isinstance(data, dict) else {"raw": data}

    async def list_orders(
        self,
        *,
        order_status_id: int,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        # Live API: startDate/endDate + orderStatusId (docs often say fromDate/orderStatusID).
        data = await self._request_json(
            "GET",
            "get-all-order",
            params={
                "orderStatusId": order_status_id,
                "startDate": from_date,
                "endDate": to_date,
            },
        )
        dist = data.get("dist") if isinstance(data, dict) else None
        if not isinstance(dist, list):
            return []
        rows: list[dict[str, Any]] = []
        for item in dist:
            if not isinstance(item, dict):
                continue
            tracking = item.get("trackingResponse")
            if isinstance(tracking, dict):
                row = dict(tracking)
                row.setdefault("trackingNumber", item.get("trackingNumber"))
                row["message"] = item.get("message")
                rows.append(row)
            else:
                rows.append(item)
        return rows

    async def list_cash_payment_receipts(
        self,
        *,
        from_date: str,
        to_date: str,
        order_status_id: int = 5,
        concurrency: int = 8,
    ) -> list[dict[str, Any]]:
        """Collect portal-style CPR documents for orders in a date range.

        Loads List Orders + Payment Status per tracking, groups by CPR number,
        and merges merchant Default Address for the receipt header.
        """
        orders = await self.list_orders(
            order_status_id=order_status_id,
            from_date=from_date,
            to_date=to_date,
        )
        tracking_numbers: list[str] = []
        seen: set[str] = set()
        for order in orders:
            tn = str(order.get("trackingNumber") or "").strip()
            if not tn or tn in seen:
                continue
            seen.add(tn)
            tracking_numbers.append(tn)

        if not tracking_numbers:
            return []

        orders_by_tracking = {
            tn: order
            for order in orders
            if isinstance(order, dict)
            and (tn := str(order.get("trackingNumber") or "").strip())
        }

        merchant: dict[str, Any] = {}
        try:
            addresses = await self.get_merchant_addresses()
            merchant = pick_default_merchant_address(addresses)
        except Exception as exc:
            logger.warning("Could not load merchant addresses for CPR: %s", exc)

        sem = asyncio.Semaphore(max(1, concurrency))
        receipts: list[dict[str, Any]] = []
        errors: list[str] = []

        async def _fetch(tn: str) -> None:
            async with sem:
                try:
                    status = await self.get_payment_status(tn)
                    receipts.extend(
                        _cpr_rows_from_payment_status(
                            status,
                            order=orders_by_tracking.get(tn),
                        )
                    )
                except PostExError as exc:
                    msg = str(exc).lower()
                    if "404" in msg or "not found" in msg:
                        logger.debug("No payment status for %s: %s", tn, exc)
                    else:
                        errors.append(f"{tn}: {exc}")
                        logger.warning("Payment status failed for %s: %s", tn, exc)
                except Exception as exc:
                    errors.append(f"{tn}: {exc}")
                    logger.warning("Payment status failed for %s: %s", tn, exc)

        await asyncio.gather(*[_fetch(tn) for tn in tracking_numbers])

        if not receipts and errors:
            raise PostExError(
                "Could not load payment status for any order. "
                f"First error: {errors[0]}"
            )

        return group_cpr_documents(receipts, merchant=merchant)

    async def list_unbooked_orders(
        self,
        *,
        order_start_date: str,
        order_end_date: str,
    ) -> list[dict[str, Any]]:
        data = await self._request_json(
            "GET",
            "get-unbooked-orders",
            params={
                "startDate": order_start_date,
                "endDate": order_end_date,
            },
        )
        dist = data.get("dist") if isinstance(data, dict) else None
        return dist if isinstance(dist, list) else []

    async def get_airway_bill(self, tracking_numbers: list[str]) -> bytes:
        cleaned = [t.strip() for t in tracking_numbers if t and t.strip()]
        if not cleaned:
            raise PostExError("Provide at least one tracking number")
        if len(cleaned) > 10:
            raise PostExError("Airway bill API allows a maximum of 10 tracking numbers")
        return await self._request_pdf(
            "GET",
            "get-invoice",
            params={"trackingNumbers": ",".join(cleaned)},
        )

    async def generate_load_sheet(
        self,
        *,
        tracking_numbers: list[str],
        pickup_address: str,
        city_name: str,
        contact_number: str,
    ) -> bytes:
        cleaned = [t.strip() for t in tracking_numbers if t and t.strip()]
        if not cleaned:
            raise PostExError("Provide at least one tracking number")
        return await self._request_pdf(
            "POST",
            "generate-load-sheet",
            json_body={
                "trackingNumbers": cleaned,
                "pickupAddress": pickup_address,
                "cityName": city_name,
                "contactNumber": contact_number,
            },
        )


def get_configured_client() -> PostExClient:
    from config import settings

    token = (settings.POSTEX_TOKEN or "").strip()
    if not token:
        raise PostExError(
            "POSTEX_TOKEN is not set in backend/.env "
            "(merchant API token from PostEx)"
        )
    base = (settings.POSTEX_BASE_URL or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    return PostExClient(token=token, base_url=base)
