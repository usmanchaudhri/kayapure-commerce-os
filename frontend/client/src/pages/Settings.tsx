/**
 * Settings - Backend Connection Configuration
 * Design: Mission Control / Aerospace Command Center
 * Allows user to configure the backend API URL and test connectivity.
 */
import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Settings2,
  Wifi,
  WifiOff,
  Loader2,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Save,
  Globe,
  Zap,
  Server,
  ExternalLink,
} from "lucide-react";
import {
  getApiBase,
  getWsBase,
  setBackendUrl,
  clearBackendUrl,
  testBackendConnection,
} from "@/lib/api";
import { toast } from "sonner";

type ConnectionStatus = "untested" | "testing" | "connected" | "failed";

export default function Settings() {
  const [backendUrl, setUrl] = useState(getApiBase());
  const [status, setStatus] = useState<ConnectionStatus>("untested");
  const [latency, setLatency] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<any>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Test connection on mount
  useEffect(() => {
    handleTest();
  }, []);

  const handleTest = useCallback(async (url?: string) => {
    const testUrl = url || backendUrl;
    setStatus("testing");
    setErrorMsg(null);
    setHealthData(null);

    const result = await testBackendConnection(testUrl);

    if (result.ok) {
      setStatus("connected");
      setLatency(result.latency || null);
      setHealthData(result.data);
    } else {
      setStatus("failed");
      setLatency(result.latency || null);
      setErrorMsg(result.error || "Unknown error");
    }
  }, [backendUrl]);

  const handleSave = useCallback(async () => {
    setIsSaving(true);

    // Test first
    const result = await testBackendConnection(backendUrl);

    if (result.ok) {
      setBackendUrl(backendUrl);
      setStatus("connected");
      setLatency(result.latency || null);
      setHealthData(result.data);
      toast.success("Backend URL saved. All API calls will now use this endpoint.");
    } else {
      setStatus("failed");
      setLatency(result.latency || null);
      setErrorMsg(result.error || "Unknown error");
      // Still save — user might want to save and fix later
      setBackendUrl(backendUrl);
      toast.warning("URL saved but connection failed. Check the backend is running.");
    }

    setIsSaving(false);
  }, [backendUrl]);

  const handleReset = useCallback(() => {
    clearBackendUrl();
    const newUrl = getApiBase();
    setUrl(newUrl);
    setStatus("untested");
    setLatency(null);
    setErrorMsg(null);
    setHealthData(null);
    toast.info("Reset to auto-detected URL. Testing connection...");
    handleTest(newUrl);
  }, [handleTest]);

  const statusColor = {
    untested: "text-muted-foreground",
    testing: "text-primary",
    connected: "text-emerald-ok",
    failed: "text-crimson-alert",
  };

  const statusIcon = {
    untested: <WifiOff className="w-4 h-4" />,
    testing: <Loader2 className="w-4 h-4 animate-spin" />,
    connected: <Wifi className="w-4 h-4" />,
    failed: <XCircle className="w-4 h-4" />,
  };

  return (
    <div className="space-y-6 animate-fade-in-up max-w-3xl">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Settings2 className="w-5 h-5 text-primary" />
          <span className="text-xs font-mono text-primary uppercase tracking-widest">
            System Configuration
          </span>
        </div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure the backend API connection for the KayaPure Commerce OS dashboard.
        </p>
      </div>

      {/* Connection Status Card */}
      <Card className="panel-border">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Server className="w-4 h-4 text-primary" />
              Backend Connection
            </CardTitle>
            <Badge
              variant="outline"
              className={`text-[10px] font-mono ${statusColor[status]}`}
            >
              {statusIcon[status]}
              <span className="ml-1.5">
                {status === "untested" && "NOT TESTED"}
                {status === "testing" && "TESTING..."}
                {status === "connected" && "CONNECTED"}
                {status === "failed" && "FAILED"}
              </span>
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* URL Input */}
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider block mb-2">
              Backend API URL
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="url"
                  value={backendUrl}
                  onChange={(e) => {
                    setUrl(e.target.value);
                    setStatus("untested");
                  }}
                  placeholder="http://your-server-ip:8000"
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-accent/30 border border-border text-sm font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleTest()}
                disabled={status === "testing" || !backendUrl}
                className="px-4"
              >
                {status === "testing" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Zap className="w-4 h-4" />
                )}
                <span className="ml-1.5">Test</span>
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground mt-1.5">
              Enter the full URL of your KayaPure backend (e.g., <code className="text-primary/80">http://192.168.1.100:8000</code>).
              The backend must have CORS enabled for this domain.
            </p>
          </div>

          {/* Connection Result */}
          {status === "connected" && (
            <div className="p-4 rounded-lg bg-emerald-ok/5 border border-emerald-ok/20">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-ok" />
                <span className="text-sm font-semibold text-emerald-ok">Connection Successful</span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div>
                  <span className="text-muted-foreground">Latency:</span>{" "}
                  <span className="text-foreground">{latency}ms</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Service:</span>{" "}
                  <span className="text-foreground">{healthData?.service || "—"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Version:</span>{" "}
                  <span className="text-foreground">{healthData?.version || "—"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Status:</span>{" "}
                  <span className="text-emerald-ok">{healthData?.status || "—"}</span>
                </div>
              </div>
            </div>
          )}

          {status === "failed" && (
            <div className="p-4 rounded-lg bg-crimson-alert/5 border border-crimson-alert/20">
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-4 h-4 text-crimson-alert" />
                <span className="text-sm font-semibold text-crimson-alert">Connection Failed</span>
              </div>
              <p className="text-xs text-muted-foreground">{errorMsg}</p>
              {latency && (
                <p className="text-[10px] text-muted-foreground/60 mt-1 font-mono">
                  Response time: {latency}ms
                </p>
              )}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center gap-3 pt-2">
            <Button
              onClick={handleSave}
              disabled={isSaving || !backendUrl}
              size="sm"
              className="glow-cyan"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              Save & Apply
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleReset}
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset to Default
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* WebSocket Info */}
      <Card className="panel-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" />
            WebSocket Connection
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-accent/20 border border-border">
            <div className="text-xs font-mono text-muted-foreground">
              <span className="text-foreground/60">WS Endpoint:</span>{" "}
              <span className="text-primary">{getWsBase()}/ws</span>
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground mt-2">
            WebSocket URL is automatically derived from the backend URL. Used for real-time agent logs and VM telemetry events.
          </p>
        </CardContent>
      </Card>

      {/* Help Card */}
      <Card className="panel-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <ExternalLink className="w-4 h-4 text-primary" />
            Troubleshooting
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-xs text-muted-foreground">
            <div className="p-3 rounded-lg bg-accent/20 border border-border">
              <p className="font-semibold text-foreground mb-1">Backend not reachable?</p>
              <ol className="list-decimal list-inside space-y-1">
                <li>Ensure the FastAPI backend is running: <code className="text-primary/80">uvicorn main:app --host 0.0.0.0 --port 8000</code></li>
                <li>Use <code className="text-primary/80">0.0.0.0</code> (not <code>127.0.0.1</code>) so it accepts external connections</li>
                <li>Check firewall allows port 8000 inbound</li>
                <li>If using HTTPS dashboard, backend must also serve HTTPS or use a tunnel</li>
              </ol>
            </div>
            <div className="p-3 rounded-lg bg-accent/20 border border-border">
              <p className="font-semibold text-foreground mb-1">CORS errors?</p>
              <p>The backend is configured with <code className="text-primary/80">allow_origins=["*"]</code> by default. If you've restricted it, add <code className="text-primary/80">https://kayadash-zhipbxxk.manus.space</code> to the allowed origins.</p>
            </div>
            <div className="p-3 rounded-lg bg-accent/20 border border-border">
              <p className="font-semibold text-foreground mb-1">Mixed content (HTTPS → HTTP)?</p>
              <p>This dashboard is served over HTTPS. Browsers block HTTP API calls from HTTPS pages. Solutions:</p>
              <ol className="list-decimal list-inside space-y-1 mt-1">
                <li>Use a reverse proxy (nginx/Caddy) with SSL in front of the backend</li>
                <li>Use a tunnel like <code className="text-primary/80">ngrok http 8000</code> to get an HTTPS URL</li>
                <li>Run the dashboard locally over HTTP instead</li>
              </ol>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
