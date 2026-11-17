#!/usr/bin/env python3
# Copyright (c) 2026 Tax Policy Associates Ltd
# SPDX-License-Identifier: MIT
"""Build a stacked bar chart of how many UK taxes were in force each year, split by category."""

from __future__ import annotations

import argparse
import csv
import json
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

from build_tax_lifespan_timeline_chart import GROUPS, classify


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_lifespans_broad.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_count_over_time_2026_11.json"
# Fixed rather than date.today(), so a re-run gives the same chart.
TODAY = date(2026, 11, 17)
DEFAULT_START_YEAR = 1000
# Label every hundredth year: ECharts takes the number of labels to skip.
CENTURY_CATEGORY_INTERVAL = 99


def parse_partial_date(year: str, value: str, *, is_end: bool) -> date | None:
    """Turn a year and an optional "YYYY", "YYYY-MM" or "YYYY-MM-DD" date into a date.

    Missing parts are filled in as early as possible for a start and as late as
    possible for an end, so a tax that ended in "1799" counts for all of 1799.
    """
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
    """The dates a tax was in force, clipped to the chart, or None if it isn't counted."""
    if row["episode_status"] in {"chart_split_only", "announced_not_enacted"}:
        # Not law yet, or a row that repeats a tax we count at another level
        # (a parent tax counted through its parts, or the reverse).
        return None
    if row["episode_status"] == "not_yet_in_force" and not include_future:
        return None
    if row["episode_status"] == "unknown":
        return None
    if not row["start_year"]:
        return None

    start = row_start(row)
    if start is None:
        return None
    if row["episode_status"] == "not_yet_in_force":
        # Law but not yet started. We count taxes on the statute book, so it
        # counts from today.
        start = min(start, chart_end)
    if start > chart_end:
        return None

    if row["episode_status"] in {"active", "not_yet_in_force"}:
        end = chart_end
    elif row["episode_status"] == "extant_at_source_date" and not row["end_year"]:
        # Dowell, our main historical source, has these still in force in 1885.
        # We haven't yet traced when they ended, so they stop at the end of 1885.
        end = date(1885, 12, 31)
    else:
        end = parse_partial_date(row["end_year"], row["end_date"], is_end=True)

    if end is None:
        return None
    if end < chart_start or start > chart_end:
        return None
    return max(start, chart_start), min(end, chart_end)


def chart_end(rows: list[dict[str, str]], include_future: bool) -> date:
    """The chart ends today. Taxes that are law but haven't started yet count from today."""
    return TODAY


def build_series(
    rows: list[dict[str, str]],
    chart_start: date,
    include_future: bool,
) -> list[dict[str, str | list[float | int]]]:
    """A running count with a point on each date the count changes (unused by the bar chart)."""
    end_date = chart_end(rows, include_future)
    events: dict[date, int] = {}
    for row in rows:
        interval = row_interval(row, chart_start, end_date, include_future)
        if interval is None:
            continue
        start, end = interval
        events[start] = events.get(start, 0) + 1
        # A tax drops out of the count the day after it ends.
        after_end = end + timedelta(days=1)
        if after_end <= end_date:
            events[after_end] = events.get(after_end, 0) - 1

    # Taxes already in force when the chart starts.
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
    """Count the taxes in force on 31 December of each year (today, for this year).

    So a tax introduced during a year shows in that year, and one abolished
    during a year doesn't.
    """
    end_date = chart_end(rows, include_future)
    categories = year_categories(chart_start, end_date)
    intervals = [
        interval
        for row in rows
        if (interval := row_interval(row, chart_start, end_date, include_future)) is not None
    ]

    data: list[int] = []
    for year_label in categories:
        point = min(date(int(year_label), 12, 31), end_date)
        data.append(sum(1 for start, end in intervals if start <= point <= end))
    return categories, data


def build_annual_series_by_group(
    rows: list[dict[str, str]],
    chart_start: date,
    include_future: bool,
) -> tuple[list[str], dict[str, list[int]]]:
    """The same year-end counts, split into the seven categories of the lifespan timeline."""
    end_date = chart_end(rows, include_future)
    categories = year_categories(chart_start, end_date)
    intervals = [
        (classify(row), interval)
        for row in rows
        if (interval := row_interval(row, chart_start, end_date, include_future)) is not None
    ]

    data: dict[str, list[int]] = {group: [] for group, _ in GROUPS}
    for year_label in categories:
        point = min(date(int(year_label), 12, 31), end_date)
        counts = {group: 0 for group, _ in GROUPS}
        for group, (start, end) in intervals:
            if start <= point <= end:
                counts[group] += 1
        for group in counts:
            data[group].append(counts[group])
    return categories, data


# Our website's chart loader builds the tooltip from a heading plus one row per
# category, filling in {x} (the year), {name} (the bar's name, which we set to
# the year's total), {series} and {y}. It has no placeholder for a colour, so
# the heading carries a small stylesheet that colours each row's dot.
TOOLTIP_WIDTH = "width:214px"
TOOLTIP_DOT_CSS = "".join(
    f'.tpa-tax-dot[data-group="{group}"]{{background:{colour}}}' for group, colour in GROUPS
)
TOOLTIP_HEADER = (
    f"<style>{TOOLTIP_DOT_CSS}</style>"
    f"<span style='display:inline-block;{TOOLTIP_WIDTH};font-size:11px;line-height:1.3;"
    "letter-spacing:.06em;text-transform:uppercase;color:#bfdbfe'>{x}</span><br>"
    f"<span style='display:inline-block;{TOOLTIP_WIDTH};font-size:18px;line-height:1.3;font-weight:700;"
    "color:#fff;padding-bottom:8px;margin-bottom:4px;border-bottom:1px solid rgba(148,163,184,.35)'>{name}</span>"
)
TOOLTIP_ROW = (
    f"<span style='display:inline-flex;align-items:center;{TOOLTIP_WIDTH};font-size:13px;line-height:1.5;"
    "color:#cbd5e1'>"
    "<i class='tpa-tax-dot' data-group='{series}' style='flex:none;width:9px;height:9px;border-radius:999px;"
    "margin-right:9px;box-shadow:0 0 0 1px rgba(255,255,255,.45)'></i>"
    "<span style='flex:1'>{series}</span>"
    "<b style='color:#fff;font-weight:600'>{y:0,0}</b></span>"
)


def build_option(categories: list[str], grouped: dict[str, list[int]], totals: list[int]) -> dict:
    # Each bar is named with the year's total ("102 taxes") so the tooltip can
    # use it as the heading; a separate total series would add a legend entry.
    # Zero counts are null, so the tooltip leaves those categories out.
    def heading(index: int) -> str:
        total = totals[index]
        return f"{total} {'tax' if total == 1 else 'taxes'}"

    group_series = [
        {
            "name": group,
            "type": "bar",
            "stack": "taxes",
            "barCategoryGap": "0%",
            "itemStyle": {"color": colour},
            "emphasis": {"disabled": True},
            "data": [
                {"name": heading(index), "value": value} if value else None
                for index, value in enumerate(grouped[group])
            ],
        }
        for group, colour in GROUPS
    ]
    return {
        "title": {
            "text": "Number of UK taxes over time",
            "left": "50%",
            "textAlign": "center",
            "top": 8,
        },
        "_tpaTooltip": {
            "header": TOOLTIP_HEADER,
            "template": TOOLTIP_ROW,
            "skipNull": True,
        },
        # The same dark tooltip as the lifespan timeline.
        "tooltip": {
            "trigger": "axis",
            "confine": True,
            "backgroundColor": "rgba(15,23,42,0.97)",
            "borderColor": "rgba(148,163,184,0.45)",
            "borderWidth": 1,
            "padding": [12, 14],
            "textStyle": {"color": "#f8fafc", "fontSize": 13},
            "extraCssText": "border-radius:12px;box-shadow:0 18px 45px rgba(15,23,42,.34);",
            "axisPointer": {"type": "line", "lineStyle": {"color": "#475569", "width": 1, "type": "solid"}},
        },
        "legend": {
            "type": "scroll",
            "top": 42,
            "left": "center",
            "itemWidth": 14,
            "itemHeight": 10,
            "textStyle": {"fontSize": 11, "color": "#334155"},
            "data": [group for group, _ in GROUPS],
        },
        "grid": {
            "left": "6%",
            "right": "4%",
            "top": 100,
            "bottom": 48,
            "containLabel": True,
        },
        "xAxis": {
            "type": "category",
            "name": "Year",
            "nameLocation": "middle",
            "nameGap": 30,
            "data": categories,
            "axisTick": {
                "alignWithLabel": True,
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
        "series": group_series,
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
        help="Leave out taxes that are law but have not yet started.",
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
    grouped_categories, grouped = build_annual_series_by_group(
        rows,
        chart_start=chart_start,
        include_future=not args.exclude_future,
    )
    assert grouped_categories == categories
    assert [sum(grouped[group][i] for group in grouped) for i in range(len(categories))] == data
    option = build_option(categories, grouped, data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(option, indent=2) + "\n")
    print(f"Wrote {args.output}")
    print(f"Points: {len(data)}")
    print(f"Final count in {categories[-1]}: {data[-1]}")


if __name__ == "__main__":
    main()
