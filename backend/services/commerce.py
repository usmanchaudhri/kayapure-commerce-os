"""
KayaPure Commerce OS - Commerce Service
Shopify API integration for daily sales data and dynamic product pricing.
Provides mock data for local development.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class CommerceService:
    """Mock Shopify API integration for sales and pricing data."""

    def __init__(self):
        self._products = {
            "KP-TUR-001": {"name": "Organic Turmeric Capsules", "price": 24.99, "daily_orders": 32},
            "KP-ASH-002": {"name": "Ashwagandha Extract", "price": 29.99, "daily_orders": 18},
            "KP-VDK-003": {"name": "Vitamin D3+K2", "price": 19.99, "daily_orders": 45},
            "KP-OMG-004": {"name": "Omega-3 Fish Oil", "price": 34.99, "daily_orders": 25},
            "KP-PRO-005": {"name": "Probiotics 50B CFU", "price": 39.99, "daily_orders": 20},
            "KP-MAG-006": {"name": "Magnesium Glycinate", "price": 22.99, "daily_orders": 28},
            "KP-COL-007": {"name": "Collagen Peptides", "price": 44.99, "daily_orders": 15},
            "KP-BSO-008": {"name": "Black Seed Oil", "price": 27.99, "daily_orders": 12},
        }

    async def get_daily_sales(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Fetch daily sales data from Shopify (mock)."""
        if date is None:
            date = datetime.utcnow()

        total_revenue = 0
        total_orders = 0
        product_sales = []

        for sku, product in self._products.items():
            # Add some randomness to simulate real data
            variance = random.uniform(0.7, 1.3)
            orders = int(product["daily_orders"] * variance)
            revenue = round(orders * product["price"], 2)
            total_revenue += revenue
            total_orders += orders

            product_sales.append({
                "sku_code": sku,
                "product_name": product["name"],
                "units_sold": orders,
                "revenue": revenue,
                "avg_order_value": round(revenue / max(orders, 1), 2),
            })

        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "avg_order_value": round(total_revenue / max(total_orders, 1), 2),
            "product_sales": product_sales,
            "source": "shopify",
        }

    async def update_product_price(self, sku_code: str, new_price: float) -> Dict[str, Any]:
        """Update product price on Shopify (mock)."""
        if sku_code not in self._products:
            return {"success": False, "error": f"SKU {sku_code} not found"}

        old_price = self._products[sku_code]["price"]
        self._products[sku_code]["price"] = new_price

        return {
            "success": True,
            "sku_code": sku_code,
            "old_price": old_price,
            "new_price": new_price,
            "change_percent": round(((new_price - old_price) / old_price) * 100, 2),
            "updated_at": datetime.utcnow().isoformat(),
        }

    async def get_product_analytics(self, sku_code: str, days: int = 30) -> Dict[str, Any]:
        """Get product analytics for a specific SKU."""
        if sku_code not in self._products:
            return {"error": f"SKU {sku_code} not found"}

        product = self._products[sku_code]
        daily_data = []
        for i in range(days):
            date = datetime.utcnow() - timedelta(days=days - i)
            variance = random.uniform(0.6, 1.4)
            orders = int(product["daily_orders"] * variance)
            daily_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "units_sold": orders,
                "revenue": round(orders * product["price"], 2),
            })

        return {
            "sku_code": sku_code,
            "product_name": product["name"],
            "current_price": product["price"],
            "avg_daily_orders": product["daily_orders"],
            "daily_data": daily_data,
        }


# Singleton
commerce_service = CommerceService()
