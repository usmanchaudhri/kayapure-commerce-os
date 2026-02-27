"""
KayaPure Commerce OS - Firecracker Manager
Manages microVM lifecycles, snapshot loading, and Host-to-Guest Vsock communication.

In production, this communicates with the Firecracker API socket to:
  1. Boot a microVM from a pre-built snapshot
  2. Pass encrypted payloads via Vsock (AF_VSOCK)
  3. Execute the action inside the isolated VM
  4. Return hardware-signed results
  5. Terminate the VM

For local development, this provides a mock implementation that simulates
VM boot times and Vsock communication patterns.
"""

import asyncio
import hashlib
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from utils.secret_manager import secret_manager


class VMSession:
    """Represents a single Firecracker microVM session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status = "initializing"
        self.boot_start_time: Optional[float] = None
        self.boot_time_ms: int = 0
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.payload_hash: Optional[str] = None
        self.code_executed: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.hardware_signature: Optional[str] = None
        self.error_log: Optional[str] = None


class FirecrackerManager:
    """
    Mock Firecracker Manager for local development.
    Simulates the full VM lifecycle including boot, execution, and teardown.
    """

    def __init__(self):
        self.active_sessions: Dict[str, VMSession] = {}
        self.completed_sessions: Dict[str, VMSession] = {}
        self.mock_mode = settings.FIRECRACKER_MOCK
        self.base_boot_time_ms = settings.VM_BOOT_TIME_MS
        self._telemetry_callbacks = []

    def register_telemetry_callback(self, callback):
        """Register a callback for real-time VM telemetry updates."""
        self._telemetry_callbacks.append(callback)

    async def _emit_telemetry(self, event_type: str, data: dict):
        """Emit telemetry event to all registered callbacks."""
        for callback in self._telemetry_callbacks:
            try:
                await callback(event_type, data)
            except Exception:
                pass

    async def boot_vm(self, snapshot_id: str = "default") -> VMSession:
        """
        Boot a Firecracker microVM from a snapshot.
        In mock mode, simulates the boot process with realistic timing.
        """
        session_id = f"fc-{uuid.uuid4().hex[:12]}"
        session = VMSession(session_id)
        session.boot_start_time = time.time()
        session.status = "booting"
        self.active_sessions[session_id] = session

        await self._emit_telemetry("vm_boot_start", {
            "session_id": session_id,
            "snapshot_id": snapshot_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        if self.mock_mode:
            # Simulate Firecracker boot time (typically 125ms for snapshot restore)
            boot_delay = self.base_boot_time_ms / 1000.0
            await asyncio.sleep(boot_delay)
            session.boot_time_ms = self.base_boot_time_ms + int(time.time() * 1000 % 50)
        else:
            # Production: Call Firecracker API socket
            # PUT /machine-config, PUT /boot-source, PUT /drives/rootfs, PUT /actions (InstanceStart)
            raise NotImplementedError("Production Firecracker not yet implemented")

        session.status = "ready"
        await self._emit_telemetry("vm_boot_complete", {
            "session_id": session_id,
            "boot_time_ms": session.boot_time_ms,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return session

    async def execute_in_vm(
        self,
        session: VMSession,
        action_type: str,
        parameters: dict,
    ) -> Dict[str, Any]:
        """
        Execute an action inside the microVM.
        1. Creates encrypted payload with required secrets
        2. Sends via Vsock to Guest
        3. Guest executes and returns signed result
        """
        session.status = "executing"

        # Create secure payload
        payload = secret_manager.create_vm_payload(action_type, parameters)
        session.payload_hash = secret_manager.hash_payload(payload)

        # Encrypt payload for Vsock transmission
        encrypted_payload = secret_manager.encrypt_payload(payload)

        await self._emit_telemetry("vm_execution_start", {
            "session_id": session.session_id,
            "action_type": action_type,
            "payload_hash": session.payload_hash,
            "timestamp": datetime.utcnow().isoformat(),
        })

        if self.mock_mode:
            result = await self._mock_execute(action_type, parameters)
            session.code_executed = self._generate_execution_code(action_type, parameters)
        else:
            raise NotImplementedError("Production Vsock communication not yet implemented")

        # Generate hardware signature (mock: SHA-256 of result)
        result_json = json.dumps(result, sort_keys=True).encode()
        session.hardware_signature = hashlib.sha256(
            result_json + session.session_id.encode()
        ).hexdigest()

        session.result = result
        session.status = "completed"
        session.completed_at = datetime.utcnow()

        await self._emit_telemetry("vm_execution_complete", {
            "session_id": session.session_id,
            "action_type": action_type,
            "result": result,
            "hardware_signature": session.hardware_signature,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return result

    async def terminate_vm(self, session: VMSession):
        """Terminate a microVM and clean up resources."""
        session.status = "terminated"
        if session.session_id in self.active_sessions:
            del self.active_sessions[session.session_id]
        self.completed_sessions[session.session_id] = session

        await self._emit_telemetry("vm_terminated", {
            "session_id": session.session_id,
            "total_lifetime_ms": int(
                (datetime.utcnow() - session.created_at).total_seconds() * 1000
            ),
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _mock_execute(self, action_type: str, parameters: dict) -> Dict[str, Any]:
        """Simulate action execution inside a microVM."""
        # Simulate execution time (200-500ms)
        await asyncio.sleep(0.2 + (hash(action_type) % 300) / 1000.0)

        executors = {
            "price_change": self._mock_price_change,
            "budget_reduction": self._mock_budget_reduction,
            "inventory_check": self._mock_inventory_check,
            "competitor_analysis": self._mock_competitor_analysis,
            "bundle_offer": self._mock_bundle_offer,
            "ad_bid_adjustment": self._mock_ad_bid_adjustment,
        }

        executor = executors.get(action_type, self._mock_generic)
        return await executor(parameters)

    async def _mock_price_change(self, params: dict) -> dict:
        return {
            "success": True,
            "action": "price_change",
            "sku": params.get("sku_code", "unknown"),
            "old_price": params.get("current_price", 0),
            "new_price": params.get("new_price", 0),
            "change_percent": params.get("change_percent", 0),
            "shopify_product_id": f"gid://shopify/Product/{hash(params.get('sku_code', '')) % 10000000}",
            "applied_at": datetime.utcnow().isoformat(),
        }

    async def _mock_budget_reduction(self, params: dict) -> dict:
        return {
            "success": True,
            "action": "budget_reduction",
            "platform": "meta_ads",
            "campaign_id": f"camp_{uuid.uuid4().hex[:8]}",
            "old_daily_budget": params.get("current_budget", 0),
            "new_daily_budget": params.get("new_budget", 0),
            "reduction_percent": params.get("reduction_percent", 30),
            "applied_at": datetime.utcnow().isoformat(),
        }

    async def _mock_inventory_check(self, params: dict) -> dict:
        return {
            "success": True,
            "action": "inventory_check",
            "warehouse": "flexport_lax",
            "sku": params.get("sku_code", "unknown"),
            "available_units": params.get("current_stock", 0),
            "in_transit_units": 500,
            "eta_days": params.get("shipping_eta_days", 14),
            "checked_at": datetime.utcnow().isoformat(),
        }

    async def _mock_competitor_analysis(self, params: dict) -> dict:
        return {
            "success": True,
            "action": "competitor_analysis",
            "sku": params.get("sku_code", "unknown"),
            "my_price": params.get("current_price", 0),
            "competitor_price": params.get("competitor_price", 0),
            "price_gap_percent": round(
                ((params.get("current_price", 1) - params.get("competitor_price", 1))
                 / params.get("current_price", 1)) * 100, 2
            ),
            "marketplace": "amazon",
            "checked_at": datetime.utcnow().isoformat(),
        }

    async def _mock_bundle_offer(self, params: dict) -> dict:
        return {
            "success": True,
            "action": "bundle_offer",
            "sku": params.get("sku_code", "unknown"),
            "discount_percent": params.get("discount_percent", 5),
            "bundle_products": params.get("bundle_skus", []),
            "shopify_discount_code": f"BUNDLE{uuid.uuid4().hex[:6].upper()}",
            "applied_at": datetime.utcnow().isoformat(),
        }

    async def _mock_ad_bid_adjustment(self, params: dict) -> dict:
        return {
            "success": True,
            "action": "ad_bid_adjustment",
            "platform": params.get("platform", "meta_ads"),
            "campaign_id": f"camp_{uuid.uuid4().hex[:8]}",
            "old_bid": params.get("current_bid", 0),
            "new_bid": params.get("new_bid", 0),
            "applied_at": datetime.utcnow().isoformat(),
        }

    async def _mock_generic(self, params: dict) -> dict:
        return {
            "success": True,
            "action": "generic",
            "parameters": params,
            "executed_at": datetime.utcnow().isoformat(),
        }

    def _generate_execution_code(self, action_type: str, parameters: dict) -> str:
        """Generate a representation of the code that was executed in the VM."""
        code_templates = {
            "price_change": f"""
# Shopify Price Update - Executed in Firecracker VM
import shopify
shopify.ShopifyResource.set_site(api_url)
product = shopify.Product.find({parameters.get('sku_code', 'SKU')})
variant = product.variants[0]
variant.price = {parameters.get('new_price', 0)}
variant.save()
""",
            "budget_reduction": f"""
# Meta Ads Budget Reduction - Executed in Firecracker VM
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.campaign import Campaign
campaign = Campaign(campaign_id)
campaign.api_update(params={{'daily_budget': {parameters.get('new_budget', 0)}}})
""",
        }
        return code_templates.get(action_type, f"# Generic execution for {action_type}\n# Parameters: {json.dumps(parameters, indent=2)}")

    def get_telemetry(self) -> dict:
        """Get current VM telemetry data."""
        return {
            "active_vms": len(self.active_sessions),
            "completed_vms": len(self.completed_sessions),
            "active_sessions": [
                {
                    "session_id": s.session_id,
                    "status": s.status,
                    "boot_time_ms": s.boot_time_ms,
                    "created_at": s.created_at.isoformat(),
                }
                for s in self.active_sessions.values()
            ],
            "avg_boot_time_ms": (
                sum(s.boot_time_ms for s in self.completed_sessions.values()) /
                max(len(self.completed_sessions), 1)
            ),
        }


# Singleton instance
firecracker_manager = FirecrackerManager()
