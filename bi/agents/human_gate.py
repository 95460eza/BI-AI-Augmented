"""Human gate — the "Jenkins reviews proposals" step (a human persona, not CI).

Pauses the graph with LangGraph's `interrupt()` so a human can select, edit, or
reject the proposed scenarios in the Streamlit UI. The graph resumes with
`Command(resume={"approved_scenarios": [...]})`, whose payload becomes this
node's output.
"""

from __future__ import annotations

from typing import Any, Dict

from langgraph.types import interrupt

from bi.state import BIState


def human_gate_node(state: BIState) -> Dict[str, Any]:
    decision = interrupt(
        {
            "kind": "scenario_review",
            "proposed_scenarios": state.get("proposed_scenarios", []),
        }
    )
    approved = (decision or {}).get("approved_scenarios", [])
    return {"approved_scenarios": approved, "phase": "approved"}
