/**
 * KayaPure Commerce OS - API Client
 * Connects to the FastAPI backend.
 *
 * Backend URL resolution priority:
 * 1. localStorage "kayapure_api_base" (user-configured via Settings page)
 * 2. VITE_API_BASE env var (build-time)
 * 3. Auto-detect Manus dev proxy (3000- → 8000-)
 * 4. Fallback: http://localhost:8000
 */

const STORAGE_KEY = "kayapure_api_base";
const WS_STORAGE_KEY = "kayapure_ws_base";

function resolveApiBase(): string {
  // 1. User-configured via Settings
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) return stored.replace(/\/$/, "");

  // 2. Explicit env var
  const envBase = import.meta.env.VITE_API_BASE;
  if (envBase) return envBase.replace(/\/$/, "");

  // 3. Auto-detect Manus dev proxy: replace "3000-" prefix with "8000-"
  const host = window.location.hostname;
  if (
    (host.includes("manus.computer") || host.includes("manus.space")) &&
    host.startsWith("3000-")
  ) {
    const backendHost = host.replace(/^3000-/, "8000-");
    return `${window.location.protocol}//${backendHost}`;
  }

  // 4. Fallback for local development
  return "http://localhost:8000";
}

function resolveWsBase(): string {
  // 1. User-configured
  const stored = localStorage.getItem(WS_STORAGE_KEY);
  if (stored) return stored.replace(/\/$/, "");

  // Derive from API base
  const apiBase = resolveApiBase();
  try {
    const url = new URL(apiBase);
    const wsProtocol = url.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProtocol}//${url.host}`;
  } catch {
    return "ws://localhost:8000";
  }
}

let API_BASE = resolveApiBase();
let WS_BASE = resolveWsBase();

/** Get the current API base URL */
export function getApiBase(): string {
  return API_BASE;
}

/** Get the current WebSocket base URL */
export function getWsBase(): string {
  return WS_BASE;
}

/** Update the backend URL at runtime (called from Settings page) */
export function setBackendUrl(httpUrl: string): void {
  const cleanUrl = httpUrl.replace(/\/$/, "");
  localStorage.setItem(STORAGE_KEY, cleanUrl);

  // Auto-derive WS URL
  try {
    const url = new URL(cleanUrl);
    const wsProtocol = url.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${url.host}`;
    localStorage.setItem(WS_STORAGE_KEY, wsUrl);
  } catch {
    // If URL parsing fails, clear WS override
    localStorage.removeItem(WS_STORAGE_KEY);
  }

  // Re-resolve
  API_BASE = resolveApiBase();
  WS_BASE = resolveWsBase();
}

/** Clear the stored backend URL and revert to auto-detection */
export function clearBackendUrl(): void {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(WS_STORAGE_KEY);
  API_BASE = resolveApiBase();
  WS_BASE = resolveWsBase();
}

/** Test connectivity to the backend */
export async function testBackendConnection(url?: string): Promise<{
  ok: boolean;
  latency?: number;
  error?: string;
  data?: any;
}> {
  const base = url ? url.replace(/\/$/, "") : API_BASE;
  const start = performance.now();
  try {
    const res = await fetch(`${base}/api/health`, {
      method: "GET",
      signal: AbortSignal.timeout(8000),
    });
    const latency = Math.round(performance.now() - start);
    if (!res.ok) {
      return { ok: false, latency, error: `HTTP ${res.status}: ${res.statusText}` };
    }
    const data = await res.json();
    return { ok: true, latency, data };
  } catch (e: any) {
    const latency = Math.round(performance.now() - start);
    const msg =
      e.name === "TimeoutError"
        ? "Connection timed out (8s)"
        : e.message === "Failed to fetch"
        ? "Cannot reach backend — check URL and CORS settings"
        : e.message;
    return { ok: false, latency, error: msg };
  }
}

// --- Core fetch helper ---
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API Error: ${res.status}`);
  }
  return res.json();
}

// --- SKU Endpoints ---
export async function fetchSKUs() {
  return fetchAPI<any[]>("/api/skus");
}

// --- Metrics Endpoints ---
export async function fetchMetrics(limit = 30) {
  return fetchAPI<any[]>(`/api/metrics?limit=${limit}`);
}

export async function fetchPnLSummary(days = 7) {
  return fetchAPI<any>(`/api/metrics/pnl-summary?days=${days}`);
}

// --- Action Endpoints ---
export async function fetchActions(status?: string) {
  const params = status ? `?status=${status}` : "";
  return fetchAPI<any[]>(`/api/actions${params}`);
}

export async function decideAction(actionId: number, decision: "approve" | "deny", comment?: string) {
  return fetchAPI<any>(`/api/actions/${actionId}/decide`, {
    method: "POST",
    body: JSON.stringify({ action: decision, comment }),
  });
}

// --- Agent Endpoints ---
export async function runAgentCycle() {
  return fetchAPI<any>("/api/agent/run-cycle", { method: "POST" });
}

export async function fetchAgentState() {
  return fetchAPI<any>("/api/agent/state");
}

// --- VM Endpoints ---
export async function fetchVMAudits(limit = 50) {
  return fetchAPI<any[]>(`/api/vm-audit?limit=${limit}`);
}

export async function fetchVMTelemetry() {
  return fetchAPI<any>("/api/vm/telemetry");
}

// --- Commerce Data ---
export async function fetchDailySales() {
  return fetchAPI<any>("/api/commerce/daily-sales");
}

export async function fetchAdSpend() {
  return fetchAPI<any>("/api/marketing/ad-spend");
}

export async function fetchInventory() {
  return fetchAPI<any>("/api/logistics/inventory");
}

// --- MCP Status ---
export async function fetchMCPStatus() {
  return fetchAPI<any>("/api/mcp/status");
}

// --- Diagnostic ---
export async function generateProtocol(request: {
  goals: string[];
  age?: number;
  gender?: string;
  existing_conditions?: string[];
  current_supplements?: string[];
}) {
  return fetchAPI<any>("/api/diagnostic/protocol", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// --- WebSocket ---
export function createWebSocket(onMessage: (data: any) => void) {
  const ws = new WebSocket(`${WS_BASE}/ws`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error("WebSocket parse error:", e);
    }
  };
  ws.onopen = () => {
    console.log("WebSocket connected to", `${WS_BASE}/ws`);
  };
  ws.onerror = (e) => {
    console.error("WebSocket error:", e);
  };
  ws.onclose = () => {
    console.log("WebSocket disconnected");
  };
  return ws;
}
