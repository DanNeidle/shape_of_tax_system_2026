#!/usr/bin/env python3
# Copyright (c) 2026 Tax Policy Associates Ltd
# SPDX-License-Identifier: MIT
"""Build a timeline of UK taxes: one line for each period a tax was in force, coloured by category."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from calendar import monthrange
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_lifespans_broad.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "code/data/uk_tax/uk_tax_lifespan_timeline_2026_11.json"
# Fixed rather than date.today(), so a re-run gives the same chart.
TODAY = date(2026, 11, 17)
DEFAULT_START_YEAR = 1000


# The seven categories and their colours, in legend order.
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
    """Turn a year and an optional "YYYY", "YYYY-MM" or "YYYY-MM-DD" date into a date.

    Missing parts are filled in as early as possible for a start and as late as
    possible for an end, so a tax that ended in "1799" runs to 31 December 1799.
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


# Current taxes take their category from our sunburst chart of the 2025-26 tax
# system. A few current taxes aren't on the sunburst; they are listed last in
# each category, next to their nearest neighbours. Abolished taxes are left to
# the keyword rules in classify().
SUNBURST_GROUPS = {
    "Employment taxes": [
        "income_tax", "employer_national_insurance_contributions", "employee_national_insurance_contributions",
        "self_employed_national_insurance_contributions", "other_national_insurance_contributions",
        "apprenticeship_levy",
    ],
    "Goods/services": [
        "value_added_tax", "insurance_premium_tax", "air_passenger_duty", "fuel_duty", "beer_duty", "wine_duty",
        "home_spirits_duty", "vehicle_excise_duty", "tobacco_duty", "modern_customs_duties",
        "remote_gaming_duty", "lottery_duty", "general_betting_duty", "machine_games_duty", "gaming_duty",
        "bingo_duty", "pool_betting_duty", "soft_drinks_industry_levy", "hgv_road_user_levy",
        "statutory_gambling_levy",
        # Not on the sunburst:
        "vaping_products_duty",
    ],
    "Business": [
        "onshore_corporation_tax", "ring_fence_corporation_tax", "digital_services_tax", "bank_levy",
        "bank_surcharge", "diverted_profits_tax", "residential_property_developer_tax", "energy_profits_levy",
        "electricity_generator_levy", "petroleum_revenue_tax",
        # Not on the sunburst:
        "multinational_top_up_tax", "domestic_top_up_tax", "public_interest_business_protection_tax",
    ],
    "Land": [
        "council_tax", "business_rates", "northern_ireland_domestic_rates", "northern_ireland_business_rates",
        "residential_sdlt", "additional_dwellings_sdlt", "non_resident_sdlt", "non_residential_sdlt",
        "annual_tax_enveloped_dwellings", "land_buildings_transaction_tax", "land_transaction_tax_wales",
    ],
    "Wealth": [
        "capital_gains_tax", "inheritance_tax", "stamp_duty_reserve_tax", "stamp_duty_shares_securities",
        # Not on the sunburst:
        "bearer_instrument_duty",
    ],
    "Environment & energy": [
        "renewables_obligation", "contracts_for_difference_supplier_obligation", "feed_in_tariffs",
        "capacity_market_supplier_charge", "warm_home_discount", "sizewell_c_rab_levy", "green_gas_levy",
        "uk_emissions_trading_scheme", "climate_change_levy", "landfill_tax", "aggregates_levy",
        "plastic_packaging_tax", "scottish_landfill_tax", "landfill_disposals_tax_wales",
        "extended_producer_responsibility_packaging_fees",
        # Not on the sunburst:
        "carbon_border_adjustment_mechanism", "scottish_aggregates_tax",
    ],
    "Other": [
        "television_licence_fee", "immigration_health_surcharge", "visa_fees", "lottery_payments",
        "levy_funded_bodies", "bank_of_england_levy", "passport_fees", "british_transport_police_levy",
        "dvla_registration_fees", "lighthouse_dues", "atol_protection_contribution", "consumer_credit_fees",
        "immigration_skills_charge", "land_registry_fees", "community_infrastructure_levy",
        "companies_house_fees", "economic_crime_levy", "horserace_betting_levy",
        # Not on the sunburst:
        "pension_protection_levy", "building_safety_levy", "landlord_registration_fee",
    ],
}
GROUP_BY_TAX_ID = {tax_id: group for group, tax_ids in SUNBURST_GROUPS.items() for tax_id in tax_ids}
assert len(GROUP_BY_TAX_ID) == sum(len(tax_ids) for tax_ids in SUNBURST_GROUPS.values())


# Abolished taxes that the keyword rules in classify() would put in the wrong category.
HISTORICAL_GROUPS = {
    "capital_transfer_tax": "Wealth",
    "investment_income_surcharge": "Wealth",
    "special_contribution": "Wealth",
    "composite_rate_tax": "Wealth",
    "east_india_african_hudson_joint_stock_tax_1692": "Wealth",
    "purchase_tax": "Goods/services",
    "car_tax": "Goods/services",
    "beer_seller_licence": "Goods/services",
    "wine_seller_licence": "Goods/services",
    "spirit_retailer_licence": "Goods/services",
    "commonwealth_monthly_assessment": "Land",
    "furnished_house_agent_duty": "Other",
    "plate_chest_duty": "Other",
}


def has_word(text: str, *words: str) -> bool:
    """Whole-word match, so "Commonwealth" is not "wealth" and "aerated" is not "rate"."""
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def classify(row: dict[str, str]) -> str:
    """Put a tax in one of the seven categories.

    Listed taxes take their listed category. Anything else is matched on words in
    its name, parent tax, category and id; the first rule that matches wins, so
    the order of the checks matters.
    """
    if row["tax_id"] in GROUP_BY_TAX_ID:
        return GROUP_BY_TAX_ID[row["tax_id"]]
    if row["tax_id"] in HISTORICAL_GROUPS:
        return HISTORICAL_GROUPS[row["tax_id"]]
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
        or has_word(text, "wealth")
        or "securities" in text
        or "shares" in text
        or "bearer" in text
        or "dividend" in text
        or "savings" in text
        or "rent income" in text
    ):
        return "Wealth"
    if (
        has_word(text, "land", "lands")
        or "property" in text
        or has_word(text, "rate", "rates")
        or "council tax" in text
        or "dwelling" in text
        or has_word(text, "house", "houses")
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
    """A date for the tooltip: "6 April 1799", "April 1799" or "1799"."""
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
    """The points for one tax's line: its two ends and 1 January of every fifth year between.

    The points are invisible; the extra ones give the tooltip something to catch
    anywhere along a long line.
    """
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
    """A tax's start, end, end label and line style, or None if it isn't drawn.

    Solid lines are taxes in force or ended. Dashed lines are taxes that are law
    but haven't started, and taxes that Dowell, our main historical source, has
    in force in 1885: we haven't yet traced when those ended, so they stop at the
    end of 1885. Dotted lines are taxes whose status we haven't established; they
    run to the end of the chart.
    """
    if row["episode_status"] in {"chart_split_only", "announced_not_enacted"}:
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
        end_label = "enacted, not yet in force"
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
    """The hover box for one tax."""
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
    # Run to today, or to the latest start date of a tax that is law but hasn't
    # started, if that is later.
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

    # One empty series per category, for the legend. Every tax's line carries its
    # category's name too, so clicking a legend entry shows or hides the category.
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
        # The y-axis is inverted, so the oldest tax gets the highest lane and sits
        # at the bottom.
        lane = len(items) - item_index - 1
        colour = GROUP_COLOURS[group]
        start_label = format_date(row["start_year"], row["start_date"])
        tooltip = tooltip_html(row, group, start_label, end_label, colour)
        opacity = 0.72 if line_type == "solid" else 0.45
        series.append(
            {
                "id": f"{row['tax_id']}-{row['episode']}",
                "name": group,
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
        # Counts that main() prints.
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
