#!/usr/bin/env python3
"""Build scatter chart: tax count vs tax revenue as % of GDP."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "code" / "data" / "country_comparison"
COUNT_CHART = DATA_DIR / "country_tax_count_comparison_2024.json"
OECD_CSV = DATA_DIR / "oecd_global_revenue_statistics_tax_gdp_2020_2024.csv"
CYPRUS_EUROSTAT_JSON = DATA_DIR / "eurostat_cyprus_tax_gdp_2024.json"
OUTPUT_CSV = DATA_DIR / "country_tax_count_vs_oecd_tax_gdp.csv"
OUTPUT_JSON = DATA_DIR / "country_tax_count_vs_oecd_tax_gdp_scatter.json"


COUNTRY_CODES = {
    "Austria": "AUT",
    "Belgium": "BEL",
    "Bulgaria": "BGR",
    "Croatia": "HRV",
    "Cyprus": "CYP",
    "Czechia": "CZE",
    "Denmark": "DNK",
    "Estonia": "EST",
    "Finland": "FIN",
    "France": "FRA",
    "Germany": "DEU",
    "Greece": "GRC",
    "Hungary": "HUN",
    "Iceland": "ISL",
    "Ireland": "IRL",
    "Italy": "ITA",
    "Latvia": "LVA",
    "Lithuania": "LTU",
    "Luxembourg": "LUX",
    "Malta": "MLT",
    "Netherlands": "NLD",
    "Norway": "NOR",
    "Poland": "POL",
    "Portugal": "PRT",
    "Romania": "ROU",
    "Slovakia": "SVK",
    "Slovenia": "SVN",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "CHE",
    "United Kingdom": "GBR",
}


def load_tax_counts() -> list[dict]:
    chart = json.loads(COUNT_CHART.read_text())
    return chart["series"][0]["data"]


def load_oecd_latest() -> dict[str, tuple[int, float]]:
    latest: dict[str, tuple[int, float]] = {}
    with OECD_CSV.open(newline="") as f:
        for row in csv.DictReader(f):
            value = row.get("OBS_VALUE")
            if not value:
                continue
            code = row["REF_AREA"]
            year = int(row["TIME_PERIOD"])
            tax_pct = float(value)
            if code not in latest or year > latest[code][0]:
                latest[code] = (year, tax_pct)
    return latest


def load_cyprus_eurostat_tax_pct() -> float:
    obj = json.loads(CYPRUS_EUROSTAT_JSON.read_text())
    values = list(obj.get("value", {}).values())
    if len(values) != 1:
        raise ValueError("Unexpected Cyprus Eurostat response shape")
    return float(values[0])


def rows() -> list[dict]:
    counts = load_tax_counts()
    latest = load_oecd_latest()
    cyprus_tax_pct = load_cyprus_eurostat_tax_pct()
    out = []
    for item in counts:
        country = item["name"]
        code = COUNTRY_CODES[country]
        if code == "CYP":
            year = 2024
            tax_pct = cyprus_tax_pct
            source = "Eurostat gov_10a_taxag (OECD Global Revenue Statistics has no Cyprus value)"
        else:
            if code not in latest:
                raise ValueError(f"No OECD tax/GDP value for {country} ({code})")
            year, tax_pct = latest[code]
            source = "OECD Global Revenue Statistics"
        out.append(
            {
                "country": country,
                "ref_area": code,
                "tax_count": int(item["value"]),
                "tax_gdp_pct": tax_pct,
                "tax_gdp_year": year,
                "tax_gdp_source": source,
                "color": item.get("itemStyle", {}).get("color", "#9CA3AF"),
            }
        )
    return out


def write_csv(data: list[dict]) -> None:
    with OUTPUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)


def chart(data: list[dict]) -> dict:
    points = []
    france_point = None
    for row in data:
        country = row["country"]
        label = {
            "show": True,
            "formatter": country,
            "position": "right",
            "distance": 6,
            "fontSize": 10,
            "color": "#111827",
            "textBorderColor": "rgba(255,255,255,0.88)",
            "textBorderWidth": 3,
        }
        if country in {"Denmark", "France", "Austria"}:
            label["position"] = "left"
        if country in {"United Kingdom", "Germany", "France"}:
            label["fontWeight"] = 800
        point = {
            "name": country,
            "value": [round(row["tax_gdp_pct"], 3), row["tax_count"]],
            "tax_gdp_year": row["tax_gdp_year"],
            "tax_gdp_source": row["tax_gdp_source"],
            "itemStyle": {
                "color": row["color"],
                "borderColor": "#ffffff",
                "borderWidth": 1.5,
            },
            "label": label,
            "symbolSize": 11 if country in {"United Kingdom", "France", "Germany"} else 8,
        }
        if country == "France":
            france_point = point
        else:
            points.append(point)

    if france_point is None:
        raise ValueError("France point not found")

    return {
        "backgroundColor": "#ffffff",
        "title": {
            "text": "Number of taxes for a country vs its tax as a % of GDP",
            "left": "center",
            "top": 8,
            "textStyle": {"fontSize": 20, "fontWeight": 700, "color": "#111827"},
        },
        "_tpaTooltip": {
            "template": "{name}<br>Tax revenue: {x:0.0}% of GDP<br>Taxes counted: {y:0}"
        },
        "tooltip": {
            "trigger": "item",
            "confine": True,
            "extraCssText": "max-width:260px;white-space:normal;padding:8px 10px;",
        },
        "legend": {
            "show": True,
            "bottom": 8,
            "left": "center",
            "data": [{"name": "Include France", "icon": "roundRect"}],
            "selected": {"Include France": False},
            "selectedMode": "multiple",
            "itemWidth": 18,
            "itemHeight": 12,
            "textStyle": {"fontSize": 13, "fontWeight": 700, "color": "#111827"},
            "inactiveColor": "#9CA3AF",
            "inactiveBorderColor": "#9CA3AF",
        },
        "grid": {
            "left": 66,
            "right": 142,
            "top": 72,
            "bottom": 92,
            "containLabel": True,
        },
        "xAxis": {
            "type": "value",
            "name": "Tax revenue (% of GDP)",
            "nameLocation": "middle",
            "nameGap": 38,
            "min": 18,
            "max": 47,
            "axisLabel": {"formatter": "{value}%", "color": "#374151"},
            "nameTextStyle": {"color": "#111827", "fontWeight": 700},
            "splitLine": {"lineStyle": {"color": "#E5E7EB"}},
        },
        "yAxis": {
            "type": "value",
            "name": "Number of taxes",
            "nameLocation": "middle",
            "nameGap": 48,
            "min": 20,
            "scale": True,
            "axisLabel": {"color": "#374151"},
            "nameTextStyle": {"color": "#111827", "fontWeight": 700},
            "splitLine": {"lineStyle": {"color": "#E5E7EB"}},
        },
        "series": [
            {
                "type": "scatter",
                "data": points,
                "legendHoverLink": False,
                "labelLayout": {"moveOverlap": "shiftY"},
                "emphasis": {
                    "focus": "self",
                    "scale": 1.15,
                    "label": {"fontWeight": 800},
                },
            },
            {
                "name": "Include France",
                "type": "scatter",
                "data": [france_point],
                "labelLayout": {"moveOverlap": "shiftY"},
                "emphasis": {
                    "focus": "self",
                    "scale": 1.15,
                    "label": {"fontWeight": 800},
                },
            }
        ],
    }


def main() -> None:
    data = rows()
    write_csv(data)
    OUTPUT_JSON.write_text(json.dumps(chart(data), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUTPUT_CSV.relative_to(ROOT)}")
    print(f"Wrote {OUTPUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
