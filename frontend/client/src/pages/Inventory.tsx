/**
 * Inventory - SKU Management & Stock Monitoring
 * Design: Mission Control / Aerospace Command Center
 * Shows SKU-level inventory, stock risk indicators, and contribution margins.
 */
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Package,
  AlertTriangle,
  TrendingUp,
  Loader2,
  Truck,
  DollarSign,
  BarChart3,
} from "lucide-react";
import { fetchSKUs } from "@/lib/api";

export default function Inventory() {
  const [skus, setSkus] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSKUs()
      .then(setSkus)
      .catch((e) => console.error("Failed to load SKUs:", e))
      .finally(() => setLoading(false));
  }, []);

  const atRiskSkus = skus.filter((s) => s.days_of_stock < 14 && s.shipping_eta_days > 14);
  const totalStock = skus.reduce((sum, s) => sum + s.current_stock, 0);

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Inventory Management</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          SKU-level stock monitoring, cost analysis, and risk assessment
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard title="Total SKUs" value={skus.length.toString()} icon={Package} color="cyan" />
        <SummaryCard title="Total Stock" value={totalStock.toLocaleString()} icon={BarChart3} color="emerald" />
        <SummaryCard
          title="At Risk"
          value={atRiskSkus.length.toString()}
          icon={AlertTriangle}
          color={atRiskSkus.length > 0 ? "amber" : "emerald"}
        />
        <SummaryCard
          title="Avg Margin"
          value={
            skus.length > 0
              ? `${(skus.reduce((s, sk) => s + (sk.contribution_margin || 0), 0) / skus.length).toFixed(1)}%`
              : "—"
          }
          icon={TrendingUp}
          color="cyan"
        />
      </div>

      {/* SKU Table */}
      <Card className="panel-border">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Package className="w-4 h-4 text-primary" />
            Product SKUs
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-3 text-muted-foreground font-medium uppercase tracking-wider">Product</th>
                    <th className="text-left py-3 px-3 text-muted-foreground font-medium uppercase tracking-wider">SKU</th>
                    <th className="text-right py-3 px-3 text-muted-foreground font-medium uppercase tracking-wider">Price</th>
                    <th className="text-right py-3 px-3 text-muted-foreground font-medium uppercase tracking-wider">COGS</th>
                    <th className="text-right py-3 px-3 text-muted-foreground font-medium uppercase tracking-wider">Stock</th>
                    <th className="text-right py-3 px-3 text-muted-foreground font-medium uppercase tracking-wider">Days Left</th>
                    <th className="text-right py-3 px-3 text-muted-foreground font-medium uppercase tracking-wider">ETA</th>
                    <th className="text-right py-3 px-3 text-muted-foreground font-medium uppercase tracking-wider">Margin</th>
                    <th className="text-center py-3 px-3 text-muted-foreground font-medium uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {skus.map((sku) => {
                    const isAtRisk = sku.days_of_stock < 14 && sku.shipping_eta_days > 14;
                    const isLowStock = sku.days_of_stock < 14;
                    return (
                      <tr
                        key={sku.id}
                        className={`border-b border-border/50 hover:bg-accent/30 transition-colors ${
                          isAtRisk ? "bg-crimson-alert/5" : ""
                        }`}
                      >
                        <td className="py-3 px-3">
                          <p className="font-medium text-foreground text-sm">{sku.name.replace("KayaPure ", "")}</p>
                        </td>
                        <td className="py-3 px-3 font-mono text-muted-foreground">{sku.sku_code}</td>
                        <td className="py-3 px-3 text-right font-mono text-foreground">
                          ${sku.current_price?.toFixed(2)}
                          {sku.competitor_price && (
                            <span className={`block text-[10px] ${sku.competitor_price < sku.current_price ? "text-crimson-alert" : "text-emerald-ok"}`}>
                              vs ${sku.competitor_price?.toFixed(2)}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-muted-foreground">
                          ${sku.unit_cogs?.toFixed(2)}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <span className="font-mono text-foreground">{sku.current_stock}</span>
                          <div className="mt-1">
                            <Progress
                              value={Math.min((sku.current_stock / 800) * 100, 100)}
                              className="h-1"
                            />
                          </div>
                        </td>
                        <td className={`py-3 px-3 text-right font-mono ${isLowStock ? "text-crimson-alert font-semibold" : "text-foreground"}`}>
                          {sku.days_of_stock?.toFixed(0)}d
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-muted-foreground">
                          <div className="flex items-center justify-end gap-1">
                            <Truck className="w-3 h-3" />
                            {sku.shipping_eta_days}d
                          </div>
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-emerald-ok">
                          {sku.contribution_margin?.toFixed(1)}%
                        </td>
                        <td className="py-3 px-3 text-center">
                          {isAtRisk ? (
                            <Badge className="bg-crimson-alert/20 text-crimson-alert border-crimson-alert/30 text-[10px]">
                              <AlertTriangle className="w-3 h-3 mr-1" />
                              AT RISK
                            </Badge>
                          ) : isLowStock ? (
                            <Badge className="bg-amber-warn/20 text-amber-warn border-amber-warn/30 text-[10px]">
                              LOW
                            </Badge>
                          ) : (
                            <Badge className="bg-emerald-ok/20 text-emerald-ok border-emerald-ok/30 text-[10px]">
                              OK
                            </Badge>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: string;
  icon: any;
  color: "cyan" | "emerald" | "amber";
}) {
  const colorMap = {
    cyan: "text-primary",
    emerald: "text-emerald-ok",
    amber: "text-amber-warn",
  };

  return (
    <Card className="panel-border">
      <CardContent className="pt-5 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{title}</p>
            <p className="text-xl font-bold text-foreground mt-1 font-mono tabular-nums">{value}</p>
          </div>
          <div className={`p-2 rounded-lg bg-accent ${colorMap[color]}`}>
            <Icon className="w-4 h-4" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
