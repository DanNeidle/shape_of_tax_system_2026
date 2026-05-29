#!/usr/bin/env python3
import json
from copy import deepcopy
from pathlib import Path

GDP_M = 2934021
ROOT_NAME = "All taxes"

EMPLOYER_NICS = 115446.805
EMPLOYEE_NICS_BASE = 47375.028
STATUTORY_RECOVERIES = 3372.178
EMPLOYEE_NICS = EMPLOYEE_NICS_BASE + STATUTORY_RECOVERIES
SELF_EMPLOYED_NICS = 2797.578
OTHER_NICS = 2410.411
TOTAL_NICS = EMPLOYER_NICS + EMPLOYEE_NICS + SELF_EMPLOYED_NICS + OTHER_NICS
LABEL_THRESHOLD_M = 250
FORCE_LABELS = {
    "Employment taxes",
    "Goods/services",
    "Business",
    "Property",
    "Wealth",
    "Environment & energy",
    "Other",
    "SDLT",
    "Other small taxes",
    "Gaming duty",
    "Bingo duty",
    "Pool betting duty",
    "Other taxes n.e.s.",
    "Bank taxes",
    "British Transport Police",
    "DVLA registration fees",
    "Lighthouse dues",
    "ATOL",
}

TOP_COLORS = [
    "#006D77",
    "#D9480F",
    "#2B4C7E",
    "#F59F00",
    "#8E44AD",
    "#2B8A3E",
    "#1B6CA8",
]

CHILD_COLORS = {
    "Employment taxes": ["#005F73", "#0A9396", "#3FBAC2", "#89D6CF"],
    "Goods/services": ["#C92A2A", "#E8590C", "#F76707", "#FF922B", "#A61E4D", "#C2255C", "#D6336C", "#F06595"],
    "Gaming duties": ["#A61E4D", "#C2255C", "#D6336C", "#E64980", "#F06595", "#F783AC", "#FAA2C1"],
    "Business": ["#1E3A5F", "#2B4C7E", "#3D6CB9", "#6D8FE8"],
    "Property": ["#B7791F", "#D69E2E", "#ECC94B", "#F6E05E"],
    "Wealth": ["#5B21B6", "#7B2CBF", "#A855F7", "#C084FC", "#D8B4FE", "#E9D5FF"],
    "Environment & energy": ["#1B5E20", "#2B8A3E", "#51A353", "#8BC34A"],
    "Environmental levies": ["#1B5E20", "#2B8A3E", "#51A353"],
    "Other": ["#0F4C75", "#1B6CA8", "#2D9DE5", "#5FB6EA"],
    "Other small taxes": ["#0F4C75", "#1B6CA8", "#2D9DE5", "#5FB6EA", "#8ECBEF"],
    "Income tax": ["#5B21B6", "#7B2CBF", "#A855F7"],
    "Property annual taxes": ["#B7791F", "#D69E2E"],
}

ITEM_COLORS = {
    "ATOL": "#005A8D",
}

ITEM_STYLE_OVERRIDES = {
    "ATOL": {"borderColor": "#005A8D", "borderWidth": 1.8},
}


def node(name, value_m, children=None, note=None):
    item = {
        "name": name,
        "value": max(value_m / 1000, 0),
        "actual_m": value_m,
        "gdp_pct": value_m / GDP_M * 100,
    }
    if note:
        item["note"] = note
    if children:
        item["children"] = children
    return item


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


def format_money(value_m):
    return f"£{value_m / 1000:.1f}bn"


def format_money_whole(value_m):
    return f"£{value_m / 1000:,.0f}bn"


def format_gdp(value_m):
    return f"{value_m / GDP_M * 100:.1f}%"


def should_show_label(item):
    if item.get("is_padding"):
        return False
    return item["actual_m"] >= LABEL_THRESHOLD_M or item["name"] in FORCE_LABELS


def pad_terminal_nodes(items, depth=1, max_depth=4):
    for item in items:
        if "children" in item:
            pad_terminal_nodes(item["children"], depth + 1, max_depth)
            continue
        if depth >= max_depth:
            continue
        child = {
            "name": item["name"],
            "value": item["value"],
            "actual_m": item["actual_m"],
            "gdp_pct": item["gdp_pct"],
            "is_padding": True,
            "itemStyle": {
                **item.get("itemStyle", {}),
                "borderWidth": 0.15,
            },
            "label": {"show": False},
        }
        item["children"] = [child]
        pad_terminal_nodes(item["children"], depth + 1, max_depth)
    return items


def label_size(value_m):
    if value_m >= 5000:
        return 11
    if value_m >= 1000:
        return 8
    if value_m >= 250:
        return 7
    return 6


def apply_colors(items, palette):
    for idx, item in enumerate(items):
        color = ITEM_COLORS.get(item["name"], palette[idx % len(palette)])
        item["itemStyle"] = {"color": color, **ITEM_STYLE_OVERRIDES.get(item["name"], {})}
        item["label"] = label_for_color(color)
        if "children" in item:
            child_palette = CHILD_COLORS.get(item["name"], palette)
            apply_colors(item["children"], child_palette)
    return items


def apply_layout_values(items, mode):
    for item in items:
        child_total_m = 0
        if "children" in item:
            apply_layout_values(item["children"], mode)
            child_total_m = sum(child["layout_m"] for child in item["children"])
        item["layout_m"] = max(item["actual_m"], child_total_m, 0)
        if mode == "gdp":
            item["value"] = item["layout_m"] / GDP_M * 100
        else:
            item["value"] = item["layout_m"] / 1000
    return items


def apply_display_labels(items, mode):
    for item in items:
        label = item.setdefault("label", {})
        value = format_money(item["actual_m"]) if mode == "money" else format_gdp(item["actual_m"])
        if item.get("is_padding"):
            label["show"] = False
        elif should_show_label(item):
            label["show"] = True
            label["formatter"] = f"{item['name']}\n{value}" if item["actual_m"] >= 1000 or item["name"] in FORCE_LABELS else item["name"]
            label["fontSize"] = label_size(item["actual_m"])
            label["lineHeight"] = max(label["fontSize"] + 1, 7)
        else:
            label["show"] = False
        item["tooltip"] = {"formatter": f"{item['name']}<br>{value}"}
        if "children" in item:
            apply_display_labels(item["children"], mode)
    return items


DIVIDEND_INCOME_TAX = 18120
SAVINGS_INCOME_TAX = 10540
# HMRC publishes property income, but not the Income Tax liability on it separately.
# Estimate: 2023-24 SPI property-income distribution taxed at broad 2024-25 NSND marginal rates.
RENT_INCOME_TAX = 9200
RESIDUAL_INCOME_TAX = 305905 - DIVIDEND_INCOME_TAX - SAVINGS_INCOME_TAX - RENT_INCOME_TAX
STAMP_TAXES_ON_SHARES = 4322
# HMRC Annual Stamp Tax Statistics 2024-25 splits the shares total as
# SDRT £3,050m and Stamp Duty £1,270m. Scale those proportions to the
# OBR/ONS National Accounts control total used in the chart.
SDRT = STAMP_TAXES_ON_SHARES * 3050 / (3050 + 1270)
STAMP_DUTY_1891 = STAMP_TAXES_ON_SHARES - SDRT
GAMING_DUTIES = 3646
# HMRC Betting and Gaming Statistics give the 2024-25 duty split on a
# cash/statistical basis. Scale those proportions to the OBR accrued control.
HMRC_GAMING_TOTAL = 1163 + 932 + 714 + 609 + 165 + 25 + 8.1
REMOTE_GAMING_DUTY = GAMING_DUTIES * 1163 / HMRC_GAMING_TOTAL
LOTTERY_DUTY = GAMING_DUTIES * 932 / HMRC_GAMING_TOTAL
GENERAL_BETTING_DUTY = GAMING_DUTIES * 714 / HMRC_GAMING_TOTAL
MACHINE_GAMES_DUTY = GAMING_DUTIES * 609 / HMRC_GAMING_TOTAL
GAMING_DUTY = GAMING_DUTIES * 165 / HMRC_GAMING_TOTAL
BINGO_DUTY = GAMING_DUTIES * 25 / HMRC_GAMING_TOTAL
POOL_BETTING_DUTY = GAMING_DUTIES - (
    REMOTE_GAMING_DUTY
    + LOTTERY_DUTY
    + GENERAL_BETTING_DUTY
    + MACHINE_GAMES_DUTY
    + GAMING_DUTY
    + BINGO_DUTY
)
ENVIRONMENTAL_LEVIES = 10517
RENEWABLES_OBLIGATION = 7766.928956566494
CONTRACTS_FOR_DIFFERENCE = 2267.47474803
WARM_HOME_DISCOUNT = ENVIRONMENTAL_LEVIES - RENEWABLES_OBLIGATION - CONTRACTS_FOR_DIFFERENCE
OTHER_SMALL_TAXES = 586.202
ATOL = 80
BRITISH_TRANSPORT_POLICE = 145
DVLA_REGISTRATION_FEES = 124
LIGHTHOUSE_DUES = 89
OTHER_SMALL_TAXES_NES = OTHER_SMALL_TAXES - ATOL - BRITISH_TRANSPORT_POLICE - DVLA_REGISTRATION_FEES - LIGHTHOUSE_DUES

data_m = [
    node("Employment taxes", 481442 - DIVIDEND_INCOME_TAX - SAVINGS_INCOME_TAX - RENT_INCOME_TAX, [
        node("Income tax on work", RESIDUAL_INCOME_TAX, note="Income tax net of separately shown dividends, savings interest and rents."),
        node("NICs", TOTAL_NICS, [
            node("Employer NICs", EMPLOYER_NICS),
            node("Employee NICs", EMPLOYEE_NICS, note="Includes statutory recoveries netted against employee NICs."),
            node("Self-employed NICs", SELF_EMPLOYED_NICS),
            node("Other NICs", OTHER_NICS),
        ]),
        node("Apprenticeship levy", 4135),
    ]),
    node("Goods/services", 156927 + 62134, [
        node("VAT", 143856, note="VAT receipts net of refunds."),
        node("Insurance premium tax", 8940),
        node("Air passenger duty", 4131),
        node("Fuel duties", 24359),
        node("Alcohol duties", 12545, [
            node("Beer and cider", 3746),
            node("Wine", 4686),
            node("Spirits", 4113),
        ]),
        node("Vehicle excise duty", 8205),
        node("Tobacco duties", 7909),
        node("Customs duties", 4870),
        node("Gaming duties", GAMING_DUTIES, [
            node("Remote gaming duty", REMOTE_GAMING_DUTY),
            node("Lottery duty", LOTTERY_DUTY),
            node("General betting duty", GENERAL_BETTING_DUTY),
            node("Machine games duty", MACHINE_GAMES_DUTY),
            node("Gaming duty", GAMING_DUTY),
            node("Bingo duty", BINGO_DUTY),
            node("Pool betting duty", POOL_BETTING_DUTY),
        ]),
        node("Soft drinks levy", 330),
        node("Lorry road levy", 157),
        node("Gaming levy", 113),
    ]),
    node("Business", 99521, [
        node("Corporation tax", 93238, [
            node("Onshore CT", 91005),
            node("Offshore CT", 2233),
        ]),
        node("Digital services tax", 874),
        node("Bank taxes", 1329 + 975, [
            node("Bank levy", 1329),
            node("Bank surcharge", 975),
        ]),
        node("Diverted profits", 105),
        node("Property developer tax", 102),
        node("Energy profits levy", 2499),
        node("Electricity generator levy", 749),
        node("Petroleum revenue tax", -350, note="Net repayments reduce receipts."),
    ]),
    node("Property", 95568, [
        node("Property annual taxes", 47417 + 32056, [
            node("Council tax", 47417),
            node("Business rates", 32056),
        ]),
        node("NI domestic rates", 485.312),
        node("NI business rates", 382.334),
        node("Property transaction taxes", 15227, [
            node("SDLT", 13885, [
                node("Residential SDLT", 7895),
                node("Additional dwellings", 2290),
                node("Non-resident SDLT", 195),
                node("Non-residential SDLT", 3505),
            ]),
            node("ATED", 133.617),
            node("LBTT (Scotland)", 899.162),
            node("LTT (Wales)", 340.612),
        ]),
    ]),
    node("Wealth", 26294 + DIVIDEND_INCOME_TAX + SAVINGS_INCOME_TAX + RENT_INCOME_TAX, [
        node("Income tax", DIVIDEND_INCOME_TAX + SAVINGS_INCOME_TAX + RENT_INCOME_TAX, [
            node("Dividend income tax", DIVIDEND_INCOME_TAX),
            node("Savings income tax", SAVINGS_INCOME_TAX),
            node("Rent income tax", RENT_INCOME_TAX, note="Estimated from HMRC SPI property-income distribution; property income is otherwise included within non-savings income tax."),
        ]),
        node("Capital gains tax", 13686),
        node("Inheritance tax", 8286),
        node("Stamp taxes on shares", STAMP_TAXES_ON_SHARES, [
            node("SDRT", SDRT),
            node("Stamp duty (1891)", STAMP_DUTY_1891),
        ]),
    ]),
    node("Environment & energy", 16971, [
        node("Environmental levies", ENVIRONMENTAL_LEVIES, [
            node("Renewables obligation", RENEWABLES_OBLIGATION),
            node("Contracts for difference", CONTRACTS_FOR_DIFFERENCE),
            node("Warm home discount", WARM_HOME_DISCOUNT),
        ]),
        node("Emissions trading", 3406),
        node("Climate change levy", 1842),
        node("Landfill tax", 497.241),
        node("Aggregates levy", 363),
        node("Plastic packaging tax", 255),
        node("Scottish landfill tax", 56.621),
        node("Welsh landfill tax", 34.138),
    ]),
    node("Other", 15559, [
        node("Licence fee", 3819),
        node("Immigration health surcharge", 2421),
        node("Visa fees", 2359),
        node("Lottery payments", 1713),
        node("Levy-funded bodies", 960.764),
        node("Bank of England levy", 733),
        node("Passport fees", 646),
        node("Other small taxes", OTHER_SMALL_TAXES, [
            node("Other taxes n.e.s.", OTHER_SMALL_TAXES_NES),
            node("British Transport Police", BRITISH_TRANSPORT_POLICE),
            node("DVLA registration fees", DVLA_REGISTRATION_FEES),
            node("Lighthouse dues", LIGHTHOUSE_DUES),
            node("ATOL", ATOL),
        ]),
        node("Consumer credit fees", 525.846),
        node("Immigration skills charge", 518),
        node("Land Registry", 399),
        node("Community infrastructure levy", 350),
        node("Companies House", 217),
        node("Economic crime levy", 124.482),
        node("Horserace betting levy", 113),
        node("Pension protection levy", 74.062),
    ]),
]

apply_colors(data_m, TOP_COLORS)
apply_layout_values(data_m, "money")
apply_display_labels(data_m, "money")


def convert_to_gdp(data):
    converted = deepcopy(data)
    apply_layout_values(converted, "gdp")
    apply_display_labels(converted, "gdp")
    return converted


def total_layout_m(data):
    return sum(item["layout_m"] for item in data)


def root_tooltip(data, mode):
    total_m = total_layout_m(data)
    value = format_gdp(total_m) if mode == "gdp" else format_money_whole(total_m)
    return {"formatter": f"{ROOT_NAME}, {value}"}


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
    "emphasis": {
        "focus": "ancestor",
        "label": {
            "fontWeight": "bold"
        }
    },
    "itemStyle": {
        "borderWidth": 1.25,
        "borderColor": "#ffffff"
    },
    "label": {
        "minAngle": 0,
        "overflow": "truncate",
        "fontFamily": "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
        "fontSize": 11,
        "fontWeight": 650,
        "color": "#102033",
        "textBorderColor": "rgba(255,255,255,0.88)",
        "textBorderWidth": 3
    },
    "levels": [
        {
            "itemStyle": {
                "color": "transparent",
                "borderColor": "transparent",
                "borderWidth": 0
            },
            "label": {"show": False}
        },
        {
            "r0": "3%",
            "r": "21%",
            "label": {
                "rotate": 0,
                "minAngle": 0,
                "fontSize": 12,
                "fontWeight": 800,
                "color": "#ffffff",
                "textBorderColor": "rgba(15,23,42,0.35)",
                "textBorderWidth": 2.5
            },
            "itemStyle": {"borderWidth": 2}
        },
        {
            "r0": "21%",
            "r": "48%",
            "label": {"rotate": "tangential", "minAngle": 0, "fontSize": 12, "fontWeight": 750}
        },
        {
            "r0": "48%",
            "r": "82%",
            "label": {"rotate": "radial", "minAngle": 0, "fontSize": 9, "fontWeight": 650}
        },
        {
            "r0": "82%",
            "r": "97%",
            "label": {"rotate": "radial", "minAngle": 0, "fontSize": 7, "fontWeight": 650}
        },
        {
            "r0": "97%",
            "r": "100%",
            "label": {"rotate": "radial", "minAngle": 0, "fontSize": 6, "fontWeight": 650}
        },
    ],
    "tooltip": root_tooltip(data_m, "money"),
    "data": data_m,
}

option = {
    "backgroundColor": "#ffffff",
    "color": TOP_COLORS,
    "_tpaSunburstLeafClickParent": True,
    "baseOption": {
        "timeline": {
            "axisType": "category",
            "bottom": 18,
            "right": 18,
            "width": 116,
            "height": 28,
            "autoPlay": False,
            "currentIndex": 0,
            "symbolSize": 7,
            "controlStyle": {"show": False},
            "lineStyle": {"color": "#D5DEE8", "width": 2},
            "checkpointStyle": {
                "symbol": "roundRect",
                "symbolSize": 13,
                "color": "#162033",
                "borderColor": "#162033",
                "borderWidth": 1
            },
            "itemStyle": {
                "color": "#F8FAFC",
                "borderColor": "#64748B",
                "borderWidth": 1
            },
            "label": {
                "fontFamily": "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
                "fontSize": 11,
                "fontWeight": 700,
                "color": "#334155"
            },
            "data": ["£bn", "GDP %"]
        },
        "tooltip": {
            "trigger": "item"
        },
        "series": [base_series],
    },
    "options": [
        {
            "tooltip": {"trigger": "item"},
            "series": [{**base_series, "tooltip": root_tooltip(data_m, "money"), "data": data_m}]
        },
        {
            "tooltip": {"trigger": "item"},
            "series": [{**base_series, "tooltip": root_tooltip(data_m, "gdp"), "data": convert_to_gdp(data_m)}]
        }
    ],
}

out = Path("code/uk_tax_system_sunburst_2024_25.json")
out.write_text(json.dumps(option, indent=2), encoding="utf-8")
print(out)
