#!/usr/bin/env python3
# Copyright (c) 2026 Tax Policy Associates Ltd
# SPDX-License-Identifier: MIT
"""Stitch together a long-run series of UK tax receipts as a share of GDP from two OBR workbooks."""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import load_workbook


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "code/data/uk_tax"
DEFAULT_OUTPUT = DATA_DIR / "uk_tax_receipts_gdp_share.tsv"
# Both workbooks are downloaded from the OBR website, obr.uk.
OBR_HISTORICAL_PUBLIC_FINANCES = DATA_DIR / "obr.uk - Historical-public-finances-database.xlsx"
OBR_DATABANK = DATA_DIR / "obr.uk - PSF_aggregates_databank_Oct_EFO.xlsx"
# The databank starts in 1948-49 and has the latest ONS revisions, so it takes
# over from then. Years after 2025-26 are forecasts, so we stop there.
DATABANK_FIRST_YEAR = 1948
LAST_OUTTURN_YEAR = "2025-26"


def databank_rows() -> list[dict[str, str]]:
    """National Accounts taxes as % of GDP from the databank, 1948-49 to 2025-26."""
    workbook = load_workbook(OBR_DATABANK, read_only=True, data_only=True)
    sheet_rows = list(workbook["Aggregates (per cent of GDP)"].iter_rows(values_only=True))
    # Column headings are on the fourth row.
    header = sheet_rows[3]
    column = [i for i, cell in enumerate(header) if isinstance(cell, str) and cell.strip() == "National account taxes"]
    assert len(column) == 1, column
    rows = []
    for row in sheet_rows[4:]:
        label = row[1]
        # Keep only rows labelled with a fiscal year, such as "1948-49".
        if not isinstance(label, str) or "-" not in label or not label[:4].isdigit():
            continue
        value = row[column[0]]
        if not value_is_number(value) or label > LAST_OUTTURN_YEAR:
            continue
        rows.append(
            {
                "year_label": label,
                "date": midpoint_date(label),
                "pct_gdp": f"{float(value):.6f}",
                "measure": "National Accounts taxes",
                "source": "OBR public finances databank, October 2026 EFO",
                "confidence": "high",
                "note": "National Accounts taxes as a percentage of GDP.",
            }
        )
    assert rows[0]["year_label"] == "1948-49" and rows[-1]["year_label"] == LAST_OUTTURN_YEAR
    return rows


def fiscal_year_start(label: str) -> int:
    return int(label.split("-")[0])


def midpoint_date(label: str) -> str:
    """Plot a fiscal year ("1948-49") at 1 July of the year it starts."""
    return f"{fiscal_year_start(label):04d}-07-01"


def value_is_number(value: object) -> bool:
    return isinstance(value, (int, float))


def build_rows(workbook_path: Path) -> list[dict[str, str]]:
    """The whole series: the historical database up to 1947-48, then the databank.

    Before 1948-49 each year takes the best measure the historical database has:
    National Accounts taxes (from 1946-47), then public sector current receipts
    (from 1900-01), then central government receipts. The two fallbacks are not
    the same measure as National Accounts taxes, so they are marked medium
    confidence.
    """
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    sheet = workbook["Receipts (per cent of GDP)"]

    rows: list[dict[str, str]] = []
    for row in sheet.iter_rows(min_row=7, max_col=26, values_only=True):
        year_label = row[0]
        if not isinstance(year_label, str) or "-" not in year_label:
            continue

        start_year = fiscal_year_start(year_label)
        if start_year >= DATABANK_FIRST_YEAR:
            continue
        measure = ""
        pct_gdp = None
        confidence = "high"
        note = ""

        # Columns Z, Y and V of the sheet.
        national_accounts_taxes = row[25]
        public_sector_current_receipts = row[24]
        central_government_receipts = row[21]

        if start_year >= 1946 and value_is_number(national_accounts_taxes):
            pct_gdp = national_accounts_taxes
            measure = "National Accounts taxes"
            note = "Direct OBR historical public finances National Accounts taxes line."
        elif start_year >= 1900 and value_is_number(public_sector_current_receipts):
            pct_gdp = public_sector_current_receipts
            measure = "Public sector current receipts"
            confidence = "medium"
            note = "Used before the OBR National Accounts taxes line begins; includes some non-tax current receipts."
        elif value_is_number(central_government_receipts):
            pct_gdp = central_government_receipts
            measure = "Central government receipts"
            confidence = "medium"
            note = "Used for 1700-1899 because the OBR workbook has no public-sector or National Accounts taxes total for these years."

        if pct_gdp is None:
            continue

        rows.append(
            {
                "year_label": year_label,
                "date": midpoint_date(year_label),
                "pct_gdp": f"{float(pct_gdp):.6f}",
                "measure": measure,
                "source": "OBR historical public finances database",
                "confidence": confidence,
                "note": note,
            }
        )

    rows.extend(databank_rows())
    return sorted(rows, key=lambda row: row["date"])


def write_rows(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["year_label", "date", "pct_gdp", "measure", "source", "confidence", "note"]
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = build_rows(OBR_HISTORICAL_PUBLIC_FINANCES)

    write_rows(rows, DEFAULT_OUTPUT)
    print(f"Wrote {DEFAULT_OUTPUT}")
    print(f"Rows: {len(rows)}")
    print(f"First point: {rows[0]['year_label']} = {rows[0]['pct_gdp']}%")
    print(f"Last point: {rows[-1]['year_label']} = {rows[-1]['pct_gdp']}%")


if __name__ == "__main__":
    main()
