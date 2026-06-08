"""Agent 2 — Data agent → MCP 1 (YugabyteDB).

Fetches the Northwind baseline by calling the `get_northwind_baseline` tool on
the YugabyteDB MCP server. The MCP tool call is automatically captured as a child
span under this agent's node in the Langfuse trace.
"""

from __future__ import annotations

from functools import partial
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from bi.mcp_client import parse_tool_result
from bi.state import BIState


async def data_agent_node(
    state: BIState, config: RunnableConfig, *, tools: List[BaseTool]
) -> Dict[str, Any]:
    by_name = {t.name: t for t in tools}
    tool = by_name.get("get_northwind_baseline")
    if tool is None:
        return {"errors": state.get("errors", []) + ["MCP tool get_northwind_baseline unavailable"]}

    raw = await tool.ainvoke({}, config=config)
    baseline = parse_tool_result(raw)

    errors = state.get("errors", [])
    if isinstance(baseline, dict) and baseline.get("warning"):
        errors = errors + [baseline["warning"]]

    return {"baseline": baseline, "errors": errors}


def make_data_agent(tools: List[BaseTool]):
    """Bind the MCP tools into the node (used by the graph builder)."""
    return partial(data_agent_node, tools=tools)
