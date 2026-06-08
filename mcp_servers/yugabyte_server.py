"""MCP 1 — YugabyteDB (Northwind) MCP server.

A real MCP server (FastMCP, streamable-http) that the Data agent reaches through
`langchain-mcp-adapters`. It exposes read-only access to the Northwind dataset on
YugabyteDB plus a curated baseline aggregator.

Run it standalone before starting the app:

    python -m mcp_servers.yugabyte_server

If YB_HOST is not configured (or the DB is unreachable), the baseline tool falls
back to bundled sample data and clearly labels the response `source="sample"`, so
the pipeline keeps working while the real connection is being set up.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from bi.config import settings
from bi.sample_data import SAMPLE_BASELINE

mcp = FastMCP(
    "yugabyte-northwind",
    host=settings.mcp_yugabyte_host,
    port=settings.mcp_yugabyte_port,
)


# --------------------------------------------------------------------------- #
# Connection helper
# --------------------------------------------------------------------------- #
def _connect():
    """Open a psycopg connection to YugabyteDB. Raises if not configured."""
    if not settings.db_configured:
        raise RuntimeError("YB_HOST is not configured")
    import psycopg

    return psycopg.connect(settings.conninfo(), connect_timeout=10)


def _rows_as_dicts(cur) -> List[Dict[str, Any]]:
    cols = [d.name for d in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# --------------------------------------------------------------------------- #
# Curated baseline queries (revenue = unit_price * quantity * (1 - discount))
# --------------------------------------------------------------------------- #
_BASELINE_QUERIES: Dict[str, str] = {
    "kpis": """
        SELECT
            (SELECT count(*) FROM orders) AS total_orders,
            (SELECT count(DISTINCT customer_id) FROM orders) AS unique_customers,
            COALESCE(SUM(od.unit_price * od.quantity * (1 - od.discount)), 0) AS total_revenue,
            (SELECT min(order_date) FROM orders) AS first_order,
            (SELECT max(order_date) FROM orders) AS last_order
        FROM order_details od
    """,
    "top_products": """
        SELECT p.product_name,
               SUM(od.unit_price * od.quantity * (1 - od.discount)) AS revenue
        FROM order_details od
        JOIN products p ON p.product_id = od.product_id
        GROUP BY p.product_name
        ORDER BY revenue DESC
        LIMIT 10
    """,
    "revenue_by_category": """
        SELECT c.category_name AS category,
               SUM(od.unit_price * od.quantity * (1 - od.discount)) AS revenue
        FROM order_details od
        JOIN products p   ON p.product_id  = od.product_id
        JOIN categories c ON c.category_id = p.category_id
        GROUP BY c.category_name
        ORDER BY revenue DESC
    """,
    "revenue_by_country": """
        SELECT o.ship_country AS country,
               SUM(od.unit_price * od.quantity * (1 - od.discount)) AS revenue
        FROM order_details od
        JOIN orders o ON o.order_id = od.order_id
        GROUP BY o.ship_country
        ORDER BY revenue DESC
        LIMIT 12
    """,
    "monthly_revenue": """
        SELECT to_char(date_trunc('month', o.order_date), 'YYYY-MM') AS month,
               SUM(od.unit_price * od.quantity * (1 - od.discount)) AS revenue
        FROM order_details od
        JOIN orders o ON o.order_id = od.order_id
        WHERE o.order_date IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """,
}


def _round_revenue(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for r in rows:
        if "revenue" in r and r["revenue"] is not None:
            r["revenue"] = round(float(r["revenue"]), 2)
    return rows


def _build_live_baseline() -> Dict[str, Any]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_BASELINE_QUERIES["kpis"])
            k = _rows_as_dicts(cur)[0]
            total_orders = int(k["total_orders"] or 0)
            total_revenue = round(float(k["total_revenue"] or 0), 2)
            kpis = {
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "avg_order_value": round(total_revenue / total_orders, 2)
                if total_orders
                else 0,
                "unique_customers": int(k["unique_customers"] or 0),
                "date_range": [str(k["first_order"]), str(k["last_order"])],
            }

            def q(name: str) -> List[Dict[str, Any]]:
                cur.execute(_BASELINE_QUERIES[name])
                return _round_revenue(_rows_as_dicts(cur))

            return {
                "source": "yugabytedb",
                "kpis": kpis,
                "top_products": q("top_products"),
                "revenue_by_category": q("revenue_by_category"),
                "revenue_by_country": q("revenue_by_country"),
                "monthly_revenue": q("monthly_revenue"),
            }


# --------------------------------------------------------------------------- #
# MCP tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def get_northwind_baseline() -> str:
    """Return the curated Northwind baseline (KPIs, top products, revenue by
    category/country, monthly revenue trend) as JSON. Falls back to bundled
    sample data if YugabyteDB is not configured or unreachable; the response's
    `source` field is "yugabytedb" or "sample" accordingly."""
    if not settings.db_configured:
        return json.dumps(SAMPLE_BASELINE)
    try:
        return json.dumps(_build_live_baseline())
    except Exception as exc:  # surfaces as an error span in Langfuse
        fallback = dict(SAMPLE_BASELINE)
        fallback["warning"] = f"DB unreachable, served sample data: {exc}"
        return json.dumps(fallback)


@mcp.tool()
def run_read_only_query(query: str) -> str:
    """Run a read-only SQL query against YugabyteDB under a READ ONLY transaction
    and return rows as JSON. Mutating statements are rejected by the database."""
    if not settings.db_configured:
        return json.dumps({"error": "YB_HOST not configured; no live database."})
    try:
        with _connect() as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(query)
                return json.dumps({"rows": _rows_as_dicts(cur)}, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def summarize_database(schema: str = "") -> str:
    """List every table in the schema with its row count. Use to explore the
    database before writing queries. Defaults to the configured YB_SCHEMA."""
    if not settings.db_configured:
        return json.dumps({"error": "YB_HOST not configured; no live database."})
    schema = schema or settings.yb_schema
    try:
        with _connect() as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s ORDER BY table_name",
                    (schema,),
                )
                tables = [r[0] for r in cur.fetchall()]
                summary = []
                for t in tables:
                    cur.execute(f'SELECT count(*) FROM "{schema}"."{t}"')
                    summary.append({"table": t, "row_count": int(cur.fetchone()[0])})
                return json.dumps({"schema": schema, "tables": summary})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
