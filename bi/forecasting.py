"""Forecasting core (MCP 3 logic).

A single pure function used both by the Python/ML MCP server and by the Forecast
agent's local fallback, so results are identical whether or not the MCP server is
running. Fits a time-series model to the historical monthly revenue, projects a
baseline forward, then applies the scenario's revenue/margin adjustments.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _future_labels(months: List[str], horizon: int) -> List[str]:
    """Continue 'YYYY-MM' labels for `horizon` months past the last one."""
    if not months:
        return [f"M+{i + 1}" for i in range(horizon)]
    try:
        y, m = (int(x) for x in months[-1].split("-"))
    except (ValueError, AttributeError):
        return [f"M+{i + 1}" for i in range(horizon)]
    out = []
    for _ in range(horizon):
        m += 1
        if m > 12:
            m = 1
            y += 1
        out.append(f"{y:04d}-{m:02d}")
    return out


def _fit_and_forecast(revenues: List[float], horizon: int) -> tuple[List[float], str]:
    """Return (forecast values, method name). Degrades gracefully."""
    n = len(revenues)
    if n == 0:
        return [0.0] * horizon, "empty"

    # Holt-Winters when there is enough signal.
    if n >= 6:
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            seasonal = "add" if n >= 24 else None
            periods = 12 if seasonal else None
            model = ExponentialSmoothing(
                revenues, trend="add", seasonal=seasonal, seasonal_periods=periods,
                initialization_method="estimated",
            ).fit()
            fc = [max(0.0, float(v)) for v in model.forecast(horizon)]
            method = "holt-winters" + ("-seasonal" if seasonal else "")
            return fc, method
        except Exception:
            pass  # fall through to linear trend

    # Linear trend via numpy.
    try:
        import numpy as np

        x = np.arange(n)
        slope, intercept = np.polyfit(x, np.array(revenues, dtype=float), 1)
        fc = [max(0.0, float(slope * (n + i) + intercept)) for i in range(horizon)]
        return fc, "linear-trend"
    except Exception:
        mean = sum(revenues) / n
        return [mean] * horizon, "mean"


def compute_forecast(
    history: List[Dict[str, Any]],
    horizon: int = 6,
    revenue_multiplier: float = 1.0,
    margin_rate: float = 0.30,
    margin_delta: float = 0.0,
) -> Dict[str, Any]:
    revenues = [
        float(h["revenue"]) for h in history if h.get("revenue") is not None
    ]
    months = [str(h.get("month", "")) for h in history]

    base_fc, method = _fit_and_forecast(revenues, horizon)
    scen_fc = [v * revenue_multiplier for v in base_fc]
    future = _future_labels(months, horizon)

    base_total = sum(base_fc)
    scen_total = sum(scen_fc)
    base_margin = base_total * margin_rate
    scen_margin = scen_total * (margin_rate + margin_delta)

    return {
        "method": method,
        "horizon": horizon,
        "baseline": {
            "total_revenue": round(base_total, 2),
            "total_margin": round(base_margin, 2),
            "monthly": [
                {"month": mo, "revenue": round(v, 2)} for mo, v in zip(future, base_fc)
            ],
        },
        "scenario": {
            "total_revenue": round(scen_total, 2),
            "total_margin": round(scen_margin, 2),
            "monthly": [
                {"month": mo, "revenue": round(v, 2)} for mo, v in zip(future, scen_fc)
            ],
        },
        "revenue_uplift_pct": round((scen_total / base_total - 1) * 100, 2)
        if base_total
        else 0.0,
        "margin_uplift_pct": round((scen_margin / base_margin - 1) * 100, 2)
        if base_margin
        else 0.0,
    }
