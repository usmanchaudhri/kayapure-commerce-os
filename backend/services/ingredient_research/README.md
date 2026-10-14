# Ingredient Research Agent #1 (CAMEL Workforce)

Phase-1 Kayapure R&D agent that researches approved catalog ingredients and proposes claim-safe combination candidates.

## Stack

- **Orchestration:** CAMEL `Workforce` (AUTO_DECOMPOSE)
- **Workers:** librarian · evidence_scout · synergy_analyst · claim_guard
- **Tools:** local catalog JSON · PubMed E-utilities · claim scanner · safety rules
- **Shell:** FastAPI routes under `/api/research/*`

LangChain/LangGraph commerce agents are unchanged.

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/research/status` | Readiness / config |
| GET | `/api/research/ingredients` | Catalog |
| POST | `/api/research/ingredient-combos` | Run Workforce research |
| GET | `/api/research/runs` | List persisted runs |
| GET | `/api/research/runs/{run_id}` | Fetch one run |

## Env

See `backend/.env.example` (`GOOGLE_API_KEY` / `LLM_BASE_MODEL_API_KEY`, optional `NCBI_API_KEY`).

**Note:** pin `mcp>=1.3,<2` for camel-ai FastMCP compatibility.

## Data

- `backend/data/ingredients/master_list.json` — 184 ingredients
- `backend/data/ingredients/priority_tags.json` — highlighted / 7-in-1 tags
- `backend/data/ingredient_research_runs/` — JSON run artifacts
