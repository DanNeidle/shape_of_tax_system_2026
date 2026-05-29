#!/usr/bin/env python3
import csv
from collections import defaultdict
from pathlib import Path


GDP_EUR = 4_305_300_000_000
EXPECTED_CHART_TOTAL = 1_816_514_000_000
EXPECTED_LAYER_1 = {
    "Employment",
    "Goods/services",
    "Business",
    "Land",
    "Wealth",
    "Environmental",
    "Other",
}
EXPECTED_ROWS = 54
MAX_CHART_LABEL_LEN = 32

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data" / "germany_tax"
TABLE = DATA_DIR / "germany_tax_revenue_layered_2024.csv"
BMF_TABLE = DATA_DIR / "germany_bmf_cash_tax_revenue_2024.csv"
EUROSTAT_TABLE = DATA_DIR / "germany_eurostat_tax_revenue_candidate_table_2024.csv"


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    rows = read_csv(TABLE)
    eurostat_rows = read_csv(EUROSTAT_TABLE)
    bmf_rows = read_csv(BMF_TABLE)

    if len(rows) != EXPECTED_ROWS:
        raise SystemExit(f"Unexpected layered row count: {len(rows)}")

    missing_layers = [
        row["chart_label_en"] for row in rows
        if row["chart_include"] == "yes"
        and (not row["layer_1"] or not row["layer_2"] or not row["layer_3"])
    ]
    if missing_layers:
        raise SystemExit(f"Rows missing layers: {missing_layers[:10]}")

    actual_layer_1 = {row["layer_1"] for row in rows if row["chart_include"] == "yes"}
    if actual_layer_1 != EXPECTED_LAYER_1:
        raise SystemExit(f"Unexpected layer_1 set: {sorted(actual_layer_1)}")

    negative_chart_rows = [
        row["chart_label_en"] for row in rows
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
        row["chart_label_en"] for row in rows
        if row["chart_include"] == "yes" and not row.get("display_explanation")
    ]
    if missing_display_explanations:
        raise SystemExit(f"Included chart rows missing display explanations: {missing_display_explanations[:10]}")

    banned_display_terms = [
        "Eurostat",
        "National Tax Lists",
        "ESA code",
        "BMF",
        "cash receipts",
        "national-tax-list",
        "classified as",
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
        (row["chart_label_en"], len(row["chart_label_en"]))
        for row in rows
        if row["chart_include"] == "yes"
        and len(row["chart_label_en"]) > MAX_CHART_LABEL_LEN
    ]
    if long_chart_labels:
        raise SystemExit(f"Chart labels longer than {MAX_CHART_LABEL_LEN}: {long_chart_labels[:10]}")

    sibling_labels = defaultdict(list)
    for row in rows:
        if row["chart_include"] != "yes":
            continue
        key = (row["layer_1"], row["layer_2"], row["layer_3"], row["chart_label_en"])
        sibling_labels[key].append(row["tax_name"])
    duplicate_sibling_labels = {
        key: names for key, names in sibling_labels.items() if len(names) > 1
    }
    if duplicate_sibling_labels:
        raise SystemExit(f"Duplicate sibling chart labels: {duplicate_sibling_labels}")

    chart_total = sum(
        int(row["chart_revenue_eur"])
        for row in rows
        if row["chart_include"] == "yes" and row["chart_revenue_eur"]
    )
    if chart_total != EXPECTED_CHART_TOTAL:
        raise SystemExit(f"Chart total mismatch: {chart_total} vs {EXPECTED_CHART_TOTAL}")

    source_total = sum(int(row["revenue_eur"]) for row in eurostat_rows)
    if source_total != EXPECTED_CHART_TOTAL:
        raise SystemExit(f"Eurostat source total mismatch: {source_total} vs {EXPECTED_CHART_TOTAL}")

    pct = chart_total / GDP_EUR * 100
    if abs(pct - 42.192506909391914) > 0.0000001:
        raise SystemExit(f"Chart GDP percentage mismatch: {pct}")

    solidarity_rows = [row for row in rows if row["chart_label_en"] == "Solidarity surcharge"]
    if len(solidarity_rows) != 1 or int(solidarity_rows[0]["chart_revenue_eur"]) != 12_634_294_172:
        raise SystemExit("Solidarity surcharge split not found or has unexpected value")

    bmf_negative_rows = [
        row for row in bmf_rows
        if row["is_total_or_memo"] == "no" and int(row["revenue_eur"]) < 0
    ]
    negative_labels_in_chart = {
        row["tax_name"] for row in rows if row["chart_include"] == "yes"
    } & {row["tax_name"] for row in bmf_negative_rows}
    if negative_labels_in_chart:
        raise SystemExit(f"BMF negative rows appear in chart: {sorted(negative_labels_in_chart)}")

    print("Germany layer audit passed")
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
    if bmf_negative_rows:
        print("Excluded negative BMF cash rows:")
        for row in bmf_negative_rows:
            print(f"- {row['tax_name']}: EUR {int(row['revenue_eur']):,}")


if __name__ == "__main__":
    main()
