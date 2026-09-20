"""
KayaPure Commerce OS - Database Schemas (SQLAlchemy ORM Models)
Defines: skus, daily_metrics, vm_audit_trail, action_proposals, checkpoints
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    Boolean,
    Enum as SQLEnum,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.database import Base
import enum


class SKU(Base):
    """Product SKU table - tracks inventory and cost data."""

    __tablename__ = "skus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    sku_code = Column(String(50), unique=True, nullable=False)
    unit_cogs = Column(Float, nullable=False, comment="Cost of Goods Sold per unit")
    lab_testing_cost = Column(Float, default=0.0, comment="Lab/testing cost per unit")
    current_stock = Column(Integer, default=0)
    daily_sales_velocity = Column(Float, default=0.0, comment="Average daily units sold")
    current_price = Column(Float, default=0.0)
    competitor_price = Column(Float, nullable=True)
    shipping_eta_days = Column(Integer, default=0, comment="Days until next shipment arrives")
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SKU(id={self.id}, name='{self.name}', stock={self.current_stock})>"


class DailyMetric(Base):
    """Daily business metrics for P&L analysis."""

    __tablename__ = "daily_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, server_default=func.now())
    revenue = Column(Float, default=0.0)
    ad_spend = Column(Float, default=0.0)
    shipping_cost = Column(Float, default=0.0)
    cogs_total = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    margin_percent = Column(Float, default=0.0)
    orders_count = Column(Integer, default=0)
    channel = Column(String(50), default="shopify", comment="Sales channel")

    def __repr__(self):
        return f"<DailyMetric(date={self.timestamp}, profit={self.net_profit})>"


class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionProposal(Base):
    """Agent-proposed actions awaiting human approval."""

    __tablename__ = "action_proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    action_type = Column(String(100), nullable=False, comment="e.g., price_change, budget_reduction")
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=True, comment="LLM reasoning chain")
    parameters = Column(JSON, nullable=True, comment="Action parameters as JSON")
    status = Column(
        SQLEnum(ActionStatus),
        default=ActionStatus.PENDING,
        nullable=False,
    )
    priority = Column(String(20), default="medium")
    sku_id = Column(Integer, nullable=True)
    result = Column(JSON, nullable=True, comment="Execution result")
    vm_session_id = Column(String(100), nullable=True)

    def __repr__(self):
        return f"<ActionProposal(id={self.id}, type='{self.action_type}', status='{self.status}')>"


class VMAuditTrail(Base):
    """Audit log for every Firecracker microVM session."""

    __tablename__ = "vm_audit_trail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    action_proposal_id = Column(Integer, nullable=True)
    vm_boot_time_ms = Column(Integer, default=0)
    payload_hash = Column(String(64), nullable=True, comment="SHA-256 hash of encrypted payload")
    code_executed = Column(Text, nullable=True, comment="The specific code/command executed")
    execution_result = Column(JSON, nullable=True)
    status = Column(String(20), default="booting")
    hardware_signature = Column(String(256), nullable=True, comment="Hardware-signed result hash")
    error_log = Column(Text, nullable=True)

    def __repr__(self):
        return f"<VMAuditTrail(session={self.session_id}, status='{self.status}')>"


class Checkpoint(Base):
    """LangGraph state persistence table."""

    __tablename__ = "checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String(100), nullable=False)
    checkpoint_id = Column(String(100), nullable=False)
    parent_checkpoint_id = Column(String(100), nullable=True)
    checkpoint_data = Column(JSON, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Checkpoint(thread={self.thread_id}, id={self.checkpoint_id})>"


class AdsAnalysisReport(Base):
    """Persisted LLM ad performance reports."""

    __tablename__ = "ads_analysis_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(100), nullable=False)
    account_name = Column(String(255), nullable=False, default="")
    report_type = Column(String(50), nullable=False, default="generate")
    days = Column(Integer, nullable=False, default=30)
    question = Column(Text, nullable=True)
    analysis_json = Column(JSON, nullable=False)
    data_snapshot_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ApifyActorRun(Base):
    """Persisted Apify Actor dataset plus optional review analysis."""

    __tablename__ = "apify_actor_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(100), unique=True, nullable=False)
    actor_id = Column(String(200), nullable=False, default="")
    dataset_id = Column(String(100), nullable=False, default="")
    status = Column(String(40), nullable=False, default="")
    source = Column(String(40), nullable=False, default="manual")
    mode = Column(String(40), nullable=False, default="reviews")
    label = Column(String(500), nullable=False, default="")
    product_title = Column(String(500), nullable=True)
    product_asin = Column(String(20), nullable=True)
    product_url = Column(Text, nullable=True)
    raw_json = Column(JSON, nullable=False)
    snapshot_json = Column(JSON, nullable=True)
    analysis_json = Column(JSON, nullable=True)
    analysis_error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ActionOutcome(Base):
    """Recorded result of an approved action execution."""

    __tablename__ = "action_outcomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_proposal_id = Column(Integer, nullable=False)
    outcome_type = Column(String(50), nullable=False, default="execution")
    success = Column(Boolean, nullable=False, default=False)
    metrics_json = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    recorded_at = Column(DateTime, server_default=func.now())


class ProfitLeakAnalysisRun(Base):
    """A single profit leak scan execution."""

    __tablename__ = "profit_leak_analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(100), nullable=False, default="")
    account_name = Column(String(255), nullable=False, default="")
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    analysis_type = Column(String(50), nullable=False, default="profit_leak_scan")
    prompt_version = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    input_data_hash = Column(String(64), nullable=True)
    status = Column(String(30), nullable=False, default="completed")
    summary_json = Column(JSON, nullable=False, default=dict)
    executive_summary = Column(Text, nullable=True)
    scan_params_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now())

    findings = relationship(
        "ProfitLeakFinding",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )


class ProfitLeakFinding(Base):
    """Structured profit leak finding with deterministic + LLM layers."""

    __tablename__ = "profit_leak_findings"

    id = Column(String(36), primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("profit_leak_analysis_runs.id"), nullable=False)
    account_id = Column(String(100), nullable=False, default="")
    account_name = Column(String(255), nullable=False, default="")
    category = Column(String(80), nullable=False)
    severity = Column(String(20), nullable=False)
    title = Column(Text, nullable=False)
    diagnosis = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    llm_explanation = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    estimated_impact_min = Column(Float, nullable=False, default=0.0)
    estimated_impact_max = Column(Float, nullable=False, default=0.0)
    entity_type = Column(String(40), nullable=False, default="")
    entity_id = Column(String(100), nullable=False, default="")
    entity_name = Column(String(255), nullable=False, default="")
    status = Column(String(30), nullable=False, default="open")
    structured_output = Column(JSON, nullable=False, default=dict)
    experiment_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now())

    analysis_run = relationship("ProfitLeakAnalysisRun", back_populates="findings")
    evidence_rows = relationship(
        "ProfitLeakFindingEvidence",
        back_populates="finding",
        cascade="all, delete-orphan",
    )


class ProfitLeakFindingEvidence(Base):
    """Metric evidence backing a profit leak finding."""

    __tablename__ = "profit_leak_finding_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    finding_id = Column(String(36), ForeignKey("profit_leak_findings.id"), nullable=False)
    evidence_type = Column(String(40), nullable=False, default="metric")
    metric_name = Column(String(80), nullable=False)
    observed_value = Column(Text, nullable=True)
    comparison_value = Column(Text, nullable=True)
    comparison_label = Column(String(120), nullable=True)
    entity_type = Column(String(40), nullable=True)
    entity_id = Column(String(100), nullable=True)
    evidence_json = Column(JSON, nullable=False, default=dict)

    finding = relationship("ProfitLeakFinding", back_populates="evidence_rows")


class PostExOrder(Base):
    """Synced PostEx shipment order (List Orders + Payment Status)."""

    __tablename__ = "postex_orders"

    tracking_number = Column(String(64), primary_key=True)
    order_ref_number = Column(String(255), nullable=True, default="")
    transaction_status = Column(String(100), nullable=True, default="")
    transaction_date = Column(DateTime, nullable=True)
    order_delivery_date = Column(DateTime, nullable=True)
    order_pickup_date = Column(DateTime, nullable=True)

    invoice_payment = Column(Float, nullable=False, default=0.0)
    upfront_payment = Column(Float, nullable=False, default=0.0)
    reserve_payment = Column(Float, nullable=False, default=0.0)
    balance_payment = Column(Float, nullable=False, default=0.0)
    transaction_fee = Column(Float, nullable=False, default=0.0)
    transaction_tax = Column(Float, nullable=False, default=0.0)

    settle = Column(Boolean, nullable=True)
    settlement_date = Column(DateTime, nullable=True)
    cpr1 = Column(String(100), nullable=True)
    cpr1_date = Column(DateTime, nullable=True)
    cpr2 = Column(String(100), nullable=True)
    cpr2_date = Column(DateTime, nullable=True)

    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    city_name = Column(String(100), nullable=True)
    merchant_name = Column(String(255), nullable=True)
    items = Column(Integer, nullable=True)

    raw_json = Column(JSON, nullable=False, default=dict)
    synced_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PostExCprReceipt(Base):
    """Cash Payment Receipt numbers linked to trackings."""

    __tablename__ = "postex_cpr_receipts"
    __table_args__ = (
        UniqueConstraint(
            "cpr_number",
            "tracking_number",
            name="uq_postex_cpr_tracking",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    cpr_number = Column(String(100), nullable=False)
    tracking_number = Column(String(64), nullable=False)
    cpr_type = Column(String(40), nullable=False, default="")
    payment_date = Column(DateTime, nullable=True)
    net_estimate = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PostExSyncState(Base):
    """Singleton sync cursor / status for PostEx order backfill."""

    __tablename__ = "postex_sync_state"

    id = Column(Integer, primary_key=True, autoincrement=False, default=1)
    backfill_complete = Column(Boolean, nullable=False, default=False)
    backfill_cursor_date = Column(String(10), nullable=True, comment="YYYY-MM-DD")
    last_incremental_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    orders_upserted = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="idle")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
