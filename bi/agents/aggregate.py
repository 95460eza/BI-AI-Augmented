"""Aggregation / recommendation (Agent 1 — Orchestrator merges results).

Joins each scenario with its adjustment, forecast, and insight; ranks by forecast
margin uplift; and emits a recommendation summary for the visualization layer.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from bi.state import BIState


def _margin_uplift(result: Dict[str, Any]) -> float:
    return float((result.get("forecast") or {}).get("margin_uplift_pct", 0) or 0)


async def aggregate_node(state: BIState, config: RunnableConfig) -> Dict[str, Any]:
    fmap = {f["id"]: f["forecast"] for f in state.get("forecasts", [])}
    imap = {i["id"]: i["insight"] for i in state.get("insights", [])}

    results: List[Dict[str, Any]] = []
    for item in state.get("executed", []):
        s = item["scenario"]
        results.append(
            {
                **s,
                "adjustment": item["adjustment"],
                "forecast": fmap.get(s.get("id")),
                "insight": imap.get(s.get("id")),
            }
        )

    results.sort(key=_margin_uplift, reverse=True)
    top = results[0] if results else None
    recommendations = {
        "top_scenario_id": top.get("id") if top else None,
        "top_scenario_title": top.get("title") if top else None,
        "ranked_ids": [r.get("id") for r in results],
        "summary": (
            f"Recommended: {top.get('title')} "
            f"(+{_margin_uplift(top):.1f}% margin, "
            f"+{(top.get('forecast') or {}).get('revenue_uplift_pct', 0):.1f}% revenue)."
            if top
            else "No scenarios to evaluate."
        ),
    }
    return {
        "scenario_results": results,
        "recommendations": recommendations,
        "phase": "complete",
    }
