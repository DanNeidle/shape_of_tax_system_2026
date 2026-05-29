#!/usr/bin/env python3
import csv
import html
import json
from copy import deepcopy
from pathlib import Path


BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
INPUT = DATA_DIR / "france_tax_revenue_layered_2024.csv"
OUTPUT = DATA_DIR / "france_tax_system_sunburst_2024.json"

GDP_EUR = 2_919_900_000_000
ROOT_NAME = "All French taxes"
LABEL_THRESHOLD_EUR = 250_000_000

TOP_COLORS = [
    "#006D77",
    "#D9480F",
    "#2B4C7E",
    "#F59F00",
    "#8E44AD",
    "#2B8A3E",
    "#1B6CA8",
]

LAYER_ORDER = [
    "Employment",
    "Goods/services",
    "Business",
    "Land",
    "Wealth",
    "Environmental",
    "Other",
]

TOP_COLOR_BY_LAYER = {
    "Employment": "#006D77",
    "Goods/services": "#D9480F",
    "Business": "#2B4C7E",
    "Land": "#F59F00",
    "Wealth": "#8E44AD",
    "Environmental": "#2B8A3E",
    "Other": "#1B6CA8",
}

CHILD_COLORS = {
    "Employment": ["#005F73", "#0A9396", "#3FBAC2", "#89D6CF"],
    "Goods/services": ["#C92A2A", "#E8590C", "#F76707", "#FF922B", "#A61E4D", "#C2255C", "#D6336C", "#F06595"],
    "Betting, gaming and lottery": ["#A61E4D", "#C2255C", "#D6336C", "#E64980", "#F06595", "#F783AC", "#FAA2C1"],
    "Business": ["#1E3A5F", "#2B4C7E", "#3D6CB9", "#6D8FE8"],
    "Land": ["#B7791F", "#D69E2E", "#ECC94B", "#F6E05E"],
    "Wealth": ["#5B21B6", "#7B2CBF", "#A855F7", "#C084FC", "#D8B4FE", "#E9D5FF"],
    "Environmental": ["#1B5E20", "#2B8A3E", "#51A353", "#8BC34A"],
    "Other": ["#0F4C75", "#1B6CA8", "#2D9DE5", "#5FB6EA"],
}

FORCE_LABELS = {
    "Employment",
    "Goods/services",
    "Business",
    "Land",
    "Wealth",
    "Environmental",
    "Other",
    "VAT",
    "Social contributions",
    "Personal income and social taxes",
    "Employer payroll and labour levies",
    "Profit and sector taxes",
    "Recurrent land and property taxes",
    "Inheritance and gifts",
}

TOOLTIP = {
    "trigger": "item",
    "confine": True,
    "extraCssText": "max-width:260px;white-space:normal;padding:8px 10px;",
}


def read_rows():
    with INPUT.open(encoding="utf-8", newline="") as handle:
        return [
            row for row in csv.DictReader(handle)
            if row["chart_include"] == "yes" and row["chart_revenue_eur"]
        ]


def format_money(value_eur):
    return f"€{value_eur / 1_000_000_000:.1f}bn"


def format_money_whole(value_eur):
    return f"€{value_eur / 1_000_000_000:,.0f}bn"


def format_gdp(value_eur):
    return f"{value_eur / GDP_EUR * 100:.1f}%"


def format_tax_pct(value_eur, total_eur):
    return f"{value_eur / total_eur * 100:.1f}%"


def label_for_color(color):
    color = color.lstrip("#")
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    if luminance < 0.47:
        return {
            "color": "#FFFFFF",
            "textBorderColor": "rgba(15,23,42,0.42)",
            "textBorderWidth": 2.8,
        }
    return {
        "color": "#172033",
        "textBorderColor": "rgba(255,255,255,0.88)",
        "textBorderWidth": 3,
    }


def should_show_label(item):
    return item["actual_eur"] >= LABEL_THRESHOLD_EUR or item["name"] in FORCE_LABELS


def label_size(value_eur):
    value_m = value_eur / 1_000_000
    if value_m >= 5000:
        return 11
    if value_m >= 1000:
        return 8
    if value_m >= 250:
        return 7
    return 6


def normalise_name(value):
    return "".join(char.casefold() for char in value if char.isalnum())


def make_tooltip(item, mode, total_eur=None):
    value = format_value(item, mode, total_eur)
    name = html.escape(item["name"])
    details = []
    french_name = item.get("french_name", "").strip()
    english_names = {normalise_name(item["name"]), normalise_name(item.get("english_name", ""))}
    if french_name and normalise_name(french_name) not in english_names:
        details.append(f"<em>{html.escape(french_name)}</em>")
    if item.get("explanation"):
        details.append(html.escape(item["explanation"]))
    detail_line = ""
    if details:
        detail_line = f"<div style=\"font-size:11px;line-height:1.3;color:#475569;white-space:normal;\">{' - '.join(details)}</div>"
    return {
        "formatter": (
            "<div style=\"max-width:240px;white-space:normal;\">"
            f"<div style=\"font-weight:700;font-size:13px;line-height:1.25;color:#0f172a;\">{name}</div>"
            f"<div style=\"font-weight:700;font-size:12px;line-height:1.35;margin-top:2px;color:#0f172a;\">{value}</div>"
            f"{detail_line}"
            "</div>"
        )
    }


def leaf(row):
    value = int(row["chart_revenue_eur"])
    return {
        "name": row["chart_label_en"],
        "value": value / 1_000_000_000,
        "actual_eur": value,
        "gdp_pct": value / GDP_EUR * 100,
        "french_name": row["tax_name"],
        "english_name": row["tax_name_english"],
        "explanation": row.get("display_explanation") or row["english_explanation"],
    }


def insert_path(root, path, item):
    cursor = root
    for part in path:
        children = cursor.setdefault("children", [])
        next_node = next((child for child in children if child["name"] == part), None)
        if next_node is None:
            next_node = {"name": part, "children": []}
            children.append(next_node)
        cursor = next_node
    cursor.setdefault("children", []).append(item)


def aggregate(item):
    if "children" not in item:
        return item["actual_eur"]
    total = sum(aggregate(child) for child in item["children"])
    item["actual_eur"] = total
    item["gdp_pct"] = total / GDP_EUR * 100
    item["value"] = total / 1_000_000_000
    return total


def prune_single_child_groups(item):
    if "children" not in item:
        return item
    children = [prune_single_child_groups(child) for child in item["children"]]
    item["children"] = children
    if len(children) != 1 or item["name"] in TOP_COLOR_BY_LAYER:
        return item

    child = children[0]
    if child["name"] == item["name"]:
        if "children" in child:
            item["children"] = child["children"]
            return prune_single_child_groups(item)
        for key, value in child.items():
            if key not in {"name", "children"}:
                item[key] = value
        item.pop("children", None)
        return item

    if "children" in child:
        item["children"] = child["children"]
        return prune_single_child_groups(item)
    return item


def make_tree(rows):
    root = {"name": ROOT_NAME, "children": []}
    for row in rows:
        path = [row["layer_1"], row["layer_2"], row["layer_3"]]
        insert_path(root, path, leaf(row))
    for child in root["children"]:
        prune_single_child_groups(child)
    order = {name: idx for idx, name in enumerate(LAYER_ORDER)}
    root["children"].sort(key=lambda item: order.get(item["name"], len(order)))
    aggregate(root)
    return root["children"]


def apply_colors(items, palette):
    for idx, item in enumerate(items):
        color = TOP_COLOR_BY_LAYER.get(item["name"], palette[idx % len(palette)])
        item["itemStyle"] = {"color": color}
        item["label"] = label_for_color(color)
        if "children" in item:
            child_palette = CHILD_COLORS.get(item["name"], palette)
            apply_colors(item["children"], child_palette)
    return items


def apply_layout_values(items, mode, total_eur=None):
    for item in items:
        child_total = 0
        if "children" in item:
            apply_layout_values(item["children"], mode, total_eur)
            child_total = sum(child["layout_eur"] for child in item["children"])
        item["layout_eur"] = max(item["actual_eur"], child_total, 0)
        if mode == "gdp":
            item["value"] = item["layout_eur"] / GDP_EUR * 100
        elif mode == "tax_pct":
            item["value"] = item["layout_eur"] / total_eur * 100
        else:
            item["value"] = item["layout_eur"] / 1_000_000_000
    return items


def format_value(item, mode, total_eur=None):
    if mode == "money":
        return format_money(item["actual_eur"])
    if mode == "tax_pct":
        return format_tax_pct(item["layout_eur"], total_eur)
    return format_gdp(item["actual_eur"])


def apply_display_labels(items, mode, total_eur=None):
    for item in items:
        label = item.setdefault("label", {})
        value = format_value(item, mode, total_eur)
        if should_show_label(item):
            label["show"] = True
            label["formatter"] = f"{item['name']}\n{value}" if item["actual_eur"] >= 1_000_000_000 or item["name"] in FORCE_LABELS else item["name"]
            label["fontSize"] = label_size(item["actual_eur"])
            label["lineHeight"] = max(label["fontSize"] + 1, 7)
        else:
            label["show"] = False
        item["tooltip"] = make_tooltip(item, mode, total_eur)
        item.pop("english_name", None)
        if "children" in item:
            apply_display_labels(item["children"], mode, total_eur)
    return items


def convert_to_gdp(data):
    converted = deepcopy(data)
    apply_layout_values(converted, "gdp")
    apply_display_labels(converted, "gdp")
    return converted


def total_layout_eur(data):
    return sum(item["layout_eur"] for item in data)


def convert_to_tax_pct(data, total_eur):
    converted = deepcopy(data)
    apply_layout_values(converted, "tax_pct", total_eur)
    apply_display_labels(converted, "tax_pct", total_eur)
    return converted


def root_tooltip(data, mode):
    total = total_layout_eur(data)
    if mode == "gdp":
        value = format_gdp(total)
    elif mode == "tax_pct":
        value = "100.0%"
    else:
        value = format_money_whole(total)
    return {"formatter": f"{ROOT_NAME}, {value}"}


def build_option():
    data = make_tree(read_rows())
    apply_colors(data, TOP_COLORS)
    # Do not pad terminal nodes: VAT-style aggregates should stop at their real depth.
    apply_layout_values(data, "money")
    apply_display_labels(data, "money")
    total_eur = total_layout_eur(data)

    base_series = {
        "name": ROOT_NAME,
        "type": "sunburst",
        "center": ["50%", "50%"],
        "radius": ["0%", "100%"],
        "startAngle": 218,
        "sort": None,
        "nodeClick": "rootToNode",
        "minAngle": 0,
        "labelLayout": {"hideOverlap": True},
        "emphasis": {"focus": "ancestor", "label": {"fontWeight": "bold"}},
        "itemStyle": {"borderWidth": 1.25, "borderColor": "#ffffff"},
        "label": {
            "minAngle": 0,
            "overflow": "truncate",
            "fontFamily": "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
            "fontSize": 11,
            "fontWeight": 650,
            "color": "#102033",
            "textBorderColor": "rgba(255,255,255,0.88)",
            "textBorderWidth": 3,
        },
        "levels": [
            {"itemStyle": {"color": "transparent", "borderColor": "transparent", "borderWidth": 0}, "label": {"show": False}},
            {"r0": "3%", "r": "21%", "label": {"rotate": 0, "minAngle": 0, "fontSize": 12, "fontWeight": 800, "color": "#ffffff", "textBorderColor": "rgba(15,23,42,0.35)", "textBorderWidth": 2.5}, "itemStyle": {"borderWidth": 2}},
            {"r0": "21%", "r": "44%", "label": {"rotate": "tangential", "minAngle": 0, "fontSize": 12, "fontWeight": 750}},
            {"r0": "44%", "r": "68%", "label": {"rotate": "radial", "minAngle": 0, "fontSize": 9, "fontWeight": 650}},
            {"r0": "68%", "r": "88%", "label": {"rotate": "radial", "minAngle": 0, "fontSize": 7, "fontWeight": 650}},
            {"r0": "88%", "r": "100%", "label": {"rotate": "radial", "minAngle": 0, "fontSize": 6, "fontWeight": 650}},
        ],
        "tooltip": root_tooltip(data, "money"),
        "data": data,
    }

    return {
        "backgroundColor": "#ffffff",
        "color": TOP_COLORS,
        "_tpaSunburstLeafClickParent": True,
        "baseOption": {
            "timeline": {
                "axisType": "category",
                "bottom": 18,
                "right": 18,
                "width": 190,
                "height": 28,
                "autoPlay": False,
                "currentIndex": 0,
                "symbolSize": 7,
                "controlStyle": {"show": False},
                "lineStyle": {"color": "#D5DEE8", "width": 2},
                "checkpointStyle": {"symbol": "roundRect", "symbolSize": 13, "color": "#162033", "borderColor": "#162033", "borderWidth": 1},
                "itemStyle": {"color": "#F8FAFC", "borderColor": "#64748B", "borderWidth": 1},
                "label": {"fontFamily": "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", "fontSize": 11, "fontWeight": 700, "color": "#334155"},
                "data": ["€bn", "GDP %", "Tax %"],
            },
            "tooltip": TOOLTIP,
            "series": [base_series],
        },
        "options": [
            {"tooltip": TOOLTIP, "series": [{**base_series, "tooltip": root_tooltip(data, "money"), "data": data}]},
            {"tooltip": TOOLTIP, "series": [{**base_series, "tooltip": root_tooltip(data, "gdp"), "data": convert_to_gdp(data)}]},
            {"tooltip": TOOLTIP, "series": [{**base_series, "tooltip": root_tooltip(data, "tax_pct"), "data": convert_to_tax_pct(data, total_eur)}]},
        ],
    }


def main():
    option = build_option()
    OUTPUT.write_text(json.dumps(option, indent=2, ensure_ascii=False), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
