"""Inbox for Apify Actor datasets started in Apify Console."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from config import settings
from models.database import SessionLocal
from services.apify_client import ApifyClient, ApifyError, parse_run_id
from services.apify_run_store import (
    get_by_run_id,
    list_runs,
    run_choices,
    run_to_view,
    save_analysis,
    upsert_run,
)
from services.reviews_analysis_agent import reviews_analysis_agent_service
from utils.logging_config import get_logger

logger = get_logger("apify_amazon")


class ApifyAmazonService:
    def __init__(self) -> None:
        self._client: Optional[ApifyClient] = None
        self._analyzing: Set[str] = set()

    def configure(self) -> None:
        token = settings.APIFY_TOKEN
        self._client = ApifyClient(token) if token else None

    @property
    def is_ready(self) -> bool:
        return bool(self._client and self._client.is_ready)

    def is_analyzing(self, run_id: str) -> bool:
        return run_id in self._analyzing

    def list_saved(self) -> List[Dict[str, str]]:
        db = SessionLocal()
        try:
            rows = list_runs(db)
            return [{"run_id": row.run_id, "label": row.label or row.run_id} for row in rows]
        finally:
            db.close()

    def saved_choices(self) -> Dict[str, str]:
        db = SessionLocal()
        try:
            return run_choices(list_runs(db))
        finally:
            db.close()

    def get_saved(self, run_id: str) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            row = get_by_run_id(db, run_id)
            if row is None:
                return None
            return run_to_view(row, analyzing=self.is_analyzing(run_id))
        finally:
            db.close()

    def latest_saved(self) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = list_runs(db, limit=1)
            if not rows:
                return None
            return run_to_view(rows[0], analyzing=self.is_analyzing(rows[0].run_id))
        finally:
            db.close()

    def _require(self) -> ApifyClient:
        if not self._client or not self._client.is_ready:
            raise ApifyError(
                "Apify is not connected. Set APIFY_TOKEN in backend/.env "
                "(console.apify.com → Settings → Integrations)."
            )
        return self._client

    async def load_run(
        self,
        run_ref: str,
        *,
        source: str = "manual",
        analyze: bool = True,
        force_analyze: bool = False,
    ) -> Dict[str, Any]:
        run_id = parse_run_id(run_ref)
        if not run_id:
            return {"error": "Paste an Apify run ID or Console run URL."}
        client = self._require()
        pack = await client.fetch_run_items(run_id)
        result = _pack_to_result(pack)
        result["loaded_run_id"] = run_id
        result["message"] = _status_note(pack.get("status"), run_id)
        result["source"] = source
        result["received_at"] = datetime.now(timezone.utc).isoformat()
        row = self._persist(result, pack=pack, source=source, reset_analysis=force_analyze)
        view = run_to_view(row, analyzing=False)
        if analyze:
            self._schedule_analysis(row.run_id, force=force_analyze)
            view["analyzing"] = self.is_analyzing(row.run_id)
        return view

    async def refresh_latest(self) -> Dict[str, Any]:
        client = self._require()
        runs = await client.list_runs(limit=20, status="SUCCEEDED")
        if not runs:
            return {
                "error": (
                    "No succeeded Actor runs on this Apify account yet. "
                    "Start an Actor in Apify Console, wait until it finishes, then refresh."
                )
            }
        latest_id = str(runs[0].get("id") or "")
        return await self.load_run(latest_id, source="api")

    async def reanalyze(self, run_id: str) -> Dict[str, Any]:
        view = self.get_saved(run_id)
        if not view:
            return {"error": "That loaded run was not found."}
        self._schedule_analysis(run_id, force=True)
        updated = self.get_saved(run_id) or view
        updated["analyzing"] = True
        return updated

    async def ingest_webhook(self, payload: Dict[str, Any], *, secret: Optional[str] = None) -> Dict[str, Any]:
        expected = (settings.APIFY_WEBHOOK_SECRET or "").strip()
        if expected:
            if not secret or secret != expected:
                raise ApifyError("Invalid Apify webhook secret.")
        event = str(payload.get("eventType") or "")
        resource = payload.get("resource") if isinstance(payload.get("resource"), dict) else {}
        event_data = payload.get("eventData") if isinstance(payload.get("eventData"), dict) else {}
        status = str(resource.get("status") or "")
        if event and "SUCCEEDED" not in event.upper() and status != "SUCCEEDED":
            return {"ignored": True, "eventType": event, "status": status}
        run_id = str(
            event_data.get("actorRunId")
            or resource.get("id")
            or payload.get("actorRunId")
            or ""
        )
        if not run_id:
            raise ApifyError("Webhook payload is missing actorRunId.")
        logger.info("Apify webhook received for run %s (%s)", run_id, event or status)
        result = await self.load_run(run_id, source="webhook")
        return {"ok": True, "run_id": run_id, "item_count": _item_count(result)}

    def _persist(self, result: Dict[str, Any], *, pack: Dict[str, Any], source: str, reset_analysis: bool):
        db = SessionLocal()
        try:
            existing = get_by_run_id(db, str(pack.get("run_id") or result.get("loaded_run_id") or ""))
            snapshot = _build_snapshot(result)
            if existing and not reset_analysis:
                old_n = len((existing.snapshot_json or {}).get("reviews") or [])
                new_n = len((snapshot.get("reviews") or []))
                if old_n != new_n:
                    reset_analysis = True
            product = (snapshot.get("product") or {}) if snapshot else {}
            reviews = (result.get("reviews") or {}).get("items") or []
            label = _run_label(product, pack.get("run_id") or result.get("loaded_run_id") or "", len(reviews))
            return upsert_run(
                db,
                run_id=str(pack.get("run_id") or result.get("loaded_run_id") or ""),
                actor_id=str(pack.get("actor_id") or ""),
                dataset_id=str(pack.get("dataset_id") or ""),
                status=str(pack.get("status") or ""),
                source=source,
                mode=str(result.get("mode") or "reviews"),
                label=label,
                product_title=(str(product.get("title"))[:500] if product.get("title") else None),
                product_asin=(str(product.get("asin"))[:20] if product.get("asin") else None),
                product_url=product.get("url"),
                raw_json=result,
                snapshot_json=snapshot,
                reset_analysis=reset_analysis,
            )
        finally:
            db.close()

    def _schedule_analysis(self, run_id: str, *, force: bool = False) -> None:
        if not run_id or run_id in self._analyzing:
            return
        db = SessionLocal()
        try:
            row = get_by_run_id(db, run_id)
            if row is None:
                return
            reviews = ((row.snapshot_json or {}).get("reviews") or []) if row.snapshot_json else []
            if not reviews:
                return
            if row.analysis_json and not force:
                return
        finally:
            db.close()
        self._analyzing.add(run_id)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._analyze_run(run_id))
        except RuntimeError:
            self._analyzing.discard(run_id)

    async def _analyze_run(self, run_id: str) -> None:
        db = SessionLocal()
        try:
            row = get_by_run_id(db, run_id)
            if row is None or not row.snapshot_json:
                return
            analysis = await reviews_analysis_agent_service.analyze(row.snapshot_json)
            save_analysis(db, run_id, analysis_json=analysis, analysis_error=None)
            logger.info("Saved review analysis for Apify run %s", run_id)
        except Exception as exc:
            logger.warning("Review analysis failed for run %s: %s", run_id, exc)
            try:
                save_analysis(db, run_id, analysis_json=None, analysis_error=str(exc))
            except Exception:
                db.rollback()
        finally:
            db.close()
            self._analyzing.discard(run_id)


def _item_count(result: Dict[str, Any]) -> int:
    reviews = (result.get("reviews") or {}).get("items") or []
    catalog = (result.get("catalog") or {}).get("items") or []
    return len(reviews) + len(catalog)


def _run_label(product: Dict[str, Any], run_id: str, review_count: int) -> str:
    title = str(product.get("title") or product.get("asin") or run_id)
    if len(title) > 72:
        title = title[:69] + "…"
    if review_count:
        return f"{title} · {review_count} reviews"
    short = run_id[:8] if run_id else "run"
    return f"{title} · {short}"


def _build_snapshot(result: Dict[str, Any]) -> Dict[str, Any]:
    reviews_pack = result.get("reviews") or {}
    catalog_pack = result.get("catalog") or {}
    review_items = reviews_pack.get("items") or []
    product_row = (catalog_pack.get("items") or [None])[0] or {}
    product = {
        "title": _first(product_row, "title", "name", "productName") or _first(
            review_items[0] if review_items else {}, "productTitle", "productName", "title"
        ),
        "asin": _first(product_row, "asin", "ASIN") or _first(
            review_items[0] if review_items else {}, "productAsin", "asin", "ASIN"
        ),
        "url": _first(product_row, "url", "productUrl") or _first(
            review_items[0] if review_items else {}, "productUrl", "url"
        ),
        "stars": _first(product_row, "stars", "rating", "averageRating", "productRating"),
        "review_count": _first(product_row, "reviewsCount", "reviewCount", "ratingsTotal"),
    }
    normalized = []
    histogram: Dict[str, int] = {}
    scores: List[float] = []
    for item in review_items:
        stars = _first(item, "ratingScore", "rating", "stars")
        key = str(stars) if stars not in (None, "") else "unknown"
        histogram[key] = histogram.get(key, 0) + 1
        try:
            scores.append(float(stars))
        except (TypeError, ValueError):
            pass
        normalized.append(
            {
                "title": _first(item, "reviewTitle", "title", "headline") or "",
                "text": _first(
                    item, "reviewDescription", "reviewText", "text", "content", "comment"
                )
                or "",
                "stars": stars,
                "verified": bool(item.get("isVerified") or item.get("verified")),
                "date": _first(item, "reviewedIn", "date", "reviewDate") or "",
            }
        )
    avg = round(sum(scores) / len(scores), 2) if scores else None
    return {
        "product": product,
        "scraped_review_count": len(normalized),
        "average_scraped_stars": avg,
        "star_histogram": histogram,
        "reviews": normalized,
    }


def _pack_to_result(pack: Dict[str, Any]) -> Dict[str, Any]:
    items = _flatten_items(pack.get("items") or [])
    product_meta = _product_wrapper(pack.get("items") or [])
    mode = "reviews" if _looks_like_reviews(items) else "catalog"
    result: Dict[str, Any] = {"mode": mode}
    if product_meta:
        result["catalog"] = {
            "run_id": pack.get("run_id"),
            "status": pack.get("status"),
            "dataset_id": pack.get("dataset_id"),
            "actor_id": pack.get("actor_id"),
            "items": [product_meta],
        }
    if mode == "reviews":
        result["reviews"] = {**pack, "items": items}
        if "catalog" not in result:
            heading = _product_from_reviews(items)
            if heading:
                result["catalog"] = {**pack, "items": [heading]}
    else:
        result["catalog"] = {**pack, "items": items}
    return result


def _flatten_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(items) != 1:
        return items
    row = items[0]
    for key in ("reviews", "reviewList", "items", "data"):
        nested = row.get(key)
        if isinstance(nested, list) and nested and isinstance(nested[0], dict):
            return nested
    return items


def _product_wrapper(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if len(items) != 1:
        return None
    row = items[0]
    nested = row.get("reviews")
    if isinstance(nested, list):
        return {key: value for key, value in row.items() if key != "reviews"}
    return None


def _product_from_reviews(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not items:
        return None
    first = items[0]
    title = _first(first, "productTitle", "productName", "title")
    asin = _first(first, "productAsin", "asin", "ASIN")
    url = _first(first, "productUrl", "url")
    if not title and not asin:
        return None
    return {
        "title": title,
        "asin": asin,
        "url": url,
        "stars": _first(first, "productRating", "stars", "averageRating"),
        "reviewsCount": _first(first, "productReviewsCount", "reviewsCount"),
    }


def _first(item: Dict[str, Any], *keys: str) -> Any:
    if not item:
        return None
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _looks_like_reviews(items: List[Dict[str, Any]]) -> bool:
    if not items:
        return False
    sample = items[0]
    keys = {str(key).lower() for key in sample}
    if any("review" in key for key in keys):
        return True
    return any(key in sample for key in ("ratingScore", "reviewedIn", "isVerified"))


def _status_note(status: Optional[str], run_id: str) -> str:
    if status in {"READY", "RUNNING"}:
        return f"Run {run_id} is still {status}. Refresh when it succeeds in Apify Console."
    if status and status != "SUCCEEDED":
        return f"Run {run_id} finished with status {status}."
    return f"Showing dataset from run {run_id}."


apify_amazon_service = ApifyAmazonService()
apify_amazon_service.configure()
