"""
KayaPure Commerce OS - Logistics Service
Mock Flexport/Cart.com integration for SKU-level inventory and landed costs.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class LogisticsService:
    """Mock Flexport and Cart.com logistics integration."""

    def __init__(self):
        self._inventory = {
            "KP-TUR-001": {
                "warehouse": "flexport_lax",
                "on_hand": 450,
                "in_transit": 2000,
                "eta_days": 21,
                "landed_cost_per_unit": 5.80,
                "shipping_cost_per_unit": 1.55,
                "last_reorder_date": "2025-02-01",
            },
            "KP-ASH-002": {
                "warehouse": "flexport_lax",
                "on_hand": 120,
                "in_transit": 1500,
                "eta_days": 28,
                "landed_cost_per_unit": 6.90,
                "shipping_cost_per_unit": 1.70,
                "last_reorder_date": "2025-01-15",
            },
            "KP-VDK-003": {
                "warehouse": "flexport_jfk",
                "on_hand": 800,
                "in_transit": 3000,
                "eta_days": 14,
                "landed_cost_per_unit": 4.50,
                "shipping_cost_per_unit": 1.20,
                "last_reorder_date": "2025-02-10",
            },
            "KP-OMG-004": {
                "warehouse": "flexport_lax",
                "on_hand": 200,
                "in_transit": 1000,
                "eta_days": 35,
                "landed_cost_per_unit": 8.20,
                "shipping_cost_per_unit": 1.90,
                "last_reorder_date": "2025-01-20",
            },
            "KP-PRO-005": {
                "warehouse": "flexport_jfk",
                "on_hand": 350,
                "in_transit": 2500,
                "eta_days": 18,
                "landed_cost_per_unit": 9.50,
                "shipping_cost_per_unit": 2.00,
                "last_reorder_date": "2025-02-05",
            },
            "KP-MAG-006": {
                "warehouse": "flexport_lax",
                "on_hand": 600,
                "in_transit": 2000,
                "eta_days": 10,
                "landed_cost_per_unit": 4.80,
                "shipping_cost_per_unit": 1.20,
                "last_reorder_date": "2025-02-12",
            },
            "KP-COL-007": {
                "warehouse": "flexport_jfk",
                "on_hand": 90,
                "in_transit": 800,
                "eta_days": 42,
                "landed_cost_per_unit": 11.50,
                "shipping_cost_per_unit": 2.00,
                "last_reorder_date": "2025-01-10",
            },
            "KP-BSO-008": {
                "warehouse": "flexport_lax",
                "on_hand": 280,
                "in_transit": 1200,
                "eta_days": 16,
                "landed_cost_per_unit": 7.10,
                "shipping_cost_per_unit": 1.50,
                "last_reorder_date": "2025-02-08",
            },
        }

    async def get_inventory_status(self, sku_code: Optional[str] = None) -> Dict[str, Any]:
        """Get inventory status for one or all SKUs."""
        if sku_code:
            if sku_code not in self._inventory:
                return {"error": f"SKU {sku_code} not found"}
            inv = self._inventory[sku_code]
            return {
                "sku_code": sku_code,
                **inv,
                "days_of_stock": round(inv["on_hand"] / max(1, random.uniform(10, 40)), 1),
                "reorder_needed": inv["on_hand"] < 200,
            }

        all_inventory = []
        for sku, inv in self._inventory.items():
            all_inventory.append({
                "sku_code": sku,
                **inv,
                "days_of_stock": round(inv["on_hand"] / max(1, random.uniform(10, 40)), 1),
                "reorder_needed": inv["on_hand"] < 200,
            })

        return {
            "total_skus": len(all_inventory),
            "total_units_on_hand": sum(i["on_hand"] for i in self._inventory.values()),
            "total_units_in_transit": sum(i["in_transit"] for i in self._inventory.values()),
            "inventory": all_inventory,
        }

    async def get_landed_costs(self, sku_code: str) -> Dict[str, Any]:
        """Get detailed landed cost breakdown for a SKU."""
        if sku_code not in self._inventory:
            return {"error": f"SKU {sku_code} not found"}

        inv = self._inventory[sku_code]
        return {
            "sku_code": sku_code,
            "landed_cost_per_unit": inv["landed_cost_per_unit"],
            "breakdown": {
                "product_cost": inv["landed_cost_per_unit"] * 0.60,
                "shipping": inv["shipping_cost_per_unit"],
                "duties_taxes": inv["landed_cost_per_unit"] * 0.15,
                "insurance": inv["landed_cost_per_unit"] * 0.05,
                "handling": inv["landed_cost_per_unit"] * 0.10,
            },
            "currency": "USD",
        }

    async def get_shipping_estimates(self) -> Dict[str, Any]:
        """Get shipping cost estimates for fulfillment."""
        return {
            "domestic": {
                "standard": {"cost": 4.99, "days": "5-7"},
                "expedited": {"cost": 9.99, "days": "2-3"},
                "overnight": {"cost": 19.99, "days": "1"},
            },
            "international": {
                "standard": {"cost": 14.99, "days": "10-14"},
                "express": {"cost": 29.99, "days": "3-5"},
            },
            "avg_cost_per_order": 5.50,
        }


# Singleton
logistics_service = LogisticsService()
