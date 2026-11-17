#!/usr/bin/env python3
# Copyright (c) 2026 Tax Policy Associates Ltd
# SPDX-License-Identifier: MIT
"""Build the bar chart of how many taxes each country has, reading country_tax_counts.csv (columns country, tax_count, color) and writing an ECharts spec to country_tax_count_comparison_2024.json."""

from __future__ import annotations

import csv
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent
# Data sits beside the script in the public repo, and in code/data in our working repo.
DATA_DIR = BASE / "data" if (BASE / "data").is_dir() else BASE.parent / "data" / "country_comparison"
INPUT = DATA_DIR / "country_tax_counts.csv"
OUTPUT = DATA_DIR / "country_tax_count_comparison_2024.json"


def read_rows() -> list[dict]:
    with INPUT.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Ties keep the order they have in the CSV.
    rows.sort(key=lambda row: int(row["tax_count"]))
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
        # Not an ECharts option: read by the page that embeds the chart.
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
        "series": [
            {
                "name": "Taxes",
                "type": "bar",
                "barMaxWidth": 18,
                "label": {"show": True, "position": "right", "color": "#111827", "fontSize": 11, "formatter": "{c}"},
                "data": data,
            }
        ],
    }


def main() -> None:
    rows = read_rows()
    OUTPUT.write_text(json.dumps(build_chart(rows), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
