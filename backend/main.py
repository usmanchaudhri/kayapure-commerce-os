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

from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from config import settings
from models.database import Base, engine, get_db, SessionLocal
from models.schemas import (
    SKU,
    DailyMetric,
    ActionProposal,
    ActionOutcome,
    AdsAnalysisReport,
    ApifyActorRun,
    VMAuditTrail,
    ActionStatus,
    ProfitLeakAnalysisRun,
    ProfitLeakFinding,
    ProfitLeakFindingEvidence,
    PostExOrder,
    PostExCprReceipt,
    PostExSyncState,
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
from services.ads_analysis_agent import ads_analysis_agent_service
from services.ingredient_research import ingredient_research_service
from services.ingredient_research.schemas import (
    IngredientCatalogResponse,
    IngredientComboRequest,
    ResearchReport,
    ResearchRunListResponse,
)
from services import action_queue
from services.report_store import list_reports_for_account, report_to_result, save_report
from services.profit_leak_store import (
    get_profit_leak_run,
    list_profit_leak_runs,
    run_to_result,
    update_finding_status,
)
from services.whatsapp_service import whatsapp_service
from services.apify_amazon import apify_amazon_service
from services.apify_client import ApifyError
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
    startup_logger.info(f"WhatsApp Cloud API enabled: {settings.WHATSAPP_ENABLED}")
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

    whatsapp_service.configure()
    startup_logger.info(
        f"WhatsApp Cloud API: {'READY' if whatsapp_service.is_ready else 'not configured'}"
    )
    startup_logger.info(
        f"Apify: {'READY' if settings.apify_ready else 'not configured'} "
        f"(webhook {settings.apify_webhook_url})"
    )
    apify_amazon_service.configure()

    # PostEx order sync (backfill continuation / incremental) in background
    if settings.POSTEX_TOKEN and settings.POSTEX_SYNC_ON_STARTUP:
        async def _postex_startup_sync():
            await asyncio.sleep(2)
            db = SessionLocal()
            try:
                from services.postex_sync import postex_sync_service

                result = await postex_sync_service.run(db, mode="auto", max_chunks=2)
                startup_logger.info(
                    "PostEx startup sync finished",
                    extra={"postex_sync": result},
                )
            except Exception as exc:
                startup_logger.warning(f"PostEx startup sync failed: {exc}")
            finally:
                db.close()

        asyncio.create_task(_postex_startup_sync())
        startup_logger.info("PostEx sync scheduled on startup")
    else:
        startup_logger.info("PostEx sync on startup: skipped")

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


@app.get("/api/facebook-ads/creatives")
async def all_creatives(
    account_id: Optional[str] = Query(default=None, description="Filter by specific account ID (e.g., act_123). If omitted, fetches all accounts."),
):
    """
    Fetch all ad creatives across all ad accounts (or a specific account).
    Returns creative name, type, status, thumbnail, body text, etc.
    """
    if not marketing_service._use_facebook or not marketing_service._fb_client:
        return {"error": "Facebook Ads client not configured", "enabled": False}

    try:
        if account_id:
            # Single account
            creatives = await marketing_service._fb_client.get_creatives_for_account(account_id)
            return {
                "total_accounts": 1,
                "total_creatives": len(creatives),
                "accounts": [{
                    "account_id": account_id,
                    "creative_count": len(creatives),
                    "creatives": creatives,
                }],
            }
        else:
            # All accounts
            result = await marketing_service._fb_client.get_all_creatives()
            return result
    except Exception as e:
        logger.error(f"Failed to fetch creatives: {e}")
        return {"error": str(e)}


# ============================================
# Campaign Management Endpoints
# ============================================

@app.get("/api/facebook-ads/campaigns")
async def get_all_campaigns(
    account_id: Optional[str] = Query(default=None, description="Filter by ad account ID"),
    days: int = Query(default=7, description="Days of insights to include"),
):
    """Fetch all campaigns across all accounts with performance insights."""
    try:
        if not marketing_service._fb_client:
            return {"error": "Facebook Ads client not configured"}

        if account_id:
            campaigns = await marketing_service._fb_client.get_campaigns_detailed(account_id)
            # Enrich with insights
            from datetime import date as date_type, timedelta
            end_date = date_type.today()
            start_date = end_date - timedelta(days=days)
            time_range = {"since": start_date.strftime("%Y-%m-%d"), "until": end_date.strftime("%Y-%m-%d")}

            import asyncio
            async def enrich(c):
                try:
                    insights = await marketing_service._fb_client.get_campaign_insights(c["id"], time_range=time_range)
                    rows = insights.get("data", [])
                    if rows:
                        perf = rows[0]
                        c["performance"] = {
                            "spend": float(perf.get("spend", 0)),
                            "impressions": int(perf.get("impressions", 0)),
                            "clicks": int(perf.get("clicks", 0)),
                            "cpc": float(perf.get("cpc", 0)),
                            "ctr": float(perf.get("ctr", 0)),
                            "reach": int(perf.get("reach", 0)),
                        }
                    else:
                        c["performance"] = None
                except Exception:
                    c["performance"] = None
                return c

            campaigns = await asyncio.gather(*[enrich(c) for c in campaigns])
            return {
                "total_campaigns": len(campaigns),
                "insights_period": time_range,
                "accounts": [{
                    "account_id": account_id,
                    "campaigns": list(campaigns),
                }],
            }
        else:
            result = await marketing_service._fb_client.get_all_campaigns(
                include_insights=True, days=days
            )
            return result
    except Exception as e:
        logger.error(f"Failed to fetch campaigns: {e}")
        return {"error": str(e)}


@app.post("/api/facebook-ads/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    campaign_name: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Queue a campaign pause for human approval."""
    action = action_queue.propose_meta_pause(
        db,
        campaign_id=campaign_id,
        campaign_name=campaign_name or campaign_id,
    )
    return {
        "success": True,
        "proposed": True,
        "action_id": action.id,
        "status": action.status.value,
        "message": "Pause queued for approval",
    }


@app.post("/api/facebook-ads/campaigns/{campaign_id}/activate")
async def activate_campaign(
    campaign_id: str,
    campaign_name: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Queue a campaign activation for human approval."""
    action = action_queue.propose_meta_activate(
        db,
        campaign_id=campaign_id,
        campaign_name=campaign_name or campaign_id,
    )
    return {
        "success": True,
        "proposed": True,
        "action_id": action.id,
        "status": action.status.value,
        "message": "Activation queued for approval",
    }


@app.post("/api/facebook-ads/campaigns/{campaign_id}/delete")
async def delete_campaign(
    campaign_id: str,
    campaign_name: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Queue a campaign archive for human approval."""
    action = action_queue.propose_meta_delete(
        db,
        campaign_id=campaign_id,
        campaign_name=campaign_name or campaign_id,
    )
    return {
        "success": True,
        "proposed": True,
        "action_id": action.id,
        "status": action.status.value,
        "message": "Archive queued for approval",
    }


@app.post("/api/facebook-ads/campaigns/{campaign_id}/budget")
async def update_campaign_budget(
    campaign_id: str,
    daily_budget: int = Query(..., description="New daily budget in cents"),
    campaign_name: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Queue a campaign budget change for human approval."""
    action = action_queue.propose_meta_budget(
        db,
        campaign_id=campaign_id,
        campaign_name=campaign_name or campaign_id,
        daily_budget_cents=daily_budget,
    )
    return {
        "success": True,
        "proposed": True,
        "action_id": action.id,
        "status": action.status.value,
        "message": "Budget update queued for approval",
    }


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
    """Approve or deny an action proposal. Executes channel actions or Firecracker on approval."""
    action_logger = get_logger("agent")
    action_logger.info(
        f"Action decision received: action_id={action_id}, decision={decision.action}",
        extra={"action_id": action_id, "decision": decision.action},
    )

    try:
        if decision.action == "deny":
            result = await action_queue.deny_action(db, action_id, comment=decision.comment)
            await ws_manager.broadcast({
                "type": "action_update",
                "data": {"id": action_id, "status": "denied", "comment": decision.comment},
            })
            return result

        result = await action_queue.approve_action(db, action_id, comment=decision.comment)
        await ws_manager.broadcast({
            "type": "action_update",
            "data": {
                "id": action_id,
                "status": result.get("status"),
                "result": result.get("execution_result"),
            },
        })
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        action_logger.error(f"Action {action_id} execution FAILED: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/actions/{action_id}/outcomes")
def get_action_outcomes(action_id: int, db: Session = Depends(get_db)):
    """List recorded outcomes for an action proposal."""
    outcomes = (
        db.query(ActionOutcome)
        .filter(ActionOutcome.action_proposal_id == action_id)
        .order_by(desc(ActionOutcome.recorded_at))
        .all()
    )
    return [
        {
            "id": o.id,
            "outcome_type": o.outcome_type,
            "success": o.success,
            "metrics_json": o.metrics_json,
            "notes": o.notes,
            "recorded_at": o.recorded_at.isoformat() if o.recorded_at else None,
        }
        for o in outcomes
    ]


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
# Ingredient Research Agent #1 (CAMEL Workforce)
# ============================================
@app.get("/api/research/ingredients", response_model=IngredientCatalogResponse)
async def list_research_ingredients(
    tag: Optional[str] = Query(default=None, description="Optional catalog tag filter"),
    limit: Optional[int] = Query(default=None, ge=1, le=500),
):
    """List ingredients from the local Kayapure research catalog."""
    tags = [tag] if tag else None
    return ingredient_research_service.get_catalog(tags=tags, limit=limit)


@app.get("/api/research/status")
async def ingredient_research_status():
    """Return configuration readiness for the ingredient research agent."""
    return {
        "ready": ingredient_research_service.is_ready,
        "default_limit": settings.INGREDIENT_RESEARCH_DEFAULT_LIMIT,
        "max_combos": settings.INGREDIENT_RESEARCH_MAX_COMBOS,
        "timeout_sec": settings.INGREDIENT_RESEARCH_TIMEOUT_SEC,
        "model_platform": settings.INGREDIENT_RESEARCH_MODEL_PLATFORM,
        "model_type": settings.INGREDIENT_RESEARCH_MODEL_TYPE,
        "ncbi_api_key_configured": bool(settings.NCBI_API_KEY),
    }


@app.post("/api/research/ingredient-combos", response_model=ResearchReport)
async def research_ingredient_combos(request: IngredientComboRequest):
    """
    Run Phase-1 CAMEL Workforce ingredient research.

    Specialists: librarian, evidence_scout, synergy_analyst, claim_guard.
    Persists JSON artifacts under backend/data/ingredient_research_runs/.
    """
    research_logger = get_logger("ingredient_research")
    research_logger.info(
        "Ingredient combo research requested",
        extra={"goal": request.goal, "format": request.format},
    )
    if not ingredient_research_service.is_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ingredient research is not configured. "
                "Set GOOGLE_API_KEY or LLM_BASE_MODEL_API_KEY."
            ),
        )
    try:
        return await ingredient_research_service.research_combos(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        research_logger.exception("Ingredient research failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Ingredient research failed: {exc}",
        ) from exc


@app.get("/api/research/runs", response_model=ResearchRunListResponse)
async def list_ingredient_research_runs(
    limit: int = Query(default=50, ge=1, le=200),
):
    """List persisted ingredient research runs (newest first)."""
    return ingredient_research_service.list_runs(limit=limit)


@app.get("/api/research/runs/{run_id}")
async def get_ingredient_research_run(run_id: str):
    """Fetch a persisted ingredient research run by id."""
    payload = ingredient_research_service.get_run(run_id)
    if not payload:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return payload


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

@app.post("/api/marketing/analyze")
async def analyze_ads(
    days: int = 7,
    question: str = "Which campaigns waste budget and what should I change?",
    account_id: str = Query(default=""),
    account_name: str = Query(default=""),
    persist: bool = Query(default=True),
    report_type: str = Query(default="generate"),
    db: Session = Depends(get_db),
):
    result = await ads_analysis_agent_service.analyze(
        days=days,
        question=question,
        account_id=account_id or None,
        account_name=account_name or None,
    )
    if persist and account_id:
        save_report(
            db,
            account_id=account_id,
            account_name=account_name or account_id,
            report_type=report_type,
            days=days,
            question=question,
            result=result,
        )
    return result


@app.get("/api/marketing/profit-leak-scan")
async def profit_leak_scan(
    since: str = Query(..., description="Start date YYYY-MM-DD"),
    until: str = Query(..., description="End date YYYY-MM-DD"),
    account_id: str = Query(default=""),
    force_refresh: bool = Query(default=False),
    explain: bool = Query(default=True),
    persist: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Run deterministic profit leak scan with optional LLM explanations and persistence."""
    from services.profit_leak_scanner import profit_leak_scanner_service

    return await profit_leak_scanner_service.scan_all_accounts(
        since=since,
        until=until,
        account_id=account_id or None,
        force_refresh=force_refresh,
        explain=explain,
        persist=persist,
        db=db if persist else None,
    )


@app.get("/api/marketing/profit-leak-runs")
def profit_leak_runs_list(
    account_id: str = Query(default=""),
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
):
    runs = list_profit_leak_runs(db, account_id=account_id or None, limit=limit)
    return [
        {
            "id": r.id,
            "account_id": r.account_id,
            "account_name": r.account_name,
            "period_start": r.period_start.strftime("%Y-%m-%d"),
            "period_end": r.period_end.strftime("%Y-%m-%d"),
            "finding_count": (r.summary_json or {}).get("finding_count", 0),
            "total_opportunity_max": (r.summary_json or {}).get("total_opportunity_max", 0),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@app.get("/api/marketing/profit-leak-runs/{run_id}")
def profit_leak_run_detail(run_id: int, db: Session = Depends(get_db)):
    run = get_profit_leak_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Profit leak scan not found")
    return run_to_result(run)


@app.patch("/api/marketing/profit-leak-findings/{finding_id}/status")
def profit_leak_finding_status(
    finding_id: str,
    status: str = Query(..., description="open | accepted | dismissed | inconclusive | completed"),
    db: Session = Depends(get_db),
):
    allowed = {"open", "accepted", "dismissed", "inconclusive", "completed"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(allowed)}")
    finding = update_finding_status(db, finding_id, status)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return {"id": finding.id, "status": finding.status}


@app.get("/api/marketing/daily-diagnosis")
async def marketing_daily_diagnosis(
    since: str = Query(...),
    until: str = Query(...),
    account_id: str = Query(default=""),
    explain: bool = Query(default=True),
):
    from services.daily_account_diagnosis import daily_account_diagnosis_service

    return await daily_account_diagnosis_service.diagnose_all(
        since=since,
        until=until,
        account_id=account_id or None,
        explain=explain,
    )


@app.get("/api/marketing/creative-intelligence")
async def marketing_creative_intelligence(
    since: str = Query(...),
    until: str = Query(...),
    account_id: str = Query(default=""),
):
    from services.creative_intelligence import creative_intelligence_service

    return await creative_intelligence_service.analyze_all(
        since=since,
        until=until,
        account_id=account_id or None,
    )


@app.get("/api/marketing/funnel-reconciliation")
async def marketing_funnel_reconciliation(
    since: str = Query(...),
    until: str = Query(...),
    account_id: str = Query(default=""),
):
    from services.funnel_reconciliation import funnel_reconciliation_service

    return await funnel_reconciliation_service.reconcile_all(
        since=since,
        until=until,
        account_id=account_id or None,
    )


@app.get("/api/marketing/supplement-economics")
async def marketing_supplement_economics(
    since: str = Query(...),
    until: str = Query(...),
    account_id: str = Query(default=""),
):
    from services.supplement_economics import supplement_economics_service

    return await supplement_economics_service.analyze_all(
        since=since,
        until=until,
        account_id=account_id or None,
    )


@app.get("/api/marketing/reports")
def list_marketing_reports(
    account_id: str = Query(...),
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
):
    reports = list_reports_for_account(db, account_id, limit=limit)
    return [
        {
            "id": r.id,
            "account_id": r.account_id,
            "account_name": r.account_name,
            "report_type": r.report_type,
            "days": r.days,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@app.get("/api/marketing/reports/{report_id}")
def get_marketing_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(AdsAnalysisReport).filter(AdsAnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report_to_result(report)


@app.get("/api/marketing/reports/{report_id}/pdf")
def download_marketing_report_pdf(report_id: int, db: Session = Depends(get_db)):
    report = db.query(AdsAnalysisReport).filter(AdsAnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    from shiny_app.lib.report_pdf import generate_report_pdf_bytes

    result = report_to_result(report)
    result["report_id"] = report.id
    pdf_bytes, filename = generate_report_pdf_bytes(
        result,
        report.account_name or report.account_id,
        report.account_id,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/marketing/report-pdfs/{filename}")
def serve_session_report_pdf(filename: str):
    """Serve a PDF written by the dashboard session. Not a DB-backed report."""
    from shiny_app.lib.report_pdf import resolve_report_pdf_path

    filepath = resolve_report_pdf_path(filename)
    if not filepath:
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/postex/pdfs/{filename}")
def serve_postex_pdf(filename: str):
    """Serve airway bill / load sheet PDFs generated via PostEx API."""
    from shiny_app.lib.postex_client import resolve_postex_pdf_path

    filepath = resolve_postex_pdf_path(filename)
    if not filepath:
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        str(filepath),
        media_type="application/pdf",
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )


# ============================================
# PostEx order sync + sales consolidation
# ============================================
@app.post("/api/postex/sync")
async def postex_sync(
    mode: str = Query(default="auto", pattern="^(auto|backfill|incremental)$"),
    max_chunks: Optional[int] = Query(default=None, ge=1, le=500),
    background: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Start PostEx order sync (backfill and/or incremental lookback)."""
    if not settings.POSTEX_TOKEN:
        raise HTTPException(status_code=400, detail="POSTEX_TOKEN is not configured")

    from services.postex_sync import get_or_create_sync_state, postex_sync_service, sync_state_dict

    state = get_or_create_sync_state(db)
    if postex_sync_service._lock.locked():
        return {**sync_state_dict(state), "message": "Sync already running", "started": False}

    if background:
        async def _run():
            session = SessionLocal()
            try:
                await postex_sync_service.run(
                    session, mode=mode, max_chunks=max_chunks
                )
            except Exception:
                pass
            finally:
                session.close()

        asyncio.create_task(_run())
        # Mark running optimistically so status polls show progress
        state.status = "running"
        state.last_error = None
        db.commit()
        db.refresh(state)
        return {**sync_state_dict(state), "message": "Sync started", "started": True}

    result = await postex_sync_service.run(db, mode=mode, max_chunks=max_chunks)
    return {**result, "started": True, "message": "Sync completed"}


@app.get("/api/postex/sync/status")
def postex_sync_status(db: Session = Depends(get_db)):
    from services.postex_sync import get_or_create_sync_state, sync_state_dict

    state = get_or_create_sync_state(db)
    return sync_state_dict(state)


@app.get("/api/postex/sales/summary")
def postex_sales_summary(
    from_date: Optional[str] = Query(default=None, alias="from"),
    to_date: Optional[str] = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
):
    """Consolidated PostEx sales totals from synced orders."""
    from services.postex_sales import sales_summary
    from services.postex_sync import _parse_datetime, get_or_create_sync_state, sync_state_dict

    from_dt = _parse_datetime(from_date) if from_date else None
    to_dt = _parse_datetime(to_date) if to_date else None
    if to_dt and to_date and "T" not in str(to_date) and len(str(to_date)) <= 10:
        # Inclusive end-of-day for date-only filters
        to_dt = to_dt.replace(hour=23, minute=59, second=59)
    summary = sales_summary(db, from_dt=from_dt, to_dt=to_dt)
    state = get_or_create_sync_state(db)
    return {**summary, "sync": sync_state_dict(state)}


@app.get("/api/postex/orders")
def postex_orders_list(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    settled: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Paginated synced PostEx orders."""
    q = db.query(PostExOrder)
    if status:
        q = q.filter(PostExOrder.transaction_status.ilike(status))
    if settled is True:
        q = q.filter(PostExOrder.settle.is_(True))
    elif settled is False:
        q = q.filter((PostExOrder.settle.is_(False)) | (PostExOrder.settle.is_(None)))
    total = q.count()
    rows = (
        q.order_by(desc(PostExOrder.transaction_date), PostExOrder.tracking_number)
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = []
    for row in rows:
        items.append(
            {
                "tracking_number": row.tracking_number,
                "order_ref_number": row.order_ref_number,
                "transaction_status": row.transaction_status,
                "transaction_date": row.transaction_date.isoformat()
                if row.transaction_date
                else None,
                "invoice_payment": row.invoice_payment,
                "upfront_payment": row.upfront_payment,
                "reserve_payment": row.reserve_payment,
                "settle": row.settle,
                "settlement_date": row.settlement_date.isoformat()
                if row.settlement_date
                else None,
                "cpr1": row.cpr1,
                "cpr2": row.cpr2,
                "city_name": row.city_name,
                "customer_name": row.customer_name,
                "synced_at": row.synced_at.isoformat() if row.synced_at else None,
            }
        )
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# ============================================
# Apify Actor inbox
# ============================================
@app.post("/webhooks/apify")
async def apify_webhook(request: Request):
    """Receive ACTOR.RUN.SUCCEEDED from Apify Console and load the dataset."""
    secret = request.headers.get("x-apify-webhook-secret") or ""
    auth = request.headers.get("authorization") or ""
    if not secret and auth.lower().startswith("bearer "):
        secret = auth[7:].strip()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Webhook body must be JSON.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object.")
    try:
        result = await apify_amazon_service.ingest_webhook(payload, secret=secret or None)
    except ApifyError as exc:
        message = str(exc)
        status = 401 if "secret" in message.lower() else 400
        raise HTTPException(status_code=status, detail=message) from exc
    return result


@app.get("/api/apify/latest")
async def apify_latest():
    latest = apify_amazon_service.latest_saved()
    return {
        "ready": apify_amazon_service.is_ready,
        "runs": apify_amazon_service.list_saved(),
        "latest": latest,
    }


# ============================================
# WhatsApp Cloud API
# ============================================
@app.get("/api/whatsapp/status")
async def whatsapp_status():
    return {
        "enabled": settings.WHATSAPP_ENABLED,
        "ready": whatsapp_service.is_ready,
        "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID or None,
    }


@app.post("/api/whatsapp/messages/text")
async def propose_whatsapp_text(
    to: str = Query(...),
    message: str = Query(...),
    db: Session = Depends(get_db),
):
    """Queue a WhatsApp text message for approval."""
    action = action_queue.propose_whatsapp_text(db, to=to, message=message)
    return {
        "success": True,
        "proposed": True,
        "action_id": action.id,
        "status": action.status.value,
    }


@app.post("/api/whatsapp/messages/template")
async def propose_whatsapp_template(
    to: str = Query(...),
    template_name: str = Query(...),
    language_code: str = Query(default="en_US"),
    db: Session = Depends(get_db),
):
    """Queue a WhatsApp template message for approval."""
    action = action_queue.propose_whatsapp_template(
        db,
        to=to,
        template_name=template_name,
        language_code=language_code,
    )
    return {
        "success": True,
        "proposed": True,
        "action_id": action.id,
        "status": action.status.value,
    }

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
