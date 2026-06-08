# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

**Phase 1 + Phase 2 are implemented and verified end-to-end** (full pipeline: discovery → human gate → forecast → insight → recommendation). The chosen stack is locked (see below). The two architecture diagrams at the repo root remain the authoritative spec:

- `ARCHITECTURE-DIAGRAM-WITH LANGFUSE.png` — full system architecture
- `ARCHITECTURE-DETAILS-WITH-LANGFUSE.png` — explanation of what each Langfuse span captures and why

## Chosen stack (locked)

- **Orchestration:** LangGraph `StateGraph` + LangChain. The full graph is in `bi/graph.py` (`build_app_graph`); each of the 6 agents + aggregate is a node in `bi/agents/`. Approving at the human-gate `interrupt` resumes the same graph straight into Phase 2.
- **LLM (Agents 3 & 6):** Anthropic Claude via `langchain-anthropic`, behind the `get_llm()` factory in `bi/llm.py` — **this is the single provider-swap seam** (set `LLM_PROVIDER=ollama` for a local model; no agent code changes).
- **MCP:** real MCP servers via `langchain-mcp-adapters` for the **data** and **ML** boundaries only. MCP 1 (YugabyteDB) → `mcp_servers/yugabyte_server.py`; MCP 3 (Python/ML forecasting, statsmodels) → `mcp_servers/ml_server.py`. Both FastMCP, streamable-HTTP. The client (`bi/mcp_client.py`) loads each server independently so one being down only drops its tools.
- **MCP 2 & MCP 4 (the "LLM API" boxes) are realized as direct `ChatAnthropic` calls, by design** — wrapping an LLM behind MCP adds servers without benefit, and the `get_llm()` factory is the better portability seam. This is a deliberate, documented deviation from the literal diagram.
- **Frontend:** Streamlit (`app.py`), including the human approval gate.
- **Observability:** Langfuse LangChain `CallbackHandler` (`bi/observability.py`) — one handler per graph run yields one trace with one span per agent/LLM/tool call.

## Commands

- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`, then `cp .env.example .env`.
- Run (3 processes): `python -m mcp_servers.yugabyte_server` (MCP 1 `:8000`), `python -m mcp_servers.ml_server` (MCP 3 `:8001`), then `streamlit run app.py`.
- Smoke test (no DB/LLM/Langfuse/servers needed; runs the whole pipeline through interrupt → resume → forecast → insight): `python smoke_test.py`.

**Graceful degradation (the app always runs):** empty `YB_HOST` → bundled Northwind sample (`bi/sample_data.py`); ML server down → forecast agent uses the identical local `bi/forecasting.compute_forecast`; empty `ANTHROPIC_API_KEY` → deterministic mock proposals/insights; no Langfuse keys → untraced.

## Implementation notes

- The MCP layer returns **content blocks** (`[{"type":"text","text":...}]`), not raw strings — always normalize tool results via `bi.mcp_client.parse_tool_result`.
- Streamlit is sync; each action opens its own event loop (`run_async`). The compiled graph + its `MemorySaver` checkpointer are cached in `st.session_state` so discovery and the post-approval resume share one thread. HTTP MCP transport is stateless per call, so reusing tools across loops is safe.
- The human gate uses LangGraph `interrupt()`; resume with `Command(resume={"approved_scenarios": [...]})`. Read the pending proposals from `graph.get_state(cfg).interrupts[0].value`.

Phase 2 fans out the approved scenarios through batch agent nodes (scenario_exec → forecast_agent → insight_agent → aggregate); each node loops over all scenarios so every agent is one Langfuse span with per-scenario MCP/LLM child spans. When adding agents/MCP servers, follow these patterns (new node + a `mcp_servers/*.py` registered in `bi/mcp_client._server_config`, with a local fallback).

## MCP servers available to the Claude Code session

These are connected to **your Claude Code session** (reachable via `ToolSearch`) — use them to *explore/verify* the data while developing. They are **separate** from the app's own MCP server (`mcp_servers/yugabyte_server.py`), which the running app talks to over HTTP and which has its own `.env` connection:

- **`yugabytedb`** — live Northwind DB. Tools: `run_read_only_query`, `run_write_query`, `summarize_database`. Use to sanity-check queries before baking them into the app's MCP server.
- **`yugabyte-docs`** — YugabyteDB documentation lookup.
- **`context7`** — up-to-date library/framework/API documentation (also via the `find-docs` skill). Use it when touching LangGraph / langchain-mcp-adapters / Langfuse — these APIs shift between releases.

App-side: MCP 1 (YugabyteDB) and MCP 3 (Python/ML) are both built and run as separate processes; MCP 2/4 are direct LLM calls by design (see "Chosen stack").

### Northwind data source — verified live

MCP 1 is connected and the Northwind dataset is loaded in the `public` schema (15 tables, ~3,362 rows). Key tables for KPIs/forecasting:

- `order_details` (2,155 rows) and `orders` (830) — the transactional core.
- `customers` (91), `products` (77), `suppliers` (29), `categories` (8), plus reference/dimension tables (`territories`, `region`, `us_states`, `employees`, `shippers`, `employee_territories`).
- `customer_customer_demo` and `customer_demographics` are **empty** (standard for Northwind) — ignore for scenario discovery.

Note: monetary/quantity columns use Postgres `real`/`smallint` (e.g. `order_details.unit_price`, `discount`, `quantity`); account for `real` precision when computing margins.

## Intended architecture (from the diagrams)

The system is a **multi-agent BI tool for business strategy** that runs in two phases, with Langfuse observability wrapped around every agent call.

### Phase 1 — Scenario discovery
- **Agent 1 (Orchestrator)** — routes tasks and merges results.
- **Agent 2 (Data agent)** → **MCP 1 (YugabyteDB)** — fetches the Northwind baseline (orders, products, customers).
- **Agent 3 (Suggestion agent)** → **MCP 2 (LLM API)** — proposes ranked scenarios (scenario ideation).
- **Human gate** — a human reviewer (referred to as "Jenkins" in the legend — this is a **persona name, not the CI tool**) selects, edits, or rejects scenarios before Phase 2 runs.

### Phase 2 — Scenario execution
- **Agent 1 (Orchestrator)** — fans out approved scenarios.
- **Agent 4 (Scenario exec)** — applies business rules in memory (no MCP).
- **Agent 5 (Forecast agent)** → **MCP 3 (Python/ML)** — predicts KPIs and margins using statsmodels / scikit-learn.
- **Agent 6 (Insight agent)** → **MCP 4 (LLM API)** — generates AI strategy tips.
- **Visualization and output layer** — KPI charts, scenario comparison, recommendations.

### Observability (Langfuse)
Langfuse SDK is embedded in each agent. Every agent call must emit a per-agent span capturing: input prompt, LLM output, latency (ms), token usage, MCP tool calls, errors/retries, cost estimate. These feed: a trace timeline / session replay dashboard, evals (output quality, scenario relevance, insight accuracy), prompt management with A/B testing, and a "Jenkins view" (a stakeholder-facing health summary — same persona as the human gate).

The details PNG spells out *why* each span matters; consult it when deciding what to log from new agent code.

## Notes for working in this repo

- The "Jenkins" naming in the diagrams is ambiguous on first read. It refers to a **human stakeholder persona** (the human approval gate / stakeholder health view), not the Jenkins CI server. Do not introduce Jenkins-the-CI-tool unless the user explicitly asks for it.
- Stack is locked (see "Chosen stack"). When adding agents/MCP servers, follow the existing patterns rather than introducing new frameworks; if a genuinely new dependency or framework is warranted, confirm with the user first.
- The app's data agent reaches Northwind through its **own** MCP server (`mcp_servers/yugabyte_server.py`) using the `.env` connection — not the session's `yugabytedb` MCP. Confirm live connection details with the user via `.env`; the app falls back to bundled sample data when `YB_HOST` is empty.
