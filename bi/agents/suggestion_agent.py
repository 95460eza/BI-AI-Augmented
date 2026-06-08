"""Agent 3 — Suggestion agent → LLM (Claude).

Proposes ranked business-strategy scenarios grounded in the Northwind baseline.
Uses structured output so Claude must return a well-formed `ScenarioSet`. If no
LLM is configured (ANTHROPIC_API_KEY unset), falls back to deterministic mock
scenarios so the pipeline still runs end-to-end.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from bi.llm import get_llm
from bi.schemas import ScenarioSet
from bi.state import BIState

_SYSTEM = (
    "You are a business-intelligence strategist. Given a baseline summary of a "
    "company's sales data, propose exactly 5 distinct, actionable business "
    "scenarios to test in a forecasting model. Rank them 1 (best) to 5. Each "
    "scenario must use a different lever (e.g. pricing, discounting, product mix, "
    "market expansion, customer retention) and be explicitly grounded in the "
    "numbers provided. Be concrete and concise."
)


def _prompt(request: str, baseline: Dict[str, Any]) -> str:
    return (
        f"Business focus: {request}\n\n"
        f"Baseline data (JSON):\n{json.dumps(baseline, indent=2)}\n\n"
        "Propose the 5 ranked scenarios."
    )


def _mock_scenarios(baseline: Dict[str, Any]) -> List[Dict[str, Any]]:
    top_cat = (baseline.get("revenue_by_category") or [{}])[0].get("category", "top category")
    top_country = (baseline.get("revenue_by_country") or [{}])[0].get("country", "top market")
    top_product = (baseline.get("top_products") or [{}])[0].get("product_name", "top product")
    specs = [
        ("SC-01", "Premium pricing on best-sellers", "pricing",
         f"Raising prices on high-demand items like {top_product} lifts margin with limited volume loss.",
         "Increase unit price 5–8% on the top 10 revenue products."),
        ("SC-02", f"Reduce discount depth in {top_cat}", "discounting",
         f"{top_cat} drives the most revenue; trimming average discount recovers margin.",
         "Cap average discount in the leading category at 5%."),
        ("SC-03", f"Expand presence in {top_country}", "market expansion",
         f"{top_country} is already the strongest market and can absorb more volume.",
         "Grow order volume 15% in the leading country via targeted promotion."),
        ("SC-04", "Rebalance product mix toward high-margin lines", "product mix",
         "Shifting volume to higher-margin categories improves blended margin.",
         "Shift 10% of low-margin volume into higher-margin categories."),
        ("SC-05", "Win-back on lapsed customers", "customer retention",
         "Re-engaging dormant accounts adds incremental orders at low cost.",
         "Target lapsed customers with a re-order incentive."),
    ]
    return [
        {
            "id": sid, "title": title, "lever": lever, "hypothesis": hyp,
            "description": desc, "expected_impact": "Positive on revenue and/or margin",
            "rationale": "Derived from the baseline figures above.", "rank": i + 1,
        }
        for i, (sid, title, lever, hyp, desc) in enumerate(specs)
    ]


async def suggestion_agent_node(state: BIState, config: RunnableConfig) -> Dict[str, Any]:
    baseline = state.get("baseline", {})
    request = state.get("request", "")

    llm = get_llm(role="suggestion")
    if llm is None:
        return {"proposed_scenarios": _mock_scenarios(baseline)}

    structured = llm.with_structured_output(ScenarioSet)
    messages = [("system", _SYSTEM), ("human", _prompt(request, baseline))]
    try:
        result: ScenarioSet = await structured.ainvoke(messages, config=config)
        scenarios = [s.model_dump() for s in sorted(result.scenarios, key=lambda s: s.rank)]
        return {"proposed_scenarios": scenarios}
    except Exception as exc:
        return {
            "proposed_scenarios": _mock_scenarios(baseline),
            "errors": state.get("errors", []) + [f"Suggestion agent fell back to mock: {exc}"],
        }
