"""BI-AI-Augmented — Streamlit frontend (Phase 1: scenario discovery).

Flow:
  1. Orchestrator → Data agent (MCP 1) → Suggestion agent (LLM) runs and pauses
     at the human gate (LangGraph `interrupt`).
  2. The reviewer (the "Jenkins" persona) selects / edits / rejects scenarios.
  3. Approving resumes the graph, which records the approved set (handed to
     Phase 2 next).

Every run is traced in Langfuse (one trace, one span per agent) when keys are set.

Run:
  1. python -m mcp_servers.yugabyte_server      # start MCP 1 (separate terminal)
  2. streamlit run app.py
"""

from __future__ import annotations

import asyncio
import uuid

import pandas as pd
import plotly.express as px
import streamlit as st
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from bi.config import settings
from bi.graph import build_app_graph
from bi.observability import flush, get_callback_handler, new_trace_id, trace_url

st.set_page_config(page_title="BI-AI-Augmented", page_icon="📊", layout="wide")


# --------------------------------------------------------------------------- #
# Async helpers (Streamlit is sync; each action runs its own event loop)
# --------------------------------------------------------------------------- #
def run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _start_discovery(graph, request: str, thread_id: str, trace_id):
    cfg = {"configurable": {"thread_id": thread_id}}
    handler = get_callback_handler(trace_id)
    if handler:
        cfg["callbacks"] = [handler]
    result = await graph.ainvoke({"request": request, "errors": []}, config=cfg)
    return result


async def _resume_with_approval(graph, approved, thread_id: str, trace_id):
    cfg = {"configurable": {"thread_id": thread_id}}
    handler = get_callback_handler(trace_id)
    if handler:
        cfg["callbacks"] = [handler]
    return await graph.ainvoke(
        Command(resume={"approved_scenarios": approved}), config=cfg
    )


def get_graph():
    """Build the graph once and keep it (with its checkpointer) in session state
    so discovery and the post-approval resume share the same thread."""
    if "graph" not in st.session_state:
        st.session_state.checkpointer = MemorySaver()
        st.session_state.graph = run_async(
            build_app_graph(checkpointer=st.session_state.checkpointer)
        )
    return st.session_state.graph


# --------------------------------------------------------------------------- #
# Sidebar — environment health (a small "Jenkins view")
# --------------------------------------------------------------------------- #
def sidebar():
    with st.sidebar:
        st.header("System health")
        st.markdown(f"**Data (MCP 1):** `{settings.mcp_yugabyte_url}`")
        st.markdown(f"**ML (MCP 3):** `{settings.mcp_ml_url}`")
        st.write("YugabyteDB:", "✅ configured" if settings.db_configured else "⚠️ sample data")
        st.write(
            "LLM:",
            f"✅ {settings.claude_model}" if settings.llm_configured else "⚠️ mock proposals",
        )
        st.write("Langfuse:", "✅ tracing" if settings.langfuse_configured else "⚪ off")
        st.divider()
        if st.button("🔄 Reset session"):
            for k in ("graph", "checkpointer", "phase1", "trace_id", "thread_id",
                      "done", "results", "recommendations"):
                st.session_state.pop(k, None)
            st.rerun()


# --------------------------------------------------------------------------- #
# Baseline visualization
# --------------------------------------------------------------------------- #
def render_baseline(baseline: dict):
    src = baseline.get("source", "unknown")
    st.caption(f"Source: **{src}**" + ("  ·  ⚠️ sample data" if src == "sample" else ""))

    k = baseline.get("kpis", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total revenue", f"${k.get('total_revenue', 0):,.0f}")
    c2.metric("Orders", f"{k.get('total_orders', 0):,}")
    c3.metric("Avg order value", f"${k.get('avg_order_value', 0):,.0f}")
    c4.metric("Customers", f"{k.get('unique_customers', 0):,}")

    left, right = st.columns(2)
    with left:
        cat = pd.DataFrame(baseline.get("revenue_by_category", []))
        if not cat.empty:
            st.plotly_chart(
                px.bar(cat, x="category", y="revenue", title="Revenue by category"),
                width='stretch',
            )
        prod = pd.DataFrame(baseline.get("top_products", []))
        if not prod.empty:
            st.plotly_chart(
                px.bar(prod, x="revenue", y="product_name", orientation="h",
                       title="Top products").update_yaxes(autorange="reversed"),
                width='stretch',
            )
    with right:
        month = pd.DataFrame(baseline.get("monthly_revenue", []))
        if not month.empty:
            st.plotly_chart(
                px.line(month, x="month", y="revenue", markers=True,
                        title="Monthly revenue"),
                width='stretch',
            )
        country = pd.DataFrame(baseline.get("revenue_by_country", []))
        if not country.empty:
            st.plotly_chart(
                px.bar(country, x="country", y="revenue", title="Revenue by country"),
                width='stretch',
            )


# --------------------------------------------------------------------------- #
# Phase 2 visualization (forecast + insight + recommendation)
# --------------------------------------------------------------------------- #
def render_phase2(results: list, recommendations: dict):
    st.subheader("Phase 2 — Forecast & insight")
    if not results:
        st.warning("No executed scenarios.")
        return

    st.success("🏆 " + recommendations.get("summary", ""))

    rows = []
    for r in results:
        f = r.get("forecast") or {}
        ins = r.get("insight") or {}
        rows.append({
            "id": r.get("id"),
            "scenario": r.get("title"),
            "lever": r.get("lever"),
            "revenue_uplift_%": f.get("revenue_uplift_pct", 0),
            "margin_uplift_%": f.get("margin_uplift_pct", 0),
            "fc_revenue": (f.get("scenario") or {}).get("total_revenue", 0),
            "fc_margin": (f.get("scenario") or {}).get("total_margin", 0),
            "recommendation": ins.get("recommendation", ""),
        })
    comp = pd.DataFrame(rows)

    st.markdown("**Scenario comparison** (ranked by margin uplift)")
    st.dataframe(comp, width='stretch', hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            px.bar(comp, x="scenario", y=["revenue_uplift_%", "margin_uplift_%"],
                   barmode="group", title="Uplift vs baseline (%)"),
            width='stretch',
        )
    with c2:
        # Baseline (shared) vs each scenario forecast over the horizon.
        base_f = (results[0].get("forecast") or {}).get("baseline", {}).get("monthly", [])
        series = [{"month": m["month"], "revenue": m["revenue"], "series": "baseline"} for m in base_f]
        for r in results:
            for m in (r.get("forecast") or {}).get("scenario", {}).get("monthly", []):
                series.append({"month": m["month"], "revenue": m["revenue"], "series": r.get("title")})
        if series:
            st.plotly_chart(
                px.line(pd.DataFrame(series), x="month", y="revenue", color="series",
                        markers=True, title="Revenue forecast by scenario"),
                width='stretch',
            )

    st.markdown("**AI strategy tips** (Agent 6 · Insight)")
    for r in results:
        ins = r.get("insight") or {}
        top = "🏆 " if r.get("id") == recommendations.get("top_scenario_id") else ""
        with st.expander(f"{top}{r.get('id')} · {r.get('title')} — {ins.get('recommendation', '')}"):
            for tip in ins.get("tips", []):
                st.markdown(f"- {tip}")
            if ins.get("key_risk"):
                st.markdown(f"**Key risk:** {ins['key_risk']}")
            st.caption("Business rules applied: " + ", ".join((r.get("adjustment") or {}).get("assumptions", [])))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    sidebar()
    st.title("📊 BI-AI-Augmented — Scenario discovery")
    st.caption("Phase 1: Orchestrator → Data agent (YugabyteDB) → Suggestion agent (Claude) → human gate")

    request = st.text_input(
        "Business focus for this run",
        value="Identify growth and margin-improvement opportunities from the Northwind sales data.",
    )

    if st.button("▶️ Run discovery", type="primary"):
        with st.spinner("Running Phase 1 agents…"):
            trace_id = new_trace_id()
            thread_id = str(uuid.uuid4())
            graph = get_graph()
            try:
                run_async(_start_discovery(graph, request, thread_id, trace_id))
            finally:
                flush()
            # Read the interrupt payload from the checkpoint.
            state = graph.get_state({"configurable": {"thread_id": thread_id}})
            interrupts = getattr(state, "interrupts", None) or []
            proposed = interrupts[0].value.get("proposed_scenarios", []) if interrupts else []
            baseline = state.values.get("baseline", {})
            st.session_state.phase1 = {"baseline": baseline, "proposed": proposed}
            st.session_state.thread_id = thread_id
            st.session_state.trace_id = trace_id
            st.session_state.done = False

    if "phase1" not in st.session_state:
        st.info("Set a focus and click **Run discovery** to begin.")
        return

    data = st.session_state.phase1
    url = trace_url(st.session_state.get("trace_id"))
    if url:
        st.markdown(f"🔗 [View this run's Langfuse trace]({url})")

    st.subheader("Baseline (Agent 2 · MCP 1 · YugabyteDB)")
    render_baseline(data["baseline"])

    st.subheader("Proposed scenarios (Agent 3 · Suggestion)")
    st.caption("Review the proposals — edit text, toggle **approve**, then submit. This is the human gate.")

    proposed = data["proposed"]
    if not proposed:
        st.warning("No scenarios were proposed.")
        return

    df = pd.DataFrame(proposed)
    df.insert(0, "approve", True)
    edited = st.data_editor(
        df,
        width='stretch',
        hide_index=True,
        column_config={
            "approve": st.column_config.CheckboxColumn("approve", default=True),
            "rank": st.column_config.NumberColumn("rank", width="small"),
            "id": st.column_config.TextColumn("id", width="small"),
        },
        disabled=["id"],
        key="scenario_editor",
    )

    if st.button("✅ Approve selected & run Phase 2 (forecast + insight)", type="primary"):
        approved = edited[edited["approve"]].drop(columns=["approve"]).to_dict("records")
        if not approved:
            st.error("Select at least one scenario to approve.")
            return
        with st.spinner("Running Phase 2 agents (scenario exec → forecast → insight)…"):
            try:
                final = run_async(
                    _resume_with_approval(
                        get_graph(), approved,
                        st.session_state.thread_id, st.session_state.get("trace_id"),
                    )
                )
            finally:
                flush()
        st.session_state.done = True
        st.session_state.results = final.get("scenario_results", [])
        st.session_state.recommendations = final.get("recommendations", {})

    if st.session_state.get("done"):
        render_phase2(
            st.session_state.get("results", []),
            st.session_state.get("recommendations", {}),
        )


if __name__ == "__main__":
    main()
