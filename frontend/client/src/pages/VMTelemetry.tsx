/**
 * VM Telemetry - Firecracker microVM monitoring
 * Design: Mission Control / Aerospace Command Center
 * Shows VM boot times, active sandboxes, and audit trail.
 */
import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Server,
  Cpu,
  Clock,
  Shield,
  Lock,
  CheckCircle2,
  XCircle,
  Loader2,
  Activity,
} from "lucide-react";
import { fetchVMAudits, fetchVMTelemetry, createWebSocket } from "@/lib/api";

const VM_IMG = "https://private-us-east-1.manuscdn.com/sessionFile/wrtUf2bzqlcbMnFN5Kbroe/sandbox/M6g0BKFQi4swuwmDLfZbzd-img-4_1771848943000_na1fn_ZmlyZWNyYWNrZXItdm0tYWJzdHJhY3Q.png?x-oss-process=image/resize,w_1920,h_1920/format,webp/quality,q_80&Expires=1798761600&Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9wcml2YXRlLXVzLWVhc3QtMS5tYW51c2Nkbi5jb20vc2Vzc2lvbkZpbGUvd3J0VWYyYnpxbGNiTW5GTjVLYnJvZS9zYW5kYm94L002ZzBCS0ZRaTRzd3V3bURMZlpiemQtaW1nLTRfMTc3MTg0ODk0MzAwMF9uYTFmbl9abWx5WldOeVlXTnJaWEl0ZG0wdFlXSnpkSEpoWTNRLnBuZz94LW9zcy1wcm9jZXNzPWltYWdlL3Jlc2l6ZSx3XzE5MjAsaF8xOTIwL2Zvcm1hdCx3ZWJwL3F1YWxpdHkscV84MCIsIkNvbmRpdGlvbiI6eyJEYXRlTGVzc1RoYW4iOnsiQVdTOkVwb2NoVGltZSI6MTc5ODc2MTYwMH19fV19&Key-Pair-Id=K2HSFNDJXOU9YS&Signature=aOn-Yq9SZpe73hjh5FWAJ0DTWcIlq--NJPB502ZLFXU31UY8GwvC6YIedBWsxoXlvv5bZ860ogD4bc8XHNeLu8bwwKYxFu7VWRcdQcqd4xmw9k1-OpLWg1dJbuFidILZ7q3PM2VUKbhBs2-gOGRMpd44HiOWCFOt5CLDih3sUY9iA0FGcIO7rTG6UYJlF4FFSTIAimnh0l7zhb5PIRPHLOogPYdkJmGmGUkADoISJ77E26aXaTAbW7QQmdBqVJewTqht~ON8ROO~Ipo9aDfWfoH1rzABKnN6bSb6NDP7TSN96af2WhZF2gcmfyffcchpYdjFJmz4u2h5KYqJxq~AHA__";

export default function VMTelemetry() {
  const [telemetry, setTelemetry] = useState<any>(null);
  const [audits, setAudits] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [vmEvents, setVmEvents] = useState<any[]>([]);

  const loadData = useCallback(async () => {
    try {
      const [tel, aud] = await Promise.all([fetchVMTelemetry(), fetchVMAudits()]);
      // Guard: only set data if responses are valid (feature flag may return {enabled: false})
      if (tel && tel.enabled !== false) setTelemetry(tel);
      if (Array.isArray(aud)) setAudits(aud);
    } catch (e) {
      console.error("Failed to load VM data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const ws = createWebSocket((data) => {
      if (data.type === "vm_telemetry") {
        setVmEvents((prev) => [...prev.slice(-30), data]);
        loadData();
      }
    });
    return () => ws.close();
  }, [loadData]);

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Hero */}
      <div className="relative rounded-xl overflow-hidden h-44">
        <img
          src={VM_IMG}
          alt="Firecracker VMs"
          className="absolute inset-0 w-full h-full object-cover opacity-25"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-background via-background/85 to-transparent" />
        <div className="relative z-10 flex items-center h-full px-8">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-5 h-5 text-primary" />
              <span className="text-xs font-mono text-primary uppercase tracking-widest">
                Hardware Isolation Layer
              </span>
            </div>
            <h1 className="text-2xl font-bold text-foreground">
              Firecracker VM Telemetry
            </h1>
            <p className="text-sm text-muted-foreground mt-1 max-w-lg">
              Monitor microVM boot times, execution sessions, and hardware-signed audit trails.
              Every action executes in a kernel-level isolated sandbox.
            </p>
          </div>
        </div>
      </div>

      {/* Telemetry KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <TelemetryCard
          title="Active VMs"
          value={telemetry?.active_vms?.toString() || "0"}
          icon={Server}
          color="cyan"
        />
        <TelemetryCard
          title="Completed Sessions"
          value={telemetry?.completed_vms?.toString() || "0"}
          icon={CheckCircle2}
          color="emerald"
        />
        <TelemetryCard
          title="Avg Boot Time"
          value={telemetry?.avg_boot_time_ms ? `${Math.round(telemetry.avg_boot_time_ms)}ms` : "—"}
          icon={Clock}
          color="amber"
        />
        <TelemetryCard
          title="Isolation Mode"
          value="MOCK"
          icon={Lock}
          color="muted"
        />
      </div>

      {/* VM Audit Trail */}
      <Card className="panel-border">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Cpu className="w-4 h-4 text-primary" />
              VM Audit Trail
            </CardTitle>
            <Badge variant="outline" className="text-[10px] font-mono">
              {audits.length} sessions
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
            </div>
          ) : audits.length === 0 ? (
            <div className="text-center py-12">
              <Server className="w-10 h-10 text-muted-foreground/20 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">No VM sessions recorded</p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                Approve an action from the Action Queue to trigger a Firecracker session
              </p>
            </div>
          ) : (
            <ScrollArea className="h-96">
              <div className="space-y-3">
                {audits.map((audit) => (
                  <div
                    key={audit.id}
                    className="p-4 rounded-lg bg-accent/20 border border-border animate-slide-in"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-2.5 h-2.5 rounded-full ${
                            audit.status === "completed"
                              ? "bg-emerald-ok"
                              : audit.status === "failed"
                              ? "bg-crimson-alert"
                              : "bg-amber-warn status-dot"
                          }`}
                        />
                        <div>
                          <p className="text-xs font-semibold font-mono text-foreground">
                            {audit.session_id}
                          </p>
                          <p className="text-[10px] text-muted-foreground font-mono">
                            Boot: {audit.vm_boot_time_ms}ms | Status: {audit.status?.toUpperCase()}
                          </p>
                        </div>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-[10px] font-mono ${
                          audit.status === "completed" ? "text-emerald-ok" : "text-crimson-alert"
                        }`}
                      >
                        {audit.status?.toUpperCase()}
                      </Badge>
                    </div>

                    {audit.hardware_signature && (
                      <div className="mt-2 flex items-center gap-2">
                        <Lock className="w-3 h-3 text-primary shrink-0" />
                        <p className="text-[10px] font-mono text-muted-foreground truncate">
                          HW-SIG: {audit.hardware_signature}
                        </p>
                      </div>
                    )}

                    {audit.execution_result && (
                      <div className="mt-2 p-2 rounded bg-card/50 border border-border">
                        <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
                          Execution Result
                        </p>
                        <pre className="text-[10px] font-mono text-foreground/60 whitespace-pre-wrap max-h-32 overflow-auto">
                          {JSON.stringify(audit.execution_result, null, 2)}
                        </pre>
                      </div>
                    )}

                    <div className="mt-2 flex items-center gap-4 text-[10px] text-muted-foreground font-mono">
                      <span>Created: {new Date(audit.created_at).toLocaleString()}</span>
                      {audit.completed_at && (
                        <span>Completed: {new Date(audit.completed_at).toLocaleString()}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      {/* Live VM Events */}
      {vmEvents.length > 0 && (
        <Card className="panel-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Activity className="w-4 h-4 text-primary" />
              Live VM Events
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-40">
              <div className="space-y-1 font-mono text-xs">
                {vmEvents.map((event, i) => (
                  <div key={i} className="flex gap-3 py-1 px-2 rounded hover:bg-accent/50">
                    <span className="text-muted-foreground shrink-0">
                      {new Date(event.data?.timestamp || Date.now()).toLocaleTimeString("en-US", { hour12: false })}
                    </span>
                    <span className="text-primary">[{event.event}]</span>
                    <span className="text-foreground/70 truncate">
                      {event.data?.session_id || "—"}
                    </span>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function TelemetryCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: string;
  icon: any;
  color: "cyan" | "emerald" | "amber" | "muted";
}) {
  const colorMap = {
    cyan: "text-primary",
    emerald: "text-emerald-ok",
    amber: "text-amber-warn",
    muted: "text-muted-foreground",
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
