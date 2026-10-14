"""PubMed / NCBI E-utilities helpers for evidence gathering."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

import httpx

from config import settings
from utils.logging_config import get_logger

logger = get_logger("ingredient_research")

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _ncbi_params(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build common NCBI query parameters including optional API key.

    Args:
        extra: Additional query parameters.

    Returns:
        Merged parameter dictionary.
    """
    params: Dict[str, Any] = {"tool": "kayapure_ingredient_research", "email": "dev@kayapure.com"}
    if settings.NCBI_API_KEY:
        params["api_key"] = settings.NCBI_API_KEY
    if extra:
        params.update(extra)
    return params


def search_pubmed(
    query: str,
    retmax: int = 5,
    ingredient: str = "",
) -> List[Dict[str, Any]]:
    """Search PubMed and return lightweight citation dicts.

    Args:
        query: Free-text PubMed query.
        retmax: Maximum number of PMIDs to fetch details for.
        ingredient: Optional ingredient label stored on each result.

    Returns:
        List of citation dictionaries with pmid/title/url/snippet/year.
    """
    q = (query or "").strip()
    if not q:
        return []

    try:
        with httpx.Client(timeout=30.0) as client:
            search_resp = client.get(
                f"{EUTILS_BASE}/esearch.fcgi",
                params=_ncbi_params(
                    {
                        "db": "pubmed",
                        "term": q,
                        "retmax": max(1, min(int(retmax), 10)),
                        "retmode": "json",
                        "sort": "relevance",
                    }
                ),
            )
            search_resp.raise_for_status()
            id_list = (
                search_resp.json()
                .get("esearchresult", {})
                .get("idlist", [])
            )
            if not id_list:
                return []

            fetch_resp = client.get(
                f"{EUTILS_BASE}/efetch.fcgi",
                params=_ncbi_params(
                    {
                        "db": "pubmed",
                        "id": ",".join(id_list),
                        "retmode": "xml",
                    }
                ),
            )
            fetch_resp.raise_for_status()
            return _parse_pubmed_xml(
                fetch_resp.text,
                ingredient=ingredient,
            )
    except Exception as exc:  # noqa: BLE001 - tool boundary
        logger.warning("PubMed search failed for query=%s: %s", q, exc)
        return [{"error": f"PubMed search failed: {exc}", "query": q}]


def _parse_pubmed_xml(xml_text: str, ingredient: str = "") -> List[Dict[str, Any]]:
    """Parse PubMed efetch XML into citation dictionaries.

    Args:
        xml_text: Raw efetch XML payload.
        ingredient: Optional ingredient label attached to each citation.

    Returns:
        Parsed citation list.
    """
    root = ElementTree.fromstring(xml_text)
    results: List[Dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = (article.findtext(".//PMID") or "").strip()
        title = (article.findtext(".//ArticleTitle") or "").strip()
        abstract_parts = [
            (node.text or "").strip()
            for node in article.findall(".//Abstract/AbstractText")
            if (node.text or "").strip()
        ]
        year = (
            article.findtext(".//JournalIssue/PubDate/Year")
            or article.findtext(".//ArticleDate/Year")
            or ""
        )
        snippet = " ".join(abstract_parts)[:500]
        results.append(
            {
                "title": title or f"PMID {pmid}",
                "pmid": pmid,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "year": year or None,
                "snippet": snippet,
                "source": "pubmed",
                "ingredient": ingredient,
            }
        )
    return results


def search_ingredient_evidence(
    ingredient: str,
    goal: str = "",
    retmax: int = 4,
) -> List[Dict[str, Any]]:
    """Search PubMed for an ingredient, optionally scoped to a health goal.

    Args:
        ingredient: Ingredient name.
        goal: Optional outcome keywords.
        retmax: Max papers to return.

    Returns:
        Citation dictionaries (or error dicts).
    """
    parts = [ingredient, "supplement OR extract OR herbal OR nutraceutical"]
    if goal:
        parts.append(goal)
    query = " AND ".join(f"({p})" for p in parts if p)
    return search_pubmed(query=query, retmax=retmax, ingredient=ingredient)
