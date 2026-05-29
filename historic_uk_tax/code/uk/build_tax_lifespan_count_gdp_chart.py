#!/usr/bin/env python3
"""Build an ECharts line chart for UK tax count and receipts/GDP over time."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

from build_tax_lifespan_count_chart import (
    CENTURY_CATEGORY_INTERVAL,
    DEFAULT_INPUT,
    DEFAULT_START_YEAR,
    build_annual_series,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPTS_INPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_receipts_gdp_share.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_count_and_gdp_over_time.json"


def load_receipts_by_year(path: Path) -> dict[str, float]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    data: dict[str, float] = {}
    for row in rows:
        year = str(int(row["date"].split("-", maxsplit=1)[0]))
        data[year] = round(float(row["pct_gdp"]), 2)
    return data


def build_receipts_series(categories: list[str], receipts_by_year: dict[str, float]) -> list[float | None]:
    return [receipts_by_year.get(year) for year in categories]


def build_option(
    categories: list[str],
    tax_count_data: list[int],
    receipts_data: list[float | None],
    chart_start: date,
) -> dict:
    return {
        "title": {
            "text": "Number of UK taxes over time, and tax receipts as % of GDP",
            "left": "50%",
            "textAlign": "center",
            "top": 8,
        },
        "_tpaTooltip": {
            "template": "{name}<br>{series}: {y:0.0}",
        },
        "tooltip": {
            "trigger": "axis",
        },
        "legend": {
            "top": 42,
            "left": "center",
            "itemWidth": 28,
            "itemHeight": 4,
            "data": ["Taxes in force", "Tax receipts (% GDP)"],
        },
        "grid": {
            "left": "6%",
            "right": "7%",
            "top": 86,
            "bottom": 48,
            "containLabel": True,
        },
        "xAxis": {
            "type": "category",
            "name": "Year",
            "nameLocation": "middle",
            "nameGap": 30,
            "boundaryGap": False,
            "data": categories,
            "axisTick": {
                "interval": CENTURY_CATEGORY_INTERVAL,
            },
            "axisLabel": {
                "interval": CENTURY_CATEGORY_INTERVAL,
            },
        },
        "yAxis": [
            {
                "type": "value",
                "name": "Taxes",
                "min": 0,
                "axisLabel": {
                    "formatter": "{value}",
                },
                "splitLine": {
                    "lineStyle": {
                        "color": "#e5e7eb",
                    },
                },
            },
            {
                "type": "value",
                "name": "% GDP",
                "min": 0,
                "axisLabel": {
                    "formatter": "{value}%",
                },
                "splitLine": {
                    "show": False,
                },
            },
        ],
        "series": [
            {
                "name": "Taxes in force",
                "type": "line",
                "step": "end",
                "showSymbol": False,
                "lineStyle": {
                    "width": 3,
                    "color": "#2563eb",
                },
                "areaStyle": {
                    "color": "rgba(37, 99, 235, 0.10)",
                },
                "emphasis": {
                    "focus": "series",
                },
                "data": tax_count_data,
            },
            {
                "name": "Tax receipts (% GDP)",
                "type": "line",
                "yAxisIndex": 1,
                "showSymbol": False,
                "connectNulls": True,
                "lineStyle": {
                    "width": 3,
                    "color": "#b91c1c",
                },
                "emphasis": {
                    "focus": "series",
                },
                "data": receipts_data,
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--receipts-input", type=Path, default=DEFAULT_RECEIPTS_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--start-year",
        type=int,
        default=DEFAULT_START_YEAR,
        help="First year to show on the chart.",
    )
    parser.add_argument(
        "--exclude-future",
        action="store_true",
        help="Exclude announced taxes that are not yet in force.",
    )
    args = parser.parse_args()

    with args.input.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    chart_start = date(args.start_year, 1, 1)
    categories, tax_count_data = build_annual_series(
        rows,
        chart_start=chart_start,
        include_future=not args.exclude_future,
    )
    receipts_data = build_receipts_series(categories, load_receipts_by_year(args.receipts_input))
    option = build_option(categories, tax_count_data, receipts_data, chart_start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(option, indent=2) + "\n")
    print(f"Wrote {args.output}")
    print(f"Tax-count points: {len(tax_count_data)}")
    print(f"Receipts/GDP points: {len(receipts_data)}")
    print(f"Final count in {categories[-1]}: {tax_count_data[-1]}")


if __name__ == "__main__":
    main()
