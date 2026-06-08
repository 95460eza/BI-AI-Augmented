"""BI pipeline LangGraph (Phase 1 + Phase 2).

    START → Orchestrator (A1) → Data agent (A2, MCP 1) → Suggestion agent (A3, LLM)
          → Human gate (interrupt: select / edit / reject)
          → Scenario exec (A4) → Forecast agent (A5, MCP 3) → Insight agent (A6, LLM)
          → Aggregate / recommend (A1 merge) → END

Compiled with a MemorySaver checkpointer so the run pauses at the human gate and
resumes — straight into Phase 2 — once scenarios are approved.
"""

from __future__ import annotations

from typing import List

from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from bi.agents.aggregate import aggregate_node
from bi.agents.data_agent import make_data_agent
from bi.agents.forecast_agent import make_forecast_agent
from bi.agents.human_gate import human_gate_node
from bi.agents.insight_agent import insight_agent_node
from bi.agents.orchestrator import orchestrator_node
from bi.agents.scenario_exec import scenario_exec_node
from bi.agents.suggestion_agent import suggestion_agent_node
from bi.mcp_client import get_mcp_tools
from bi.state import BIState


def build_graph(tools: List[BaseTool], checkpointer=None):
    builder = StateGraph(BIState)

    # Phase 1 — discovery
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("data_agent", make_data_agent(tools))
    builder.add_node("suggestion_agent", suggestion_agent_node)
    builder.add_node("human_gate", human_gate_node)
    # Phase 2 — execution
    builder.add_node("scenario_exec", scenario_exec_node)
    builder.add_node("forecast_agent", make_forecast_agent(tools))
    builder.add_node("insight_agent", insight_agent_node)
    builder.add_node("aggregate", aggregate_node)

    builder.add_edge(START, "orchestrator")
    builder.add_edge("orchestrator", "data_agent")
    builder.add_edge("data_agent", "suggestion_agent")
    builder.add_edge("suggestion_agent", "human_gate")
    builder.add_edge("human_gate", "scenario_exec")
    builder.add_edge("scenario_exec", "forecast_agent")
    builder.add_edge("forecast_agent", "insight_agent")
    builder.add_edge("insight_agent", "aggregate")
    builder.add_edge("aggregate", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())


async def build_app_graph(checkpointer=None):
    """Fetch MCP tools and compile the full pipeline graph."""
    tools = await get_mcp_tools()
    return build_graph(tools, checkpointer=checkpointer)


# Backwards-compatible alias (Phase 1 entrypoint name).
build_phase1_graph = build_app_graph
