/**
 * Action Queue - Pending Agent Proposals
 * Design: Mission Control / Aerospace Command Center
 * Lists pending agent proposals with Approve/Deny buttons.
 */
import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  CheckCircle2,
  XCircle,
  Shield,
  Crosshair,
  Clock,
  Loader2,
  AlertTriangle,
  Zap,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { fetchActions, decideAction, createWebSocket } from "@/lib/api";
import { toast } from "sonner";

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  pending: { color: "text-amber-warn", bg: "bg-amber-warn/10", label: "PENDING" },
  approved: { color: "text-primary", bg: "bg-primary/10", label: "APPROVED" },
  denied: { color: "text-muted-foreground", bg: "bg-muted/50", label: "DENIED" },
  executing: { color: "text-primary", bg: "bg-primary/10", label: "EXECUTING" },
  completed: { color: "text-emerald-ok", bg: "bg-emerald-ok/10", label: "COMPLETED" },
  failed: { color: "text-crimson-alert", bg: "bg-crimson-alert/10", label: "FAILED" },
};

const ACTION_ICONS: Record<string, any> = {
  inventory_shield: Shield,
  competitor_snipe: Crosshair,
};

export default function ActionQueue() {
  const [actions, setActions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filter, setFilter] = useState<string>("all");

  const loadActions = useCallback(async () => {
    try {
      const data = await fetchActions();
      // Guard: only set actions if response is an array (feature flag may return object)
      if (Array.isArray(data)) {
        setActions(data);
      }
    } catch (e) {
      console.error("Failed to fetch actions:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadActions();
  }, [loadActions]);

  useEffect(() => {
    const ws = createWebSocket((data) => {
      if (data.type === "action_update") {
        setActions((prev) =>
          prev.map((a) =>
            a.id === data.data.id ? { ...a, status: data.data.status, result: data.data.result } : a
          )
        );
      }
    });
    return () => ws.close();
  }, []);

  const handleDecision = async (actionId: number, decision: "approve" | "deny") => {
    setProcessingId(actionId);
    try {
      await decideAction(actionId, decision);
      toast.success(`Action ${decision === "approve" ? "approved" : "denied"} successfully`);
      loadActions();
    } catch (e: any) {
      toast.error(`Failed: ${e.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const filteredActions = filter === "all" ? actions : actions.filter((a) => a.status === filter);
  const pendingCount = actions.filter((a) => a.status === "pending").length;

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Action Queue</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Review and approve agent-proposed actions
          </p>
        </div>
        <div className="flex items-center gap-3">
          {pendingCount > 0 && (
            <Badge className="bg-amber-warn/20 text-amber-warn border-amber-warn/30 font-mono">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {pendingCount} PENDING
            </Badge>
          )}
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2">
        {["all", "pending", "completed", "denied", "failed"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              filter === f
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            }`}
          >
            {f.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Action Cards */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      ) : filteredActions.length === 0 ? (
        <Card className="panel-border">
          <CardContent className="py-16 text-center">
            <Zap className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">No actions found</p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              Run an agent cycle from the Control Tower to generate proposals
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredActions.map((action) => {
            const Icon = ACTION_ICONS[action.action_type] || Zap;
            const status = STATUS_CONFIG[action.status] || STATUS_CONFIG.pending;
            const isExpanded = expandedId === action.id;
            const isPending = action.status === "pending";
            const isProcessing = processingId === action.id;

            return (
              <Card key={action.id} className="panel-border animate-slide-in">
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    {/* Icon */}
                    <div className={`p-2.5 rounded-lg ${status.bg} shrink-0 mt-0.5`}>
                      <Icon className={`w-5 h-5 ${status.color}`} />
                    </div>

                    {/* Content */}
                    <div className="flex-1">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="text-sm font-semibold text-foreground">{action.title}</h3>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant="outline" className={`text-[10px] font-mono ${status.color}`}>
                              {status.label}
                            </Badge>
                            <Badge variant="outline" className="text-[10px] font-mono">
                              {action.priority?.toUpperCase()}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground font-mono">
                              ID:{action.id}
                            </span>
                          </div>
                        </div>

                        {/* Action Buttons */}
                        {isPending && (
                          <div className="flex gap-2 shrink-0">
                            <Button
                              size="sm"
                              onClick={() => handleDecision(action.id, "approve")}
                              disabled={isProcessing}
                              className="bg-emerald-ok/20 text-emerald-ok hover:bg-emerald-ok/30 border border-emerald-ok/30"
                            >
                              {isProcessing ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <>
                                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                                  Approve
                                </>
                              )}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleDecision(action.id, "deny")}
                              disabled={isProcessing}
                              className="text-muted-foreground hover:text-crimson-alert hover:border-crimson-alert/30"
                            >
                              <XCircle className="w-3.5 h-3.5 mr-1" />
                              Deny
                            </Button>
                          </div>
                        )}
                      </div>

                      <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                        {action.description}
                      </p>

                      {/* Expandable Details */}
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : action.id)}
                        className="flex items-center gap-1 mt-2 text-[10px] text-primary hover:text-primary/80 transition-colors"
                      >
                        {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        {isExpanded ? "Hide details" : "Show details"}
                      </button>

                      {isExpanded && (
                        <div className="mt-3 p-3 rounded-lg bg-accent/30 border border-border">
                          {action.parameters && (
                            <div>
                              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Parameters</p>
                              <pre className="text-[11px] font-mono text-foreground/70 whitespace-pre-wrap">
                                {JSON.stringify(action.parameters, null, 2)}
                              </pre>
                            </div>
                          )}
                          {action.result && (
                            <div className="mt-3">
                              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Execution Result</p>
                              <pre className="text-[11px] font-mono text-foreground/70 whitespace-pre-wrap">
                                {JSON.stringify(action.result, null, 2)}
                              </pre>
                            </div>
                          )}
                          {action.reasoning && (
                            <div className="mt-3">
                              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Agent Reasoning</p>
                              <p className="text-xs text-foreground/70">{action.reasoning}</p>
                            </div>
                          )}
                          <div className="mt-2 text-[10px] text-muted-foreground font-mono">
                            Created: {new Date(action.created_at).toLocaleString()}
                            {action.vm_session_id && ` | VM: ${action.vm_session_id}`}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
