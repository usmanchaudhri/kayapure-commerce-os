"""LLM analysis of Amazon review snapshots from Apify."""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import settings
from utils.logging_config import get_logger

logger = get_logger("reviews_analysis")


class ReviewTheme(BaseModel):
    theme: str = Field(..., description="Short theme name.")
    sentiment: str = Field(..., description="positive, negative, or mixed.")
    evidence: str = Field(..., description="Brief evidence from the reviews.")


class ReviewRecommendation(BaseModel):
    action: str = Field(..., description="What to change on the listing, product, or ads.")
    rationale: str
    expected_impact: str
    priority: str


class ReviewAnalysisResult(BaseModel):
    summary: str
    overall_sentiment: str
    key_findings: List[str]
    themes: List[ReviewTheme]
    complaints: List[str]
    praise: List[str]
    risks: List[str]
    recommendations: List[ReviewRecommendation]
    confidence: float = Field(..., ge=0, le=1)


class ReviewsAnalysisAgentService:
    def __init__(self) -> None:
        self.llm = ChatGoogleGenerativeAI(
            model=settings.LLM_BASE_MODEL,
            temperature=0.3,
            api_key=settings.LLM_BASE_MODEL_API_KEY,
            max_retries=0,
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a senior ecommerce analyst reviewing Amazon customer feedback. "
                    "Use only the provided reviews. Do not invent quotes, ratings, or counts. "
                    "Focus on what buyers like, what they complain about, and concrete listing or product actions.",
                ),
                (
                    "human",
                    "Analyze these Amazon reviews.\n"
                    "Question: {question}\n\n"
                    "Snapshot:\n{dataset_json}",
                ),
            ]
        )
        self.chain = self.prompt | self.llm.with_structured_output(ReviewAnalysisResult)

    @property
    def is_ready(self) -> bool:
        return bool(settings.LLM_BASE_MODEL_API_KEY)

    async def analyze(
        self,
        snapshot: Dict[str, Any],
        question: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_ready:
            raise RuntimeError("LLM_BASE_MODEL_API_KEY is not set.")
        payload = _trim_snapshot(snapshot)
        result = await self.chain.ainvoke(
            {
                "question": question
                or "Summarize sentiment, recurring complaints, praise, and actions to improve conversion.",
                "dataset_json": payload,
            }
        )
        return result.model_dump()


def _trim_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    reviews = list(snapshot.get("reviews") or [])[:120]
    return {
        "product": snapshot.get("product") or {},
        "scraped_review_count": snapshot.get("scraped_review_count"),
        "average_scraped_stars": snapshot.get("average_scraped_stars"),
        "star_histogram": snapshot.get("star_histogram") or {},
        "reviews": reviews,
    }


reviews_analysis_agent_service = ReviewsAnalysisAgentService()
