#!/usr/bin/env python3
import csv
from pathlib import Path


GDP_EUR = 2_919_900_000_000
BASE = Path(__file__).resolve().parent
TABLE = BASE.parent / "data" / "france_tax" / "france_tax_revenue_candidate_table_2024.csv"

EXPECTED_HEADERS = [
    "tax_name",
    "tax_name_english",
    "english_explanation",
    "revenue_eur",
    "revenue_pct_gdp",
    "source_for_data",
    "notes",
]


def source_family(row):
    if row["source_for_data"].startswith("Eurostat"):
        return "Eurostat"
    if row["source_for_data"].startswith("Cour") or row["source_for_data"].startswith("Projet de loi"):
        return "Cour"
    return "Other"


def main():
    with TABLE.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_HEADERS:
            raise SystemExit(f"Unexpected headers: {reader.fieldnames}")
        rows = list(reader)

    if len(rows) != 356:
        raise SystemExit(f"Unexpected row count: {len(rows)}")

    duplicate_rows = len(rows) - len({tuple(row[h] for h in EXPECTED_HEADERS) for row in rows})
    if duplicate_rows:
        raise SystemExit(f"Duplicate rows found: {duplicate_rows}")

    family_counts = {"Eurostat": 0, "Cour": 0, "Other": 0}
    for row in rows:
        family_counts[source_family(row)] += 1
        for field in ["tax_name", "tax_name_english", "english_explanation", "source_for_data"]:
            if not row[field].strip():
                raise SystemExit(f"Missing {field}: {row}")
        if row["revenue_eur"]:
            expected_pct = int(row["revenue_eur"]) / GDP_EUR * 100
            actual_pct = float(row["revenue_pct_gdp"])
            if abs(expected_pct - actual_pct) > 0.000001:
                raise SystemExit(f"GDP percentage mismatch for {row['tax_name']}: {actual_pct} vs {expected_pct}")
        elif row["revenue_pct_gdp"]:
            raise SystemExit(f"GDP percentage present without revenue: {row['tax_name']}")

    if family_counts != {"Eurostat": 112, "Cour": 244, "Other": 0}:
        raise SystemExit(f"Unexpected source-family counts: {family_counts}")

    missing_revenue = [row for row in rows if not row["revenue_eur"]]
    if len(missing_revenue) != 95:
        raise SystemExit(f"Unexpected missing-revenue count: {len(missing_revenue)}")
    if any(source_family(row) != "Cour" for row in missing_revenue):
        raise SystemExit("A non-Cour row is missing revenue")

    eurostat_total = sum(int(row["revenue_eur"]) for row in rows if row["revenue_eur"] and source_family(row) == "Eurostat")
    cour_rows = [row for row in rows if source_family(row) == "Cour"]
    cour_overlap_adjustments = [
        row for row in cour_rows
        if row["tax_name"] == "Less: Cour low-yield taxes already included in Eurostat aggregates"
    ]
    if len(cour_overlap_adjustments) != 1:
        raise SystemExit(f"Expected exactly one Cour overlap adjustment, found {len(cour_overlap_adjustments)}")

    cour_known_total = sum(
        int(row["revenue_eur"])
        for row in cour_rows
        if row["revenue_eur"] and row not in cour_overlap_adjustments
    )
    d995_negative_adjustment = sum(
        int(row["revenue_eur"])
        for row in rows
        if row["revenue_eur"].startswith("-") and source_family(row) == "Eurostat"
    )
    all_row_total = sum(int(row["revenue_eur"]) for row in rows if row["revenue_eur"])

    if eurostat_total != 1_321_460_000_000:
        raise SystemExit(f"Unexpected Eurostat net total: {eurostat_total}")
    if cour_known_total != 7_225_124_488:
        raise SystemExit(f"Unexpected Cour known/estimated-yield total: {cour_known_total}")
    if d995_negative_adjustment != -4_621_000_000:
        raise SystemExit(f"Unexpected D995 negative-adjustment total: {d995_negative_adjustment}")
    if int(cour_overlap_adjustments[0]["revenue_eur"]) != -cour_known_total:
        raise SystemExit("Cour overlap adjustment does not offset Cour known-yield rows")
    if all_row_total != eurostat_total:
        raise SystemExit(f"Full CSV total does not reconcile to Eurostat total: {all_row_total} vs {eurostat_total}")

    print("Audit passed")
    print(f"Rows: {len(rows)}")
    print(f"Eurostat net total: EUR {eurostat_total:,}")
    print(f"Cour known/estimated-yield total: EUR {cour_known_total:,}")
    print(f"Full CSV reconciled total: EUR {all_row_total:,}")
    print(f"Full CSV reconciled % GDP: {all_row_total / GDP_EUR * 100:.6f}%")
    print(f"Missing Cour 2024 yields without a supplemental or 2019-uprated estimate: {len(missing_revenue)}")


if __name__ == "__main__":
    main()
