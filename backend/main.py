"""
KayaPure Autonomous Commerce OS - Main FastAPI Application
Control Plane: Manages reasoning, P&L analysis, state, and WebSocket communication.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from config import settings
from models.database import Base, engine, get_db, SessionLocal
from models.schemas import (
    SKU,
    DailyMetric,
    ActionProposal,
    VMAuditTrail,
    ActionStatus,
)
from models.api_models import (
    SKUResponse,
    SKUCreate,
    DailyMetricResponse,
    DailyMetricCreate,
    ActionProposalResponse,
    ActionProposalCreate,
    ActionApproval,
    VMAuditResponse,
    PnLSummary,
    GraphState,
    HealthGoalRequest,
    ProtocolResponse,
    SupplementRecommendation,
)
from services.firecracker_manager import firecracker_manager
from services.commerce import commerce_service
from services.marketing import marketing_service
from services.logistics import logistics_service
from services.facebook_ads_client import FacebookAdsClient
from graph.workflow import commerce_graph, firecracker_executor_node, CommerceState

# ============================================
# Initialize Structured Logging & LangSmith
# ============================================
from utils.logging_config import setup_logging, setup_langsmith_tracing, get_logger, set_correlation_id
from utils.api_middleware import RequestLoggingMiddleware

# Initialize logging FIRST — before any other logger is used
setup_logging(log_dir="logs")

# Setup LangSmith tracing (no-op if LANGSMITH_API_KEY not set)
langsmith_enabled = setup_langsmith_tracing()

logger = get_logger("api")
startup_logger = get_logger("startup")


# ============================================
# WebSocket Connection Manager
# ============================================
class ConnectionManager:
    """Manages WebSocket connections for real-time agent logs and telemetry."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected (total: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected (total: {len(self.active_connections)})")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


ws_manager = ConnectionManager()


# ============================================
# Application Lifecycle
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    startup_logger.info("=" * 60)
    startup_logger.info("KayaPure Commerce OS starting up...")
    startup_logger.info(f"LangSmith tracing: {'ENABLED' if langsmith_enabled else 'DISABLED'}")
    startup_logger.info(f"Facebook Ads API enabled: {settings.FACEBOOK_ADS_ENABLED}")
    startup_logger.info(f"Firecracker mock: {settings.FIRECRACKER_MOCK}")
    startup_logger.info("=" * 60)

    # Register VM telemetry callback
    async def telemetry_callback(event_type: str, data: dict):
        await ws_manager.broadcast({
            "type": "vm_telemetry",
            "event": event_type,
            "data": data,
        })

    firecracker_manager.register_telemetry_callback(telemetry_callback)

    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    startup_logger.info("Database tables verified")

    # Initialize Facebook Ads API client
    fb_client = None
    if settings.facebook_ads_ready:
        startup_logger.info("Facebook Ads API enabled — connecting to Graph API...")
        fb_client = FacebookAdsClient(
            access_token=settings.FACEBOOK_ACCESS_TOKEN,
            account_id=settings.META_ADS_ACCOUNT_ID,
        )
        try:
            account_info = await fb_client.initialize()
            marketing_service.configure(
                fb_client=fb_client,
                meta_account_id=settings.META_ADS_ACCOUNT_ID,
            )
            startup_logger.info(
                f"MarketingService configured with live Facebook Ads API — "
                f"account: {account_info.get('name', 'unknown')}",
                extra={"account_info": account_info},
            )
        except Exception as e:
            startup_logger.warning(
                f"Facebook Ads API init failed — MarketingService using mock data: {e}",
                extra={"error": str(e)},
            )
            fb_client = None
    else:
        startup_logger.info("Facebook Ads API disabled or not configured — MarketingService using mock data")

    startup_logger.info("KayaPure Commerce OS ready to serve requests")

    yield

    # Shutdown: close Facebook Ads client
    startup_logger.info("Shutting down — closing connections...")
    if fb_client:
        await fb_client.close()
    startup_logger.info("Shutdown complete")


# ============================================
# FastAPI App
# ============================================
app = FastAPI(
    title="KayaPure Autonomous Commerce OS",
    description="Agentic Commerce Platform with Firecracker Isolation",
    version="1.0.0",
    lifespan=lifespan,
)

# Add request logging middleware (must be added before CORS)
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)


# ============================================
# Health & Status
# ============================================
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "KayaPure Commerce OS",
        "version": "1.0.0",
        "langsmith_tracing": langsmith_enabled,
        "facebook_ads_enabled": settings.FACEBOOK_ADS_ENABLED,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================
# Feature Flags — Data Source Control
# ============================================
def source_disabled_response(source_name: str):
    """Standard response for disabled data sources."""
    return {
        "enabled": False,
        "source": source_name,
        "message": f"{source_name} data source is not connected. Enable it by adding '{source_name}' to ENABLED_SOURCES in your .env file.",
        "data": None,
    }


@app.get("/api/feature-flags")
async def get_feature_flags():
    """Return which data sources are enabled/disabled for the frontend."""
    all_sources = ["marketing", "commerce", "logistics", "dwh", "vm", "diagnostic"]
    return {
        "enabled_sources": list(settings.enabled_sources),
        "sources": {
            source: {
                "enabled": settings.is_source_enabled(source),
                "label": {
                    "marketing": "Marketing (Meta Ads)",
                    "commerce": "Commerce (Shopify)",
                    "logistics": "Logistics (Flexport)",
                    "dwh": "Data Warehouse (PostgreSQL)",
                    "vm": "VM Telemetry (Firecracker)",
                    "diagnostic": "Diagnostic Storefront",
                }.get(source, source.title()),
            }
            for source in all_sources
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================
# Facebook Ads Status & Diagnostics
# ============================================
@app.get("/api/facebook-ads/status")
async def facebook_ads_status():
    """Check Facebook Ads API connection status and marketing service mode."""
    return {
        "facebook_ads_enabled": settings.FACEBOOK_ADS_ENABLED,
        "meta_ads": {
            "configured": settings.facebook_ads_ready,
            "connected": marketing_service._use_facebook,
            "account_id": settings.META_ADS_ACCOUNT_ID[:8] + "..." if settings.META_ADS_ACCOUNT_ID else "not set",
            "api_version": "v21.0",
        },
        "marketing_service_mode": "facebook_api" if marketing_service._use_facebook else "mock",
        "langsmith_tracing": langsmith_enabled,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/facebook-ads/total-spend")
async def total_spend_all_accounts(
    since: str = Query(default="2025-01-01", description="Start date (YYYY-MM-DD)"),
    until: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD), defaults to today"),
):
    """
    Fetch total ad spend across ALL ad accounts from `since` to `until`.
    Discovers all accounts accessible by the access token and aggregates spend.
    """
    if not marketing_service._use_facebook or not marketing_service._fb_client:
        return {"error": "Facebook Ads client not configured", "enabled": False}

    try:
        result = await marketing_service._fb_client.get_total_spend_all_accounts(
            since=since, until=until
        )
        return result
    except Exception as e:
        logger.error(f"Failed to fetch total spend: {e}")
        return {"error": str(e)}


# ============================================
# Logs Endpoint — view structured logs from the dashboard
# ============================================
@app.get("/api/logs")
async def get_logs(
    component: Optional[str] = Query(default=None, description="Filter by component: facebook_ads, agent, api"),
    level: Optional[str] = Query(default=None, description="Filter by level: DEBUG, INFO, WARNING, ERROR"),
    limit: int = Query(default=100, le=1000),
    correlation_id: Optional[str] = Query(default=None, description="Filter by correlation ID"),
):
    """
    Read structured JSON logs from the log files.
    Useful for debugging from the dashboard without SSH access.
    """
    import os

    # Map component to log file
    file_map = {
        "facebook_ads": "logs/facebook_ads.log",
        "agent": "logs/agent.log",
        "api": "logs/api.log",
        None: "logs/kayapure.log",
    }

    log_file = file_map.get(component, "logs/kayapure.log")

    if not os.path.exists(log_file):
        return {"logs": [], "file": log_file, "message": "Log file not found"}

    logs = []
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()

        # Read from the end (newest first)
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)

                # Apply filters
                if level and entry.get("level") != level.upper():
                    continue
                if correlation_id and entry.get("correlation_id") != correlation_id:
                    continue

                logs.append(entry)

                if len(logs) >= limit:
                    break
            except json.JSONDecodeError:
                continue

    except Exception as e:
        return {"logs": [], "file": log_file, "error": str(e)}

    return {
        "logs": logs,
        "file": log_file,
        "count": len(logs),
        "total_lines": len(lines) if 'lines' in dir() else 0,
    }


# ============================================
# SKU Endpoints
# ============================================
@app.get("/api/skus")
def list_skus(db: Session = Depends(get_db)):
    """List all SKUs with computed metrics."""
    if not settings.is_source_enabled("dwh"):
        return source_disabled_response("dwh")
    skus = db.query(SKU).all()
    result = []
    for sku in skus:
        sku_dict = {
            "id": sku.id,
            "name": sku.name,
            "sku_code": sku.sku_code,
            "unit_cogs": sku.unit_cogs,
            "lab_testing_cost": sku.lab_testing_cost,
            "current_stock": sku.current_stock,
            "daily_sales_velocity": sku.daily_sales_velocity,
            "current_price": sku.current_price,
            "competitor_price": sku.competitor_price,
            "shipping_eta_days": sku.shipping_eta_days,
            "last_updated": sku.last_updated,
            "days_of_stock": round(sku.current_stock / max(sku.daily_sales_velocity, 1), 1),
            "contribution_margin": round(
                ((sku.current_price - sku.unit_cogs - sku.lab_testing_cost) / max(sku.current_price, 1)) * 100, 2
            ),
        }
        result.append(SKUResponse(**sku_dict))
    return result


@app.post("/api/skus")
def create_sku(sku_data: SKUCreate, db: Session = Depends(get_db)):
    """Create a new SKU."""
    if not settings.is_source_enabled("dwh"):
        return source_disabled_response("dwh")
    sku = SKU(**sku_data.model_dump())
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku


@app.get("/api/skus/{sku_id}")
def get_sku(sku_id: int, db: Session = Depends(get_db)):
    """Get a specific SKU by ID."""
    if not settings.is_source_enabled("dwh"):
        return source_disabled_response("dwh")
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    return sku


# ============================================
# Daily Metrics / P&L Endpoints
# ============================================
@app.get("/api/metrics")
def list_metrics(
    limit: int = Query(default=30, le=365),
    channel: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List daily metrics, ordered by most recent. Always available if metrics exist in the database."""
    query = db.query(DailyMetric).order_by(desc(DailyMetric.timestamp))
    if channel:
        query = query.filter(DailyMetric.channel == channel)
    return query.limit(limit).all()


@app.get("/api/metrics/pnl-summary")
def get_pnl_summary(days: int = Query(default=7, le=90), db: Session = Depends(get_db)):
    """Get P&L summary for the specified period. Always available if metrics exist in the database."""
    metrics = (
        db.query(DailyMetric)
        .order_by(desc(DailyMetric.timestamp))
        .limit(days)
        .all()
    )
    if not metrics:
        raise HTTPException(status_code=404, detail="No metrics found")

    total_revenue = sum(m.revenue for m in metrics)
    total_cogs = sum(m.cogs_total for m in metrics)
    total_ad_spend = sum(m.ad_spend for m in metrics)
    total_shipping = sum(m.shipping_cost for m in metrics)
    gross_profit = total_revenue - total_cogs
    net_profit = gross_profit - total_ad_spend - total_shipping
    contribution_margin = (net_profit / max(total_revenue, 1)) * 100

    return PnLSummary(
        total_revenue=round(total_revenue, 2),
        total_cogs=round(total_cogs, 2),
        total_ad_spend=round(total_ad_spend, 2),
        total_shipping=round(total_shipping, 2),
        gross_profit=round(gross_profit, 2),
        net_profit=round(net_profit, 2),
        contribution_margin=round(contribution_margin, 2),
        period=f"last_{days}_days",
    )


# ============================================
# Action Proposals (The Action Queue)
# ============================================
@app.get("/api/actions", response_model=List[ActionProposalResponse])
def list_actions(
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """List action proposals, optionally filtered by status."""
    query = db.query(ActionProposal).order_by(desc(ActionProposal.created_at))
    if status:
        query = query.filter(ActionProposal.status == status)
    return query.limit(limit).all()


@app.get("/api/actions/{action_id}", response_model=ActionProposalResponse)
def get_action(action_id: int, db: Session = Depends(get_db)):
    """Get a specific action proposal."""
    action = db.query(ActionProposal).filter(ActionProposal.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@app.post("/api/actions/{action_id}/decide")
async def decide_action(action_id: int, decision: ActionApproval, db: Session = Depends(get_db)):
    """Approve or deny an action proposal. Triggers Firecracker execution on approval."""
    action_logger = get_logger("agent")
    action_logger.info(
        f"Action decision received: action_id={action_id}, decision={decision.action}",
        extra={"action_id": action_id, "decision": decision.action},
    )

    action = db.query(ActionProposal).filter(ActionProposal.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != ActionStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Action is already {action.status}")

    if decision.action == "deny":
        action.status = ActionStatus.DENIED
        db.commit()
        action_logger.info(f"Action {action_id} DENIED", extra={"action_id": action_id})
        await ws_manager.broadcast({
            "type": "action_update",
            "data": {"id": action.id, "status": "denied", "comment": decision.comment},
        })
        return {"status": "denied", "action_id": action.id}

    # Approve and execute
    action.status = ActionStatus.EXECUTING
    db.commit()
    action_logger.info(
        f"Action {action_id} APPROVED — executing in Firecracker",
        extra={"action_id": action_id, "action_type": action.action_type},
    )

    await ws_manager.broadcast({
        "type": "action_update",
        "data": {"id": action.id, "status": "executing"},
    })

    # Execute in Firecracker
    try:
        state: CommerceState = {
            "current_action": {
                "action_type": action.action_type,
                "parameters": action.parameters or {},
            },
            "sales_data": None,
            "ad_spend_data": None,
            "inventory_data": None,
            "pnl_summary": None,
            "sku_analysis": None,
            "proposed_actions": [],
            "agent_reasoning": None,
            "approval_status": "approved",
            "execution_result": None,
            "thread_id": str(uuid.uuid4()),
            "cycle_count": 0,
            "agent_logs": [],
            "errors": [],
        }

        result_state = await firecracker_executor_node(state)
        execution_result = result_state.get("execution_result", {})

        # Record in audit trail
        vm_session_id = execution_result.get("vm_session_id", f"fc-{uuid.uuid4().hex[:12]}")
        audit = VMAuditTrail(
            session_id=vm_session_id,
            action_proposal_id=action.id,
            vm_boot_time_ms=execution_result.get("boot_time_ms", 0),
            payload_hash=execution_result.get("payload_hash", ""),
            code_executed=json.dumps(action.parameters),
            execution_result=execution_result,
            status="completed" if execution_result.get("success") else "failed",
            hardware_signature=execution_result.get("hardware_signature", ""),
        )
        audit.completed_at = datetime.utcnow()
        db.add(audit)

        action.status = ActionStatus.COMPLETED if execution_result.get("success") else ActionStatus.FAILED
        action.result = execution_result
        action.vm_session_id = vm_session_id
        db.commit()

        action_logger.info(
            f"Action {action_id} execution {'COMPLETED' if execution_result.get('success') else 'FAILED'}",
            extra={
                "action_id": action_id,
                "vm_session_id": vm_session_id,
                "success": execution_result.get("success"),
                "boot_time_ms": execution_result.get("boot_time_ms"),
            },
        )

        # Broadcast logs
        for log in result_state.get("agent_logs", []):
            await ws_manager.broadcast({"type": "agent_log", "data": log})

        await ws_manager.broadcast({
            "type": "action_update",
            "data": {
                "id": action.id,
                "status": action.status.value if hasattr(action.status, 'value') else str(action.status),
                "result": execution_result,
            },
        })

        return {
            "status": action.status.value if hasattr(action.status, 'value') else str(action.status),
            "action_id": action.id,
            "execution_result": execution_result,
        }

    except Exception as e:
        action.status = ActionStatus.FAILED
        action.result = {"error": str(e)}
        db.commit()
        action_logger.error(
            f"Action {action_id} execution FAILED: {e}",
            extra={"action_id": action_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Agent Workflow Trigger
# ============================================
@app.post("/api/agent/run-cycle")
async def run_agent_cycle(db: Session = Depends(get_db)):
    """
    Trigger a full agent cycle: sensor -> P&L -> strategy -> proposals.
    Returns the proposed actions for the Action Queue.
    """
    workflow_logger = get_logger("workflow")
    thread_id = str(uuid.uuid4())
    cid = set_correlation_id(f"cycle-{thread_id[:8]}")

    workflow_logger.info(
        f"Agent cycle STARTED (thread: {thread_id[:8]})",
        extra={"thread_id": thread_id, "correlation_id": cid},
    )

    await ws_manager.broadcast({
        "type": "agent_log",
        "data": {
            "timestamp": datetime.utcnow().isoformat(),
            "node": "orchestrator",
            "message": f"Starting agent cycle (thread: {thread_id[:8]}...)",
        },
    })

    initial_state: CommerceState = {
        "sales_data": None,
        "ad_spend_data": None,
        "inventory_data": None,
        "pnl_summary": None,
        "sku_analysis": None,
        "proposed_actions": [],
        "agent_reasoning": None,
        "current_action": None,
        "approval_status": None,
        "execution_result": None,
        "thread_id": thread_id,
        "cycle_count": 0,
        "agent_logs": [],
        "errors": [],
    }

    try:
        # Run the graph
        result = await commerce_graph.ainvoke(initial_state)

        # Broadcast all agent logs
        for log in result.get("agent_logs", []):
            await ws_manager.broadcast({"type": "agent_log", "data": log})

        # Save proposed actions to database
        saved_actions = []
        for proposal in result.get("proposed_actions", []):
            action = ActionProposal(
                action_type=proposal.get("action_type", "unknown"),
                title=proposal.get("title", "Untitled Action"),
                description=proposal.get("description", ""),
                reasoning=result.get("agent_reasoning", ""),
                parameters=proposal.get("parameters"),
                priority=proposal.get("priority", "medium"),
            )
            db.add(action)
            db.commit()
            db.refresh(action)
            saved_actions.append({
                "id": action.id,
                "action_type": action.action_type,
                "title": action.title,
                "priority": action.priority,
                "status": "pending",
            })

            await ws_manager.broadcast({
                "type": "action_update",
                "data": {
                    "id": action.id,
                    "action_type": action.action_type,
                    "title": action.title,
                    "status": "pending",
                    "priority": action.priority,
                },
            })

        # Save daily metrics
        pnl = result.get("pnl_summary", {})
        if pnl:
            metric = DailyMetric(
                revenue=pnl.get("total_revenue", 0),
                ad_spend=pnl.get("total_ad_spend", 0),
                shipping_cost=pnl.get("total_shipping", 0),
                cogs_total=pnl.get("total_cogs", 0),
                net_profit=pnl.get("net_profit", 0),
                margin_percent=pnl.get("contribution_margin", 0),
            )
            db.add(metric)
            db.commit()

        workflow_logger.info(
            f"Agent cycle COMPLETED — {len(saved_actions)} actions proposed",
            extra={
                "thread_id": thread_id,
                "actions_proposed": len(saved_actions),
                "pnl_revenue": pnl.get("total_revenue"),
                "pnl_net_profit": pnl.get("net_profit"),
                "pnl_margin": pnl.get("contribution_margin"),
                "errors": result.get("errors", []),
            },
        )

        return {
            "thread_id": thread_id,
            "pnl_summary": result.get("pnl_summary"),
            "proposed_actions": saved_actions,
            "agent_reasoning": result.get("agent_reasoning"),
            "sku_analysis": result.get("sku_analysis"),
            "errors": result.get("errors", []),
        }

    except Exception as e:
        workflow_logger.error(
            f"Agent cycle FAILED: {e}",
            extra={"thread_id": thread_id, "error": str(e)},
            exc_info=True,
        )
        await ws_manager.broadcast({
            "type": "agent_log",
            "data": {
                "timestamp": datetime.utcnow().isoformat(),
                "node": "orchestrator",
                "message": f"ERROR: Agent cycle failed - {str(e)}",
            },
        })
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/state")
async def get_agent_state():
    """Get current agent state and graph status."""
    return {
        "status": "idle",
        "vm_telemetry": firecracker_manager.get_telemetry(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================
# VM Audit Trail
# ============================================
@app.get("/api/vm-audit")
def list_vm_audits(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """List VM audit trail entries."""
    if not settings.is_source_enabled("vm"):
        return source_disabled_response("vm")
    return (
        db.query(VMAuditTrail)
        .order_by(desc(VMAuditTrail.created_at))
        .limit(limit)
        .all()
    )


# ============================================
# VM Telemetry
# ============================================
@app.get("/api/vm/telemetry")
async def get_vm_telemetry():
    """Get current Firecracker VM telemetry."""
    if not settings.is_source_enabled("vm"):
        return source_disabled_response("vm")
    return firecracker_manager.get_telemetry()


# ============================================
# Diagnostic Storefront - AI Supplement Protocols
# ============================================
@app.post("/api/diagnostic/protocol")
async def generate_protocol(request: HealthGoalRequest):
    """
    Generate a science-backed supplement protocol based on health goals.
    Uses LLM to create personalized recommendations.
    """
    if not settings.is_source_enabled("diagnostic"):
        return source_disabled_response("diagnostic")
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    diag_logger = get_logger("agent")
    diag_logger.info(
        f"Protocol generation requested: goals={request.goals}",
        extra={"goals": request.goals, "age": request.age, "gender": request.gender},
    )

    try:
        llm = ChatOpenAI(model=settings.STRATEGY_MODEL, temperature=0.4)

        prompt = f"""You are a clinical nutritionist AI for KayaPure supplements. Based on the user's health goals, create a personalized supplement protocol.

Health Goals: {', '.join(request.goals)}
Age: {request.age or 'Not specified'}
Gender: {request.gender or 'Not specified'}
Existing Conditions: {', '.join(request.existing_conditions or ['None'])}
Current Supplements: {', '.join(request.current_supplements or ['None'])}

Available KayaPure Products:
- Organic Turmeric Capsules (anti-inflammatory, joint health)
- Ashwagandha Extract (stress, cortisol, energy)
- Vitamin D3+K2 (bone health, immunity)
- Omega-3 Fish Oil (heart, brain, inflammation)
- Probiotics 50B CFU (gut health, immunity)
- Magnesium Glycinate (sleep, muscle, stress)
- Collagen Peptides (skin, joints, gut)
- Black Seed Oil (immunity, antioxidant)

Respond in this exact JSON format:
{{
    "protocol_name": "Name of the protocol",
    "recommendations": [
        {{
            "product_name": "Product Name",
            "dosage": "Specific dosage",
            "timing": "When to take",
            "scientific_basis": "Brief scientific explanation",
            "confidence_score": 0.85
        }}
    ],
    "disclaimer": "Standard health disclaimer",
    "sources": ["List of scientific references"]
}}"""

        response = await llm.ainvoke([
            SystemMessage(content="You are a science-based supplement advisor. Always include disclaimers. Respond only in valid JSON."),
            HumanMessage(content=prompt),
        ])

        # Parse LLM response
        response_text = response.content.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        protocol_data = json.loads(response_text)
        diag_logger.info(
            f"Protocol generated: {protocol_data.get('protocol_name', 'unknown')}",
            extra={"protocol_name": protocol_data.get("protocol_name")},
        )
        return ProtocolResponse(**protocol_data)

    except json.JSONDecodeError:
        diag_logger.warning("LLM returned invalid JSON — using fallback protocol")
        # Fallback protocol
        return ProtocolResponse(
            protocol_name="General Wellness Protocol",
            recommendations=[
                SupplementRecommendation(
                    product_name="KayaPure Vitamin D3+K2",
                    dosage="2000 IU daily",
                    timing="Morning with food",
                    scientific_basis="Vitamin D supports immune function and bone health. K2 ensures proper calcium utilization.",
                    confidence_score=0.9,
                ),
                SupplementRecommendation(
                    product_name="KayaPure Magnesium Glycinate",
                    dosage="400mg daily",
                    timing="Evening, 30 min before bed",
                    scientific_basis="Magnesium glycinate supports sleep quality and muscle recovery with high bioavailability.",
                    confidence_score=0.85,
                ),
                SupplementRecommendation(
                    product_name="KayaPure Probiotics 50B CFU",
                    dosage="1 capsule daily",
                    timing="Morning on empty stomach",
                    scientific_basis="Diverse probiotic strains support gut microbiome diversity and immune function.",
                    confidence_score=0.8,
                ),
            ],
            disclaimer="These recommendations are for informational purposes only and do not constitute medical advice. Consult your healthcare provider before starting any supplement regimen.",
            sources=[
                "Holick MF. Vitamin D deficiency. N Engl J Med. 2007;357(3):266-281.",
                "Abbasi B, et al. The effect of magnesium supplementation on primary insomnia. J Res Med Sci. 2012;17(12):1161-1169.",
                "Hill C, et al. Expert consensus document: The International Scientific Association for Probiotics and Prebiotics. Nat Rev Gastroenterol Hepatol. 2014;11(8):506-514.",
            ],
        )
    except Exception as e:
        diag_logger.error(f"Protocol generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Protocol generation failed: {str(e)}")


# ============================================
# Commerce Data Endpoints (for dashboard)
# ============================================
@app.get("/api/commerce/daily-sales")
async def get_daily_sales():
    """Get today's sales data from Shopify."""
    if not settings.is_source_enabled("commerce"):
        return source_disabled_response("commerce")
    return await commerce_service.get_daily_sales()


@app.get("/api/marketing/ad-spend")
async def get_ad_spend(days: int = Query(default=7, ge=1, le=90, description="Number of days of ad spend data to return (1-90)")):
    """
    Get ad spend data.
    - days=1: returns today's data only (legacy behavior)
    - days=7: returns last 7 days with daily breakdown (default)
    - days=30: returns last 30 days with daily breakdown
    """
    if not settings.is_source_enabled("marketing"):
        return source_disabled_response("marketing")
    if days == 1:
        return await marketing_service.get_ad_spend_summary()
    return await marketing_service.get_ad_spend_history(days=days)


@app.get("/api/logistics/inventory")
async def get_inventory():
    """Get current inventory status."""
    if not settings.is_source_enabled("logistics"):
        return source_disabled_response("logistics")
    return await logistics_service.get_inventory_status()


# ============================================
# WebSocket Endpoint
# ============================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time agent logs and telemetry."""
    await ws_manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_json({
            "type": "connection",
            "data": {
                "status": "connected",
                "timestamp": datetime.utcnow().isoformat(),
                "vm_telemetry": firecracker_manager.get_telemetry(),
            },
        })

        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# ============================================
# Mount Shiny Dashboard at /dashboard
# ============================================
try:
    import sys
    import os
    # Add project root to path so shiny_app can import backend services
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from shiny_app.app import shiny_app as _shiny_app
    from starlette.routing import Mount
    app.mount("/dashboard", _shiny_app)
    startup_logger.info("Shiny dashboard mounted at /dashboard")
except ImportError as e:
    startup_logger.warning(f"Shiny dashboard not available (missing dependency): {e}")
except Exception as e:
    startup_logger.warning(f"Shiny dashboard mount failed: {e}")


# ============================================
# Entry Point
# ============================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
