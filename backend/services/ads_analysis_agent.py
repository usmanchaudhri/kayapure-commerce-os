from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from config import settings
from services.marketing import marketing_service


class AdsRecommendation(BaseModel):
    action: str = Field(..., description="What to change.")
    rationale: str
    expected_impact: str
    priority: str
    target_layer: str = Field(
        default="campaign",
        description="Where to act: campaign | adset | ad | creative | budget | audience",
    )
    target_id: str = Field(default="", description="Object id when known (adset/ad/campaign).")
    target_name: str = Field(default="", description="Human-readable object name when known.")


class LayerFinding(BaseModel):
    layer: str = Field(..., description="campaign | adset | ad | creative | delivery")
    name: str
    object_id: str = ""
    diagnosis: str
    evidence: str = Field(default="", description="Metric evidence supporting the diagnosis.")


class AdsAnalysisResult(BaseModel):
    summary: str
    key_findings: List[str]
    risks: List[str]
    recommendations: List[AdsRecommendation]
    confidence: float = Field(..., ge=0, le=1)


class CampaignAnalysisResult(BaseModel):
    summary: str
    root_cause: str = Field(
        ...,
        description="Primary reason this campaign under/over-performs.",
    )
    key_findings: List[str]
    layer_findings: List[LayerFinding] = Field(
        default_factory=list,
        description="Diagnoses at campaign, ad set, ad, and creative layers.",
    )
    risks: List[str]
    recommendations: List[AdsRecommendation]
    confidence: float = Field(..., ge=0, le=1)


class AdsAnalysisAgentService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.LLM_BASE_MODEL,
            temperature=0.7,
            api_key=settings.LLM_BASE_MODEL_API_KEY,
            max_retries=0,
        )

        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a senior Meta Ads performance analyst. "
                "Use only provided data. Do not invent metrics. "
                "Recommend concrete campaign-level actions.",
            ),
            (
                "human",
                "Analyze this Facebook ads dataset for the last {days} days.\n"
                "Question: {question}\n\n"
                "Dataset:\n{dataset_json}",
            ),
        ])
        self.chain = self.prompt | self.llm.with_structured_output(AdsAnalysisResult)

        self.campaign_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a senior Meta Ads forensic analyst specializing in single-campaign deep dives. "
                "Use only provided data. Do not invent metrics or creatives. "
                "Explain WHY the campaign is or is not performing: delivery, audience, creative fatigue, "
                "budget/bid, offer/landing fit, and learning-phase issues. "
                "Always drill from campaign → ad sets → ads/creatives. "
                "Name specific ad sets and ads when recommending pauses, scales, or creative refreshes. "
                "If data is thin, say so and lower confidence.",
            ),
            (
                "human",
                "Deep-analyze this Meta campaign for {days} days ({period_start} → {period_end}).\n"
                "Account: {account_name} ({account_id})\n"
                "Campaign: {campaign_name} ({campaign_id})\n"
                "Question: {question}\n\n"
                "Dataset (campaign totals, daily trend, ad sets, ads, creatives):\n{dataset_json}",
            ),
        ])
        self.campaign_chain = self.campaign_prompt | self.llm.with_structured_output(
            CampaignAnalysisResult
        )

    async def analyze(
        self,
        days: int = 7,
        question: Optional[str] = None,
        account_id: Optional[str] = None,
        account_name: Optional[str] = None,
    ) -> dict[str, Any]:
        dataset = await marketing_service.get_ad_spend_history(
            days=days, account_id=account_id
        )

        if account_id:
            dataset["requested_account_id"] = account_id
        if account_name:
            dataset["requested_account_name"] = account_name

        campaigns = dataset.get("campaigns", [])
        if account_id:
            campaigns = [c for c in campaigns if c.get("account_id") == account_id]
        payload = {
            "period": dataset.get("period"),
            "currency": dataset.get("currency"),
            "total_spend": dataset.get("total_spend"),
            "avg_ctr": dataset.get("avg_ctr"),
            "avg_cpc": dataset.get("avg_cpc"),
            "daily_breakdown": dataset.get("daily_breakdown", [])[-days:],
            "campaigns": campaigns[:50],
            "source": dataset.get("source"),
            "scoped_account_id": account_id,
            "scoped_account_name": account_name,
        }

        result = await self.chain.ainvoke({
            "days": days,
            "question": question or "Find waste, winners, and optimization opportunities.",
            "dataset_json": payload,
        })

        return {
            "analysis": result.model_dump(),
            "data_snapshot": payload,
            "report_scope": "account",
        }

    async def analyze_campaign(
        self,
        *,
        account_id: str,
        campaign_id: str,
        since: str,
        until: str,
        account_name: Optional[str] = None,
        campaign_name: Optional[str] = None,
        currency: str = "USD",
        question: Optional[str] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Deep campaign forensic analysis (ad sets + ads + creatives)."""
        fb = marketing_service._fb_client
        if not fb:
            raise RuntimeError("Facebook Ads client is not configured.")

        dataset = await fb.get_campaign_deep_dataset(
            account_id,
            campaign_id,
            since=since,
            until=until,
            account_name=account_name or "",
            campaign_name=campaign_name or "",
            currency=currency,
            force_refresh=force_refresh,
        )

        campaign = dataset.get("campaign") or {}
        period = dataset.get("period") or {}
        days = max(
            1,
            len(dataset.get("daily_breakdown") or [])
            or _days_between(since, until),
        )

        # Compact payload for the LLM (already trimmed in the client)
        payload = {
            "scope": "campaign",
            "period": period,
            "currency": dataset.get("currency", currency),
            "account_id": account_id,
            "account_name": account_name or dataset.get("account_name"),
            "campaign": campaign,
            "campaign_totals": dataset.get("campaign_totals"),
            "total_spend": dataset.get("total_spend"),
            "avg_ctr": dataset.get("avg_ctr"),
            "avg_cpc": dataset.get("avg_cpc"),
            "daily_breakdown": dataset.get("daily_breakdown"),
            "adsets_count": dataset.get("adsets_count"),
            "adsets": dataset.get("adsets"),
            "ads_count": dataset.get("ads_count"),
            "ads": dataset.get("ads"),
            "weak_ads_by_ctr": dataset.get("weak_ads_by_ctr"),
            "source": dataset.get("source"),
        }

        default_q = (
            f"Why is campaign '{campaign.get('name') or campaign_name}' performing the way it is? "
            "Identify root causes at ad set and ad/creative level. "
            "Recommend specific pauses, scales, creative refreshes, and budget/bid changes."
        )
        result = await self.campaign_chain.ainvoke({
            "days": days,
            "period_start": period.get("start", since),
            "period_end": period.get("end", until),
            "account_name": account_name or dataset.get("account_name") or account_id,
            "account_id": account_id,
            "campaign_name": campaign.get("name") or campaign_name or campaign_id,
            "campaign_id": campaign_id,
            "question": question or default_q,
            "dataset_json": payload,
        })

        return {
            "analysis": result.model_dump(),
            "data_snapshot": payload,
            "report_scope": "campaign",
        }


def _days_between(since: str, until: str) -> int:
    try:
        from datetime import datetime

        a = datetime.strptime(since, "%Y-%m-%d")
        b = datetime.strptime(until, "%Y-%m-%d")
        return max(1, (b - a).days + 1)
    except Exception:
        return 7


ads_analysis_agent_service = AdsAnalysisAgentService()
