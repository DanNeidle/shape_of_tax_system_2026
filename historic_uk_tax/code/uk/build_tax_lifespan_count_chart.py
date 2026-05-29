#!/usr/bin/env python3
"""Build an ECharts line chart for the broad UK tax count over time."""

from __future__ import annotations

import argparse
import csv
import json
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_lifespans_broad.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_count_over_time.json"
TODAY = date(2026, 5, 28)
DEFAULT_START_YEAR = 1000
CENTURY_CATEGORY_INTERVAL = 99


def parse_partial_date(year: str, value: str, *, is_end: bool) -> date | None:
    if not year:
        return None
    if not value:
        return date(int(year), 12, 31) if is_end else date(int(year), 1, 1)

    parts = [int(part) for part in value.split("-")]
    if len(parts) == 1:
        return date(parts[0], 12, 31) if is_end else date(parts[0], 1, 1)
    if len(parts) == 2:
        if is_end:
            return date(parts[0], parts[1], monthrange(parts[0], parts[1])[1])
        return date(parts[0], parts[1], 1)
    return date(parts[0], parts[1], parts[2])


def row_start(row: dict[str, str]) -> date | None:
    return parse_partial_date(row["start_year"], row["start_date"], is_end=False)


def row_interval(
    row: dict[str, str],
    chart_start: date,
    chart_end: date,
    include_future: bool,
) -> tuple[date, date] | None:
    if row["episode_status"] == "chart_split_only":
        return None
    if row["episode_status"] == "not_yet_in_force" and not include_future:
        return None
    if row["episode_status"] == "unknown":
        return None
    if not row["start_year"]:
        return None

    start = row_start(row)
    if start is None or start > chart_end:
        return None

    if row["episode_status"] in {"active", "not_yet_in_force"}:
        end = chart_end
    elif row["episode_status"] == "extant_at_source_date" and not row["end_year"]:
        # Dowell-era rows marked extant but not yet traced past the source date.
        end = date(1885, 12, 31)
    else:
        end = parse_partial_date(row["end_year"], row["end_date"], is_end=True)

    if end is None:
        return None
    if end < chart_start or start > chart_end:
        return None
    return max(start, chart_start), min(end, chart_end)


def chart_end(rows: list[dict[str, str]], include_future: bool) -> date:
    end = TODAY
    if include_future:
        for row in rows:
            if row["episode_status"] == "not_yet_in_force":
                start = row_start(row)
                if start is not None:
                    end = max(end, start)
    return end


def build_series(
    rows: list[dict[str, str]],
    chart_start: date,
    include_future: bool,
) -> list[dict[str, str | list[float | int]]]:
    end_date = chart_end(rows, include_future)
    events: dict[date, int] = {}
    for row in rows:
        interval = row_interval(row, chart_start, end_date, include_future)
        if interval is None:
            continue
        start, end = interval
        events[start] = events.get(start, 0) + 1
        after_end = end + timedelta(days=1)
        if after_end <= end_date:
            events[after_end] = events.get(after_end, 0) - 1

    # Count anything already in force at the chart start.
    count = 0
    for event_date in sorted(date_ for date_ in events if date_ <= chart_start):
        count += events[event_date]

    data: list[dict[str, str | list[float | int]]] = [
        {"name": chart_start.isoformat(), "value": [chart_start.isoformat(), count]}
    ]
    for event_date in sorted(date_ for date_ in events if chart_start < date_ <= end_date):
        count += events[event_date]
        data.append({"name": event_date.isoformat(), "value": [event_date.isoformat(), count]})
    if data[-1]["name"] != end_date.isoformat():
        data.append({"name": end_date.isoformat(), "value": [end_date.isoformat(), count]})
    return data


def year_categories(chart_start: date, chart_max: date) -> list[str]:
    return [str(year) for year in range(chart_start.year, chart_max.year + 1)]


def build_annual_series(
    rows: list[dict[str, str]],
    chart_start: date,
    include_future: bool,
) -> tuple[list[str], list[int]]:
    end_date = chart_end(rows, include_future)
    categories = year_categories(chart_start, end_date)
    intervals = [
        interval
        for row in rows
        if (interval := row_interval(row, chart_start, end_date, include_future)) is not None
    ]

    data: list[int] = []
    for year_label in categories:
        # Use year-end counts so in-year enactments are visible in their calendar year.
        point = min(date(int(year_label), 12, 31), end_date)
        data.append(sum(1 for start, end in intervals if start <= point <= end))
    return categories, data


def build_option(categories: list[str], data: list[int], chart_start: date) -> dict:
    return {
        "title": {
            "text": "Number of UK taxes over time",
            "left": "50%",
            "textAlign": "center",
            "top": 8,
        },
        "_tpaTooltip": {
            "template": "{name}<br>Taxes in force: {y:0,0}",
        },
        "tooltip": {
            "trigger": "axis",
        },
        "grid": {
            "left": "6%",
            "right": "4%",
            "top": 64,
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
        "yAxis": {
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
                    "color": "rgba(37, 99, 235, 0.12)",
                },
                "emphasis": {
                    "focus": "series",
                },
                "data": data,
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
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
    categories, data = build_annual_series(
        rows,
        chart_start=chart_start,
        include_future=not args.exclude_future,
    )
    option = build_option(categories, data, chart_start=chart_start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(option, indent=2) + "\n")
    print(f"Wrote {args.output}")
    print(f"Points: {len(data)}")
    print(f"Final count in {categories[-1]}: {data[-1]}")


if __name__ == "__main__":
    main()
