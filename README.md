# KayaPure Autonomous Commerce OS

A full-stack autonomous commerce platform that uses **LangGraph agentic workflows** to monitor P&L metrics, propose strategic actions, and execute them in **hardware-isolated Firecracker microVMs** — all with human-in-the-loop approval.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  Control Tower │ Action Queue │ Inventory │ Diagnostic   │
└──────────────────────┬──────────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────▼──────────────────────────────────┐
│                  Backend (FastAPI)                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │            LangGraph Workflow                     │   │
│  │  Sensor → P&L Analyzer → Strategy → Human Gate   │   │
│  │                                    → Executor     │   │
│  └──────────────────────────────────────────────────┘   │
│  Commerce Service │ Marketing Service │ Logistics Svc   │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  PostgreSQL │ Mock Firecracker VMs │ External APIs       │
└─────────────────────────────────────────────────────────┘
```

---

## Monorepo Structure

```
kayapure-commerce-os/
├── backend/                    # Python FastAPI backend
│   ├── main.py                 # FastAPI app, routes, WebSocket
│   ├── config.py               # Environment configuration
│   ├── requirements.txt        # Python dependencies
│   ├── .env                    # Environment variables
│   ├── models/
│   │   ├── database.py         # SQLAlchemy connection
│   │   ├── schemas.py          # ORM models (SKU, Metrics, Actions, VM Audit)
│   │   └── api_models.py       # Pydantic request/response models
│   ├── graph/
│   │   └── workflow.py         # LangGraph 5-node agentic workflow
│   ├── services/
│   │   ├── commerce.py         # Shopify integration
│   │   ├── marketing.py        # Meta/Google Ads integration
│   │   ├── logistics.py        # Flexport/Cart.com integration
│   │   └── firecracker_manager.py  # Mock Firecracker microVM manager
│   ├── utils/
│   │   └── secret_manager.py   # Secure API key handling
│   └── migrations/
│       └── 001_initial_schema.sql  # PostgreSQL schema + seed data
│
├── frontend/                   # React 19 + Vite + Tailwind dashboard
│   ├── package.json            # Node.js dependencies
│   ├── vite.config.ts          # Vite configuration
│   ├── tsconfig.json           # TypeScript configuration
│   ├── client/
│   │   ├── index.html          # HTML entry point
│   │   └── src/
│   │       ├── App.tsx         # Routes & layout
│   │       ├── index.css       # Mission Control dark theme
│   │       ├── pages/
│   │       │   ├── ControlTower.tsx       # Main dashboard with P&L + agent graph
│   │       │   ├── ActionQueue.tsx        # Approve/deny agent proposals
│   │       │   ├── Inventory.tsx          # SKU management & risk monitoring
│   │       │   ├── VMTelemetry.tsx        # Firecracker VM audit trail
│   │       │   └── DiagnosticStorefront.tsx  # AI supplement protocol generator
│   │       ├── components/
│   │       │   └── DashboardLayout.tsx    # Sidebar + top bar layout
│   │       └── lib/
│   │           └── api.ts      # API client for backend communication
│   └── server/
│       └── index.ts            # Static file server (production)
│
└── README.md                   # This file
```

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 20+** (with pnpm)
- **PostgreSQL 14+**

### 1. Backend Setup

```bash
cd backend

# Create and configure database
sudo -u postgres createdb kayapure_commerce
sudo -u postgres psql -c "CREATE USER kayapure WITH PASSWORD 'kayapure_secure_2024';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE kayapure_commerce TO kayapure;"

# Run migrations
psql -U kayapure -d kayapure_commerce -f migrations/001_initial_schema.sql

# Install Python dependencies
pip install -r requirements.txt

# Start the backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Start the dev server
pnpm run dev
```

The frontend runs on `http://localhost:3000` and connects to the backend at `http://localhost:8000`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/skus` | List all SKUs with inventory data |
| GET | `/api/metrics` | Daily P&L metrics |
| GET | `/api/metrics/pnl-summary` | Aggregated P&L summary |
| GET | `/api/actions` | List proposed actions (filterable by status) |
| POST | `/api/actions/{id}/decide` | Approve or deny an action |
| POST | `/api/agent/run-cycle` | Trigger a full LangGraph agent cycle |
| GET | `/api/agent/state` | Current agent state |
| GET | `/api/vm-audit` | Firecracker VM audit trail |
| GET | `/api/vm/telemetry` | VM telemetry summary |
| POST | `/api/diagnostic/protocol` | Generate AI supplement protocol |
| WS | `/ws` | Real-time WebSocket for agent logs & updates |

---

## LangGraph Workflow

The agent runs a 5-node directed graph:

1. **Sensor Node** — Polls Shopify, Meta Ads, and logistics APIs for current data
2. **P&L Analyzer** — Calculates contribution margins, identifies at-risk SKUs
3. **Strategy Agent** — Uses LLM reasoning to propose actions (inventory shields, competitor snipes)
4. **Human Approval Gate** — Queues proposals for human review (approve/deny)
5. **Firecracker Executor** — Executes approved actions in hardware-isolated microVMs

---

## Key Features

- **Real-time P&L Dashboard** — Revenue, profit, ad spend, and shipping cost tracking
- **Agentic Workflow** — LangGraph-powered autonomous decision-making with human oversight
- **Hardware Isolation** — Every action executes in a Firecracker microVM with hardware-signed audit trail
- **Diagnostic Storefront** — AI-generated supplement protocols based on health goals
- **WebSocket Updates** — Real-time agent activity logs and VM telemetry

---

## Environment Variables

Create a `.env` file in `backend/` with:

```env
DATABASE_URL=postgresql://kayapure:kayapure_secure_2024@localhost:5432/kayapure_commerce
OPENAI_API_KEY=your-openai-key          # Optional: enables LLM strategy agent
SHOPIFY_API_KEY=your-shopify-key        # Optional: enables live Shopify data
META_ACCESS_TOKEN=your-meta-token       # Optional: enables Meta Ads data
GOOGLE_ADS_API_KEY=your-google-key      # Optional: enables Google Ads data
```

---

## License

Private — KayaPure Commerce OS
