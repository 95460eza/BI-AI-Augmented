"""Agent 5 — Forecast agent → MCP 3 (Python/ML).

For each executed scenario, predicts revenue/margin over the forecast horizon by
calling the `forecast_kpis` tool on the ML MCP server. Each MCP call is captured
as a child span under this agent in the Langfuse trace. If the ML server is
unavailable, falls back to the identical local `compute_forecast` so the pipeline
still runs.
"""

from __future__ import annotations

from functools import partial
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from bi.forecasting import compute_forecast
from bi.mcp_client import parse_tool_result
from bi.state import BIState

_HORIZON = 6


async def forecast_agent_node(
    state: BIState, config: RunnableConfig, *, tools: List[BaseTool]
) -> Dict[str, Any]:
    history = (state.get("baseline") or {}).get("monthly_revenue", [])
    tool = {t.name: t for t in tools}.get("forecast_kpis")

    forecasts: List[Dict[str, Any]] = []
    errors = state.get("errors", [])
    for item in state.get("executed", []):
        adj = item["adjustment"]
        args = {
            "history": history,
            "horizon": _HORIZON,
            "revenue_multiplier": adj["revenue_multiplier"],
            "margin_rate": adj["margin_rate"],
            "margin_delta": adj["margin_delta"],
        }
        try:
            if tool is not None:
                raw = await tool.ainvoke(args, config=config)
                fc = parse_tool_result(raw)
            else:
                fc = compute_forecast(**args)
                fc["source"] = "local-fallback"
        except Exception as exc:  # noqa: BLE001
            fc = compute_forecast(**args)
            fc["source"] = "local-fallback"
            errors = errors + [f"Forecast MCP failed for {item['scenario'].get('id')}: {exc}"]
        forecasts.append({"id": item["scenario"].get("id"), "forecast": fc})

    return {"forecasts": forecasts, "errors": errors}


def make_forecast_agent(tools: List[BaseTool]):
    return partial(forecast_agent_node, tools=tools)
