"""Agent 4 — Scenario exec.

Applies business rules **in memory (no MCP)** to turn each approved scenario into
a quantified `ScenarioAdjustment` (revenue/volume multipliers, margin delta) that
the Forecast agent can act on. Rules key off the scenario's `lever`.
"""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from bi.schemas import ScenarioAdjustment
from bi.state import BIState

_BASE_MARGIN = 0.30

# lever keyword -> (revenue_multiplier, margin_delta, volume_multiplier, assumptions)
_RULES = {
    "pricing": (1.0388, 0.04, 0.98,
                ["+6% price on top sellers", "-2% volume elasticity", "+4pt margin"]),
    "discount": (1.00, 0.03, 1.00,
                 ["discount depth capped", "+3pt margin recovered", "volume held flat"]),
    "market": (1.15, 0.00, 1.15,
               ["+15% volume in lead market", "margin rate unchanged"]),
    "expansion": (1.15, 0.00, 1.15,
                  ["+15% volume from expansion", "margin rate unchanged"]),
    "product mix": (1.02, 0.03, 1.00,
                    ["shift to higher-margin lines", "+3pt blended margin"]),
    "mix": (1.02, 0.03, 1.00,
            ["shift to higher-margin lines", "+3pt blended margin"]),
    "retention": (1.05, 0.01, 1.05,
                  ["+5% volume from win-back", "+1pt margin from loyalty"]),
}
_DEFAULT = (1.03, 0.01, 1.02, ["generic uplift assumption"])


def derive_adjustment(scenario: Dict[str, Any]) -> ScenarioAdjustment:
    lever = (scenario.get("lever") or "").lower()
    rev, mdelta, vol, notes = _DEFAULT
    for key, vals in _RULES.items():
        if key in lever:
            rev, mdelta, vol, notes = vals
            break
    return ScenarioAdjustment(
        revenue_multiplier=rev,
        margin_rate=_BASE_MARGIN,
        margin_delta=mdelta,
        volume_multiplier=vol,
        assumptions=notes,
    )


async def scenario_exec_node(state: BIState, config: RunnableConfig) -> Dict[str, Any]:
    executed = [
        {"scenario": s, "adjustment": derive_adjustment(s).model_dump()}
        for s in state.get("approved_scenarios", [])
    ]
    return {"executed": executed, "phase": "execution"}
