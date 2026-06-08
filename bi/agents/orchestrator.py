"""Agent 1 — Orchestrator.

Routes tasks and merges results. In Phase 1 it sets up the run; in Phase 2 it
fans out approved scenarios. Deterministic (no LLM) so it stays cheap and
predictable, while still appearing as its own span in the Langfuse trace.
"""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from bi.state import BIState


async def orchestrator_node(state: BIState, config: RunnableConfig) -> Dict[str, Any]:
    request = state.get("request") or "Identify growth and margin-improvement opportunities."
    return {
        "request": request,
        "phase": "discovery",
        "errors": state.get("errors", []),
    }
