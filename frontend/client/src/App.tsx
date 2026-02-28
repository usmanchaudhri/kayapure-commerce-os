import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import DashboardLayout from "./components/DashboardLayout";
import ControlTower from "./pages/ControlTower";
import ActionQueue from "./pages/ActionQueue";
import DiagnosticStorefront from "./pages/DiagnosticStorefront";
import VMTelemetry from "./pages/VMTelemetry";
import Inventory from "./pages/Inventory";
import Settings from "./pages/Settings";
import DataSources from "./pages/DataSources";

function Router() {
  return (
    <DashboardLayout>
      <Switch>
        <Route path="/" component={ControlTower} />
        <Route path="/actions" component={ActionQueue} />
        <Route path="/diagnostic" component={DiagnosticStorefront} />
        <Route path="/vm-telemetry" component={VMTelemetry} />
        <Route path="/inventory" component={Inventory} />
        <Route path="/data-sources" component={DataSources} />
        <Route path="/settings" component={Settings} />
        <Route path="/404" component={NotFound} />
        <Route component={NotFound} />
      </Switch>
    </DashboardLayout>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="dark">
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
