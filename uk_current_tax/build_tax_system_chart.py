#!/usr/bin/env python3
# Copyright (c) 2026 Tax Policy Associates Ltd
# SPDX-License-Identifier: MIT
"""Build our sunburst chart of every UK tax in 2025-26 from OBR, ONS and HMRC data."""
import json
import re
from copy import deepcopy
from pathlib import Path

import openpyxl
import pandas as pd

if not __debug__:
    raise SystemExit("Run without -O: this script's reconciliation checks are assertions.")

BASE = Path(__file__).resolve().parent
# Data is in ./data in the public repo, and in code/data/uk_tax in our own.
PUBLIC_LAYOUT = (BASE / "data").is_dir()
DATA_DIR = BASE / "data" if PUBLIC_LAYOUT else BASE.parent / "data" / "uk_tax"
OUTPUT = (BASE if PUBLIC_LAYOUT else DATA_DIR) / "uk_tax_system_sunburst_2025_26.json"

# ---------------------------------------------------------------------------
# Source files. Chart figures are in £m and, apart from the stamp-tax split, come from these.
# 2025-26 is outturn in the OBR's October 2026 EFO.
# ---------------------------------------------------------------------------
YEAR = "2025-26"
OBR_ANNEX = DATA_DIR / "obr.uk - efo-october-2026-charts-and-tables-annex-tables.xlsx"
OBR_RECEIPTS = DATA_DIR / "obr.uk - efo-october-2026-detailed-forecast-tables-receipts.xlsx"
# March 2026 EFO: used only for its forecast of 2025-26 packaging (EPR) fees.
OBR_MARCH_RECEIPTS = DATA_DIR / "obr_efo_march_2026_detailed_forecast_tables_receipts.xlsx"
ONS_APPENDIX_D = DATA_DIR / "ons.gov.uk - publicsectorcurrentreceiptsappendixdfinal.xlsx"  # released 21 Oct 2026
HMRC_GAMBLING = DATA_DIR / "assets.publishing.service.gov.uk - 2026_Jul_Bet_and_Gam_Tab.ods"  # released 30 Sep 2026
HMRC_IT_LIABILITIES = DATA_DIR / "assets.publishing.service.gov.uk - Collated_Income_Tax_liabilities_statistics_tables_-_2.1_to_2.6.ods"  # 2023-24 to 2026-27 edition, July 2026
HMRC_SPI_3_7 = DATA_DIR / "hmrc_personal_incomes_table_3_7_property_interest_dividend_other_2023_24.xlsx"


def _clean_label(value):
    """Collapse whitespace and strip a footnote number stuck to the end of a label."""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return re.sub(r"(?<=[A-Za-z\)])\d+$", "", text).strip()


class _Table(dict):
    """Label to £m. Looking up a label that appears twice with different values raises KeyError."""

    def __init__(self, where):
        super().__init__()
        self.where = where
        self.ambiguous = set()

    def __getitem__(self, label):
        if label in self.ambiguous:
            raise KeyError(f"{label!r} appears more than once in {self.where}")
        return super().__getitem__(label)


def obr_table(path, sheet):
    """Read the 2025-26 column of an OBR table (in £bn) as {label: £m}."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    rows = list(wb[sheet].iter_rows(values_only=True))
    col = None
    out = _Table(f"{path.name} {sheet}")
    for row in rows:
        if col is None:
            for idx, cell in enumerate(row):
                if isinstance(cell, str) and cell.strip() == YEAR:
                    col = idx
            continue
        value = row[col] if col < len(row) else None
        if not isinstance(value, (int, float)):
            continue
        labels = [c for c in row[:col] if isinstance(c, str) and c.strip() and not c.strip().startswith("of which")]
        if not labels:
            continue
        label = _clean_label(labels[-1])
        # A label repeated with a different value is blocked, not silently resolved.
        if label in out and out[label] != value * 1000:
            out.ambiguous.add(label)
        out.setdefault(label, value * 1000)
    if col is None:
        raise ValueError(f"{YEAR} column not found in {path.name} {sheet}")
    return out


def obr_levies_not_yet_in_ons_m():
    """Capacity market and Sizewell C RAB levy for 2025-26, in £m.

    The ONS hasn't yet added these to outturn, so OBR Table 4.20 shows them as zero. Its footnote
    gives what they would have been, rounded to £0.1bn.
    """
    wb = openpyxl.load_workbook(OBR_RECEIPTS, data_only=True, read_only=True)
    for row in wb["4.20"].iter_rows(values_only=True):
        for cell in row:
            if isinstance(cell, str) and "yet to include capacity market" in cell:
                match = re.search(
                    r"capacity market auctions and the Sizewell C RAB charge.*?"
                    r"£([\d.]+) billion and £([\d.]+) billion respectively in 2025-26",
                    cell,
                )
                if match is None:
                    raise ValueError(f"OBR Table 4.20 footnote has changed wording: {cell!r}")
                return float(match.group(1)) * 1000, float(match.group(2)) * 1000
    raise ValueError("OBR Table 4.20 footnote on capacity market and Sizewell C not found")


def obr_gdp_m():
    """Nominal GDP for 2025-26 from OBR Table TA.3, in £m."""
    wb = openpyxl.load_workbook(OBR_ANNEX, data_only=True, read_only=True)
    rows = list(wb["TA.3"].iter_rows(values_only=True))
    header = next(r for r in rows if YEAR in [str(c).strip() for c in r if c is not None])
    col = [str(c).strip() if c is not None else "" for c in header].index(YEAR)
    for row in rows:
        if isinstance(row[1], str) and row[1].startswith("Nominal GDP (£ billion)"):
            return row[col] * 1000
    raise ValueError("Nominal GDP row not found")


def ons_fy_m(column_text):
    """Sum one ONS Appendix D column over April 2025 to March 2026, in £m."""
    wb = openpyxl.load_workbook(ONS_APPENDIX_D, data_only=True, read_only=True)
    rows = list(wb["Time Series"].iter_rows(values_only=True))
    header = [re.sub(r"\s+", " ", str(c or "")) for c in rows[4]]
    matches = [i for i, h in enumerate(header) if column_text in h]
    if len(matches) != 1:
        raise ValueError(f"{column_text!r} matched {len(matches)} ONS columns")
    col = matches[0]
    months = [f"2025 {m}" for m in ("Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")]
    months += [f"2026 {m}" for m in ("Jan", "Feb", "Mar")]
    by_label = {str(r[0]).strip(): r for r in rows[5:] if r[0]}
    return float(sum(by_label[m][col] for m in months))


def hmrc_gambling_k():
    """2025-26 receipts of each gambling duty, in £k, from HMRC's betting and gaming statistics
    (Table 1a).
    """
    df = pd.read_excel(HMRC_GAMBLING, engine="odf", sheet_name="Table_1_BG_receipts", header=None)
    header = [re.sub(r"\s+", " ", str(c)).strip() for c in df.iloc[5]]
    row = df[df[0].astype(str).str.strip() == "2025 to 2026"].iloc[0]
    wanted = {
        "Remote gaming duty": "Remote Gaming Duty",
        "Lottery duty": "Lottery Duty",
        "General betting duty": "General Betting Duty",
        "Machine games duty": "Machine Games Duty",
        "Gaming duty": "Gaming Duty",
        "Bingo duty": "Bingo Duty",
        "Pool betting duty": "Pool Betting Duty",
    }
    out = {}
    for chart_name, hmrc_name in wanted.items():
        idx = [i for i, h in enumerate(header) if h.startswith(hmrc_name)][0]
        out[chart_name] = float(row[idx])
    return out


def hmrc_table_2_6():
    """Income tax on savings, on dividends and in total for 2025-26, in £m (HMRC Table 2.6,
    projected from the 2023-24 SPI).
    """
    df = pd.read_excel(HMRC_IT_LIABILITIES, engine="odf", sheet_name="2_6_IT_by_income_source_2025-26", header=None)
    labels = df[0].astype(str)
    header = df[labels.str.startswith("Breakdown of Income Tax")].iloc[0]
    assert str(header[5]).strip() == "All Income Tax payers", header[5]
    for prefix in ("Income Tax on savings", "Income Tax on dividends"):
        # One row each for basic, higher and additional rate.
        assert labels.str.startswith(prefix).sum() == 3, prefix
    assert labels.str.startswith("Total Income Tax liability").sum() == 1
    all_payers = df[5]
    savings = float(all_payers[labels.str.startswith("Income Tax on savings")].astype(float).sum())
    dividends = float(all_payers[labels.str.startswith("Income Tax on dividends")].astype(float).sum())
    total = float(all_payers[labels.str.startswith("Total Income Tax liability")].astype(float).iloc[0])
    return savings, dividends, total


def rent_income_tax_estimate_m():
    """Estimate income tax on rents, in £m, rounded to £100m.

    HMRC doesn't publish this. We take the 2023-24 SPI split of net property income by total-income
    band (Table 3.7, the latest available) and apply a broad marginal rate to each band: 20% below
    £50,000, 40% from £50,000 to £150,000, 45% above.

    The 2025-26 thresholds are frozen at their 2024-25 levels, so the same rates apply. We don't
    uprate property income from 2023-24.
    """
    wb = openpyxl.load_workbook(HMRC_SPI_3_7, data_only=True, read_only=True)
    rows = list(wb["Table_3_7"].iter_rows(values_only=True))
    header = next(r for r in rows if isinstance(r[0], str) and r[0].startswith("Range of total income"))
    assert str(header[2]).startswith("Net income from property (Amount)"), header[2]
    all_ranges = float(next(r for r in rows if r[0] == "All ranges")[2])
    total = 0.0
    property_income = 0.0
    for row in rows:
        lower = row[0]
        if not isinstance(lower, (int, float)):
            continue
        amount = float(row[2])  # net income from property, £m
        property_income += amount
        if lower < 50000:
            rate = 0.20
        elif lower < 150000:
            rate = 0.40
        else:
            rate = 0.45
        total += amount * rate
    # The band figures are rounded, so allow 1% against the published total.
    assert abs(property_income - all_ranges) <= 0.01 * all_ranges, (property_income, all_ranges)
    return round(total, -2)


A5 = obr_table(OBR_ANNEX, "TA.5")
T41 = obr_table(OBR_RECEIPTS, "4.1")    # Other HMRC taxes
T42 = obr_table(OBR_RECEIPTS, "4.2")    # Other taxes
T44 = obr_table(OBR_RECEIPTS, "4.4")    # Income tax and NICs
T47 = obr_table(OBR_RECEIPTS, "4.7")    # Property transaction taxes
T420 = obr_table(OBR_RECEIPTS, "4.20")  # Environmental levies

GDP_M = obr_gdp_m()
ROOT_NAME = "All taxes"

EMPLOYER_NICS = T44["Class 1 Employer NICs"]
EMPLOYEE_NICS_BASE = T44["Class 1 Employee NICs"]
STATUTORY_RECOVERIES = T44["Statutory payment recoveries"]
EMPLOYEE_NICS = EMPLOYEE_NICS_BASE + STATUTORY_RECOVERIES
SELF_EMPLOYED_NICS = T44["Class 4 and Class 2 Self employed NICs"]
OTHER_NICS = T44["Other NIC"]
TOTAL_NICS = EMPLOYER_NICS + EMPLOYEE_NICS + SELF_EMPLOYED_NICS + OTHER_NICS
# Segments under £250m go unlabelled, except those named here.
LABEL_THRESHOLD_M = 250
FORCE_LABELS = {
    "Employment taxes",
    "Goods/services",
    "Business",
    "Land",
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

# Palette for each parent's children, keyed by the parent's name.
CHILD_COLORS = {
    "Employment taxes": ["#005F73", "#0A9396", "#3FBAC2", "#89D6CF"],
    "Goods/services": ["#C92A2A", "#E8590C", "#F76707", "#FF922B", "#A61E4D", "#C2255C", "#D6336C", "#F06595"],
    "Gaming duties": ["#A61E4D", "#C2255C", "#D6336C", "#E64980", "#F06595", "#F783AC", "#FAA2C1"],
    "Business": ["#1E3A5F", "#2B4C7E", "#3D6CB9", "#6D8FE8"],
    "Land": ["#B7791F", "#D69E2E", "#ECC94B", "#F6E05E"],
    "Wealth": ["#5B21B6", "#7B2CBF", "#A855F7", "#C084FC", "#D8B4FE", "#E9D5FF"],
    "Environment & energy": ["#1B5E20", "#2B8A3E", "#51A353", "#8BC34A"],
    "Environmental levies": ["#1B5E20", "#2B8A3E", "#51A353", "#66BB6A", "#7CB342", "#9CCC65", "#A5D6A7"],
    "Other": ["#0F4C75", "#1B6CA8", "#2D9DE5", "#5FB6EA"],
    "Other small taxes": ["#0F4C75", "#1B6CA8", "#2D9DE5", "#5FB6EA", "#8ECBEF"],
    "Income tax": ["#5B21B6", "#7B2CBF", "#A855F7"],
    "Land annual": ["#B7791F", "#D69E2E"],
}

ITEM_COLORS = {
    "ATOL": "#005A8D",
}

ITEM_STYLE_OVERRIDES = {
    "ATOL": {"borderColor": "#005A8D", "borderWidth": 1.8},
}


def node(name, value_m, children=None, note=None):
    """One chart segment. A value of None means the sum of the children; a negative value is drawn
    as zero.
    """
    if value_m is None:
        value_m = sum(child["actual_m"] for child in children)
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
    """White text on dark segments, dark text on light ones."""
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
    sign = "-" if value_m < 0 else ""
    if abs(value_m) < 100:
        # Under £100m, show £m: "£0.0bn" for a tax raising £26m helps nobody.
        return f"{sign}£{abs(value_m):.0f}m"
    return f"{sign}£{abs(value_m) / 1000:.1f}bn"


def format_money_whole(value_m):
    return f"£{value_m / 1000:,.0f}bn"


def format_gdp(value_m):
    return f"{value_m / GDP_M * 100:.1f}%"


def format_tax_pct(value_m, total_m):
    return f"{value_m / total_m * 100:.1f}%"


def should_show_label(item):
    if item.get("is_padding"):
        return False
    return item["actual_m"] >= LABEL_THRESHOLD_M or item["name"] in FORCE_LABELS


def pad_terminal_nodes(items, depth=1, max_depth=4):
    """Extend each leaf above max_depth with unlabelled copies of itself down to that depth. Not
    called at present.
    """
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
    """Font size for a segment's label: bigger segments get bigger text."""
    if value_m >= 5000:
        return 11
    if value_m >= 1000:
        return 8
    if value_m >= 250:
        return 7
    return 6


def apply_colors(items, palette):
    """Colour each segment from its parent's palette, with a label colour that stays readable."""
    for idx, item in enumerate(items):
        color = ITEM_COLORS.get(item["name"], palette[idx % len(palette)])
        item["itemStyle"] = {"color": color, **ITEM_STYLE_OVERRIDES.get(item["name"], {})}
        item["label"] = label_for_color(color)
        if "children" in item:
            child_palette = CHILD_COLORS.get(item["name"], palette)
            apply_colors(item["children"], child_palette)
    return items


def apply_layout_values(items, mode, total_m=None):
    """Set each segment's drawn size for the view: £bn, % of GDP or % of total tax.

    A parent is drawn at least as big as its children, and a negative value as zero, so children
    always fit inside their parent.
    """
    for item in items:
        child_total_m = 0
        if "children" in item:
            apply_layout_values(item["children"], mode, total_m)
            child_total_m = sum(child["layout_m"] for child in item["children"])
        item["layout_m"] = max(item["actual_m"], child_total_m, 0)
        if mode == "gdp":
            item["value"] = item["layout_m"] / GDP_M * 100
        elif mode == "tax_pct":
            item["value"] = item["layout_m"] / total_m * 100
        else:
            item["value"] = item["layout_m"] / 1000
    return items


def format_value(item, mode, total_m=None):
    if mode == "money":
        return format_money(item["actual_m"])
    if mode == "tax_pct":
        return format_tax_pct(item["layout_m"], total_m)
    return format_gdp(item["actual_m"])


def apply_display_labels(items, mode, total_m=None):
    """Set each segment's label and tooltip for the view."""
    for item in items:
        label = item.setdefault("label", {})
        value = format_value(item, mode, total_m)
        if item.get("is_padding"):
            label["show"] = False
        elif should_show_label(item):
            label["show"] = True
            # The value is shown only for segments of £1bn or more, or those in FORCE_LABELS.
            label["formatter"] = f"{item['name']}\n{value}" if item["actual_m"] >= 1000 or item["name"] in FORCE_LABELS else item["name"]
            label["fontSize"] = label_size(item["actual_m"])
            label["lineHeight"] = max(label["fontSize"] + 1, 7)
        else:
            label["show"] = False
        item["tooltip"] = {"formatter": f"{item['name']}<br>{value}"}
        if "children" in item:
            apply_display_labels(item["children"], mode, total_m)
    return items


# ---------------------------------------------------------------------------
# Income tax. The OBR total, split into tax on dividends and savings (HMRC liabilities, scaled to
# the OBR total), on rents (our estimate) and on work (the rest).
# ---------------------------------------------------------------------------
INCOME_TAX = A5["Income tax"]
HMRC_SAVINGS_TAX, HMRC_DIVIDEND_TAX, HMRC_TOTAL_LIABILITY = hmrc_table_2_6()
IT_SCALE = INCOME_TAX / HMRC_TOTAL_LIABILITY
DIVIDEND_INCOME_TAX = HMRC_DIVIDEND_TAX * IT_SCALE
SAVINGS_INCOME_TAX = HMRC_SAVINGS_TAX * IT_SCALE
RENT_INCOME_TAX = rent_income_tax_estimate_m()
RESIDUAL_INCOME_TAX = INCOME_TAX - DIVIDEND_INCOME_TAX - SAVINGS_INCOME_TAX - RENT_INCOME_TAX

# ---------------------------------------------------------------------------
# VAT. The OBR's VAT line is already net of refunds to public bodies (it equals ONS "VAT - of which
# other"). The refunds are a separate line, which we leave out. Don't deduct them twice.
# ---------------------------------------------------------------------------
VAT = A5["Value added tax"]
VAT_REFUNDS = A5["VAT refunds"]
assert abs(VAT - ons_fy_m("Value added tax - of which other")) < 1, "OBR VAT should equal ONS VAT net of refunds"

# ---------------------------------------------------------------------------
# Stamp taxes on shares. No 2025-26 split has been published, so we use HMRC's 2024-25 proportions
# (SDRT £3,050m, stamp duty £1,270m).
# ---------------------------------------------------------------------------
STAMP_TAXES_ON_SHARES = A5["Stamp taxes on shares"]
SDRT = STAMP_TAXES_ON_SHARES * 3050 / (3050 + 1270)
STAMP_DUTY_1891 = STAMP_TAXES_ON_SHARES - SDRT

# ---------------------------------------------------------------------------
# Gambling. The OBR total, split in proportion to HMRC's 2025-26 receipts.
# ---------------------------------------------------------------------------
GAMING_DUTIES = T41["Betting and gaming taxes"]
_gambling = hmrc_gambling_k()
_gambling_total = sum(_gambling.values())
GAMBLING_SPLIT = {name: GAMING_DUTIES * value / _gambling_total for name, value in _gambling.items()}

# ---------------------------------------------------------------------------
# Alcohol. The ONS Appendix D split, which sums to the OBR total. Domestic wine, cider and perry go
# in with beer.
# ---------------------------------------------------------------------------
ALCOHOL = A5["Alcohol duties"]
BEER_AND_CIDER = ons_fy_m("Alcohol duties - of which beer") + ons_fy_m("of which domestic wines, cider and perry")
WINE = ons_fy_m("Alcohol duties - of which imported wines")
SPIRITS = ons_fy_m("Alcohol duties - of which spirits")
assert abs(BEER_AND_CIDER + WINE + SPIRITS - ALCOHOL) < 1

# ---------------------------------------------------------------------------
# Environmental levies, OBR Table 4.20. The ONS doesn't yet count the capacity market or the
# Sizewell C levy, so the table shows zero for both. We add the figures from its footnote, so the
# chart total is above the OBR's by that amount.
# ---------------------------------------------------------------------------
ENVIRONMENTAL_LEVIES_ONS = A5["Environmental levies"]
assert T420["Capacity market"] == 0 and T420["Sizewell C RAB levy"] == 0
CAPACITY_MARKET, SIZEWELL_C_LEVY = obr_levies_not_yet_in_ons_m()
LEVIES_NOT_YET_IN_ONS = CAPACITY_MARKET + SIZEWELL_C_LEVY
ENV_LEVY_SPLIT = {
    "Renewables obligation": T420["Renewables obligation"],
    "Contracts for difference": T420["Contracts for difference"],
    "Feed-in tariffs": T420["Feed-in tariffs"],
    "Capacity market": CAPACITY_MARKET,
    "Warm home discount": T420["Warm home discount"],
    "Sizewell C levy": SIZEWELL_C_LEVY,
    "Green gas levy": T420["Green gas levy"],
}
ENVIRONMENTAL_LEVIES = ENVIRONMENTAL_LEVIES_ONS + LEVIES_NOT_YET_IN_ONS
assert abs(sum(ENV_LEVY_SPLIT.values()) - ENVIRONMENTAL_LEVIES) < 1

# ---------------------------------------------------------------------------
# Packaging (extended producer responsibility) fees. Charged since April 2025 but zero in the
# October 2026 outturn. The OBR gives no "would have been" figure, so we use its March 2026
# forecast for 2025-26: a forecast, not an outturn.
# ---------------------------------------------------------------------------
EPR_FEES = obr_table(OBR_MARCH_RECEIPTS, "3.2")["Extended producer responsibility Fees"]
# Guards against picking up the wrong line.
assert 1000 < EPR_FEES < 2000, EPR_FEES
NOT_YET_IN_ONS = LEVIES_NOT_YET_IN_ONS + EPR_FEES

# ---------------------------------------------------------------------------
# Other small taxes. The OBR Table 4.2 total, split using ONS Appendix D lines.
# ---------------------------------------------------------------------------
OTHER_SMALL_TAXES = T42["Other small taxes"]
ATOL = ons_fy_m("Air Travel Organisers Licence")
BRITISH_TRANSPORT_POLICE = ons_fy_m("of which British Transport Police")
DVLA_REGISTRATION_FEES = ons_fy_m("Driver and Vehicle Licensing Agency")
LIGHTHOUSE_DUES = ons_fy_m("of which lighthouse dues")
OTHER_SMALL_TAXES_NES = OTHER_SMALL_TAXES - ATOL - BRITISH_TRANSPORT_POLICE - DVLA_REGISTRATION_FEES - LIGHTHOUSE_DUES
assert OTHER_SMALL_TAXES_NES > 0

# ---------------------------------------------------------------------------
# Lines that are zero in 2025-26 and so not drawn. We check they really are zero, so nothing with
# revenue is dropped by mistake.
# ---------------------------------------------------------------------------
ZERO_LINES = {
    "4.1": ["Carbon border adjustment mechanism", "Vaping tax"],
    "4.2": [
        "Pension Protection Fund levy", "Extended producer responsibility Fees", "Building safety levy",
        "Scottish aggregates levy", "International student levy", "Landlord Registration Fees",
    ],
}
for table, names in ZERO_LINES.items():
    source = T41 if table == "4.1" else T42
    for name in names:
        assert source[name] == 0, (name, source[name])

SDLT_CHILDREN = [
    node("Residential SDLT", T47["Main rates"]),
    node("Additional dwellings", T47["Higher rates on additional dwellings"]),
    node("Non-resident SDLT", T47["Non-UK resident surcharge"]),
    node("Non-residential SDLT", T47["SDLT from non-residential property"]),
]

# The chart, in £m: categories, then taxes, then any breakdown of a tax.
data_m = [
    node("Employment taxes", RESIDUAL_INCOME_TAX + TOTAL_NICS + A5["Apprenticeship levy"], [
        node("Income tax on work", RESIDUAL_INCOME_TAX, note="Income tax net of separately shown dividends, savings interest and rents."),
        node("NICs", TOTAL_NICS, [
            node("Employer NICs", EMPLOYER_NICS),
            node("Employee NICs", EMPLOYEE_NICS, note="Includes statutory payment recoveries."),
            node("Self-employed NICs", SELF_EMPLOYED_NICS),
            node("Other NICs", OTHER_NICS),
        ]),
        node("Apprenticeship levy", A5["Apprenticeship levy"]),
    ]),
    node("Goods/services", None, [
        node("VAT", VAT, note="VAT net of refunds to government bodies."),
        node("Insurance premium tax", A5["Insurance premium tax"]),
        node("Air passenger duty", A5["Air passenger duty"]),
        node("Fuel duties", A5["Fuel duties"]),
        node("Alcohol duties", ALCOHOL, [
            node("Beer and cider", BEER_AND_CIDER),
            node("Wine", WINE),
            node("Spirits", SPIRITS),
        ]),
        node("Vehicle excise duty", A5["Vehicle excise duties"]),
        node("Tobacco duties", A5["Tobacco duties"]),
        node("Customs duties", T41["Customs duties"]),
        node("Gaming duties", GAMING_DUTIES, [node(name, value) for name, value in GAMBLING_SPLIT.items()]),
        node("Soft drinks levy", T41["Soft drink industry levy"]),
        node("Lorry road levy", T42["Lorry road user levy"]),
        node("Gaming levy", T42["Statutory gaming levy"]),
    ]),
    node("Business", None, [
        node("Corporation tax", A5["Corporation tax"], [
            node("Onshore CT", A5["Onshore"]),
            node("Offshore CT", A5["Offshore"]),
        ]),
        node("Digital services tax", A5["Digital services tax"]),
        node("Bank taxes", A5["Bank levy"] + A5["Bank surcharge"], [
            node("Bank levy", A5["Bank levy"]),
            node("Bank surcharge", A5["Bank surcharge"]),
        ]),
        node("Diverted profits", T41["Diverted profits tax"]),
        node("Property developer tax", T41["Residential property developer tax"]),
        node("Energy profits levy", A5["Energy profits levy"]),
        node("Electricity generator levy", A5["Electricity generator levy"]),
        node("Petroleum revenue tax", A5["Petroleum revenue tax"], note="Net repayments reduce receipts."),
    ]),
    node("Land", None, [
        node("Land annual", None, [
            node("Council tax", A5["Council tax"]),
            node("Business rates", A5["Business rates"]),
            node("NI domestic rates", T42["Northern Ireland domestic rates"]),
            node("NI business rates", T42["Northern Ireland business rates"]),
        ]),
        node("Land transactions", A5["Property transaction taxes"], [
            node("SDLT", T47["Total SDLT"], SDLT_CHILDREN),
            node("ATED", T47["Annual tax on enveloped dwellings (ATED)"]),
            node("LBTT (Scotland)", T47["Land and buildings transactions tax (Scotland)"]),
            node("LTT (Wales)", T47["Land transactions tax (Wales)"]),
        ]),
    ]),
    node("Wealth", None, [
        node("Income tax", DIVIDEND_INCOME_TAX + SAVINGS_INCOME_TAX + RENT_INCOME_TAX, [
            node("Dividend income tax", DIVIDEND_INCOME_TAX),
            node("Savings income tax", SAVINGS_INCOME_TAX),
            node("Rent income tax", RENT_INCOME_TAX, note="Estimated from HMRC SPI property-income distribution; property income is otherwise included within non-savings income tax."),
        ]),
        node("Capital gains tax", A5["Capital gains tax"]),
        node("Inheritance tax", A5["Inheritance tax"]),
        node("Stamp taxes on shares", STAMP_TAXES_ON_SHARES, [
            node("SDRT", SDRT),
            node("Stamp duty (1891)", STAMP_DUTY_1891),
        ]),
    ]),
    node("Environment & energy", None, [
        node("Environmental levies", ENVIRONMENTAL_LEVIES, [node(name, value) for name, value in ENV_LEVY_SPLIT.items()]),
        node("Emissions trading", A5["Emissions trading scheme"]),
        node("Climate change levy", A5["Climate change levy"]),
        node("Packaging fees (EPR)", EPR_FEES, note="OBR March 2026 forecast; not yet in ONS outturn."),
        node("Landfill tax", T41["Landfill tax"]),
        node("Aggregates levy", T41["Aggregates levy"]),
        node("Plastic packaging tax", T41["Plastic packaging tax"]),
        node("Scottish landfill tax", T42["Scottish landfill tax"]),
        node("Welsh landfill tax", T42["Welsh landfill tax"]),
    ]),
    node("Other", None, [
        node("Licence fee", A5["Licence fee receipts"]),
        node("Immigration health surcharge", T42["Immigration health surcharge"]),
        node("Visa fees", T42["Visa fees"]),
        node("Lottery payments", T42["Camelot payments to National Lottery Distribution Fund"]),
        node("Levy-funded bodies", T42["Other levy funded body receipts"]),
        node("Bank of England levy", T42["Bank of England Levy"]),
        node("Passport fees", T42["Passport fees"]),
        node("Other small taxes", OTHER_SMALL_TAXES, [
            node("Other taxes n.e.s.", OTHER_SMALL_TAXES_NES),
            node("British Transport Police", BRITISH_TRANSPORT_POLICE),
            node("DVLA registration fees", DVLA_REGISTRATION_FEES),
            node("Lighthouse dues", LIGHTHOUSE_DUES),
            node("ATOL", ATOL),
        ]),
        node("Consumer credit fees", T42["Consumer Credit Act fees"]),
        node("Immigration skills charge", T42["Immigration skills charge"]),
        node("Land Registry", T42["Land registry"]),
        node("Community infrastructure levy", T42["Community infrastructure levy"]),
        node("Companies House", T42["Companies House receipts"]),
        node("Economic crime levy", T42["Economic crime levy"]),
        node("Horserace betting levy", T42["Horserace betting levy"]),
    ]),
]


def check_children(items, path=""):
    """Check every parent equals the sum of its children, to within £1m."""
    for item in items:
        if "children" not in item:
            continue
        child_sum = sum(child["actual_m"] for child in item["children"])
        gap = item["actual_m"] - child_sum
        # Except SDLT: OBR Table 4.7's four components sum to £14m less than its SDLT total.
        allowed = 15 if item["name"] == "SDLT" else 1
        assert abs(gap) <= allowed, (path + item["name"], item["actual_m"], child_sum)
        check_children(item["children"], path + item["name"] + " > ")


check_children(data_m)

CHART_TOTAL_M = sum(item["actual_m"] for item in data_m)
NA_TAXES_M = A5["National Accounts taxes"]
# The chart total is the OBR's National Accounts taxes, less VAT refunds, plus the items not yet in
# ONS outturn.
assert abs(CHART_TOTAL_M - (NA_TAXES_M - VAT_REFUNDS + NOT_YET_IN_ONS)) < 1, CHART_TOTAL_M


def leaves(items):
    """Yield every segment that has no children."""
    for item in items:
        if "children" in item:
            yield from leaves(item["children"])
        else:
            yield item


print(f"OBR National Accounts taxes {YEAR}: £{NA_TAXES_M:,.0f}m")
print(f"less VAT refunds: £{VAT_REFUNDS:,.0f}m")
print(f"plus capacity market and Sizewell C levy (not yet in ONS outturn): £{LEVIES_NOT_YET_IN_ONS:,.0f}m")
print(f"plus packaging (EPR) fees (OBR March 2026 forecast): £{EPR_FEES:,.1f}m")
print(f"chart total: £{CHART_TOTAL_M:,.0f}m = {CHART_TOTAL_M / GDP_M * 100:.2f}% of GDP (£{GDP_M:,.0f}m)")
print(f"income tax split: dividends £{DIVIDEND_INCOME_TAX:,.0f}m, savings £{SAVINGS_INCOME_TAX:,.0f}m, rent £{RENT_INCOME_TAX:,.0f}m, work £{RESIDUAL_INCOME_TAX:,.0f}m")
_leaves = list(leaves(data_m))
print(f"chart leaves: {len(_leaves)} (of which positive: {sum(1 for l in _leaves if l['actual_m'] > 0)})")

apply_colors(data_m, TOP_COLORS)
apply_layout_values(data_m, "money")
apply_display_labels(data_m, "money")


def convert_to_gdp(data):
    """A copy of the chart sized and labelled as % of GDP."""
    converted = deepcopy(data)
    apply_layout_values(converted, "gdp")
    apply_display_labels(converted, "gdp")
    return converted


def total_actual_m(data):
    # Uses actual values, not drawn ones, so net repayments such as PRT reduce the total.
    return sum(item["actual_m"] for item in data)


TOTAL_TAX_M = total_actual_m(data_m)


def convert_to_tax_pct(data):
    """A copy of the chart sized and labelled as % of total tax."""
    converted = deepcopy(data)
    apply_layout_values(converted, "tax_pct", TOTAL_TAX_M)
    apply_display_labels(converted, "tax_pct", TOTAL_TAX_M)
    return converted


def root_tooltip(data, mode):
    """Tooltip for the centre of the chart: the total in the view's units."""
    total_m = total_actual_m(data)
    if mode == "gdp":
        value = format_gdp(total_m)
    elif mode == "tax_pct":
        value = "100.0%"
    else:
        value = format_money_whole(total_m)
    return {"formatter": f"{ROOT_NAME}, {value}"}


# ECharts sunburst. The first level is the hidden root; the other five are the rings, from the
# centre out.
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

# Three views, switched with the timeline control: £bn, % of GDP and % of total tax.
option = {
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
            "data": ["£bn", "GDP %", "Tax %"]
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
        },
        {
            "tooltip": {"trigger": "item"},
            "series": [{**base_series, "tooltip": root_tooltip(data_m, "tax_pct"), "data": convert_to_tax_pct(data_m)}]
        }
    ],
}

OUTPUT.write_text(json.dumps(option, indent=2), encoding="utf-8")
print(OUTPUT)
