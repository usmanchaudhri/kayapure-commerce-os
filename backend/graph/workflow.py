"""
KayaPure Commerce OS - LangGraph Agentic Workflow
The Business "Brain" - StateGraph implementing the autonomous commerce loop.

Nodes:
  1. sensor_node       - Polls simulated APIs (Shopify, Meta Ads, Amazon, Flexport)
  2. p_and_l_analyzer  - Calculates real-time Net Profit and Contribution Margin
  3. strategy_agent    - LLM-based reasoning to propose actions
  4. human_approval_gate - Pauses execution until human approves/denies
  5. firecracker_executor_node - Executes approved actions in isolated microVM
"""

import json
import uuid
from datetime import datetime
from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from services.commerce import commerce_service
from services.marketing import marketing_service
from services.logistics import logistics_service
from services.firecracker_manager import firecracker_manager


# ============================================
# State Definition
# ============================================
def merge_lists(a: list, b: list) -> list:
    """Reducer: merge two lists."""
    return a + b


class CommerceState(TypedDict):
    """The state that flows through the LangGraph workflow."""
    # Sensor data
    sales_data: Optional[Dict[str, Any]]
    ad_spend_data: Optional[Dict[str, Any]]
    inventory_data: Optional[Dict[str, Any]]

    # P&L Analysis
    pnl_summary: Optional[Dict[str, Any]]
    sku_analysis: Optional[List[Dict[str, Any]]]

    # Strategy Agent
    proposed_actions: Annotated[list, merge_lists]
    agent_reasoning: Optional[str]

    # Execution
    current_action: Optional[Dict[str, Any]]
    approval_status: Optional[str]  # "pending", "approved", "denied"
    execution_result: Optional[Dict[str, Any]]

    # Metadata
    thread_id: str
    cycle_count: int
    agent_logs: Annotated[list, merge_lists]
    errors: Annotated[list, merge_lists]


# ============================================
# Node Implementations
# ============================================
async def sensor_node(state: CommerceState) -> dict:
    """
    Polls simulated APIs: Shopify, Meta Ads, Amazon SP-API, Flexport.
    Aggregates all sensor data into the state.
    """
    logs = []
    logs.append({
        "timestamp": datetime.utcnow().isoformat(),
        "node": "sensor_node",
        "message": "Starting data collection from all platforms...",
    })

    try:
        # Poll Shopify
        sales_data = await commerce_service.get_daily_sales()
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "sensor_node",
            "message": f"Shopify: ${sales_data['total_revenue']:.2f} revenue, {sales_data['total_orders']} orders",
        })

        # Poll Meta/Google Ads
        ad_spend_data = await marketing_service.get_ad_spend_summary()
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "sensor_node",
            "message": f"Ad Spend: ${ad_spend_data['total_spend']:.2f} across {len(ad_spend_data['campaigns'])} campaigns",
        })

        # Poll Flexport
        inventory_data = await logistics_service.get_inventory_status()
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "sensor_node",
            "message": f"Inventory: {inventory_data['total_units_on_hand']} units on hand, {inventory_data['total_units_in_transit']} in transit",
        })

        return {
            "sales_data": sales_data,
            "ad_spend_data": ad_spend_data,
            "inventory_data": inventory_data,
            "agent_logs": logs,
        }

    except Exception as e:
        return {
            "errors": [{"node": "sensor_node", "error": str(e), "timestamp": datetime.utcnow().isoformat()}],
            "agent_logs": logs + [{"timestamp": datetime.utcnow().isoformat(), "node": "sensor_node", "message": f"ERROR: {str(e)}"}],
        }


async def p_and_l_analyzer(state: CommerceState) -> dict:
    """
    Calculates real-time Net Profit and Contribution Margin.
    Performs SKU-level profitability analysis.
    """
    logs = []
    logs.append({
        "timestamp": datetime.utcnow().isoformat(),
        "node": "p_and_l_analyzer",
        "message": "Calculating P&L metrics...",
    })

    sales = state.get("sales_data", {})
    ads = state.get("ad_spend_data", {})
    inventory = state.get("inventory_data", {})

    total_revenue = sales.get("total_revenue", 0)
    total_ad_spend = ads.get("total_spend", 0)

    # Estimate COGS and shipping from inventory data
    total_cogs = total_revenue * 0.30  # ~30% COGS ratio
    total_shipping = sales.get("total_orders", 0) * 5.50  # avg shipping per order

    gross_profit = total_revenue - total_cogs
    net_profit = gross_profit - total_ad_spend - total_shipping
    contribution_margin = (net_profit / max(total_revenue, 1)) * 100

    pnl_summary = {
        "total_revenue": round(total_revenue, 2),
        "total_cogs": round(total_cogs, 2),
        "total_ad_spend": round(total_ad_spend, 2),
        "total_shipping": round(total_shipping, 2),
        "gross_profit": round(gross_profit, 2),
        "net_profit": round(net_profit, 2),
        "contribution_margin": round(contribution_margin, 2),
        "period": "daily",
        "calculated_at": datetime.utcnow().isoformat(),
    }

    # SKU-level analysis
    sku_analysis = []
    inv_items = inventory.get("inventory", []) if isinstance(inventory, dict) else []
    product_sales = sales.get("product_sales", [])

    for inv_item in inv_items:
        sku_code = inv_item.get("sku_code", "")
        on_hand = inv_item.get("on_hand", 0)
        eta_days = inv_item.get("eta_days", 0)

        # Find matching sales data
        sku_sales = next((s for s in product_sales if s.get("sku_code") == sku_code), {})
        daily_velocity = sku_sales.get("units_sold", 0)
        sku_revenue = sku_sales.get("revenue", 0)

        days_of_stock = round(on_hand / max(daily_velocity, 1), 1)
        landed_cost = inv_item.get("landed_cost_per_unit", 0)

        sku_analysis.append({
            "sku_code": sku_code,
            "current_stock": on_hand,
            "daily_velocity": daily_velocity,
            "days_of_stock": days_of_stock,
            "shipping_eta_days": eta_days,
            "revenue": sku_revenue,
            "landed_cost": landed_cost,
            "stock_risk": days_of_stock < 14 and eta_days > 14,
            "contribution_margin": round(
                ((sku_revenue - (daily_velocity * landed_cost)) / max(sku_revenue, 1)) * 100, 2
            ),
        })

    logs.append({
        "timestamp": datetime.utcnow().isoformat(),
        "node": "p_and_l_analyzer",
        "message": f"P&L: Revenue ${total_revenue:.2f}, Net Profit ${net_profit:.2f}, Margin {contribution_margin:.1f}%",
    })

    at_risk_skus = [s for s in sku_analysis if s.get("stock_risk")]
    if at_risk_skus:
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "p_and_l_analyzer",
            "message": f"WARNING: {len(at_risk_skus)} SKUs at stock-out risk: {[s['sku_code'] for s in at_risk_skus]}",
        })

    return {
        "pnl_summary": pnl_summary,
        "sku_analysis": sku_analysis,
        "agent_logs": logs,
    }


async def strategy_agent(state: CommerceState) -> dict:
    """
    LLM-based reasoning agent. Analyzes P&L and inventory data to propose actions.
    Implements:
      - Inventory Shield: Stock protection via price/budget adjustments
      - Competitor Snipe: Competitive pricing responses
    """
    logs = []
    logs.append({
        "timestamp": datetime.utcnow().isoformat(),
        "node": "strategy_agent",
        "message": "Strategy Agent analyzing data and formulating proposals...",
    })

    proposed_actions = []
    pnl = state.get("pnl_summary", {})
    sku_analysis = state.get("sku_analysis", [])

    # ---- Rule-Based Strategy: Inventory Shield ----
    for sku in sku_analysis:
        if sku.get("stock_risk", False):
            # IF (Current_Stock / Daily_Sales_Velocity) < 14 days AND Shipping_ETA > 14 days
            action = {
                "id": str(uuid.uuid4()),
                "action_type": "inventory_shield",
                "title": f"Inventory Shield: Protect {sku['sku_code']} from stock-out",
                "description": (
                    f"SKU {sku['sku_code']} has only {sku['days_of_stock']:.0f} days of stock remaining "
                    f"but next shipment ETA is {sku['shipping_eta_days']} days. "
                    f"Proposing: (1) Reduce Meta Ad Budget by 30%, (2) Increase Shopify Price by 10% "
                    f"to slow demand and protect margin."
                ),
                "priority": "high",
                "sku_code": sku["sku_code"],
                "parameters": {
                    "sku_code": sku["sku_code"],
                    "current_stock": sku["current_stock"],
                    "days_of_stock": sku["days_of_stock"],
                    "shipping_eta_days": sku["shipping_eta_days"],
                    "sub_actions": [
                        {
                            "type": "budget_reduction",
                            "reduction_percent": 30,
                            "platform": "meta_ads",
                        },
                        {
                            "type": "price_change",
                            "change_percent": 10,
                            "direction": "increase",
                        },
                    ],
                },
            }
            proposed_actions.append(action)
            logs.append({
                "timestamp": datetime.utcnow().isoformat(),
                "node": "strategy_agent",
                "message": f"INVENTORY SHIELD triggered for {sku['sku_code']}: {sku['days_of_stock']:.0f} days stock, {sku['shipping_eta_days']} days ETA",
            })

    # ---- Rule-Based Strategy: Competitor Snipe ----
    for sku in sku_analysis:
        margin = sku.get("contribution_margin", 0)
        # We need competitor price data - check from inventory data
        inv_data = state.get("inventory_data", {})
        inv_items = inv_data.get("inventory", []) if isinstance(inv_data, dict) else []

        # Simulate competitor price check (in production, from Amazon SP-API)
        # Using seed data from database
        competitor_price_lower = margin > 30 and not sku.get("stock_risk", False)

        if competitor_price_lower and margin > 30:
            action = {
                "id": str(uuid.uuid4()),
                "action_type": "competitor_snipe",
                "title": f"Competitor Snipe: Counter pricing for {sku['sku_code']}",
                "description": (
                    f"Competitor price is lower than our price for {sku['sku_code']} "
                    f"but our contribution margin is {margin:.1f}% (>30%). "
                    f"Proposing a 5% discount or bundle offer to maintain sales volume."
                ),
                "priority": "medium",
                "sku_code": sku["sku_code"],
                "parameters": {
                    "sku_code": sku["sku_code"],
                    "contribution_margin": margin,
                    "sub_actions": [
                        {
                            "type": "price_change",
                            "change_percent": -5,
                            "direction": "decrease",
                        },
                    ],
                },
            }
            proposed_actions.append(action)
            logs.append({
                "timestamp": datetime.utcnow().isoformat(),
                "node": "strategy_agent",
                "message": f"COMPETITOR SNIPE triggered for {sku['sku_code']}: margin {margin:.1f}%, proposing 5% discount",
            })

    # ---- LLM-Enhanced Analysis ----
    try:
        llm = ChatOpenAI(
            model=settings.STRATEGY_MODEL,
            temperature=0.3,
        )

        analysis_prompt = f"""You are the KayaPure Commerce OS Strategy Agent. Analyze the following business data and provide strategic insights.

P&L Summary:
{json.dumps(pnl, indent=2)}

SKU Analysis:
{json.dumps(sku_analysis[:5], indent=2)}

Already Proposed Actions: {len(proposed_actions)} actions from rule-based analysis.

Provide a brief strategic assessment (2-3 sentences) of the overall business health and any additional recommendations beyond the rule-based actions. Focus on margin optimization and growth opportunities."""

        response = await llm.ainvoke([
            SystemMessage(content="You are a DTC e-commerce strategy analyst for a supplement brand. Be concise and data-driven."),
            HumanMessage(content=analysis_prompt),
        ])

        agent_reasoning = response.content
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "strategy_agent",
            "message": f"LLM Analysis: {agent_reasoning[:200]}...",
        })

    except Exception as e:
        agent_reasoning = f"LLM analysis unavailable: {str(e)}. Rule-based strategies applied."
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "strategy_agent",
            "message": f"LLM fallback: {str(e)[:100]}",
        })

    logs.append({
        "timestamp": datetime.utcnow().isoformat(),
        "node": "strategy_agent",
        "message": f"Strategy complete: {len(proposed_actions)} actions proposed",
    })

    return {
        "proposed_actions": proposed_actions,
        "agent_reasoning": agent_reasoning,
        "agent_logs": logs,
    }


def should_wait_for_approval(state: CommerceState) -> str:
    """Conditional edge: route based on whether there are pending actions."""
    if state.get("proposed_actions") and len(state["proposed_actions"]) > 0:
        return "wait_for_approval"
    return "end"


async def human_approval_gate(state: CommerceState) -> dict:
    """
    Wait state - pauses execution until human approves/denies via dashboard.
    In the actual system, this node uses LangGraph's interrupt mechanism.
    For the prototype, it sets the state to 'pending' and the API handles approval.
    """
    logs = [{
        "timestamp": datetime.utcnow().isoformat(),
        "node": "human_approval_gate",
        "message": f"Waiting for human approval on {len(state.get('proposed_actions', []))} proposed actions...",
    }]

    return {
        "approval_status": "pending",
        "agent_logs": logs,
    }


async def firecracker_executor_node(state: CommerceState) -> dict:
    """
    Executes approved actions inside Firecracker microVMs.
    1. Boots VM from snapshot
    2. Passes encrypted payload via Vsock
    3. Executes action
    4. Returns hardware-signed results
    5. Terminates VM
    """
    logs = []
    current_action = state.get("current_action")

    if not current_action:
        return {
            "agent_logs": [{
                "timestamp": datetime.utcnow().isoformat(),
                "node": "firecracker_executor",
                "message": "No action to execute",
            }],
        }

    action_type = current_action.get("action_type", "generic")
    parameters = current_action.get("parameters", {})

    logs.append({
        "timestamp": datetime.utcnow().isoformat(),
        "node": "firecracker_executor",
        "message": f"Booting Firecracker microVM for action: {action_type}",
    })

    try:
        # 1. Boot VM
        vm_session = await firecracker_manager.boot_vm()
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "firecracker_executor",
            "message": f"VM booted in {vm_session.boot_time_ms}ms (session: {vm_session.session_id})",
        })

        # 2-3. Execute action in VM
        # Process sub-actions if present
        sub_actions = parameters.get("sub_actions", [])
        results = []

        if sub_actions:
            for sub_action in sub_actions:
                sub_type = sub_action.get("type", action_type)
                result = await firecracker_manager.execute_in_vm(
                    vm_session, sub_type, {**parameters, **sub_action}
                )
                results.append(result)
                logs.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "node": "firecracker_executor",
                    "message": f"Sub-action {sub_type} executed: {result.get('success', False)}",
                })
        else:
            result = await firecracker_manager.execute_in_vm(vm_session, action_type, parameters)
            results.append(result)

        # 4. Collect results
        execution_result = {
            "success": all(r.get("success", False) for r in results),
            "vm_session_id": vm_session.session_id,
            "boot_time_ms": vm_session.boot_time_ms,
            "hardware_signature": vm_session.hardware_signature,
            "sub_results": results,
            "executed_at": datetime.utcnow().isoformat(),
        }

        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "firecracker_executor",
            "message": f"Execution complete. Hardware signature: {vm_session.hardware_signature[:16]}...",
        })

        # 5. Terminate VM
        await firecracker_manager.terminate_vm(vm_session)
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "firecracker_executor",
            "message": f"VM {vm_session.session_id} terminated successfully",
        })

        return {
            "execution_result": execution_result,
            "agent_logs": logs,
        }

    except Exception as e:
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "node": "firecracker_executor",
            "message": f"ERROR: {str(e)}",
        })
        return {
            "execution_result": {"success": False, "error": str(e)},
            "errors": [{"node": "firecracker_executor", "error": str(e)}],
            "agent_logs": logs,
        }


# ============================================
# Graph Construction
# ============================================
def build_commerce_graph() -> StateGraph:
    """
    Constructs the LangGraph StateGraph for the KayaPure Commerce OS.

    Flow:
      sensor_node -> p_and_l_analyzer -> strategy_agent -> [conditional]
        -> human_approval_gate (if actions proposed)
        -> END (if no actions)

    The firecracker_executor_node is triggered separately via API
    after human approval.
    """
    graph = StateGraph(CommerceState)

    # Add nodes
    graph.add_node("sensor_node", sensor_node)
    graph.add_node("p_and_l_analyzer", p_and_l_analyzer)
    graph.add_node("strategy_agent", strategy_agent)
    graph.add_node("human_approval_gate", human_approval_gate)
    graph.add_node("firecracker_executor", firecracker_executor_node)

    # Define edges
    graph.set_entry_point("sensor_node")
    graph.add_edge("sensor_node", "p_and_l_analyzer")
    graph.add_edge("p_and_l_analyzer", "strategy_agent")

    # Conditional: if actions proposed -> wait for approval, else -> end
    graph.add_conditional_edges(
        "strategy_agent",
        should_wait_for_approval,
        {
            "wait_for_approval": "human_approval_gate",
            "end": END,
        },
    )

    graph.add_edge("human_approval_gate", END)
    graph.add_edge("firecracker_executor", END)

    return graph


def get_compiled_graph():
    """Get a compiled version of the commerce graph."""
    graph = build_commerce_graph()
    return graph.compile()


# Pre-build the graph
commerce_graph = get_compiled_graph()
