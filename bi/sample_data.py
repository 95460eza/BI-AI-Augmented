"""Bundled Northwind baseline sample.

Used by the YugabyteDB MCP server as a fallback when YB_HOST is not configured
or the database is unreachable, so the pipeline always has data to run on. The
shape is identical to what the live aggregate queries return, and the figures are
representative of the classic Northwind dataset.
"""

from __future__ import annotations

from typing import Any, Dict

SAMPLE_BASELINE: Dict[str, Any] = {
    "source": "sample",
    "kpis": {
        "total_orders": 830,
        "total_revenue": 1265793.04,
        "avg_order_value": 1525.05,
        "unique_customers": 89,
        "date_range": ["1996-07-04", "1998-05-06"],
    },
    "top_products": [
        {"product_name": "Côte de Blaye", "revenue": 149984.20},
        {"product_name": "Thüringer Rostbratwurst", "revenue": 80368.67},
        {"product_name": "Raclette Courdavault", "revenue": 71155.70},
        {"product_name": "Tarte au sucre", "revenue": 47234.97},
        {"product_name": "Camembert Pierrot", "revenue": 46825.48},
        {"product_name": "Gnocchi di nonna Alice", "revenue": 42593.06},
        {"product_name": "Manjimup Dried Apples", "revenue": 41819.65},
        {"product_name": "Alice Mutton", "revenue": 32698.38},
        {"product_name": "Carnarvon Tigers", "revenue": 29171.87},
        {"product_name": "Rössle Sauerkraut", "revenue": 25696.64},
    ],
    "revenue_by_category": [
        {"category": "Beverages", "revenue": 267868.18},
        {"category": "Dairy Products", "revenue": 234507.29},
        {"category": "Confections", "revenue": 167357.22},
        {"category": "Meat/Poultry", "revenue": 163022.36},
        {"category": "Seafood", "revenue": 131261.74},
        {"category": "Condiments", "revenue": 106047.09},
        {"category": "Produce", "revenue": 99984.58},
        {"category": "Grains/Cereals", "revenue": 95744.59},
    ],
    "revenue_by_country": [
        {"country": "USA", "revenue": 245582.85},
        {"country": "Germany", "revenue": 230284.63},
        {"country": "Austria", "revenue": 128003.84},
        {"country": "Brazil", "revenue": 106925.78},
        {"country": "France", "revenue": 81358.31},
        {"country": "UK", "revenue": 58971.31},
        {"country": "Venezuela", "revenue": 56810.51},
        {"country": "Sweden", "revenue": 54495.30},
    ],
    "monthly_revenue": [
        {"month": "1997-01", "revenue": 61258.07},
        {"month": "1997-02", "revenue": 38483.63},
        {"month": "1997-03", "revenue": 38547.22},
        {"month": "1997-04", "revenue": 53032.95},
        {"month": "1997-05", "revenue": 53781.29},
        {"month": "1997-06", "revenue": 36362.80},
        {"month": "1997-07", "revenue": 51020.86},
        {"month": "1997-08", "revenue": 47287.67},
        {"month": "1997-09", "revenue": 55629.24},
        {"month": "1997-10", "revenue": 66749.23},
        {"month": "1997-11", "revenue": 43533.81},
        {"month": "1997-12", "revenue": 71398.43},
    ],
}
