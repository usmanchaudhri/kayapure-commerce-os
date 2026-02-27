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
)
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
