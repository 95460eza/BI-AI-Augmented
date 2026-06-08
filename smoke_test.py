"""End-to-end smoke test (no DB, no LLM key, no Langfuse needed).

Runs the full pipeline: Orchestrator -> Data agent (MCP 1, sample data) ->
Suggestion agent (mock) -> human gate (interrupt) -> [resume] -> Scenario exec
-> Forecast agent (MCP 3 if up, else local) -> Insight agent (mock) -> aggregate.
"""

import asyncio

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from bi.graph import build_app_graph


async def main():
    cp = MemorySaver()
    graph = await build_app_graph(checkpointer=cp)
    cfg = {"configurable": {"thread_id": "smoke-1"}}

    await graph.ainvoke(
        {"request": "Find margin opportunities", "errors": []}, config=cfg
    )

    state = graph.get_state(cfg)
    interrupts = getattr(state, "interrupts", None) or []
    assert interrupts, "expected an interrupt at the human gate"
    proposed = interrupts[0].value["proposed_scenarios"]
    baseline = state.values["baseline"]
    print(f"baseline source = {baseline.get('source')}")
    print(f"baseline total_revenue = {baseline['kpis']['total_revenue']}")
    print(f"proposed scenarios = {len(proposed)}")
    for s in proposed:
        print(f"  [{s['rank']}] {s['id']} {s['title']} (lever={s['lever']})")

    # Approve the top 3, resume straight into Phase 2.
    approved = sorted(proposed, key=lambda s: s["rank"])[:3]
    final = await graph.ainvoke(
        Command(resume={"approved_scenarios": approved}), config=cfg
    )

    assert len(final["approved_scenarios"]) == 3
    results = final["scenario_results"]
    print(f"\nfinal phase = {final.get('phase')}")
    print(f"scenario_results = {len(results)}")
    fc_method = (results[0].get("forecast") or {}).get("method")
    fc_source = (results[0].get("forecast") or {}).get("source", "mcp")
    print(f"forecast method = {fc_method} (source={fc_source})")
    print("\nScenario comparison (ranked by margin uplift):")
    for r in results:
        f = r.get("forecast") or {}
        print(
            f"  {r['id']} {r['title'][:34]:34s} "
            f"rev +{f.get('revenue_uplift_pct', 0):5.1f}%  "
            f"margin +{f.get('margin_uplift_pct', 0):5.1f}%  "
            f"rec={r.get('insight', {}).get('recommendation', '')[:18]}"
        )
    rec = final["recommendations"]
    print(f"\nrecommendation: {rec['summary']}")

    assert len(results) == 3
    assert all(r.get("forecast") for r in results)
    assert all(r.get("insight") for r in results)
    assert rec["top_scenario_id"] in {r["id"] for r in results}
    print("\nSMOKE TEST PASSED ✅ (Phase 1 + Phase 2)")


if __name__ == "__main__":
    asyncio.run(main())
