#!/usr/bin/env python3
import csv
import re
from pathlib import Path

from openpyxl import load_workbook


GDP_EUR_M = 2_919_900
# INSEE annual-average CPI inflation: 2020 +0.5%, 2021 +1.6%,
# 2022 +5.2%, 2023 +4.9%, 2024 +2.0%.
CPI_UPRATING_2019_TO_2024 = 1.005 * 1.016 * 1.052 * 1.049 * 1.020

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data" / "france_tax"
EUROSTAT_NTL = DATA_DIR / "eurostat_national_tax_lists_2025_2026-04-22.xlsx"
COUR_LOW_YIELD = DATA_DIR / "20250417-annexe-listing-des-taxes-concernees.xlsx"
OUTPUT = DATA_DIR / "france_tax_revenue_candidate_table_2024.csv"

EUROSTAT_SOURCE = (
    "Eurostat, National Tax Lists - individual taxes, updated 22 Apr 2026; "
    "file: code/data/france_tax/eurostat_national_tax_lists_2025_2026-04-22.xlsx"
)
COUR_SOURCE = (
    "Cour des comptes, Les taxes a faible rendement, annex listing, Apr 2025; "
    "file: code/data/france_tax/20250417-annexe-listing-des-taxes-concernees.xlsx"
)
PLF2025_TAXES_AFFECTEES_SOURCE = (
    "Projet de loi de finances 2025, Voies et moyens tome 1, liste des taxes affectees; "
    "file: code/data/france_tax/plf2025_voies_moyens_taxes_affectees.xls"
)

SUPPLEMENTAL_2024_YIELDS_EUR = {
    "Droit de licence sur la rémunération des débitants de tabac": {
        "amount_eur": 360_118_595,
        "source": PLF2025_TAXES_AFFECTEES_SOURCE,
        "source_detail": "execution 2024, tax label: Droit de licence sur la rémunération des débitants de tabacs",
    },
}

SOCIAL_CONTRIBUTION_LEAF_CODES = {
    "D611C",
    "D612",
    "D613CE",
    "D613CS",
    "D613CN",
    "D613V",
}

UNCOLLECTIBLE_ADJUSTMENT_CODES = {
    "D995B",
    "D995C",
    "D995D",
    "D995E",
    "D995FE",
    "D995FS",
    "D995FN",
}

OBJECTIVE = {
    "Correction défaillance marché": "market-failure correction",
    "Correction defaillance marche": "market-failure correction",
    "Correction defaillance marché": "market-failure correction",
    "Incitation": "behavioural incentive",
    "Rendement": "budget-raising",
    "Service rendu": "service-related",
}

PAYER = {
    "Entreprises": "businesses",
    "Particuliers": "individuals",
    "Autres": "other payers",
}

BASE_EN = {
    "Production": "production",
    "Consommation": "consumption",
    "Capital": "capital",
    "Benefice": "profits",
    "Bénéfice": "profits",
    "Masse salariale": "payroll",
}

ECONOMIC_FUNCTION = {
    "C": "consumption",
    "AT": "alcohol/tobacco",
    "E": "energy",
    "P": "pollution",
    "T": "transport",
    "KS": "capital/stock of wealth",
    "KIH": "household capital income",
    "KIC": "corporate capital income",
    "KISE": "self-employed capital income",
    "LEYRS": "employer labour",
    "LEES": "employee labour",
    "LNON": "non-employed labour",
    "RP": "recurrent immovable property",
    "O": "other property",
    "_Z": "not classified",
}


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalise_key(value):
    value = clean_text(value).lower()
    value = value.replace("œ", "oe").replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def eur_and_pct(value_m):
    if value_m is None or value_m == "":
        return "", ""
    if isinstance(value_m, str):
        marker = value_m.strip().upper()
        if marker in {"", "L", "M"}:
            return "", ""
        value_m = float(value_m.replace(",", "."))
    value_eur = round(float(value_m) * 1_000_000)
    pct = float(value_m) / GDP_EUR_M * 100
    return str(value_eur), f"{pct:.6f}"


def estimated_2024_from_2019(value_2019_m):
    if not isinstance(value_2019_m, (int, float)):
        return None
    if value_2019_m <= 0:
        return None
    return float(value_2019_m) * CPI_UPRATING_2019_TO_2024


def supplemental_yield_for_tax(tax_name):
    return SUPPLEMENTAL_2024_YIELDS_EUR.get(tax_name)


def eurostat_explanation(row):
    econ = ECONOMIC_FUNCTION.get(clean_text(row["economic_function"]), clean_text(row["economic_function"]))
    property_tax = ECONOMIC_FUNCTION.get(
        clean_text(row["property_environment_code"]),
        clean_text(row["property_environment_code"]),
    )
    bits = [f"Eurostat national-tax-list line classified as ESA code {row['sto']}."]
    if econ and econ != "not classified":
        bits.append(f"Economic function: {econ}.")
    if property_tax and property_tax != "not classified":
        bits.append(f"Environmental/property tag: {property_tax}.")
    return " ".join(bits)


def read_eurostat_rows():
    wb = load_workbook(EUROSTAT_NTL, read_only=True, data_only=True)
    ws = wb["FR"]
    header = list(ws.iter_rows(min_row=8, max_row=8, values_only=True))[0]
    year_cols = {value: idx for idx, value in enumerate(header) if isinstance(value, int)}
    col_2024 = year_cols[2024]

    rows = []
    seen = set()
    current_parent_by_sto = {}
    for raw in ws.iter_rows(min_row=9, values_only=True):
        sto = clean_text(raw[0])
        detail = clean_text(raw[1])
        raw_tax_name = "" if raw[2] is None else str(raw[2])
        raw_tax_name_english = "" if raw[5] is None else str(raw[5])
        tax_name = clean_text(raw_tax_name)
        tax_name_english = clean_text(raw_tax_name_english)
        economic_function = clean_text(raw[9])
        property_environment_code = clean_text(raw[10])
        value_2024 = raw[col_2024]

        if not sto or not tax_name:
            continue
        if detail != "_T" and not raw_tax_name[:1].isspace() and not isinstance(value_2024, (int, float)):
            current_parent_by_sto[sto] = (tax_name, tax_name_english)
        if raw_tax_name[:1].isspace() and sto in current_parent_by_sto:
            parent_name, parent_name_english = current_parent_by_sto[sto]
            tax_name = f"{parent_name} - {tax_name}"
            tax_name_english = f"{parent_name_english} - {tax_name_english}"

        keep = False
        is_uncollectible_adjustment = False
        note_parts = []
        if detail != "_T":
            keep = True
        elif sto in SOCIAL_CONTRIBUTION_LEAF_CODES:
            keep = True
            note_parts.append("Social-contribution component retained because Eurostat does not provide a lower French national-tax-list split.")
        elif sto in UNCOLLECTIBLE_ADJUSTMENT_CODES:
            keep = True
            is_uncollectible_adjustment = True
            note_parts.append("Negative adjustment: Eurostat D995 taxes/social contributions assessed but unlikely to be collected, included to convert gross assessed tax/social contribution rows to an amount-collected basis.")

        if not keep:
            continue
        if not isinstance(value_2024, (int, float)):
            continue
        if value_2024 <= 0 and not is_uncollectible_adjustment:
            continue
        if is_uncollectible_adjustment:
            value_2024 = -abs(value_2024)
            tax_name = f"Less: {tax_name}"
            tax_name_english = f"Less: {tax_name_english}"

        key = (normalise_key(tax_name), normalise_key(tax_name_english), round(float(value_2024), 6))
        if key in seen:
            continue
        seen.add(key)

        source = f"{EUROSTAT_SOURCE}; FR sheet; STO {sto}; DETAILS {detail}; 2024"
        if tax_name.lower().startswith("autres taxes") or tax_name.lower() == "autres taxes":
            note_parts.append("Eurostat grouped 'other taxes' line; likely contains multiple legal taxes and may overlap with more specific Cour des comptes low-yield entries.")
        note_parts.append("Eurostat NTL covers general government plus EU institutions (S.13 + S.212), so local taxes are in scope.")

        revenue_eur, revenue_pct_gdp = eur_and_pct(value_2024)
        row = {
            "tax_name": tax_name,
            "tax_name_english": tax_name_english,
            "english_explanation": eurostat_explanation(
                {
                    "sto": sto,
                    "economic_function": economic_function,
                    "property_environment_code": property_environment_code,
                }
            ),
            "revenue_eur": revenue_eur,
            "revenue_pct_gdp": revenue_pct_gdp,
            "source_for_data": source,
            "notes": " ".join(note_parts),
        }
        rows.append(row)
    return rows


def low_yield_explanation(raw):
    objective = OBJECTIVE.get(clean_text(raw["Objectif"]), clean_text(raw["Objectif"]).lower())
    payer = PAYER.get(clean_text(raw["Redevable"]), clean_text(raw["Redevable"]).lower())
    base = BASE_EN.get(clean_text(raw["Assiette"]), clean_text(raw["Assiette"]).lower())
    collector = clean_text(raw["Collecteur"])
    beneficiary = clean_text(raw["Affectataire"])

    parts = [f"Low-yield {objective} levy"]
    if base:
        parts.append(f"on {base}")
    if payer:
        parts.append(f"paid by {payer}")
    sentence = " ".join(parts) + "."
    extra = []
    if collector:
        extra.append(f"Collector: {collector}.")
    if beneficiary:
        extra.append(f"Beneficiary: {beneficiary}.")
    return " ".join([sentence, *extra])


def english_name_for_low_yield(raw):
    # The Cour annex does not provide official English names. Use a clean
    # descriptive label from structured fields rather than a brittle legal-title translation.
    objective = OBJECTIVE.get(clean_text(raw["Objectif"]), clean_text(raw["Objectif"]).lower())
    payer = PAYER.get(clean_text(raw["Redevable"]), clean_text(raw["Redevable"]).lower())
    base = BASE_EN.get(clean_text(raw["Assiette"]), clean_text(raw["Assiette"]).lower())
    parts = ["Low-yield", objective, "levy"]
    if base:
        parts.append(f"on {base}")
    if payer:
        parts.append(f"paid by {payer}")
    return " ".join(parts)


def read_low_yield_rows():
    wb = load_workbook(COUR_LOW_YIELD, read_only=True, data_only=True)
    ws = wb["Inventaire"]
    headers = [clean_text(cell.value) for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    rows = []
    for raw in ws.iter_rows(min_row=2, values_only=True):
        if not any(raw):
            continue
        rec = {headers[idx]: raw[idx] for idx in range(min(len(headers), len(raw)))}
        tax_name = clean_text(rec.get("Libellé"))
        status = clean_text(rec.get("Etat"))
        if not tax_name:
            continue
        if status not in {"En vigueur entre 2019 et 2024", "Créée entre 2019 et 2024"}:
            continue

        value_2024 = rec.get("Enjeu 2024")
        value_2019 = rec.get("Enjeu 2019")
        estimated_2024_m = None
        supplemental = None
        if not isinstance(value_2024, (int, float)):
            supplemental = supplemental_yield_for_tax(tax_name)
            if supplemental is None:
                estimated_2024_m = estimated_2024_from_2019(value_2019)

        if supplemental is not None:
            revenue_eur = str(supplemental["amount_eur"])
            revenue_pct_gdp = f"{supplemental['amount_eur'] / (GDP_EUR_M * 1_000_000) * 100:.6f}"
        else:
            revenue_value_m = value_2024 if isinstance(value_2024, (int, float)) else estimated_2024_m
            revenue_eur, revenue_pct_gdp = eur_and_pct(revenue_value_m)
        notes = [
            f"Cour low-yield-tax inventory id {clean_text(rec.get('Identifiant'))}.",
            f"Status: {status}.",
            f"Objective: {clean_text(rec.get('Objectif'))}; payer: {clean_text(rec.get('Redevable'))}; base: {clean_text(rec.get('Assiette'))}.",
            "The Cour annex is an individual-tax inventory and may overlap with Eurostat grouped/aggregate NTL rows; do not sum both sources without reconciliation.",
            "English name is a descriptive label generated from the Cour structured fields; the Cour annex does not provide an official English legal title.",
        ]
        if isinstance(value_2019, (int, float)):
            notes.append(f"Cour Enjeu 2019: EUR {value_2019:g}m.")
        if supplemental is not None:
            notes.append(
                f"No Cour Enjeu 2024 figure; revenue uses an exact 2024 execution amount from {supplemental['source_detail']}."
            )
        elif estimated_2024_m is not None:
            notes.append(
                "No Cour Enjeu 2024 figure; revenue is an estimate from Cour Enjeu 2019 uprated to 2024 using INSEE annual-average CPI inflation for 2020-2024."
            )
            notes.append(f"CPI uprating factor used: {CPI_UPRATING_2019_TO_2024:.9f}.")
        elif not revenue_eur:
            notes.append("No known or estimated 2024 yield in the Cour annex; cannot be area-sized without an estimate.")
        else:
            notes.append("Revenue is the Cour 'enjeu 2024' figure, in EUR after conversion from EUR millions.")

        source_measure = "Enjeu 2024"
        source_prefix = COUR_SOURCE
        if supplemental is not None:
            source_prefix = supplemental["source"]
            source_measure = supplemental["source_detail"]
        elif estimated_2024_m is not None:
            source_measure = "Enjeu 2019 uprated to 2024 using INSEE CPI"
        source = f"{source_prefix}; Cour Inventaire sheet id {clean_text(rec.get('Identifiant'))}; {source_measure}"
        rows.append(
            {
                "tax_name": tax_name,
                "tax_name_english": english_name_for_low_yield(rec),
                "english_explanation": low_yield_explanation(rec),
                "revenue_eur": revenue_eur,
                "revenue_pct_gdp": revenue_pct_gdp,
                "source_for_data": source,
                "notes": " ".join(notes),
            }
        )
    return rows


def overlap_adjustment_row(low_yield_rows):
    known_total_eur = sum(int(row["revenue_eur"]) for row in low_yield_rows if row["revenue_eur"])
    known_total_m = known_total_eur / 1_000_000
    revenue_eur, revenue_pct_gdp = eur_and_pct(-known_total_m)
    return {
        "tax_name": "Less: Cour low-yield taxes already included in Eurostat aggregates",
        "tax_name_english": "Less: Cour low-yield taxes already included in Eurostat aggregates",
        "english_explanation": "Negative overlap adjustment so the full CSV can be summed without double-counting Cour individual low-yield taxes that are already included within Eurostat national-accounts tax rows.",
        "revenue_eur": revenue_eur,
        "revenue_pct_gdp": revenue_pct_gdp,
        "source_for_data": f"{COUR_SOURCE}; generated reconciliation adjustment",
        "notes": "This is not a separate tax. It offsets Cour rows with known 2024 yields because those rows are presented individually for visibility but are already included within the Eurostat source-family control total.",
    }


def main():
    eurostat_rows = read_eurostat_rows()
    low_yield_rows = read_low_yield_rows()
    rows = eurostat_rows + low_yield_rows + [overlap_adjustment_row(low_yield_rows)]
    rows.sort(key=lambda row: (row["tax_name"].lower(), row["source_for_data"]))

    fieldnames = [
        "tax_name",
        "tax_name_english",
        "english_explanation",
        "revenue_eur",
        "revenue_pct_gdp",
        "source_for_data",
        "notes",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    numeric_rows = [row for row in rows if row["revenue_eur"]]
    print(f"Wrote {OUTPUT}")
    print(f"Rows: {len(rows)}")
    print(f"Rows with 2024 revenue: {len(numeric_rows)}")
    print(f"Rows with missing revenue: {len(rows) - len(numeric_rows)}")


if __name__ == "__main__":
    main()
