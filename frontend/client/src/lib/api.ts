/**
 * KayaPure Commerce OS - API Client
 * Connects to the FastAPI backend running on port 8000.
 */

const API_BASE = "http://localhost:8000";

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
  const ws = new WebSocket(`ws://localhost:8000/ws`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error("WebSocket parse error:", e);
    }
  };
  ws.onopen = () => {
    console.log("WebSocket connected");
  };
  ws.onerror = (e) => {
    console.error("WebSocket error:", e);
  };
  return ws;
}
