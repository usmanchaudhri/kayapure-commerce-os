/**
 * Data Sources — Sensor Node Feed Viewer
 * Design: Mission Control / Aerospace Command Center
 *
 * Displays all data the Sensor Node polls from external services:
 * - Marketing (Meta Ads via MCP)
 * - Commerce (Shopify)
 * - Logistics (Flexport / Cart.com)
 * - Data Warehouse (PostgreSQL metrics + SKUs)
 * - MCP Connection Status
 *
 * Each source is shown as a collapsible panel with raw + formatted data,
 * last-polled timestamp, and connection status.
 */
import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Radio,
  Megaphone,
  ShoppingCart,
  Truck,
  Database,
  RefreshCcw,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Zap,
  Eye,
  Code,
  BarChart3,
  DollarSign,
  TrendingUp,
  Package,
  AlertTriangle,
} from "lucide-react";
import {
  fetchAdSpend,
  fetchDailySales,
  fetchInventory,
  fetchMCPStatus,
  fetchMetrics,
  fetchSKUs,
  fetchPnLSummary,
} from "@/lib/api";
import { toast } from "sonner";

type FeedStatus = "idle" | "loading" | "success" | "error";

interface DataFeed {
  id: string;
  name: string;
  source: string;
  protocol: string;
  icon: any;
  color: string;
  glowClass: string;
  description: string;
  status: FeedStatus;
  data: any;
  error: string | null;
  lastPolled: Date | null;
  latencyMs: number | null;
}

const INITIAL_FEEDS: DataFeed[] = [
  {
    id: "marketing",
    name: "Marketing — Meta Ads",
    source: "Pipeboard MCP Server",
    protocol: "MCP (JSON-RPC 2.0 / Streamable HTTP)",
    icon: Megaphone,
    color: "text-amber-warn",
    glowClass: "glow-amber",
    description: "Ad spend, campaign performance, CPC, CTR, and ROAS from Meta Ads via MCP.",
    status: "idle",
    data: null,
    error: null,
    lastPolled: null,
    latencyMs: null,
  },
  {
    id: "commerce",
    name: "Commerce — Shopify",
    source: "Shopify Admin API",
    protocol: "REST / GraphQL",
    icon: ShoppingCart,
    color: "text-primary",
    glowClass: "glow-cyan-sm",
    description: "Daily sales, order count, average order value, and top-selling products.",
    status: "idle",
    data: null,
    error: null,
    lastPolled: null,
    latencyMs: null,
  },
  {
    id: "logistics",
    name: "Logistics — Flexport / Cart.com",
    source: "Flexport API",
    protocol: "REST API",
    icon: Truck,
    color: "text-emerald-ok",
    glowClass: "glow-emerald",
    description: "Inventory levels, shipment status, warehouse stock, and fulfillment ETAs.",
    status: "idle",
    data: null,
    error: null,
    lastPolled: null,
    latencyMs: null,
  },
  {
    id: "dwh-metrics",
    name: "Data Warehouse — P&L Metrics",
    source: "PostgreSQL (kayapure_db)",
    protocol: "SQL / SQLAlchemy ORM",
    icon: Database,
    color: "text-purple-400",
    glowClass: "",
    description: "Historical revenue, COGS, ad spend, shipping costs, and margin calculations.",
    status: "idle",
    data: null,
    error: null,
    lastPolled: null,
    latencyMs: null,
  },
  {
    id: "dwh-skus",
    name: "Data Warehouse — SKU Catalog",
    source: "PostgreSQL (kayapure_db)",
    protocol: "SQL / SQLAlchemy ORM",
    icon: Package,
    color: "text-purple-400",
    glowClass: "",
    description: "Product catalog with COGS, pricing, stock levels, sales velocity, and competitor pricing.",
    status: "idle",
    data: null,
    error: null,
    lastPolled: null,
    latencyMs: null,
  },
  {
    id: "mcp-status",
    name: "MCP Connection Status",
    source: "MCP Client Manager",
    protocol: "Internal",
    icon: Zap,
    color: "text-primary",
    glowClass: "glow-cyan-sm",
    description: "Connection status, available tools, and configuration for all MCP servers.",
    status: "idle",
    data: null,
    error: null,
    lastPolled: null,
    latencyMs: null,
  },
];

export default function DataSources() {
  const [feeds, setFeeds] = useState<DataFeed[]>(INITIAL_FEEDS);
  const [isPollingAll, setIsPollingAll] = useState(false);
  const [expandedRaw, setExpandedRaw] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState("formatted");

  // Poll a single feed
  const pollFeed = useCallback(async (feedId: string) => {
    setFeeds((prev) =>
      prev.map((f) => (f.id === feedId ? { ...f, status: "loading" as FeedStatus } : f))
    );

    const start = performance.now();
    try {
      let data: any;
      switch (feedId) {
        case "marketing":
          data = await fetchAdSpend();
          break;
        case "commerce":
          data = await fetchDailySales();
          break;
        case "logistics":
          data = await fetchInventory();
          break;
        case "dwh-metrics":
          data = await fetchPnLSummary(7);
          break;
        case "dwh-skus":
          data = await fetchSKUs();
          break;
        case "mcp-status":
          data = await fetchMCPStatus();
          break;
        default:
          throw new Error("Unknown feed");
      }
      const latency = Math.round(performance.now() - start);

      setFeeds((prev) =>
        prev.map((f) =>
          f.id === feedId
            ? { ...f, status: "success" as FeedStatus, data, error: null, lastPolled: new Date(), latencyMs: latency }
            : f
        )
      );
    } catch (e: any) {
      const latency = Math.round(performance.now() - start);
      setFeeds((prev) =>
        prev.map((f) =>
          f.id === feedId
            ? { ...f, status: "error" as FeedStatus, error: e.message, lastPolled: new Date(), latencyMs: latency }
            : f
        )
      );
    }
  }, []);

  // Poll all feeds
  const pollAll = useCallback(async () => {
    setIsPollingAll(true);
    toast.info("Polling all data sources...");
    const feedIds = INITIAL_FEEDS.map((f) => f.id);
    await Promise.allSettled(feedIds.map((id) => pollFeed(id)));
    setIsPollingAll(false);
    toast.success("All data sources polled");
  }, [pollFeed]);

  // Auto-poll on mount
  useEffect(() => {
    pollAll();
  }, []);

  const toggleRaw = (feedId: string) => {
    setExpandedRaw((prev) => ({ ...prev, [feedId]: !prev[feedId] }));
  };

  const successCount = feeds.filter((f) => f.status === "success").length;
  const errorCount = feeds.filter((f) => f.status === "error").length;
  const loadingCount = feeds.filter((f) => f.status === "loading").length;

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Radio className="w-5 h-5 text-primary" />
            <span className="text-xs font-mono text-primary uppercase tracking-widest">
              Sensor Node
            </span>
          </div>
          <h1 className="text-2xl font-bold text-foreground">Data Sources</h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-xl">
            All external data feeds polled by the Sensor Node. Each source shows live connection status, response latency, and the raw data returned.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Summary badges */}
          <div className="flex items-center gap-2 text-xs font-mono">
            {successCount > 0 && (
              <Badge variant="outline" className="text-emerald-ok border-emerald-ok/30">
                <CheckCircle2 className="w-3 h-3 mr-1" />
                {successCount} OK
              </Badge>
            )}
            {errorCount > 0 && (
              <Badge variant="outline" className="text-crimson-alert border-crimson-alert/30">
                <XCircle className="w-3 h-3 mr-1" />
                {errorCount} FAIL
              </Badge>
            )}
            {loadingCount > 0 && (
              <Badge variant="outline" className="text-primary border-primary/30">
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                {loadingCount}
              </Badge>
            )}
          </div>
          <Button
            onClick={pollAll}
            disabled={isPollingAll}
            size="sm"
            className="glow-cyan"
          >
            {isPollingAll ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCcw className="w-4 h-4 mr-2" />
            )}
            Poll All Sources
          </Button>
        </div>
      </div>

      {/* Feed Cards */}
      <div className="space-y-4">
        {feeds.map((feed) => (
          <FeedCard
            key={feed.id}
            feed={feed}
            onPoll={() => pollFeed(feed.id)}
            rawExpanded={expandedRaw[feed.id] || false}
            onToggleRaw={() => toggleRaw(feed.id)}
          />
        ))}
      </div>
    </div>
  );
}

// ========================================
// Feed Card Component
// ========================================
function FeedCard({
  feed,
  onPoll,
  rawExpanded,
  onToggleRaw,
}: {
  feed: DataFeed;
  onPoll: () => void;
  rawExpanded: boolean;
  onToggleRaw: () => void;
}) {
  const Icon = feed.icon;

  const statusBadge = {
    idle: (
      <Badge variant="outline" className="text-muted-foreground text-[10px] font-mono">
        NOT POLLED
      </Badge>
    ),
    loading: (
      <Badge variant="outline" className="text-primary text-[10px] font-mono">
        <Loader2 className="w-3 h-3 mr-1 animate-spin" />
        POLLING...
      </Badge>
    ),
    success: (
      <Badge variant="outline" className="text-emerald-ok text-[10px] font-mono">
        <CheckCircle2 className="w-3 h-3 mr-1" />
        OK {feed.latencyMs ? `(${feed.latencyMs}ms)` : ""}
      </Badge>
    ),
    error: (
      <Badge variant="outline" className="text-crimson-alert text-[10px] font-mono">
        <XCircle className="w-3 h-3 mr-1" />
        ERROR
      </Badge>
    ),
  };

  return (
    <Card className={`panel-border transition-all duration-300 ${feed.status === "success" ? feed.glowClass : ""}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg bg-accent ${feed.color}`}>
              <Icon className="w-4.5 h-4.5" />
            </div>
            <div>
              <CardTitle className="text-sm font-semibold text-foreground">
                {feed.name}
              </CardTitle>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="text-[10px] font-mono text-muted-foreground">
                  {feed.source}
                </span>
                <span className="text-[10px] text-muted-foreground/50">•</span>
                <span className="text-[10px] font-mono text-muted-foreground/70">
                  {feed.protocol}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {statusBadge[feed.status]}
            {feed.lastPolled && (
              <span className="text-[10px] font-mono text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {feed.lastPolled.toLocaleTimeString("en-US", { hour12: false })}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={onPoll}
              disabled={feed.status === "loading"}
              className="h-7 px-2.5"
            >
              {feed.status === "loading" ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCcw className="w-3.5 h-3.5" />
              )}
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-2">{feed.description}</p>
      </CardHeader>

      {/* Data Content */}
      {feed.status === "error" && (
        <CardContent className="pt-0">
          <div className="p-3 rounded-lg bg-crimson-alert/5 border border-crimson-alert/20">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-crimson-alert shrink-0" />
              <span className="text-xs text-crimson-alert font-mono">{feed.error}</span>
            </div>
          </div>
        </CardContent>
      )}

      {feed.status === "success" && feed.data && (
        <CardContent className="pt-0">
          <Tabs defaultValue="formatted" className="w-full">
            <TabsList className="h-8 bg-accent/30">
              <TabsTrigger value="formatted" className="text-xs h-6 gap-1.5">
                <Eye className="w-3 h-3" />
                Formatted
              </TabsTrigger>
              <TabsTrigger value="raw" className="text-xs h-6 gap-1.5">
                <Code className="w-3 h-3" />
                Raw JSON
              </TabsTrigger>
            </TabsList>

            <TabsContent value="formatted" className="mt-3">
              <FormattedView feedId={feed.id} data={feed.data} />
            </TabsContent>

            <TabsContent value="raw" className="mt-3">
              <ScrollArea className="h-64">
                <pre className="text-[11px] font-mono text-muted-foreground bg-accent/20 p-4 rounded-lg border border-border overflow-x-auto whitespace-pre-wrap break-words">
                  {JSON.stringify(feed.data, null, 2)}
                </pre>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </CardContent>
      )}
    </Card>
  );
}

// ========================================
// Formatted Data Views per Feed
// ========================================
function FormattedView({ feedId, data }: { feedId: string; data: any }) {
  switch (feedId) {
    case "marketing":
      return <MarketingView data={data} />;
    case "commerce":
      return <CommerceView data={data} />;
    case "logistics":
      return <LogisticsView data={data} />;
    case "dwh-metrics":
      return <MetricsView data={data} />;
    case "dwh-skus":
      return <SKUView data={data} />;
    case "mcp-status":
      return <MCPStatusView data={data} />;
    default:
      return <pre className="text-xs font-mono">{JSON.stringify(data, null, 2)}</pre>;
  }
}

// --- Marketing (Meta Ads) ---
function MarketingView({ data }: { data: any }) {
  const campaigns = data?.campaigns || [];
  const summary = data?.summary || {};

  return (
    <div className="space-y-4">
      {/* Summary Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniKPI label="Total Spend" value={`$${summary.total_spend?.toFixed(2) || "0"}`} icon={DollarSign} color="text-amber-warn" />
        <MiniKPI label="Total Clicks" value={summary.total_clicks?.toLocaleString() || "0"} icon={BarChart3} color="text-primary" />
        <MiniKPI label="Avg CTR" value={`${summary.avg_ctr?.toFixed(2) || "0"}%`} icon={TrendingUp} color="text-emerald-ok" />
        <MiniKPI label="Source" value={summary.source === "mcp" ? "LIVE MCP" : summary.source?.toUpperCase() || "—"} icon={Zap} color={summary.source === "mcp" ? "text-emerald-ok" : "text-muted-foreground"} />
      </div>

      {/* Campaign Table */}
      {campaigns.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-accent/30 text-muted-foreground font-mono uppercase tracking-wider">
                <th className="text-left px-3 py-2">Campaign</th>
                <th className="text-right px-3 py-2">Spend</th>
                <th className="text-right px-3 py-2">Clicks</th>
                <th className="text-right px-3 py-2">Impr.</th>
                <th className="text-right px-3 py-2">CTR</th>
                <th className="text-right px-3 py-2">CPC</th>
                <th className="text-center px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c: any, i: number) => (
                <tr key={i} className="border-t border-border hover:bg-accent/10 transition-colors">
                  <td className="px-3 py-2 text-foreground font-medium max-w-[200px] truncate">{c.campaign_name || c.name || "—"}</td>
                  <td className="px-3 py-2 text-right font-mono text-amber-warn">${Number(c.spend || 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right font-mono text-foreground">{Number(c.clicks || 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right font-mono text-muted-foreground">{Number(c.impressions || 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right font-mono text-primary">{Number(c.ctr || 0).toFixed(2)}%</td>
                  <td className="px-3 py-2 text-right font-mono text-muted-foreground">${Number(c.cpc || 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-center">
                    <Badge variant="outline" className={`text-[9px] ${c.status === "ACTIVE" ? "text-emerald-ok border-emerald-ok/30" : "text-muted-foreground"}`}>
                      {c.status || "—"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// --- Commerce (Shopify) ---
function CommerceView({ data }: { data: any }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniKPI label="Total Revenue" value={`$${data?.total_revenue?.toFixed(2) || "0"}`} icon={DollarSign} color="text-primary" />
        <MiniKPI label="Orders" value={data?.order_count?.toString() || "0"} icon={ShoppingCart} color="text-emerald-ok" />
        <MiniKPI label="Avg Order Value" value={`$${data?.avg_order_value?.toFixed(2) || "0"}`} icon={TrendingUp} color="text-amber-warn" />
        <MiniKPI label="Source" value={data?.source?.toUpperCase() || "MOCK"} icon={Zap} color="text-muted-foreground" />
      </div>
      {data?.top_products && data.top_products.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-accent/30 text-muted-foreground font-mono uppercase tracking-wider">
                <th className="text-left px-3 py-2">Product</th>
                <th className="text-right px-3 py-2">Units</th>
                <th className="text-right px-3 py-2">Revenue</th>
              </tr>
            </thead>
            <tbody>
              {data.top_products.map((p: any, i: number) => (
                <tr key={i} className="border-t border-border hover:bg-accent/10 transition-colors">
                  <td className="px-3 py-2 text-foreground font-medium">{p.name || p.product_name || "—"}</td>
                  <td className="px-3 py-2 text-right font-mono text-foreground">{p.units_sold || p.quantity || "—"}</td>
                  <td className="px-3 py-2 text-right font-mono text-primary">${Number(p.revenue || 0).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// --- Logistics ---
function LogisticsView({ data }: { data: any }) {
  const items = data?.items || data?.warehouses || [];
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniKPI label="Total Units" value={data?.total_units?.toLocaleString() || data?.summary?.total_units?.toLocaleString() || "—"} icon={Package} color="text-emerald-ok" />
        <MiniKPI label="In Transit" value={data?.in_transit?.toString() || data?.summary?.in_transit?.toString() || "—"} icon={Truck} color="text-amber-warn" />
        <MiniKPI label="Low Stock" value={data?.low_stock_count?.toString() || data?.summary?.low_stock?.toString() || "—"} icon={AlertTriangle} color="text-crimson-alert" />
        <MiniKPI label="Source" value={data?.source?.toUpperCase() || "MOCK"} icon={Zap} color="text-muted-foreground" />
      </div>
      {items.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-accent/30 text-muted-foreground font-mono uppercase tracking-wider">
                <th className="text-left px-3 py-2">Location / SKU</th>
                <th className="text-right px-3 py-2">Quantity</th>
                <th className="text-right px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 10).map((item: any, i: number) => (
                <tr key={i} className="border-t border-border hover:bg-accent/10 transition-colors">
                  <td className="px-3 py-2 text-foreground font-medium">{item.name || item.warehouse || item.sku || "—"}</td>
                  <td className="px-3 py-2 text-right font-mono text-foreground">{item.quantity || item.units || "—"}</td>
                  <td className="px-3 py-2 text-right">
                    <Badge variant="outline" className={`text-[9px] ${item.status === "healthy" || item.status === "ok" ? "text-emerald-ok" : "text-amber-warn"}`}>
                      {item.status || "—"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// --- DWH Metrics (P&L) ---
function MetricsView({ data }: { data: any }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <MiniKPI label="Revenue" value={`$${data?.total_revenue?.toLocaleString() || "0"}`} icon={DollarSign} color="text-primary" />
      <MiniKPI label="COGS" value={`$${data?.total_cogs?.toLocaleString() || "0"}`} icon={Package} color="text-muted-foreground" />
      <MiniKPI label="Ad Spend" value={`$${data?.total_ad_spend?.toLocaleString() || "0"}`} icon={Megaphone} color="text-amber-warn" />
      <MiniKPI label="Net Profit" value={`$${data?.net_profit?.toLocaleString() || "0"}`} icon={TrendingUp} color="text-emerald-ok" />
      <MiniKPI label="Gross Profit" value={`$${data?.gross_profit?.toLocaleString() || "0"}`} icon={BarChart3} color="text-primary" />
      <MiniKPI label="Shipping" value={`$${data?.total_shipping?.toLocaleString() || "0"}`} icon={Truck} color="text-muted-foreground" />
      <MiniKPI label="Margin" value={`${data?.contribution_margin?.toFixed(1) || "0"}%`} icon={TrendingUp} color="text-emerald-ok" />
      <MiniKPI label="Period" value={data?.period?.replace(/_/g, " ") || "—"} icon={Clock} color="text-muted-foreground" />
    </div>
  );
}

// --- DWH SKUs ---
function SKUView({ data }: { data: any }) {
  const skus = Array.isArray(data) ? data : [];
  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <ScrollArea className="max-h-64">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-accent/30 text-muted-foreground font-mono uppercase tracking-wider sticky top-0">
              <th className="text-left px-3 py-2">SKU</th>
              <th className="text-left px-3 py-2">Name</th>
              <th className="text-right px-3 py-2">Price</th>
              <th className="text-right px-3 py-2">COGS</th>
              <th className="text-right px-3 py-2">Stock</th>
              <th className="text-right px-3 py-2">Velocity</th>
              <th className="text-right px-3 py-2">Days Left</th>
              <th className="text-right px-3 py-2">Margin</th>
            </tr>
          </thead>
          <tbody>
            {skus.map((sku: any, i: number) => {
              const daysLeft = sku.days_of_stock || (sku.current_stock / Math.max(sku.daily_sales_velocity, 1));
              const isLow = daysLeft < 14;
              return (
                <tr key={i} className="border-t border-border hover:bg-accent/10 transition-colors">
                  <td className="px-3 py-2 font-mono text-primary">{sku.sku_code}</td>
                  <td className="px-3 py-2 text-foreground font-medium max-w-[180px] truncate">{sku.name}</td>
                  <td className="px-3 py-2 text-right font-mono text-foreground">${sku.current_price?.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right font-mono text-muted-foreground">${sku.unit_cogs?.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right font-mono text-foreground">{sku.current_stock?.toLocaleString()}</td>
                  <td className="px-3 py-2 text-right font-mono text-muted-foreground">{sku.daily_sales_velocity}/day</td>
                  <td className={`px-3 py-2 text-right font-mono ${isLow ? "text-crimson-alert" : "text-emerald-ok"}`}>
                    {Math.round(daysLeft)}d
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-emerald-ok">{sku.contribution_margin?.toFixed(1)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </ScrollArea>
    </div>
  );
}

// --- MCP Status ---
function MCPStatusView({ data }: { data: any }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniKPI
          label="MCP Enabled"
          value={data?.mcp_enabled ? "YES" : "NO"}
          icon={Zap}
          color={data?.mcp_enabled ? "text-emerald-ok" : "text-crimson-alert"}
        />
        <MiniKPI
          label="Meta Ads"
          value={data?.meta_ads?.connected ? "CONNECTED" : "DISCONNECTED"}
          icon={Megaphone}
          color={data?.meta_ads?.connected ? "text-emerald-ok" : "text-crimson-alert"}
        />
        <MiniKPI
          label="Tools Available"
          value={data?.meta_ads?.tools_available?.toString() || "0"}
          icon={Code}
          color="text-primary"
        />
        <MiniKPI
          label="Service Mode"
          value={data?.marketing_service_mode?.toUpperCase() || "—"}
          icon={Radio}
          color={data?.marketing_service_mode === "mcp" ? "text-emerald-ok" : "text-amber-warn"}
        />
      </div>
      <div className="p-3 rounded-lg bg-accent/20 border border-border">
        <div className="text-[11px] font-mono text-muted-foreground space-y-1">
          <div>
            <span className="text-foreground/60">Server URL:</span>{" "}
            <span className="text-primary">{data?.meta_ads?.server_url || "—"}</span>
          </div>
          <div>
            <span className="text-foreground/60">Account ID:</span>{" "}
            <span className="text-foreground">{data?.meta_ads?.account_id || "—"}</span>
          </div>
          <div>
            <span className="text-foreground/60">Timestamp:</span>{" "}
            <span className="text-foreground">{data?.timestamp || "—"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ========================================
// Mini KPI Card
// ========================================
function MiniKPI({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: any;
  color: string;
}) {
  return (
    <div className="p-3 rounded-lg bg-accent/20 border border-border">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-3.5 h-3.5 ${color}`} />
        <span className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">{label}</span>
      </div>
      <p className={`text-sm font-bold font-mono ${color}`}>{value}</p>
    </div>
  );
}
