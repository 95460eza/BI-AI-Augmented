"""MCP 3 — Python/ML MCP server.

A real MCP server (FastMCP, streamable-http) that the Forecast agent (Agent 5)
reaches through `langchain-mcp-adapters`. It predicts KPIs and margins from the
historical revenue series using statsmodels / scikit-learn (see bi.forecasting).

Run it standalone before starting the app:

    python -m mcp_servers.ml_server
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from bi.config import settings
from bi.forecasting import compute_forecast

mcp = FastMCP(
    "python-ml",
    host=settings.mcp_ml_host,
    port=settings.mcp_ml_port,
)


@mcp.tool()
def forecast_kpis(
    history: List[Dict[str, Any]],
    horizon: int = 6,
    revenue_multiplier: float = 1.0,
    margin_rate: float = 0.30,
    margin_delta: float = 0.0,
) -> str:
    """Forecast revenue and margin over `horizon` months.

    `history` is a list of {"month": "YYYY-MM", "revenue": float}. The scenario's
    effect is applied via `revenue_multiplier` (volume/price change) and
    `margin_delta` (change in margin rate). Returns JSON with baseline vs scenario
    totals, monthly series, and uplift percentages.
    """
    result = compute_forecast(
        history=history,
        horizon=horizon,
        revenue_multiplier=revenue_multiplier,
        margin_rate=margin_rate,
        margin_delta=margin_delta,
    )
    return json.dumps(result)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
