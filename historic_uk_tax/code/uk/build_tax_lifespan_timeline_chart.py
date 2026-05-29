#!/usr/bin/env python3
"""Build a compact lifespan timeline chart for UK taxes."""

from __future__ import annotations

import argparse
import csv
import html
import json
from calendar import monthrange
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_lifespans_broad.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_lifespan_timeline.json"
TODAY = date(2026, 5, 28)
DEFAULT_START_YEAR = 1000


GROUPS = [
    ("Employment taxes", "#006D77"),
    ("Goods/services", "#D9480F"),
    ("Business", "#2B4C7E"),
    ("Land", "#F59F00"),
    ("Wealth", "#8E44AD"),
    ("Environment & energy", "#2B8A3E"),
    ("Other", "#1B6CA8"),
]

GROUP_COLOURS = dict(GROUPS)
MONTH_NAMES = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


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


def classify(row: dict[str, str]) -> str:
    text = " ".join(
        [
            row["tax_name"],
            row["parent_tax"],
            row["category"],
            row["tax_id"],
        ]
    ).lower()
    if "corporation" in text or "business" in text or "bank" in text or "profits" in text or "petroleum" in text:
        return "Business"
    if (
        "environment" in text
        or "carbon" in text
        or "climate" in text
        or "landfill" in text
        or "emissions" in text
        or "aggregates" in text
        or "plastic" in text
        or "green gas" in text
        or "renewables" in text
    ):
        return "Environment & energy"
    if (
        "capital gains" in text
        or "inheritance" in text
        or "estate duty" in text
        or "legacy duty" in text
        or "succession duty" in text
        or "wealth" in text
        or "securities" in text
        or "shares" in text
        or "bearer" in text
        or "dividend" in text
        or "savings" in text
        or "rent income" in text
    ):
        return "Wealth"
    if (
        "land" in text
        or "property" in text
        or "rate" in text
        or "council tax" in text
        or "dwelling" in text
        or "house" in text
        or "hearth" in text
        or "window" in text
        or "development" in text
        or "infrastructure" in text
        or "building safety" in text
    ):
        return "Land"
    if (
        "national insurance" in text
        or "social contribution" in text
        or "payroll" in text
        or "employment" in text
        or "apprenticeship levy" in text
        or "income tax" in text
        or "special contribution" in text
        or "health and social care" in text
    ):
        return "Employment taxes"
    if (
        "duty" in text
        or "custom" in text
        or "excise" in text
        or "commodity" in text
        or "drink" in text
        or "vat" in text
        or "betting" in text
        or "gaming" in text
        or "gambling" in text
        or "bingo" in text
        or "lottery" in text
        or ("levy" in text and "soft drinks" in text)
    ):
        return "Goods/services"
    return "Other"


def format_date(year: str, value: str, *, active_text: str | None = None) -> str:
    if active_text is not None:
        return active_text
    if value:
        parts = value.split("-")
        if len(parts) == 3:
            year_part, month_part, day_part = parts
            return f"{int(day_part)} {MONTH_NAMES[int(month_part)]} {year_part}"
        if len(parts) == 2:
            year_part, month_part = parts
            return f"{MONTH_NAMES[int(month_part)]} {year_part}"
        return value
    if year:
        return year
    return "unknown"


def line_points(
    start: date,
    end: date,
    chart_start: date,
    lane: int,
) -> list[list[str | int]]:
    start_value = max(start, chart_start)
    end_value = end
    point_values = {start_value, end_value}

    first_tick = (start_value.year // 5) * 5
    if first_tick < start_value.year:
        first_tick += 5
    tick = first_tick
    while tick < end_value.year:
        point_values.add(date(tick, 1, 1))
        tick += 5

    return [[value.isoformat(), lane] for value in sorted(point_values)]


def interval(row: dict[str, str], chart_end: date) -> tuple[date, date, str, str] | None:
    if row["episode_status"] == "chart_split_only":
        return None

    start = parse_partial_date(row["start_year"], row["start_date"], is_end=False)
    if start is None:
        return None

    if row["episode_status"] == "active":
        end = chart_end
        end_label = "still in force"
        line_type = "solid"
    elif row["episode_status"] == "not_yet_in_force":
        end = chart_end
        end_label = "announced/not yet in force"
        line_type = "dashed"
    elif row["episode_status"] == "extant_at_source_date" and not row["end_year"]:
        end = date(1885, 12, 31)
        end_label = "extant in source; later end not traced"
        line_type = "dashed"
    elif row["episode_status"] == "unknown":
        end = chart_end
        end_label = "end not yet traced"
        line_type = "dotted"
    else:
        end = parse_partial_date(row["end_year"], row["end_date"], is_end=True)
        if end is None:
            return None
        end_label = format_date(row["end_year"], row["end_date"])
        line_type = "solid"

    if end < start:
        end = start
    return start, min(end, chart_end), end_label, line_type


def tooltip_html(row: dict[str, str], group: str, start_label: str, end_label: str, colour: str) -> str:
    tax_name = html.escape(row["tax_name"])
    group_label = html.escape(group)
    status = html.escape(row["episode_status"].replace("_", " "))
    jurisdiction = html.escape(row["jurisdiction"] or "unknown")
    parent = row["parent_tax"].strip()
    parent_line = ""
    if parent and parent.lower() != row["tax_name"].lower():
        parent_line = (
            "<div style='margin-top:4px;font-size:12px;line-height:1.35;color:#cbd5e1'>"
            f"{html.escape(parent)}"
            "</div>"
        )

    return (
        "<div style='min-width:260px;max-width:360px;padding:12px 14px'>"
        "<div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>"
        f"<span style='width:10px;height:10px;border-radius:999px;background:{colour};display:inline-block'></span>"
        f"<span style='font-size:12px;letter-spacing:.02em;text-transform:uppercase;color:#bfdbfe'>{group_label}</span>"
        "</div>"
        f"<div style='font-size:16px;line-height:1.25;font-weight:700;color:#fff'>{tax_name}</div>"
        f"{parent_line}"
        "<div style='margin-top:10px;display:grid;grid-template-columns:72px 1fr;gap:4px 12px;font-size:13px;line-height:1.35'>"
        "<div style='color:#94a3b8'>Start</div>"
        f"<div style='color:#f8fafc'>{html.escape(start_label)}</div>"
        "<div style='color:#94a3b8'>End</div>"
        f"<div style='color:#f8fafc'>{html.escape(end_label)}</div>"
        "<div style='color:#94a3b8'>Status</div>"
        f"<div style='color:#f8fafc'>{status}</div>"
        "<div style='color:#94a3b8'>Place</div>"
        f"<div style='color:#f8fafc'>{jurisdiction}</div>"
        "</div>"
        "</div>"
    )


def build_option(rows: list[dict[str, str]], start_year: int) -> dict:
    chart_start = date(start_year, 1, 1)
    chart_end = max(
        [TODAY]
        + [
            parse_partial_date(row["start_year"], row["start_date"], is_end=False)
            for row in rows
            if row["episode_status"] == "not_yet_in_force"
        ]
    )

    items = []
    skipped = 0
    for row in rows:
        row_interval = interval(row, chart_end)
        if row_interval is None:
            skipped += 1
            continue
        start, end, end_label, line_type = row_interval
        if end < chart_start:
            skipped += 1
            continue
        group = classify(row)
        items.append((start, end, row["tax_name"].lower(), row, group, end_label, line_type))

    items.sort(key=lambda item: (item[0], item[1], item[2]))

    series = []
    for group, colour in GROUPS:
        series.append(
            {
                "name": group,
                "type": "line",
                "color": colour,
                "data": [],
                "showInLegend": True,
                "symbol": "none",
                "lineStyle": {"color": colour, "width": 4},
                "itemStyle": {"color": colour},
                "tooltip": {"show": False},
            }
        )

    for item_index, (start, end, _sort_name, row, group, end_label, line_type) in enumerate(items):
        lane = len(items) - item_index - 1
        colour = GROUP_COLOURS[group]
        start_label = format_date(row["start_year"], row["start_date"])
        tooltip = tooltip_html(row, group, start_label, end_label, colour)
        opacity = 0.72 if line_type == "solid" else 0.45
        series.append(
            {
                "id": f"{row['tax_id']}-{row['episode']}",
                "taxName": row["tax_name"],
                "groupName": group,
                "type": "line",
                "showInLegend": False,
                "showSymbol": True,
                "symbol": "circle",
                "symbolSize": 7,
                "triggerLineEvent": True,
                "smooth": False,
                "data": line_points(start, end, chart_start, lane),
                "lineStyle": {
                    "color": colour,
                    "width": 2.5,
                    "opacity": opacity,
                    "type": line_type,
                    "cap": "round",
                },
                "itemStyle": {
                    "color": colour,
                    "opacity": 0,
                },
                "tooltip": {
                    "formatter": tooltip,
                },
                "emphasis": {
                    "focus": "series",
                    "lineStyle": {
                        "width": 6,
                        "opacity": 1,
                    },
                },
                "z": 2,
            }
        )

    return {
        "color": [colour for _group, colour in GROUPS],
        "title": {
            "text": "Every UK tax since William the Conqueror",
            "left": "50%",
            "textAlign": "center",
            "top": 8,
        },
        "tooltip": {
            "trigger": "item",
            "backgroundColor": "rgba(15,23,42,0.97)",
            "borderColor": "rgba(148,163,184,0.45)",
            "borderWidth": 1,
            "padding": 0,
            "confine": True,
            "extraCssText": "border-radius:12px;box-shadow:0 18px 45px rgba(15,23,42,.34);",
            "textStyle": {
                "fontFamily": "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
            },
        },
        "legend": {
            "type": "scroll",
            "top": 54,
            "left": "center",
            "itemWidth": 18,
            "itemHeight": 4,
            "textStyle": {"fontSize": 11, "color": "#334155"},
            "data": [
                {
                    "name": group,
                    "icon": "path://M0 45 L100 45 L100 55 L0 55 Z",
                    "itemStyle": {"color": colour, "borderColor": colour},
                }
                for group, colour in GROUPS
            ],
        },
        "grid": {
            "left": 18,
            "right": 22,
            "top": 98,
            "bottom": 42,
            "containLabel": False,
        },
        "xAxis": {
            "type": "time",
            "min": chart_start.isoformat(),
            "max": chart_end.isoformat(),
            "axisLine": {"lineStyle": {"color": "#94a3b8"}},
            "axisTick": {"lineStyle": {"color": "#cbd5e1"}},
            "axisLabel": {
                "formatter": "{yyyy}",
                "color": "#475569",
            },
            "splitLine": {"show": True, "lineStyle": {"color": "#eef2f7"}},
        },
        "yAxis": {
            "type": "value",
            "inverse": True,
            "min": -1,
            "max": max(len(items), 1),
            "show": False,
        },
        "series": series,
        "_tpaMeta": {
            "items": len(items),
            "skipped_missing_or_out_of_range": skipped,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    args = parser.parse_args()

    with args.input.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    option = build_option(rows, args.start_year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(option, indent=2) + "\n")
    print(f"Wrote {args.output}")
    print(f"Tax episodes plotted: {option['_tpaMeta']['items']}")
    print(f"Skipped rows: {option['_tpaMeta']['skipped_missing_or_out_of_range']}")


if __name__ == "__main__":
    main()
