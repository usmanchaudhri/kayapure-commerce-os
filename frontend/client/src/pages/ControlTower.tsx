/**
 * Control Tower - Main Dashboard
 * Design: Mission Control / Aerospace Command Center
 * Visualizes the LangGraph "Thinking" process, P&L metrics, and VM telemetry.
 */
import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  ShoppingCart,
  Megaphone,
  Truck,
  Play,
  Loader2,
  Brain,
  Cpu,
  ArrowRight,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { fetchPnLSummary, fetchMetrics, runAgentCycle, fetchAgentState, createWebSocket } from "@/lib/api";
import { toast } from "sonner";

const HERO_IMG = "https://private-us-east-1.manuscdn.com/sessionFile/wrtUf2bzqlcbMnFN5Kbroe/sandbox/M6g0BKFQi4swuwmDLfZbzd-img-1_1771848961000_na1fn_aGVyby1jb21tYW5kLWNlbnRlcg.png?x-oss-process=image/resize,w_1920,h_1920/format,webp/quality,q_80&Expires=1798761600&Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9wcml2YXRlLXVzLWVhc3QtMS5tYW51c2Nkbi5jb20vc2Vzc2lvbkZpbGUvd3J0VWYyYnpxbGNiTW5GTjVLYnJvZS9zYW5kYm94L002ZzBCS0ZRaTRzd3V3bURMZlpiemQtaW1nLTFfMTc3MTg0ODk2MTAwMF9uYTFmbl9hR1Z5YnkxamIyMXRZVzVrTFdObGJuUmxjZy5wbmc~eC1vc3MtcHJvY2Vzcz1pbWFnZS9yZXNpemUsd18xOTIwLGhfMTkyMC9mb3JtYXQsd2VicC9xdWFsaXR5LHFfODAiLCJDb25kaXRpb24iOnsiRGF0ZUxlc3NUaGFuIjp7IkFXUzpFcG9jaFRpbWUiOjE3OTg3NjE2MDB9fX1dfQ__&Key-Pair-Id=K2HSFNDJXOU9YS&Signature=tci04Bq08IvWxht-QbUctIUhdK4eSRTMQ4p357DHrlUifEYOpmRHIOdV8JGOkJhmarYg3miv8I6FwKXxMuBNIYvnn2DmRKlebt-zBz6tM5kn2h96rm5DZRtQ1u5a3EZA0U1pUzKUUpCOjJBSRCqUholNhEvT2aBrgXXENZt03DJbLXTK7adgIjYGoyq23jP5U~GOmzo1gYxZdvqOxpI4zjhNDhZMOELGKlDjgXUaSmGaC0TLjAJjUKJr3PTj5z2p0FLkWlZos5hR7G7lhdOcIhzNpLlZxJDVCLhozHYvnudJorTO6VnY5k05jaRaN~kJKdbhYmGqc8H3QI-GTKFLfw__";

const BRAIN_IMG = "https://private-us-east-1.manuscdn.com/sessionFile/wrtUf2bzqlcbMnFN5Kbroe/sandbox/M6g0BKFQi4swuwmDLfZbzd-img-3_1771848946000_na1fn_YWdlbnQtYnJhaW4tdmlzdWFsaXphdGlvbg.png?x-oss-process=image/resize,w_1920,h_1920/format,webp/quality,q_80&Expires=1798761600&Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9wcml2YXRlLXVzLWVhc3QtMS5tYW51c2Nkbi5jb20vc2Vzc2lvbkZpbGUvd3J0VWYyYnpxbGNiTW5GTjVLYnJvZS9zYW5kYm94L002ZzBCS0ZRaTRzd3V3bURMZlpiemQtaW1nLTNfMTc3MTg0ODk0NjAwMF9uYTFmbl9ZV2RsYm5RdFluSmhhVzR0ZG1semRXRnNhWHBoZEdsdmJnLnBuZz94LW9zcy1wcm9jZXNzPWltYWdlL3Jlc2l6ZSx3XzE5MjAsaF8xOTIwL2Zvcm1hdCx3ZWJwL3F1YWxpdHkscV84MCIsIkNvbmRpdGlvbiI6eyJEYXRlTGVzc1RoYW4iOnsiQVdTOkVwb2NoVGltZSI6MTc5ODc2MTYwMH19fV19&Key-Pair-Id=K2HSFNDJXOU9YS&Signature=oLcRO9xAjTO6WJMgdJ9sflcdV6GlMLRiFis3QcbKgXhsu574983IabAEh4ERWMFweZyVGEIOdC6oHE90BejTGrq03Kv2giS2JYd8VHymWhlqCHJSzMuDzy-VFSGVxa5ZY1gjdOU2K~iUfl2R4skCgz1gRHFQVXKMJ51qP7H19ZVM5YjP-igV6H8w2H9Fm2wHqXd1zfvqc9nFY7QUGzpmBLbAWqXcnLBV9rstRuDvqYNeMQtXOPUu5bvHjFI9GWILdcfGuCxqzFfoENmmeg~TJct80zLY4i5~mRSSmb6ndYvFLqPV6WGauIIoud~KT2YAVdN8B-2~TO4QsFvIeRjUYQ__";

const GRAPH_NODES = [
  { id: "sensor", label: "Sensor Node", desc: "Polling APIs" },
  { id: "pnl", label: "P&L Analyzer", desc: "Calculating margins" },
  { id: "strategy", label: "Strategy Agent", desc: "LLM reasoning" },
  { id: "approval", label: "Human Gate", desc: "Awaiting decision" },
  { id: "executor", label: "Firecracker VM", desc: "Isolated execution" },
];

export default function ControlTower() {
  const [pnl, setPnl] = useState<any>(null);
  const [metrics, setMetrics] = useState<any[]>([]);
  const [agentLogs, setAgentLogs] = useState<any[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const [cycleResult, setCycleResult] = useState<any>(null);

  useEffect(() => {
    fetchPnLSummary(7)
      .then((data) => {
        // Guard: if feature flag disabled, API returns {enabled: false, ...} instead of P&L object
        if (data && data.enabled !== false && data.total_revenue !== undefined) {
          setPnl(data);
        }
      })
      .catch(() => {});
    fetchMetrics(7)
      .then((data) => {
        // Guard: only set metrics if response is an array
        if (Array.isArray(data)) {
          setMetrics(data);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const ws = createWebSocket((data) => {
      if (data.type === "agent_log") {
        setAgentLogs((prev) => [...prev.slice(-50), data.data]);
        const node = data.data?.node;
        if (node) {
          const nodeMap: Record<string, string> = {
            sensor_node: "sensor",
            p_and_l_analyzer: "pnl",
            strategy_agent: "strategy",
            human_approval_gate: "approval",
            firecracker_executor: "executor",
          };
          setActiveNode(nodeMap[node] || null);
        }
      }
    });
    return () => ws.close();
  }, []);

  const handleRunCycle = useCallback(async () => {
    setIsRunning(true);
    setAgentLogs([]);
    setActiveNode("sensor");
    try {
      const result = await runAgentCycle();
      setCycleResult(result);
      toast.success(`Agent cycle complete: ${result.proposed_actions?.length || 0} actions proposed`);
      // Refresh P&L
      fetchPnLSummary(7)
        .then((data) => {
          if (data && data.enabled !== false && data.total_revenue !== undefined) setPnl(data);
        })
        .catch(() => {});
      fetchMetrics(7)
        .then((data) => {
          if (Array.isArray(data)) setMetrics(data);
        })
        .catch(() => {});
    } catch (e: any) {
      toast.error(`Agent cycle failed: ${e.message}`);
    } finally {
      setIsRunning(false);
      setActiveNode(null);
    }
  }, []);

  const chartData = metrics
    .map((m) => ({
      date: new Date(m.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      revenue: m.revenue,
      profit: m.net_profit,
      adSpend: m.ad_spend,
    }))
    .reverse();

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Hero Banner */}
      <div className="relative rounded-xl overflow-hidden h-48">
        <img
          src={HERO_IMG}
          alt="Command Center"
          className="absolute inset-0 w-full h-full object-cover opacity-40"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-background via-background/80 to-transparent" />
        <div className="relative z-10 flex items-center h-full px-8">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">
              Autonomous Commerce Control Tower
            </h1>
            <p className="text-sm text-muted-foreground mt-1 max-w-lg">
              Real-time P&L monitoring, agentic strategy execution, and hardware-isolated action deployment via Firecracker microVMs.
            </p>
            <Button
              onClick={handleRunCycle}
              disabled={isRunning}
              className="mt-4 glow-cyan"
              size="sm"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Agent Running...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Run Agent Cycle
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Net Revenue"
          value={pnl ? `$${pnl.total_revenue.toLocaleString()}` : "—"}
          subtitle="Last 7 days"
          icon={DollarSign}
          trend="up"
          color="cyan"
        />
        <KPICard
          title="Net Profit"
          value={pnl ? `$${pnl.net_profit.toLocaleString()}` : "—"}
          subtitle={pnl ? `${pnl.contribution_margin.toFixed(1)}% margin` : "—"}
          icon={TrendingUp}
          trend="up"
          color="emerald"
        />
        <KPICard
          title="Ad Spend"
          value={pnl ? `$${pnl.total_ad_spend.toLocaleString()}` : "—"}
          subtitle="Meta + Google"
          icon={Megaphone}
          trend="neutral"
          color="amber"
        />
        <KPICard
          title="Shipping"
          value={pnl ? `$${pnl.total_shipping.toLocaleString()}` : "—"}
          subtitle="Fulfillment costs"
          icon={Truck}
          trend="neutral"
          color="muted"
        />
      </div>

      {/* Main Grid: Chart + Graph Visualization */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Revenue Chart */}
        <Card className="lg:col-span-2 panel-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <ShoppingCart className="w-4 h-4 text-primary" />
              Revenue & Profit Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="oklch(0.75 0.14 200)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="oklch(0.75 0.14 200)" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="oklch(0.72 0.17 155)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="oklch(0.72 0.17 155)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.28 0.025 260)" />
                    <XAxis dataKey="date" tick={{ fill: "oklch(0.65 0.02 250)", fontSize: 11 }} />
                    <YAxis tick={{ fill: "oklch(0.65 0.02 250)", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "oklch(0.16 0.02 260)",
                        border: "1px solid oklch(0.28 0.025 260)",
                        borderRadius: "8px",
                        color: "oklch(0.92 0.01 250)",
                        fontSize: 12,
                      }}
                    />
                    <Area type="monotone" dataKey="revenue" stroke="oklch(0.75 0.14 200)" fill="url(#colorRevenue)" strokeWidth={2} />
                    <Area type="monotone" dataKey="profit" stroke="oklch(0.72 0.17 155)" fill="url(#colorProfit)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                  Run an agent cycle to populate data
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* LangGraph Visualization */}
        <Card className="panel-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Brain className="w-4 h-4 text-primary" />
              Agent Graph
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {GRAPH_NODES.map((node, i) => (
                <div key={node.id}>
                  <div
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all duration-300 ${
                      activeNode === node.id
                        ? "border-primary bg-primary/10 glow-cyan-sm"
                        : "border-border bg-card/50"
                    }`}
                  >
                    <div
                      className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                        activeNode === node.id
                          ? "bg-primary status-dot"
                          : "bg-muted-foreground/30"
                      }`}
                    />
                    <div className="flex-1">
                      <p className="text-xs font-semibold text-foreground">{node.label}</p>
                      <p className="text-[10px] text-muted-foreground font-mono">{node.desc}</p>
                    </div>
                    {activeNode === node.id && (
                      <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
                    )}
                  </div>
                  {i < GRAPH_NODES.length - 1 && (
                    <div className="flex justify-center py-0.5">
                      <div
                        className={`w-px h-3 ${
                          activeNode === GRAPH_NODES[i + 1]?.id || activeNode === node.id
                            ? "bg-primary"
                            : "bg-border"
                        }`}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent Logs */}
      <Card className="panel-border">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Cpu className="w-4 h-4 text-primary" />
              Agent Activity Log
            </CardTitle>
            <Badge variant="outline" className="text-[10px] font-mono">
              {agentLogs.length} entries
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-48">
            {agentLogs.length > 0 ? (
              <div className="space-y-1 font-mono text-xs">
                {agentLogs.map((log, i) => (
                  <div
                    key={i}
                    className="flex gap-3 py-1 px-2 rounded hover:bg-accent/50 animate-slide-in"
                  >
                    <span className="text-muted-foreground shrink-0 tabular-nums">
                      {new Date(log.timestamp).toLocaleTimeString("en-US", { hour12: false })}
                    </span>
                    <span
                      className={`shrink-0 w-24 text-right ${
                        log.node === "strategy_agent"
                          ? "text-amber-warn"
                          : log.node === "firecracker_executor"
                          ? "text-crimson-alert"
                          : "text-primary"
                      }`}
                    >
                      [{log.node?.replace(/_/g, " ").slice(0, 14)}]
                    </span>
                    <span className="text-foreground/80">{log.message}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                <span className="font-mono">Awaiting agent cycle...</span>
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

function KPICard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: any;
  trend: "up" | "down" | "neutral";
  color: "cyan" | "emerald" | "amber" | "muted";
}) {
  const colorMap = {
    cyan: "text-primary",
    emerald: "text-emerald-ok",
    amber: "text-amber-warn",
    muted: "text-muted-foreground",
  };
  const glowMap = {
    cyan: "glow-cyan-sm",
    emerald: "glow-emerald",
    amber: "glow-amber",
    muted: "",
  };

  return (
    <Card className={`panel-border ${glowMap[color]}`}>
      <CardContent className="pt-5 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{title}</p>
            <p className="text-xl font-bold text-foreground mt-1 font-mono tabular-nums">{value}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</p>
          </div>
          <div className={`p-2 rounded-lg bg-accent ${colorMap[color]}`}>
            <Icon className="w-4 h-4" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
