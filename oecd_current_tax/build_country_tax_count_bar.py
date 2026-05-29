#!/usr/bin/env python3
"""Build the country tax-count bar chart.

Input CSV columns:
  country,tax_count,color
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent
INPUT = BASE / "country_tax_counts.csv"
OUTPUT = BASE / "country_tax_count_comparison_2024.json"


def read_rows() -> list[dict]:
    with INPUT.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda row: (int(row["tax_count"]), row["country"]))
    return rows


def build_chart(rows: list[dict]) -> dict:
    countries = [row["country"] for row in rows]
    data = [
        {
            "name": row["country"],
            "value": int(row["tax_count"]),
            "itemStyle": {"color": row.get("color") or "#9CA3AF"},
        }
        for row in rows
    ]
    return {
        "title": {
            "text": "Number of taxes by country",
            "subtext": "UK, France and Germany use our project counts; other countries use Eurostat National Tax List named 2024 lines",
            "left": "center",
            "top": 8,
            "textStyle": {"fontSize": 20, "fontWeight": 700, "color": "#111827"},
            "subtextStyle": {"fontSize": 12, "color": "#4B5563"},
        },
        "_tpaTooltip": {"template": "{name}<br>Taxes counted: {x:0}"},
        "tooltip": {"trigger": "item"},
        "grid": {"left": 150, "right": 58, "top": 82, "bottom": 48, "containLabel": True},
        "xAxis": {
            "type": "value",
            "name": "Number of taxes",
            "nameLocation": "middle",
            "nameGap": 34,
            "axisLabel": {"color": "#374151"},
            "splitLine": {"lineStyle": {"color": "#E5E7EB"}},
        },
        "yAxis": {
            "type": "category",
            "inverse": True,
            "data": countries,
            "axisLabel": {"color": "#111827", "fontSize": 12},
            "axisTick": {"show": False},
        },
        "series": [{"type": "bar", "data": data, "barWidth": 18}],
    }


def main() -> None:
    rows = read_rows()
    OUTPUT.write_text(json.dumps(build_chart(rows), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
