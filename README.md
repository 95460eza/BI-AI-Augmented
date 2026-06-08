# BI-AI-Augmented

AI-generated scenarios for delivering BI strategies — a multi-agent business-intelligence
tool that discovers, reviews, and (Phase 2) forecasts business-strategy scenarios over the
Northwind dataset, with full Langfuse observability on every agent call.

## Stack

- **Orchestration:** LangGraph (`StateGraph`) + LangChain
- **LLM (Agents 3 & 6):** Anthropic Claude via `langchain-anthropic`, behind a `get_llm()` provider-swap seam
- **MCP servers:** YugabyteDB (MCP 1) today; Python/ML (MCP 3) in Phase 2 — connected via `langchain-mcp-adapters`
- **Observability:** Langfuse LangChain callback handler (one trace per run, one span per agent)
- **Frontend:** Streamlit

## Architecture (Phase 1 + Phase 2 — implemented)

```
START → Orchestrator (Agent 1)
      → Data agent (Agent 2)  ── MCP 1 ─→ YugabyteDB / Northwind
      → Suggestion agent (Agent 3) ─────→ Claude (ranked scenarios)
      → Human gate  (interrupt: select / edit / reject)
      → Scenario exec (Agent 4)  ───────→ in-memory business rules → adjustments
      → Forecast agent (Agent 5) ── MCP 3 ─→ Python/ML (statsmodels Holt-Winters)
      → Insight agent (Agent 6)  ───────→ Claude (strategy tips, grounded in forecast)
      → Aggregate / recommend (Agent 1 merge)
      → END  →  ranked scenarios + recommendation + charts
```

Approving at the human gate resumes the same graph straight into Phase 2. Each scenario is
forecast over a 6-month horizon (baseline vs scenario revenue & margin) and gets AI strategy
tips; the orchestrator ranks them and recommends one.

> **Note on "Jenkins":** in the architecture diagrams this is a **human reviewer persona**
> (the human gate / stakeholder health view), **not** the Jenkins CI server.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the values you have
```

Fill in `.env`:

- **YugabyteDB (MCP 1):** `YB_HOST`, `YB_PORT` (YSQL default `5433`), `YB_DATABASE`, `YB_USER`,
  `YB_PASSWORD`, `YB_SSLMODE`. *Leave `YB_HOST` empty to run on bundled Northwind sample data.*
- **LLM:** `ANTHROPIC_API_KEY` (+ optional `CLAUDE_MODEL`). *Empty key → deterministic mock proposals.*
- **Langfuse (optional):** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.

Everything is optional to *start* — the app degrades gracefully (sample data, mock LLM, no
tracing) so you can see the pipeline run before wiring real services.

## Run

Three processes. **Terminals 1 & 2 — the MCP servers:**

```bash
python -m mcp_servers.yugabyte_server     # MCP 1 — data, on :8000/mcp
python -m mcp_servers.ml_server           # MCP 3 — forecasting, on :8001/mcp
```

**Terminal 3 — the app:**

```bash
streamlit run app.py
```

Then: set a business focus → **Run discovery** → review/edit/approve scenarios at the human
gate → **Approve & run Phase 2** → see forecasts, comparison charts, AI tips, and the
recommended scenario. If Langfuse is configured, each run links to its trace.

> If the ML server (MCP 3) isn't running, the Forecast agent falls back to the identical
> local `compute_forecast`, so the app still works — it just isn't going over MCP.

## Smoke test

Verifies the whole pipeline (Phase 1 + Phase 2) on sample data + mock LLM — no external
services required — through the interrupt, resume, forecast, and insight steps:

```bash
python -m mcp_servers.yugabyte_server &    # MCP 1 (optional; sample data otherwise)
python -m mcp_servers.ml_server &          # MCP 3 (optional; local fallback otherwise)
python smoke_test.py
```

## Layout

```
bi/
  config.py          # env/.env settings (shared by app + MCP servers)
  llm.py             # get_llm() provider-swap factory
  observability.py   # Langfuse client + callback handler
  schemas.py         # Scenario / ScenarioSet (structured LLM output)
  state.py           # LangGraph BIState
  mcp_client.py      # MultiServerMCPClient (resilient) + tool-result normalizer
  sample_data.py     # bundled Northwind baseline fallback
  forecasting.py     # compute_forecast (MCP 3 logic + local fallback)
  graph.py           # full Phase 1 + Phase 2 StateGraph
  agents/            # orchestrator, data_agent, suggestion_agent, human_gate,
                     #   scenario_exec, forecast_agent, insight_agent, aggregate
mcp_servers/
  yugabyte_server.py # MCP 1 (FastMCP): baseline, read-only query, summarize
  ml_server.py       # MCP 3 (FastMCP): forecast_kpis
app.py               # Streamlit UI: human gate + Phase 2 visualization
```
