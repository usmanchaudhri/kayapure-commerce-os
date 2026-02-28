/**
 * Mission Control Dashboard Layout
 * Persistent sidebar + top status bar + main content area
 * Includes backend connection status indicator
 */
import { ReactNode, useState, useEffect, useCallback } from "react";
import { Link, useLocation } from "wouter";
import {
  LayoutDashboard,
  ListChecks,
  Stethoscope,
  Server,
  Package,
  Brain,
  ChevronLeft,
  ChevronRight,
  Activity,
  Settings2,
  Wifi,
  WifiOff,
  Loader2,
  Radio,
} from "lucide-react";
import { testBackendConnection, getApiBase } from "@/lib/api";

const NAV_ITEMS = [
  { path: "/", label: "Control Tower", icon: LayoutDashboard },
  { path: "/actions", label: "Action Queue", icon: ListChecks },
  { path: "/inventory", label: "Inventory", icon: Package },
  { path: "/vm-telemetry", label: "VM Telemetry", icon: Server },
  { path: "/data-sources", label: "Data Sources", icon: Radio },
  { path: "/diagnostic", label: "Diagnostic", icon: Stethoscope },
  { path: "/settings", label: "Settings", icon: Settings2 },
];

type BackendStatus = "checking" | "online" | "offline";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Check backend connectivity on mount and every 30 seconds
  const checkBackend = useCallback(async () => {
    setBackendStatus("checking");
    const result = await testBackendConnection();
    setBackendStatus(result.ok ? "online" : "offline");
  }, []);

  useEffect(() => {
    checkBackend();
    const interval = setInterval(checkBackend, 30000);
    return () => clearInterval(interval);
  }, [checkBackend]);

  // Re-check when navigating (in case user just saved settings)
  useEffect(() => {
    checkBackend();
  }, [location, checkBackend]);

  const statusIndicator = {
    checking: {
      icon: <Loader2 className="w-3 h-3 animate-spin text-primary" />,
      text: "CHECKING",
      dotClass: "bg-primary status-dot",
    },
    online: {
      icon: <Wifi className="w-3 h-3 text-emerald-ok" />,
      text: "SYSTEMS NOMINAL",
      dotClass: "bg-emerald-ok status-dot",
    },
    offline: {
      icon: <WifiOff className="w-3 h-3 text-crimson-alert" />,
      text: "BACKEND OFFLINE",
      dotClass: "bg-crimson-alert status-dot",
    },
  };

  const si = statusIndicator[backendStatus];

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside
        className={`${
          collapsed ? "w-16" : "w-56"
        } flex flex-col border-r border-border bg-sidebar transition-all duration-300 shrink-0`}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-14 border-b border-sidebar-border">
          <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center shrink-0">
            <Brain className="w-5 h-5 text-primary" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <h1 className="text-sm font-bold text-foreground tracking-tight truncate">
                KayaPure OS
              </h1>
              <p className="text-[10px] text-muted-foreground font-mono">
                COMMERCE BRAIN v1.0
              </p>
            </div>
          )}
        </div>

        {/* Nav Items */}
        <nav className="flex-1 py-3 px-2 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = location === item.path;
            const Icon = item.icon;
            return (
              <Link key={item.path} href={item.path}>
                <div
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-all duration-200 group ${
                    isActive
                      ? "bg-primary/15 text-primary glow-cyan-sm"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent"
                  }`}
                >
                  <Icon
                    className={`w-4.5 h-4.5 shrink-0 ${
                      isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                    }`}
                  />
                  {!collapsed && (
                    <span className="truncate font-medium">{item.label}</span>
                  )}
                </div>
              </Link>
            );
          })}
        </nav>

        {/* Collapse Toggle */}
        <div className="px-2 pb-3">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex items-center justify-center w-full py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Status Bar */}
        <header className="h-14 border-b border-border bg-card/50 backdrop-blur-sm flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-4">
            <h2 className="text-sm font-semibold text-foreground">
              {NAV_ITEMS.find((n) => n.path === location)?.label || "Dashboard"}
            </h2>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <div className={`w-2 h-2 rounded-full shrink-0 ${si.dotClass}`} />
              <span className="font-mono">{si.text}</span>
            </div>
          </div>

          <div className="flex items-center gap-5">
            {/* Backend URL indicator */}
            {backendStatus === "offline" && (
              <Link href="/settings">
                <span className="text-[10px] font-mono text-crimson-alert hover:underline cursor-pointer">
                  Configure Backend →
                </span>
              </Link>
            )}
            <div className="flex items-center gap-2 text-xs">
              <Activity className="w-3.5 h-3.5 text-primary" />
              <span className="font-mono text-muted-foreground">
                UPTIME 99.97%
              </span>
            </div>
            <div className="text-xs font-mono text-muted-foreground tabular-nums">
              {currentTime.toLocaleTimeString("en-US", { hour12: false })} UTC
            </div>
          </div>
        </header>

        {/* Offline Banner */}
        {backendStatus === "offline" && (
          <div className="bg-crimson-alert/10 border-b border-crimson-alert/20 px-6 py-2 flex items-center gap-3">
            <WifiOff className="w-4 h-4 text-crimson-alert shrink-0" />
            <p className="text-xs text-crimson-alert">
              <span className="font-semibold">Backend unreachable</span> at{" "}
              <code className="text-crimson-alert/80">{getApiBase()}</code>.{" "}
              <Link href="/settings">
                <span className="underline cursor-pointer font-medium">Go to Settings</span>
              </Link>{" "}
              to configure the correct backend URL.
            </p>
          </div>
        )}

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
