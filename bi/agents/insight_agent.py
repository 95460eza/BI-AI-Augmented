"""Agent 6 — Insight agent → LLM (Claude).

Generates strategy tips grounded in each scenario's forecast numbers. Uses
structured output (`InsightOutput`); falls back to deterministic tips when no LLM
is configured so the pipeline runs offline.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from bi.llm import get_llm
from bi.schemas import InsightOutput
from bi.state import BIState

_SYSTEM = (
    "You are a business-strategy advisor. Given one scenario and its forecast "
    "(baseline vs scenario revenue and margin, with uplift percentages), produce "
    "2-4 concrete, actionable tips, name the single biggest risk, and give a "
    "go/hold/refine recommendation. Ground every statement in the numbers."
)


def _prompt(scenario: Dict[str, Any], forecast: Dict[str, Any]) -> str:
    return (
        f"Scenario: {scenario.get('title')} (lever: {scenario.get('lever')})\n"
        f"Hypothesis: {scenario.get('hypothesis')}\n\n"
        f"Forecast (JSON):\n{json.dumps(forecast, indent=2)}\n\n"
        "Provide the insight."
    )


def _mock_insight(scenario: Dict[str, Any], forecast: Dict[str, Any]) -> Dict[str, Any]:
    rev = forecast.get("revenue_uplift_pct", 0)
    mar = forecast.get("margin_uplift_pct", 0)
    rec = "go" if mar >= 3 else ("refine" if mar > 0 else "hold")
    return {
        "tips": [
            f"Projected revenue uplift of {rev:.1f}% over the horizon — size the rollout accordingly.",
            f"Margin moves {mar:+.1f}%; protect it by holding the assumed discount/price discipline.",
            f"Pilot the '{scenario.get('lever')}' lever on a subset before full rollout.",
        ],
        "key_risk": "Assumed volume/price elasticity may not hold; validate on a pilot.",
        "recommendation": f"{rec} — based on a {mar:+.1f}% margin effect.",
    }


async def insight_agent_node(state: BIState, config: RunnableConfig) -> Dict[str, Any]:
    llm = get_llm(role="insight")
    structured = llm.with_structured_output(InsightOutput) if llm is not None else None

    fmap = {f["id"]: f["forecast"] for f in state.get("forecasts", [])}
    insights: List[Dict[str, Any]] = []
    errors = state.get("errors", [])

    for item in state.get("executed", []):
        scenario = item["scenario"]
        forecast = fmap.get(scenario.get("id"), {})
        if structured is None:
            insights.append({"id": scenario.get("id"), "insight": _mock_insight(scenario, forecast)})
            continue
        try:
            messages = [("system", _SYSTEM), ("human", _prompt(scenario, forecast))]
            result: InsightOutput = await structured.ainvoke(messages, config=config)
            insights.append({"id": scenario.get("id"), "insight": result.model_dump()})
        except Exception as exc:  # noqa: BLE001
            insights.append({"id": scenario.get("id"), "insight": _mock_insight(scenario, forecast)})
            errors = errors + [f"Insight agent fell back to mock for {scenario.get('id')}: {exc}"]

    return {"insights": insights, "errors": errors}
