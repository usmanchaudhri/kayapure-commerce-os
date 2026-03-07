from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from config import settings
from services.marketing import marketing_service

class AdsRecommendation(BaseModel):
    action: str = Field(..., description="What to change.")
    rationale: str
    expected_impact: str
    priority: str

class AdsAnalysisResult(BaseModel):
    summary: str
    key_findings: List[str]
    risks: List[str]
    recommendations: List[AdsRecommendation]
    confidence: float = Field(..., ge=0, le=1)

class AdsAnalysisAgentService:
    def __init__(self):
        self.llm = ChatOpenAI(model=settings.LLM_MODEL,
                              temperature=0.7,
                              api_key=settings.OPENAI_API_KEY)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a senior Meta Ads performance analyst."           
             "Use only provided data. Do not invent metrics."
             "Recommend concrete campaign-level actions."),
            ("human",
             "Analyze this Facebook ads dataset for the last {days} days.\n"
             "Question: {question}\n\n"
             "Dataset:\n{dataset_json}")
        ])
        self.chain = self.prompt | self.llm.with_structured_output(AdsAnalysisResult)

    async def analyze(self, days: int=7, question: Optional[str] = None) -> dict[str, Any]:
        dataset = await marketing_service.get_ad_spend_history(days=days)

        # Optional: trim dataset to reduce token usage
        payload = {
            "period": dataset.get("period"),
            "currency": dataset.get("currency"),
            "total_spend": dataset.get("total_spend"),
            "avg_ctr": dataset.get("avg_ctr"),
            "avg_cpc": dataset.get("avg_cpc"),
            "daily_breakdown": dataset.get("daily_breakdown", [])[-days:],
            "campaigns": dataset.get("campaigns", [])[:50],
            "source": dataset.get("source"),
        }

        result = await self.chain.ainvoke({
            "days": days,
            "question": question or "Find waste, winners, and optimization opportunities.",
            "dataset_json": payload,
        })

        return {
            "analysis": result.model_dump(),
            "data_snapshot": payload,
        }

ads_analysis_agent_service = AdsAnalysisAgentService()
