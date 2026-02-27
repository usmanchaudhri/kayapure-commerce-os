/**
 * Mission Control Dashboard Layout
 * Persistent sidebar + top status bar + main content area
 */
import { ReactNode, useState, useEffect } from "react";
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
} from "lucide-react";

const NAV_ITEMS = [
  { path: "/", label: "Control Tower", icon: LayoutDashboard },
  { path: "/actions", label: "Action Queue", icon: ListChecks },
  { path: "/inventory", label: "Inventory", icon: Package },
  { path: "/vm-telemetry", label: "VM Telemetry", icon: Server },
  { path: "/diagnostic", label: "Diagnostic", icon: Stethoscope },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

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
              <div className="status-dot bg-emerald-ok" />
              <span className="font-mono">SYSTEMS NOMINAL</span>
            </div>
          </div>

          <div className="flex items-center gap-5">
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

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
