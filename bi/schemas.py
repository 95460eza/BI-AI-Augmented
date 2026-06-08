"""Pydantic schemas shared across agents.

`ScenarioSet` is used as the structured-output schema for the Suggestion agent,
so Claude is forced to return well-formed, ranked scenarios.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class Scenario(BaseModel):
    id: str = Field(description="Short stable id, e.g. 'SC-01'.")
    title: str = Field(description="Concise scenario name.")
    lever: str = Field(
        description="The primary business lever, e.g. pricing, discounting, "
        "product mix, market expansion, customer retention."
    )
    hypothesis: str = Field(description="The business hypothesis being tested.")
    description: str = Field(description="What the scenario changes, in 1-2 sentences.")
    expected_impact: str = Field(
        description="Qualitative expected effect on KPIs (revenue, margin, volume)."
    )
    rationale: str = Field(
        description="Why this is grounded in the baseline data provided."
    )
    rank: int = Field(description="1 = highest priority.", ge=1)


class ScenarioSet(BaseModel):
    scenarios: List[Scenario] = Field(description="Ranked scenarios, best first.")


class ScenarioAdjustment(BaseModel):
    """Quantified effect of a scenario, derived in-memory by Agent 4."""

    revenue_multiplier: float = Field(description="Multiplier on forecast revenue.")
    margin_rate: float = Field(description="Assumed baseline gross-margin rate.")
    margin_delta: float = Field(description="Change in margin rate from the lever.")
    volume_multiplier: float = Field(description="Multiplier on unit volume.")
    assumptions: List[str] = Field(description="Business rules applied.")


class InsightOutput(BaseModel):
    """Strategy tips from Agent 6, grounded in the forecast numbers."""

    tips: List[str] = Field(description="2-4 concrete, actionable tips.")
    key_risk: str = Field(description="The single biggest risk to watch.")
    recommendation: str = Field(description="Go / hold / refine, with one reason.")
