"""LangGraph shared state for the BI pipeline."""

from __future__ import annotations

from typing import Any, Dict, List

from typing_extensions import TypedDict


class BIState(TypedDict, total=False):
    # Inputs
    request: str  # the business focus / question from the user

    # Phase 1 — discovery
    baseline: Dict[str, Any]  # Northwind KPIs from the Data agent (via MCP 1)
    proposed_scenarios: List[Dict[str, Any]]  # from the Suggestion agent
    approved_scenarios: List[Dict[str, Any]]  # from the human gate

    # Phase 2 — execution
    executed: List[Dict[str, Any]]  # Agent 4: scenario + derived adjustment
    forecasts: List[Dict[str, Any]]  # Agent 5: {id, forecast} via MCP 3
    insights: List[Dict[str, Any]]  # Agent 6: {id, insight} via LLM
    scenario_results: List[Dict[str, Any]]  # merged per-scenario results
    recommendations: Dict[str, Any]  # ranked recommendation summary

    # Bookkeeping
    phase: str
    errors: List[str]
