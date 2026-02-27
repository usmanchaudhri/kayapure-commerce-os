"""
KayaPure Commerce OS - Pydantic API Models
Request/Response schemas for the REST API.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


# --- Enums ---
class ActionStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class PriorityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- SKU Models ---
class SKUBase(BaseModel):
    name: str
    sku_code: str
    unit_cogs: float
    lab_testing_cost: float = 0.0
    current_stock: int = 0
    daily_sales_velocity: float = 0.0
    current_price: float = 0.0
    competitor_price: Optional[float] = None
    shipping_eta_days: int = 0


class SKUCreate(SKUBase):
    pass


class SKUResponse(SKUBase):
    id: int
    last_updated: Optional[datetime] = None
    days_of_stock: Optional[float] = None
    contribution_margin: Optional[float] = None

    class Config:
        from_attributes = True


# --- Daily Metrics Models ---
class DailyMetricBase(BaseModel):
    revenue: float = 0.0
    ad_spend: float = 0.0
    shipping_cost: float = 0.0
    cogs_total: float = 0.0
    net_profit: float = 0.0
    margin_percent: float = 0.0
    orders_count: int = 0
    channel: str = "shopify"


class DailyMetricCreate(DailyMetricBase):
    pass


class DailyMetricResponse(DailyMetricBase):
    id: int
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Action Proposal Models ---
class ActionProposalBase(BaseModel):
    action_type: str
    title: str
    description: str
    reasoning: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    priority: str = "medium"
    sku_id: Optional[int] = None


class ActionProposalCreate(ActionProposalBase):
    pass


class ActionProposalResponse(ActionProposalBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: ActionStatusEnum = ActionStatusEnum.PENDING
    result: Optional[Dict[str, Any]] = None
    vm_session_id: Optional[str] = None

    class Config:
        from_attributes = True


class ActionApproval(BaseModel):
    action: str = Field(..., pattern="^(approve|deny)$")
    comment: Optional[str] = None


# --- VM Audit Trail Models ---
class VMAuditResponse(BaseModel):
    id: int
    session_id: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    action_proposal_id: Optional[int] = None
    vm_boot_time_ms: int = 0
    code_executed: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    status: str = "booting"
    hardware_signature: Optional[str] = None
    error_log: Optional[str] = None

    class Config:
        from_attributes = True


# --- P&L Analysis Models ---
class PnLSummary(BaseModel):
    total_revenue: float
    total_cogs: float
    total_ad_spend: float
    total_shipping: float
    gross_profit: float
    net_profit: float
    contribution_margin: float
    period: str


# --- Agent State Models ---
class AgentLogEntry(BaseModel):
    timestamp: datetime
    node: str
    message: str
    data: Optional[Dict[str, Any]] = None


class GraphState(BaseModel):
    current_node: str
    thread_id: str
    is_paused: bool = False
    pending_actions: int = 0
    last_updated: Optional[datetime] = None


# --- Diagnostic Storefront Models ---
class HealthGoalRequest(BaseModel):
    goals: List[str] = Field(..., description="List of health goals")
    age: Optional[int] = None
    gender: Optional[str] = None
    existing_conditions: Optional[List[str]] = None
    current_supplements: Optional[List[str]] = None


class SupplementRecommendation(BaseModel):
    product_name: str
    dosage: str
    timing: str
    scientific_basis: str
    confidence_score: float


class ProtocolResponse(BaseModel):
    protocol_name: str
    recommendations: List[SupplementRecommendation]
    disclaimer: str
    sources: List[str]


# --- WebSocket Models ---
class WSMessage(BaseModel):
    type: str  # "agent_log", "action_update", "vm_telemetry", "pnl_update"
    data: Dict[str, Any]
