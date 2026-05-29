#!/usr/bin/env python3
import csv
from pathlib import Path


GDP_EUR = 2_919_900_000_000
EXPECTED_CHART_TOTAL = 1_321_460_000_000
EXPECTED_LAYER_1 = {
    "Employment",
    "Goods/services",
    "Business",
    "Land",
    "Wealth",
    "Environmental",
    "Other",
}
MAX_CHART_LABEL_LEN = 32

BASE = Path(__file__).resolve().parent
TABLE = BASE / "data" / "france_tax_revenue_layered_2024.csv"


def main():
    with TABLE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != 355:
        raise SystemExit(f"Unexpected row count: {len(rows)}")

    missing_layers = [
        row["tax_name"] for row in rows
        if not row["layer_1"] or not row["layer_2"] or not row["layer_3"]
    ]
    if missing_layers:
        raise SystemExit(f"Rows missing layers: {missing_layers[:10]}")

    actual_layer_1 = {row["layer_1"] for row in rows}
    if actual_layer_1 != EXPECTED_LAYER_1:
        raise SystemExit(f"Unexpected layer_1 set: {sorted(actual_layer_1)}")

    negative_chart_rows = [
        row["tax_name"] for row in rows
        if row["chart_include"] == "yes"
        and row["chart_revenue_eur"]
        and int(row["chart_revenue_eur"]) < 0
    ]
    if negative_chart_rows:
        raise SystemExit(f"Negative rows included in chart: {negative_chart_rows}")

    missing_chart_labels = [
        row["tax_name"] for row in rows
        if row["chart_include"] == "yes" and not row["chart_label_en"]
    ]
    if missing_chart_labels:
        raise SystemExit(f"Included chart rows missing short English labels: {missing_chart_labels[:10]}")

    missing_display_explanations = [
        row["tax_name"] for row in rows
        if row["chart_include"] == "yes" and not row.get("display_explanation")
    ]
    if missing_display_explanations:
        raise SystemExit(f"Included chart rows missing display explanations: {missing_display_explanations[:10]}")

    banned_display_terms = [
        "Eurostat national-tax-list",
        "ESA code",
        "Collector:",
        "Beneficiary:",
        "Low-yield",
        "Tax or compulsory charge grouped under",
        "Residual tax category",
        "Administrative or service-related charge treated as tax revenue",
    ]
    bad_display_explanations = [
        (row["chart_label_en"], row["display_explanation"])
        for row in rows
        if row["chart_include"] == "yes"
        and any(term in row.get("display_explanation", "") for term in banned_display_terms)
    ]
    if bad_display_explanations:
        raise SystemExit(f"Visitor-facing explanations contain source jargon: {bad_display_explanations[:10]}")

    long_chart_labels = [
        (row["chart_label_en"], row["tax_name"])
        for row in rows
        if row["chart_include"] == "yes"
        and len(row["chart_label_en"]) > MAX_CHART_LABEL_LEN
    ]
    if long_chart_labels:
        raise SystemExit(f"Chart labels longer than {MAX_CHART_LABEL_LEN}: {long_chart_labels[:10]}")

    sibling_labels = {}
    for row in rows:
        if row["chart_include"] != "yes":
            continue
        key = (row["layer_1"], row["layer_2"], row["chart_label_en"])
        sibling_labels.setdefault(key, []).append(row["tax_name"])
    duplicate_sibling_labels = {
        key: names for key, names in sibling_labels.items() if len(names) > 1
    }
    if duplicate_sibling_labels:
        raise SystemExit(f"Duplicate sibling chart labels: {duplicate_sibling_labels}")

    excluded_negative_rows = [
        row for row in rows
        if row["revenue_eur"]
        and int(row["revenue_eur"]) < 0
        and row["chart_include"] == "no"
    ]
    if len(excluded_negative_rows) != 7:
        raise SystemExit(f"Expected 7 excluded negative D995 rows, found {len(excluded_negative_rows)}")

    global_overlap_rows = [
        row for row in rows
        if row["tax_name"] == "Less: Cour low-yield taxes already included in Eurostat aggregates"
    ]
    if global_overlap_rows:
        raise SystemExit("Global Cour overlap adjustment should not appear in layered chart table")

    chart_total = sum(
        int(row["chart_revenue_eur"])
        for row in rows
        if row["chart_include"] == "yes" and row["chart_revenue_eur"]
    )
    if chart_total != EXPECTED_CHART_TOTAL:
        raise SystemExit(f"Chart total mismatch: {chart_total} vs {EXPECTED_CHART_TOTAL}")

    pct = chart_total / GDP_EUR * 100
    if abs(pct - 45.25702935032022) > 0.0000001:
        raise SystemExit(f"Chart GDP percentage mismatch: {pct}")

    print("Layer audit passed")
    print(f"Rows: {len(rows)}")
    print(f"Chart total: EUR {chart_total:,}")
    print(f"Chart % GDP: {pct:.6f}%")
    print(f"Max chart label length: {max(len(row['chart_label_en']) for row in rows if row['chart_include'] == 'yes')}")
    print("Layer 1 totals:")
    for layer in sorted(EXPECTED_LAYER_1):
        layer_total = sum(
            int(row["chart_revenue_eur"])
            for row in rows
            if row["layer_1"] == layer
            and row["chart_include"] == "yes"
            and row["chart_revenue_eur"]
        )
        print(f"- {layer}: EUR {layer_total:,}")


if __name__ == "__main__":
    main()
