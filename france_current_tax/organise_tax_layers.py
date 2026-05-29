#!/usr/bin/env python3
import csv
import re
import unicodedata
from pathlib import Path
from collections import defaultdict


BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data" / "france_tax"
INPUT = DATA_DIR / "france_tax_revenue_candidate_table_2024.csv"
OUTPUT = DATA_DIR / "france_tax_revenue_layered_2024.csv"
GDP_EUR = 2_919_900_000_000

LAYER_FIELDS = [
    "chart_label_en",
    "layer_1",
    "layer_2",
    "layer_3",
    "layer_4",
    "classification_notes",
    "display_explanation",
    "chart_include",
    "chart_revenue_eur",
    "chart_revenue_pct_gdp",
    "netted_adjustments_eur",
    "netting_notes",
]

EXACT_LABELS = {
    "Accise sur l'électricité": "Electricity duty",
    "Amendes et confiscations": "Fines",
    "Autres prélèvements sociaux": "Other social levies",
    "Autres taxes": "Other taxes",
    "Autres taxes sur l'énergie": "Other energy taxes",
    "Autres taxes sur la pollution": "Other pollution taxes",
    "Autres taxes sur le revenu": "Other income taxes",
    "Chambre d'agriculture": "Agriculture chamber tax",
    "Contribution au remboursement de la dette sociale": "CRDS",
    "Contribution de solidarité pour l'autonomie": "Autonomy contribution",
    "Contribution de sécurité immobilière": "Land registry tax",
    "Contribution des distributeurs d'énergie électrique basse tension": "Low-voltage suppliers levy",
    "Contribution patronale au dialogue social (0,016%)": "Social dialogue levy",
    "Contribution patronale sur stock-options": "Stock option levy",
    "Contribution sociale de solidarité des sociétés": "Corporate solidarity levy",
    "Contribution sociale généralisée": "CSG",
    "Contribution sociale sur les bénéfices des sociétés": "Corporate profits surtax",
    "Contribution sur les rentes infra marginales (électricité)": "Electricity rent levy",
    "Contribution vie étudiante et campus": "Student campus levy",
    "Contributions des entreprises à la formation professionnelle et à l'apprentissage": "Training levy",
    "Contributions sur les loyers immobiliers": "Rent contribution",
    "Cotisation BTP intempéries": "Bad-weather levy",
    "Cotisation des entreprises cinématographiques au profit du CNC (Centre national du cinéma)": "Cinema levy",
    "Cotisation foncière des entreprises": "Business property tax",
    "Cotisation patronale pour le FNAL (Fonds national d'aide au logement)": "Housing payroll levy",
    "Cotisation sur la valeur ajoutée des entreprises - Part sur le capital": "CVAE capital part",
    "Cotisation sur la valeur ajoutée des entreprises - Part sur les salaires": "CVAE wage part",
    "Cotisation versée par les organismes HLM": "Social housing levy",
    "Cotisations sociales effectives obligatoires à la charge des employeurs": "Employer social contribs",
    "Cotisations sociales effectives obligatoires à la charge des personnes n'occupant pas d'emploi": "Non-employed contribs",
    "Cotisations sociales effectives obligatoires à la charge des salariés": "Employee social contribs",
    "Cotisations sociales effectives obligatoires à la charge des travailleurs indépendants": "Self-employed contribs",
    "Cotisations sociales effectives volontaires des ménages": "Voluntary social contribs",
    "Cotisations sociales imputées à la charge des employeurs": "Imputed employer contribs",
    "Cotisations sur primes d'assurance": "Insurance premium tax",
    "Droit annuel de francisation et de navigation": "Navigation duty",
    "Droit annuel de francisation et de navigation en Corse ; Droit de passeport en Corse": "Corsica navigation duty",
    "Droit et contribution pour frais de contrôle": "AMF control fees",
    "Droits assimilés au droit d'octroi de mer sur les rhums et spiritueux à base d'alcool de cru": "Rum duty",
    "Droits d'enregistrement (y compris taxe additionnelle)": "Registration duties",
    "Droits d'importation": "Import duties",
    "Droits de plaidoirie": "Advocacy rights",
    "Foncier bâti": "Built property tax",
    "Foncier non-bâti (partie)": "Land tax",
    "Forfait social": "Forfait social",
    "Imposition sur les pylônes": "Pylon tax",
    "Impositions forfaitaires sur les entreprises de réseaux": "Network business tax",
    "Impôt de solidarité sur la fortune (jusque 2017) / Impôt sur la fortune immobilière (à partir de 2018)": "Real estate wealth tax",
    "Impôt sur le revenu": "Income tax",
    "Impôts sur les sociétés y compris majoration et frais de poursuite": "Corporation tax",
    "Mutations à titre gratuit": "Inheritance tax",
    "Mutations à titre onéreux d'immeubles et droits immobiliers": "Property transfer duty",
    "Octroi de mer": "Dock dues",
    "Participation des employeurs à l'effort de construction": "Construction payroll levy",
    "Prélèvement sur les jeux de cercle en ligne": "Online poker levy",
    "Prélèvements sur les revenus des capitaux mobiliers": "Investment income levy",
    "Produit de l'imposition chambre de commerce": "Commerce chamber tax",
    "Produits de la loterie nationale et du loto": "Lottery duties",
    "Recettes diverses et pénalités": "Misc penalties",
    "Redevance cynégétique (permis de chasse)": "Hunting licence",
    "Redevances sur les prélèvements de l'eau": "Water abstraction fees",
    "Redevances UMTS 2G et 3G": "Mobile spectrum fees",
    "Retenue sur les bénéfices non commerciaux": "Non-business profits tax",
    "TA-TINB - Taxe additionnelle à la taxe sur les installations nucléaires de base dite \"de stockage\"": "Nuclear storage tax",
    "TA-TINB - Taxe additionnelle à la taxe sur les installations nucléaires de base dite \"Recherche\"": "Nuclear research tax",
    "Taxe GEMAPI": "Flood prevention tax",
    "Taxe additionnelle sur le foncier non-bâti": "Unbuilt land surtax",
    "Taxe chambre métier": "Trades chamber tax",
    "Taxe d'habitation - Part sur la consommation": "Residence tax: consumption",
    "Taxe d'habitation - Part sur le capital": "Residence tax: capital",
    "Taxe de risque systémique": "Systemic risk tax",
    "Taxe de solidarité additionnelle": "Health insurance levy",
    "Taxe due par les entreprises de transport public aérien et maritime (Corse, DOM)": "Corsica/overseas transport",
    "Taxe due par les opérateurs de communications électroniques": "Telecoms operator tax",
    "Taxe exceptionnelle de solidarité sur les hautes rémunérations": "High pay levy",
    "Taxe intérieure de consommation des produits énergétiques": "Energy products duty",
    "Taxe intérieure sur la consommation de gaz naturel": "Natural gas duty",
    "Taxe spéciale sur les conventions d'assurance": "Insurance contracts tax",
    "Taxe spéciale sur les véhicules routiers (taxe à l'essieu)": "Axle tax",
    "Taxe spéciale d'équipement au profit de l'établissement public Société du Grand Paris": "Grand Paris levy",
    "Taxe sur construction de bureaux et sur les locaux à usage de bureaux": "Office premises tax",
    "Taxe sur infrastructures de transport longues distances": "Long-distance transport",
    "Taxe sur les certificats d'immatriculation des véhicules": "Vehicle registration tax",
    "Taxe sur les émissions de CO2": "CO2 emissions tax",
    "Taxe sur les boissons édulcorées": "Sweet drinks tax",
    "Taxe sur les mises à disposition de produits pétroliers pour le stockage stratégique": "Oil storage levy",
    "Taxe sur les primes d'assurances": "Insurance premiums tax",
    "Taxe sur les services numériques": "Digital services tax",
    "Taxe sur les surfaces commerciales": "Retail area tax",
    "Taxe sur les transactions financières": "Financial transaction tax",
    "Taxe sur les véhicules de tourisme des sociétés": "Company car tax",
    "Taxe sur primes d'assurance automobile": "Car insurance tax",
    "Taxes au profit de l'Association sur la garantie des salaires": "Wage guarantee levy",
    "Taxes pharmaceutiques (contribution grossistes répartiteurs, taxe sur les ventes de médicaments et de cosmétiques)": "Pharmaceutical taxes",
    "Taxes sur la construction": "Construction taxes",
    "Taxes sur les boissons": "Drinks taxes",
    "Taxes sur les jeux des casinos": "Casino gaming taxes",
    "Taxes sur les paris hippiques": "Horse-race betting tax",
    "Taxes sur les salaires": "Payroll tax",
    "Taxes sur les services professionnels hors droits de mutations": "Professional services tax",
    "Taxes sur les spectacles": "Entertainment taxes",
    "Taxes sur les tabacs": "Tobacco duties",
    "Taxes sur les transports": "Transport taxes",
    "TVA": "VAT",
    "Versement mobilité": "Mobility payroll levy",
}

DISPLAY_EXPLANATIONS = {
    "VAT": "France's value added tax on goods and services.",
    "Employer social contribs": "Compulsory employer social security contributions on employees' pay.",
    "Employee social contribs": "Compulsory employee social security contributions deducted from wages.",
    "Self-employed contribs": "Compulsory social security contributions paid by self-employed workers.",
    "Non-employed contribs": "Compulsory social security contributions paid by people who are not in employment.",
    "Voluntary social contribs": "Voluntary social security contributions paid by households.",
    "Imputed employer contribs": "Social benefits paid directly by employers and recorded as employer social contributions in the national accounts.",
    "Income tax": "France's personal income tax.",
    "CSG": "A broad social charge on employment, pensions and investment income.",
    "CRDS": "A social charge used to help repay social-security debt.",
    "Other social levies": "Other social charges on household income.",
    "Corporation tax": "France's corporation tax on company profits.",
    "Corporate profits surtax": "A surtax on company profits.",
    "Corporate solidarity levy": "A business levy based mainly on company turnover.",
    "Digital services tax": "A tax on revenues from large digital-services businesses.",
    "Long-distance transport": "A sector levy on long-distance transport infrastructure.",
    "Non-business profits tax": "Withholding tax on some non-commercial profits.",
    "Business property tax": "The business property element of France's local business-tax system.",
    "CVAE capital part": "The capital-share element of the former value-added business tax.",
    "CVAE wage part": "The wage-share element of the former value-added business tax.",
    "Network business tax": "Flat-rate taxes on network businesses such as energy, telecoms and transport infrastructure.",
    "Retail area tax": "A tax on large retail premises.",
    "Pharmaceutical taxes": "Sector levies on pharmaceutical and health-product businesses.",
    "Commerce chamber tax": "A business levy used to fund chambers of commerce.",
    "Trades chamber tax": "A business levy used to fund chambers of trades and crafts.",
    "Agriculture chamber tax": "A levy used to fund chambers of agriculture.",
    "Built property tax": "Local tax on developed land and buildings.",
    "Land tax": "Local tax on undeveloped land.",
    "Unbuilt land surtax": "Additional tax on undeveloped land.",
    "Residence tax: capital": "The capital element of France's residence tax.",
    "Residence tax: consumption": "The consumption element of France's residence tax.",
    "Office premises tax": "Tax on offices and similar premises.",
    "Construction taxes": "Taxes on construction and development.",
    "Land registry tax": "Charge recorded as a tax on land-registration formalities.",
    "Rent contribution": "Tax on some real-estate rents.",
    "Property transfer duty": "Transfer duty on sales of land and buildings.",
    "Registration duties": "Registration duties on legal acts and transactions.",
    "Professional services tax": "Tax on some professional services connected with property transactions.",
    "Inheritance tax": "Tax on inheritances and lifetime gifts.",
    "Real estate wealth tax": "Annual wealth tax on high-value real estate.",
    "Financial transaction tax": "Tax on transactions in certain financial securities.",
    "Investment income levy": "Tax or social charge on investment income.",
    "Energy products duty": "Excise duty on petrol, diesel and other energy products.",
    "Electricity duty": "Excise duty on electricity consumption.",
    "Natural gas duty": "Excise duty on natural gas consumption.",
    "Oil storage levy": "Levy on oil products used to fund strategic oil stocks.",
    "Parking spaces tax": "Tax on parking spaces.",
    "Other energy taxes": "Other taxes on energy or fuel use.",
    "Tobacco duties": "Excise duties on tobacco products.",
    "Drinks taxes": "Duties on alcoholic, sugary or other drinks.",
    "Sweet drinks tax": "Tax on sweetened drinks.",
    "Intermediate alcohol duty": "Duty on intermediate alcoholic products.",
    "Wine duty": "Duty on wine, cider, perry and similar drinks.",
    "Rum duty": "Duty on rum and similar spirits.",
    "Insurance contracts tax": "Tax on insurance contracts.",
    "Insurance premium tax": "Tax on insurance premiums.",
    "Insurance premiums tax": "Tax on insurance premiums.",
    "Car insurance tax": "Tax on motor insurance premiums.",
    "Health insurance levy": "Levy on complementary health insurance contracts.",
    "Lottery duties": "Taxes on lottery products.",
    "Casino gaming taxes": "Taxes on casino gaming.",
    "Horse-race betting tax": "Tax on horse-race betting.",
    "Online poker levy": "Tax on online poker games.",
    "Import duties": "Customs duties on imports.",
    "Dock dues": "Local import and consumption tax in French overseas territories.",
    "Vehicle registration tax": "Tax paid when vehicles are registered.",
    "Company car tax": "Tax on company cars.",
    "Axle tax": "Tax on heavy goods vehicles by axle or weight.",
    "Navigation duty": "Duty on the registration or use of certain boats.",
    "Transport taxes": "Taxes on transport services or transport use.",
    "Mobility payroll levy": "Local payroll levy used to fund public transport.",
    "Training levy": "Employer levy used to fund vocational training and apprenticeships.",
    "Payroll tax": "Tax on payrolls, mainly paid by employers outside the VAT system.",
    "Forfait social": "Employer charge on some employee benefits and remuneration not subject to normal social contributions.",
    "Housing payroll levy": "Employer payroll levy used to fund housing support.",
    "Construction payroll levy": "Employer levy for housing construction and support.",
    "Autonomy contribution": "Employer payroll levy used to fund support for older and disabled people.",
    "Wage guarantee levy": "Employer levy funding the wage-guarantee scheme for insolvent employers.",
    "Stock option levy": "Employer levy on stock options.",
    "Social dialogue levy": "Employer levy used to fund social dialogue arrangements.",
    "Bad-weather levy": "Construction-sector levy funding bad-weather compensation.",
    "CO2 emissions tax": "Tax on carbon dioxide emissions from vehicles.",
    "Flood prevention tax": "Local tax used to fund flood prevention and aquatic-environment management.",
    "Water abstraction fees": "Charges on water abstraction treated as taxes in the national accounts.",
    "Other pollution taxes": "Other taxes on pollution or environmentally harmful activities.",
    "Pylon tax": "Tax on electricity pylons.",
    "Nuclear storage tax": "Additional tax on nuclear installations for radioactive-waste storage.",
    "Nuclear research tax": "Additional tax on nuclear installations for research funding.",
    "Nuclear safety levy": "Levy used to fund radioprotection and nuclear-safety work.",
    "Nuclear support tax": "Additional tax on nuclear installations used for local support around nuclear sites.",
    "Employee option levy": "Employee charge on stock options.",
    "Island bridge toll": "Departmental charge on bridges linking the mainland to maritime islands.",
    "Wind farm tax": "Tax on wind farms or marine turbines.",
    "CDC interest levy": "Levy on interest paid by Caisse des dépôts et consignations on deposited funds.",
    "Hydrocarbon tax": "Levy on the production of liquid or gaseous hydrocarbons.",
    "Water levy overseas": "Water-agency levy in France's overseas departments.",
    "Water levy": "Water, sewerage or sanitation-related levy.",
    "Mineral water surtax": "Surtax on mineral waters.",
    "Plastics industry levy": "Levy used to fund a technical centre for the plastics and composites industry.",
    "Tourist tax surtax": "Additional departmental tax on tourist accommodation.",
    "Tourism tax": "Additional Paris-region tax on tourist accommodation.",
    "Pleasure craft tax": "Annual tax on certain pleasure craft.",
    "Vacant homes tax": "Annual tax on vacant dwellings.",
    "Street sweeping tax": "Local tax used to fund street sweeping.",
    "Registration surtax": "Departmental surtax on some registration duties.",
    "Insurer reserve exit tax": "One-off tax on insurers' capitalisation reserves.",
    "Guyane land agency": "Special equipment tax used to fund the Guyane public land agency.",
    "Lorraine land agency": "Special equipment tax used to fund the Lorraine public land agency.",
    "Normandie land agency": "Special equipment tax used to fund the Normandie public land agency.",
    "PACA land agency": "Special equipment tax used to fund the PACA public land agency.",
    "Development land tax": "Tax on sales of undeveloped land made buildable by planning decisions.",
    "Property gains tax": "Tax on some real-estate capital gains.",
    "Residence permit tax": "Tax on electronic residence and travel permits.",
    "Guadeloupe coastal levy": "Special equipment tax for Guadeloupe's coastal-zone public body.",
    "Martinique coastal levy": "Special equipment tax for Martinique's coastal-zone public body.",
    "Furniture industry levy": "Industry levy on furniture and wood-sector goods.",
    "Building materials levy": "Industry levy on concrete, terracotta and construction-material goods.",
    "Mechanical industry levy": "Industry levy on mechanical and metal-construction goods.",
    "Health certificates": "Charge for sanitary and phytosanitary certificates, treated as tax revenue.",
    "Other import taxes": "Other import-related taxes not separately identified.",
    "Other product taxes": "Other taxes on products or consumption not separately identified.",
    "Other property taxes": "Other property-related taxes not separately identified.",
    "Other business taxes": "Other business taxes not separately identified.",
    "Other payroll taxes": "Other payroll-related taxes not separately identified.",
    "Other corporate taxes": "Other company taxes not separately identified.",
    "Other wealth taxes": "Other wealth-related taxes not separately identified.",
    "Other capital taxes": "Other capital taxes not separately identified.",
    "Fines": "Fines and confiscations counted as tax-like revenue in the national accounts.",
    "Misc penalties": "Miscellaneous penalties counted as tax-like revenue.",
    "Hunting licence": "Hunting licence charge counted as tax-like revenue.",
    "Hunting fees": "Hunting-related fees treated as tax revenue.",
    "AMF control fees": "Financial-market supervision fees counted as tax-like revenue.",
    "Mobile spectrum fees": "Mobile spectrum charges counted as tax-like revenue.",
    "Document stamp duty": "Small stamp duty on official documents.",
    "Judicial acts duty": "Small duty on judicial and extra-judicial documents.",
    "Advocacy rights": "Small court-related charge on legal pleadings.",
    "Advocacy equivalent": "Equivalent court-related charge where ordinary advocacy rights do not apply.",
    "ID card stamp duty": "Stamp duty on national identity cards.",
    "Gold/silver assay duty": "Assay duty on gold and silver articles.",
    "Service charge": "Service-related charge treated as tax revenue.",
    "Service charge interlocal": "Charge for access to Nordic skiing facilities and related local services.",
    "Student campus levy": "Charge paid by students to fund campus services.",
    "Cinema levy": "Levy on cinema businesses used to fund film and audiovisual support.",
    "Telecoms operator tax": "Tax on electronic communications operators.",
    "Low-voltage suppliers levy": "Levy on low-voltage electricity distribution.",
    "Grand Paris levy": "Special equipment tax used to fund Grand Paris infrastructure.",
    "Systemic risk tax": "Levy on financial institutions linked to systemic-risk regulation.",
}

LAYER_EXPLANATIONS = {
    "Social contributions": "Compulsory or voluntary social security contributions.",
    "Personal income and social taxes": "Taxes and social charges on personal income.",
    "Employer payroll and labour levies": "Employer levy connected with payroll, employees or workforce costs.",
    "Profit and sector taxes": "Tax on business profits or on a specific business sector.",
    "Business production and sector levies": "Business levy based on production, premises, turnover or sector activity.",
    "Other production taxes": "Other tax on business production or activity.",
    "Recurrent land and property taxes": "Recurring tax on land, buildings or business premises.",
    "Property transaction and registration taxes": "Tax or duty on registering transactions or transferring property.",
    "Inheritance and gifts": "Tax on inheritances or lifetime gifts.",
    "Wealth taxes": "Annual wealth or real-estate wealth tax.",
    "Financial capital taxes": "Tax on financial assets, investment income or securities transactions.",
    "Energy and fuel duties": "Tax on energy, fuel or electricity use.",
    "Alcohol, tobacco and drinks duties": "Duty on alcohol, tobacco, soft drinks or similar products.",
    "Insurance taxes": "Tax or levy on insurance contracts or premiums.",
    "Betting, gaming and lottery": "Tax on betting, gaming, casinos or lotteries.",
    "Import and border taxes": "Customs, import or border-related tax.",
    "Transport and vehicle taxes": "Tax on vehicles, transport services or transport use.",
    "Specific services and media taxes": "Tax on a specific service, media or entertainment activity.",
    "Other consumption taxes": "Other tax on goods, services or consumption.",
    "Carbon and emissions taxes": "Tax linked to carbon dioxide or greenhouse-gas emissions.",
    "Water and flood levies": "Tax or charge linked to water use, flood prevention or aquatic environments.",
    "Pollution taxes": "Tax on pollution or environmentally harmful activities.",
    "Energy-network environmental levies": "Tax on energy infrastructure treated as environmental revenue.",
    "Fines, penalties and miscellaneous tax-like charges": "Fine, penalty, licence charge or other tax-like receipt.",
    "Service-related tax-like charges": "Administrative or service-related charge treated as tax revenue.",
    "Residual other taxes": "Residual tax category not separately identified in the source table.",
}


def ntext(value):
    value = (value or "").lower()
    value = value.replace("œ", "oe").replace("’", "'")
    value = "".join(
        char for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def source_sto(row):
    source = row["source_for_data"]
    if "STO " not in source:
        return ""
    return source.split("STO ", 1)[1].split(";", 1)[0]


def is_cour(row):
    return row["source_for_data"].startswith("Cour") or row["source_for_data"].startswith("Projet de loi")


def is_eurostat(row):
    return row["source_for_data"].startswith("Eurostat")


def note_contains(row, value):
    return value.lower() in ntext(row.get("notes", ""))


def has_any(text, needles):
    return any(needle in text for needle in needles)


def shorten_label(label, max_len=32):
    label = re.sub(r"\s+", " ", label).strip(" -;,.")
    replacements = [
        ("Contribution", "Levy"),
        ("contribution", "levy"),
        ("Professional", "Prof."),
        ("professional", "prof."),
        ("Apprenticeship", "Apprentice"),
        ("apprenticeship", "apprentice"),
        ("Registration", "Reg."),
        ("registration", "reg."),
        ("Electricity", "Power"),
        ("electricity", "power"),
        ("Pharmaceutical", "Pharma"),
        ("pharmaceutical", "pharma"),
        ("development", "dev."),
        ("Development", "Dev."),
        ("departmental", "dept."),
        ("Departmental", "Dept."),
        ("territorial", "local"),
        ("Territorial", "Local"),
    ]
    for old, new in replacements:
        if len(label) <= max_len:
            break
        label = label.replace(old, new)
    if len(label) <= max_len:
        return label
    return label[:max_len - 1].rstrip(" -;,./") + "…"


def display_key(label):
    return re.sub(r"\s+\d+$", "", label or "").strip()


def display_explanation(row):
    label = display_key(row["chart_label_en"])
    if label in DISPLAY_EXPLANATIONS:
        return DISPLAY_EXPLANATIONS[label]

    name = ntext(row["tax_name"])
    english = ntext(row["tax_name_english"])
    text = f"{name} {english}"

    if row["tax_name"].startswith("Less:"):
        return "Technical adjustment used to avoid double-counting in the chart."

    if has_any(text, ["tva", "vat"]):
        return DISPLAY_EXPLANATIONS["VAT"]
    if has_any(text, ["cotisations sociales imputees"]):
        return DISPLAY_EXPLANATIONS["Imputed employer contribs"]
    if has_any(text, ["cotisations sociales effectives obligatoires a la charge des employeurs"]):
        return DISPLAY_EXPLANATIONS["Employer social contribs"]
    if has_any(text, ["cotisations sociales effectives obligatoires a la charge des salaries"]):
        return DISPLAY_EXPLANATIONS["Employee social contribs"]
    if has_any(text, ["travailleurs independants"]):
        return DISPLAY_EXPLANATIONS["Self-employed contribs"]
    if has_any(text, ["contribution sociale generalisee"]):
        return DISPLAY_EXPLANATIONS["CSG"]
    if has_any(text, ["remboursement de la dette sociale"]):
        return DISPLAY_EXPLANATIONS["CRDS"]
    if has_any(text, ["impot sur le revenu"]):
        return DISPLAY_EXPLANATIONS["Income tax"]
    if has_any(text, ["impots sur les societes"]):
        return DISPLAY_EXPLANATIONS["Corporation tax"]
    if has_any(text, ["foncier bati"]):
        return DISPLAY_EXPLANATIONS["Built property tax"]
    if has_any(text, ["foncier non-bati"]):
        return DISPLAY_EXPLANATIONS["Land tax"]
    if has_any(text, ["mutations a titre gratuit", "inheritance"]):
        return DISPLAY_EXPLANATIONS["Inheritance tax"]
    if has_any(text, ["taxe interieure de consommation des produits energetiques"]):
        return DISPLAY_EXPLANATIONS["Energy products duty"]
    if has_any(text, ["accise sur l'electricite", "excise duty on electricity"]):
        return DISPLAY_EXPLANATIONS["Electricity duty"]
    if has_any(text, ["tabac", "tobacco"]):
        return "Duty or levy on tobacco products."
    if has_any(text, ["alcool", "vins", "boissons", "sucres", "premix"]):
        return "Duty or levy on alcohol, soft drinks or similar products."
    if has_any(text, ["jeux", "paris", "casinos", "loterie"]):
        return "Tax on betting, gaming, casinos or lotteries."
    if has_any(text, ["assurance", "insurance"]):
        return "Tax or levy on insurance contracts or premiums."
    if has_any(text, ["vehicule", "transport", "navigation", "immatriculation"]):
        return "Tax on vehicles, transport services or transport use."
    if has_any(text, ["water", "gemapi", "flood", "aquatic", "prelevements de l'eau", "pollution de l'eau"]):
        return "Tax or charge linked to water use, flood prevention or aquatic environments."
    if has_any(text, ["pollution"]):
        return "Tax on pollution or environmentally harmful activities."

    if label.startswith("Other "):
        layer_text = LAYER_EXPLANATIONS.get(row["layer_2"], "Residual tax category not separately identified in the source table.")
        return layer_text

    if row["layer_2"] in LAYER_EXPLANATIONS:
        return LAYER_EXPLANATIONS[row["layer_2"]]

    if row["layer_1"]:
        return f"Tax or compulsory charge grouped under {row['layer_1'].lower()}."
    return "Tax or compulsory charge included in the French national-accounts total."


def label_for_autres_taxes(row):
    sto = source_sto(row)
    labels = {
        "D2122C": "Other import taxes",
        "D214A": "Other product taxes",
        "D214E": "Other product taxes",
        "D214H": "Other product taxes",
        "D214L": "Other product taxes",
        "D29A": "Other property taxes",
        "D29B": "Other business taxes",
        "D29C": "Other payroll taxes",
        "D29E": "Other business taxes",
        "D29H": "Other business taxes",
        "D51M": "Other income/social taxes",
        "D51O": "Other corporate taxes",
        "D59A": "Other wealth taxes",
        "D59F": "Other wealth taxes",
        "D91B": "Other capital taxes",
    }
    return labels.get(sto, "Other taxes")


def label_from_french_name(row):
    name = row["tax_name"]
    text = ntext(name)
    layer_2 = row.get("layer_2", "")

    if name == "Autres taxes":
        return label_for_autres_taxes(row)

    if name in EXACT_LABELS:
        return EXACT_LABELS[name]

    if "fraction percue en corse" in text and "tabac" in text:
        return "Corsica tobacco duty"
    if "fraction percue en outre-mer" in text and "tabac" in text:
        return "Overseas tobacco duty"
    if "france continentale" in text and "tabac" in text:
        return "Mainland tobacco duty"
    if "produits intermediaires" in text and "alcool" in text:
        return "Intermediate alcohol duty"
    if "vins" in text and "alcool" in text:
        return "Wine duty"
    if "electricite" in text and "accise" in text:
        return "Electricity duty"
    if "charbons" in text:
        return "Coal duty"
    if "commissaires aux comptes" in text:
        return "Auditors levy"
    if "accidents agricoles" in text:
        return "Farm accident insurance"
    if "installations nucleaires de base" in text and "accompagnement" in text:
        return "Nuclear support tax"
    if "installations nucleaires de base" in text and "stockage" in text:
        return "Nuclear storage tax"
    if "installations nucleaires de base" in text and "recherche" in text:
        return "Nuclear research tax"
    if "radioprotection" in text or "surete nucleaire" in text:
        return "Nuclear safety levy"
    if "dommages consecutifs" in text:
        return "Medical injury fund levy"
    if "fonds d'assurance formation" in text:
        return "Training fund levy"
    if "reparation de l'automobile" in text:
        return "Vehicle repair levy"
    if "travail temporaire" in text:
        return "Temp-work training levy"
    if "dispositifs medicaux" in text:
        return "Medical devices ad levy"
    if "laboratoires" in text and "publicite" in text:
        return "Drug advertising levy"
    if "dialogue social" in text:
        return "Social dialogue levy"
    if "stock-options" in text:
        return "Stock option levy"
    if "options de souscription" in text:
        return "Employee option levy"
    if "formation professionnelle" in text and "batiment" in text:
        return "Construction training levy"
    if "saint pierre" in text:
        return "St Pierre training levy"
    if "intermittents" in text:
        return "Performers training levy"
    if "artistes auteurs" in text:
        return "Artists training levy"
    if "professions non salariees dans le domaine agricole" in text:
        return "Farm training levy"
    if "professions non salariees" in text and "hors artisanat" in text:
        return "Self-employed training levy"
    if "particuliers employeurs" in text:
        return "Household employer levy"
    if "peche maritime" in text:
        return "Fishery training levy"
    if "cotisations percues" in text and "effort de construction" in text:
        return "PEEC contributions"
    if "prelevement sur la participation" in text and "effort de construction" in text:
        return "PEEC levy"
    if "preretraite" in text:
        return "Early retirement levy"
    if "mise a la retraite" in text:
        return "Retirement indemnity levy"
    if "paris sportifs" in text:
        return "Sports betting levy"
    if "paris hippiques en ligne" in text:
        return "Online racing betting fee"
    if "jeux de cercle" in text:
        return "Online poker levy"
    if "boissons edulcorees" in text:
        return "Sweet drinks tax"
    if "fournisseurs agrees de produits de tabac" in text:
        return "Tobacco supplier levy"
    if "debitants de tabac" in text:
        return "Tobacco licence duty"
    if "rhums" in text or "spiritueux" in text:
        return "Rum duty"
    if "engins maritimes" in text:
        return "Pleasure craft tax"
    if "audiovisuelle" in text or "cinematographiques" in text:
        return "Film/media levy"
    if "publicite" in text:
        return "Advertising levy"
    if "streaming" in text or "musique en ligne" in text:
        return "Music streaming tax"
    if "spectacles vivants" in text:
        return "Live performance tax"
    if "spectacles cinematographiques" in text:
        return "Cinema ticket tax"
    if "theatre prive" in text:
        return "Private theatre tax"
    if "titres de sejour" in text:
        return "Residence permit tax"
    if "visa" in text or "naturalisation" in text:
        return "Immigration document tax"
    if "permis de conduire" in text:
        return "Driving licence tax"
    if "permis de chasse" in text or "chasser" in text:
        return "Hunting licence"
    if "cartes nationales d'identite" in text:
        return "ID card stamp duty"
    if "taxe additionnelle departementale a la taxe de sejour" in text:
        return "Tourist tax surtax"
    if "francisation" in text and "corse" in text:
        return "Corsica navigation duty"
    if "metro" in text or "transport" in text or "ratp" in text:
        return "Transport levy"
    if "billet d'avion" in text:
        return "Air passenger surcharge"
    if "vehicules" in text or "immatriculation" in text:
        return "Vehicle tax"
    if "autoroute" in text or "infrastructures de transport" in text:
        return "Transport infrastructure tax"
    if "or" in text and "mine" in text:
        return "Gold mining tax"
    if "matieres d'or et d'argent" in text:
        return "Gold/silver assay duty"
    if "redevances communale" in text and "mines" in text:
        return "Mining royalties"
    if "metaux precieux" in text:
        return "Precious metals tax"
    if "revenus des capitaux mobiliers" in text:
        return "Investment income levy"
    if "trust" in text:
        return "Trust levy"
    if "carried-interests" in text:
        return "Carried interest levy"
    if "successions" in text:
        return "Estates levy"
    if "droits d'enregistrement" in text and "departementale additionnelle" in text:
        return "Registration surtax"
    if "contrats d'assurance-vie en desherence" in text:
        return "Dormant insurance levy"
    if "reserve de capitalisation" in text:
        return "Insurer reserve exit tax"
    if "caisse des depots" in text:
        return "CDC interest levy"
    if "taxe de balayage" in text:
        return "Street sweeping tax"
    if "surfaces de stationnement" in text:
        return "Parking spaces tax"
    if "50 pas geometrique" in text and "guadeloupe" in text:
        return "Guadeloupe coastal levy"
    if "50 pas geometrique" in text and "martinique" in text:
        return "Martinique coastal levy"
    if "50 pas geometrique" in text:
        return "Coastal-zone levy"
    if "confisques" in text:
        return "Confiscated assets levy"
    if "logements vacants" in text:
        return "Vacant homes tax"
    if "foncier non-bati" in text:
        return "Unbuilt land surtax"
    if "societe du grand paris" in text:
        return "Grand Paris levy"
    if "bureaux" in text or "locaux" in text:
        return "Office premises tax"
    if "terrains nus" in text:
        return "Development land tax"
    if "archeologie preventive" in text:
        return "Archaeology levy"
    if "droit de bail" in text or "baux" in text:
        return "Lease duty"
    if "ouvrages d'art reliant" in text:
        return "Island bridge toll"
    if re.search(r"\b(epa|epf|epfa)\b", text):
        if "lorraine" in text:
            return "Lorraine land agency"
        if "guyane" in text:
            return "Guyane land agency"
        if "normandie" in text:
            return "Normandie land agency"
        if "paca" in text:
            return "PACA land agency"
        return "Land agency levy"
    if "plasturgie" in text or "composites" in text:
        return "Plastics industry levy"
    if "eaux minerales" in text:
        return "Mineral water surtax"
    if "l'eau" in text or "agences de l'eau" in text or "aquatique" in text or "assainissement" in text:
        return "Water levy"
    if "veterinaire" in text or "vegetaux" in text:
        return "Agri-food inspection fee"
    if "tgap" in text or "dechets" in text or "pollution" in text:
        return "Pollution tax"
    if "hydrocarbures" in text:
        return "Hydrocarbon tax"
    if "renouvelable" in text:
        return "Renewable fuel levy"
    if "eoliennes" in text:
        return "Wind farm tax"
    if "nuisances sonores" in text:
        return "Airport noise tax"
    if "phytopharmaceutiques" in text:
        return "Pesticides approval fee"
    if "organismes assureurs" in text:
        return "Insurer levy"
    if "primes ou cotisations d'assurance" in text:
        return "Farm insurance levy"
    if "premieres ventes de medicaments" in text:
        return "Medicines sales levy"
    if "institutions financieres" in text:
        return "Financial institutions levy"
    if "appellation d'origine" in text or "indication geographique" in text:
        return "Origin-label duty"
    if "defrichement" in text:
        return "Deforestation levy"
    if "entreprises d'assurance" in text:
        return "Insurance company levy"
    if "abattage" in text:
        return "Slaughter fee"
    if "biocides" in text:
        return "Biocides fee"
    if "inpi" in text:
        return "Patent office fees"
    if "energie hydraulique" in text:
        return "Hydropower royalties"
    if "institut des corps gras" in text:
        return "Oils/fats levy"
    if "biologie medicale" in text:
        return "Medical lab levy"
    if "stations et liaisons radioelectriques" in text:
        return "Private radio tax"
    if re.search(r"\bcci\b", text) or "commerce" in text:
        return "Commerce chamber tax"
    if "chambre de metiers" in text or "cma" in text:
        return "Trades chamber tax"
    if "agriculture" in text:
        return "Agriculture levy"
    if "avoue" in text:
        return "Avoues levy"
    if "avoues" in text:
        return "Avoues levy"
    if "plaidoirie" in text:
        if "equivalente" in text:
            return "Advocacy equivalent"
        return "Advocacy rights"
    if "h3c" in text:
        return "Audit regulator levy"
    if "umts" in text:
        return "Mobile spectrum fees"
    if "hlm" in text:
        return "Social housing levy"
    if "non paiement" in text and "formation professionnelle" in text:
        return "Training default levy"
    if "plus-values immobilieres" in text:
        return "Property gains tax"
    if "tourisme" in text or "sejour" in text:
        return "Tourism tax"
    if "redevances cynegetiques" in text:
        return "Hunting fees"
    if "papill" in text:
        return "Paper levy"
    if "remontees mecaniques" in text:
        return "Ski lift tax"
    if "fonderie" in text:
        return "Foundry products tax"
    if "cuir" in text:
        return "Leather industry levy"
    if "papier" in text:
        return "Paper industry levy"
    if "ameublement" in text:
        return "Furniture industry levy"
    if "beton" in text or "terre cuite" in text:
        return "Building materials levy"
    if "horlogerie" in text or "bijouterie" in text:
        return "Jewellery/watch levy"
    if "textile" in text or "habillement" in text:
        return "Clothing industry levy"
    if "construction metallique" in text or "mecanique" in text:
        return "Mechanical industry levy"
    if "certificats sanitaires" in text:
        return "Health certificates"
    if "actes judiciaires" in text:
        return "Judicial acts duty"
    if "timbre de dimension" in text:
        return "Document stamp duty"

    if row["tax_name_english"] and not row["tax_name_english"].startswith("Low-yield"):
        return shorten_label(row["tax_name_english"])

    if layer_2 == "Business production and sector levies":
        return "Sector levy"
    if layer_2 == "Employer payroll and labour levies":
        return "Payroll levy"
    if layer_2 == "Service-related tax-like charges":
        return "Service charge"
    if layer_2 == "Other capital taxes":
        return "Capital levy"
    if layer_2 == "Other consumption taxes":
        return "Consumption levy"
    return shorten_label(row["tax_name_english"] or row["tax_name"])


def dedupe_labels(rows):
    groups = {}
    for row in rows:
        if row.get("chart_include") != "yes":
            continue
        key = (row["layer_1"], row["layer_2"], row["chart_label_en"])
        groups.setdefault(key, []).append(row)

    for (layer_1, layer_2, label), grouped in groups.items():
        if len(grouped) <= 1:
            continue
        for idx, row in enumerate(sorted(grouped, key=lambda item: item["tax_name"]), start=1):
            text = ntext(row["tax_name"])
            suffix = ""
            if "corse" in text:
                suffix = " Corsica"
            elif "outre-mer" in text or "dom" in text:
                suffix = " overseas"
            elif "france continentale" in text:
                suffix = " mainland"
            elif "departements" in text:
                suffix = " dept."
            elif "communes" in text:
                suffix = " local"
            elif "ile-de-france" in text:
                suffix = " Paris region"
            elif "guadeloupe" in text:
                suffix = " Guadeloupe"
            elif "martinique" in text:
                suffix = " Martinique"
            elif "part intercommunale" in text:
                suffix = " interlocal"
            else:
                suffix = f" {idx}"
            row["chart_label_en"] = shorten_label(f"{label}{suffix}", max_len=32)


def classify_eurostat(row):
    name = ntext(row["tax_name"])
    english = ntext(row["tax_name_english"])
    explanation = ntext(row["english_explanation"])
    sto = source_sto(row)
    label_text = f"{name} {english}"
    text = f"{name} {english} {explanation}"

    if name.startswith("less:"):
        if "cotisations sociales" in name:
            return ("Employment", "Uncollectible adjustments", "Social contributions", "", "Eurostat D995 negative adjustment.")
        if "revenu" in name:
            return ("Employment", "Uncollectible adjustments", "Income taxes", "", "Eurostat D995 negative adjustment.")
        if "production" in name:
            return ("Business", "Uncollectible adjustments", "Production taxes", "", "Eurostat D995 negative adjustment.")
        if "impots courants" in name:
            return ("Other", "Uncollectible adjustments", "Other current taxes", "", "Eurostat D995 negative adjustment.")

    if sto.startswith("D61"):
        return ("Employment", "Social contributions", "Compulsory/voluntary social contributions", row["tax_name"], "UK-equivalent treatment: social contributions sit with NICs/employment taxes.")

    if "csg" in text or "crds" in text or name in {"impot sur le revenu", "autres taxes"} and sto.startswith("D51M"):
        return ("Employment", "Personal income and social taxes", "Income/social contribution hybrids", row["tax_name"], "CSG/CRDS/PIT are not split by source in this table; kept with employment/personal income taxes.")
    if "impot sur le revenu" in name or sto.startswith("D51M") or sto.startswith("D51A") or sto == "D51E":
        return ("Employment", "Personal income and social taxes", "Income tax", row["tax_name"], "UK-equivalent treatment: personal income tax kept with employment taxes unless a capital-income line is separately identified.")

    if has_any(label_text, ["taxes sur les salaires", "versement mobilite", "formation professionnelle", "apprentissage", "fnal", "garantie des salaires", "forfait social", "haut", "stock-options", "effort de construction", "solidarite pour l'autonomie"]):
        return ("Employment", "Employer payroll and labour levies", "Payroll levies", row["tax_name"], "UK-equivalent treatment: employer payroll levies sit with employment taxes, like apprenticeship levy/NICs.")

    if has_any(label_text, ["impots sur les societes", "corporation income tax", "benefices des societes", "corporations profits", "non business profits", "digital services", "services numeriques", "contribution sociale de solidarite des societes", "systemic risk", "risque systemique", "infrastructures de transport longues distances", "electricity producers profit", "rentes infra marginales"]):
        return ("Business", "Profit and sector taxes", "Corporate and sector profits", row["tax_name"], "UK-equivalent treatment: corporation/profit/sector levies sit with business taxes.")

    if has_any(label_text, ["cotisation sur la valeur ajoutee", "network corporations", "entreprises de reseaux", "surfaces commerciales", "chambre de commerce", "chamber of commerce", "chambre metier", "chamber of trades", "chambre d'agriculture", "pharmaceutical taxes", "taxes pharmaceutiques", "communications electroniques"]):
        return ("Business", "Business production and sector levies", "Production/sector levies", row["tax_name"], "French-specific production/sector business levy.")

    if has_any(label_text, ["foncier bati", "foncier non-bati", "taxe d'habitation", "council tax", "cotisation fonciere", "real-estate properties", "non-developed land", "creation and on the use of offices", "construction de bureaux", "taxes sur la construction", "construction", "registry land", "securite immobiliere", "real-estate rents", "loyers immobiliers"]):
        return ("Land", "Recurrent land and property taxes", "Land/buildings/business premises", row["tax_name"], "UK-equivalent treatment: land/property taxes align with council tax/business rates/property taxes.")

    if has_any(label_text, ["droits d'enregistrement", "registration taxes", "mutations"]) and not has_any(label_text, ["mutations a titre gratuit", "inheritance"]):
        return ("Land", "Property transaction and registration taxes", "Transfer/registration taxes", row["tax_name"], "UK-equivalent treatment: property-transfer duties sit with land/property taxes.")

    if has_any(label_text, ["mutations a titre gratuit", "inheritance", "wealth tax", "fortune immobiliere", "revenus des capitaux mobiliers", "income from financial assets", "financial transactions", "transactions financieres", "impot de solidarite sur la fortune"]):
        if has_any(label_text, ["mutations a titre gratuit", "inheritance"]):
            return ("Wealth", "Inheritance and gifts", "Inheritance/gift taxes", row["tax_name"], "UK-equivalent treatment: inheritance/gift taxes sit with wealth.")
        if has_any(label_text, ["wealth tax", "fortune immobiliere", "impot de solidarite sur la fortune"]):
            return ("Wealth", "Wealth taxes", "Annual wealth/real-estate wealth taxes", row["tax_name"], "UK-equivalent treatment: annual wealth taxes sit with wealth.")
        return ("Wealth", "Financial capital taxes", "Financial assets/transactions", row["tax_name"], "UK-equivalent treatment: financial-capital taxes sit with wealth.")

    if has_any(label_text, ["tva", "vat"]):
        return ("Goods/services", "VAT", "VAT", row["tax_name"], "Direct UK equivalent: VAT.")
    if has_any(label_text, ["produits energetiques", "energy products", "electricity", "gaz naturel", "oil products", "petroliers", "mineral oil", "domestic duty on energy", "excise duty on electricity"]):
        return ("Goods/services", "Energy and fuel duties", "Energy/fuel consumption duties", row["tax_name"], "UK-equivalent treatment: energy/fuel consumption duties sit with goods/services rather than environmental taxes.")
    if has_any(label_text, ["tabac", "tobacco", "boissons", "beverages", "alcohol", "alcools"]):
        return ("Goods/services", "Alcohol, tobacco and drinks duties", "Excise duties", row["tax_name"], "Direct UK equivalent: alcohol/tobacco/soft-drink-style duties.")
    if has_any(label_text, ["insurance", "assurance", "automobile insurance"]):
        return ("Goods/services", "Insurance taxes", "Insurance-premium taxes", row["tax_name"], "Direct UK equivalent: insurance premium tax.")
    if has_any(label_text, ["loterie", "loto", "casinos", "paris hippiques", "horse-race", "national lottery", "casino"]):
        return ("Goods/services", "Betting, gaming and lottery", "Gaming/gambling duties", row["tax_name"], "Direct UK equivalent: betting/gaming/lottery duties.")
    if has_any(label_text, ["amendes et confiscations", "various receipts", "penalites", "penalties", "redevance cynegetique", "hunting licence"]):
        return ("Other", "Fines, penalties and miscellaneous tax-like charges", "Fines/licences/miscellaneous", row["tax_name"], "UK-equivalent treatment: miscellaneous tax-like receipts sit with Other.")
    if has_any(label_text, ["import", "octroi de mer", "dock dues"]):
        return ("Goods/services", "Import and border taxes", "Customs/dock/import lines", row["tax_name"], "Direct UK equivalent: customs/import duties; octroi de mer treated as a goods/import consumption tax.")
    if has_any(label_text, ["vehicules", "vehicle", "transport", "navigation", "certificats d'immatriculation", "axle tax", "taxe a l'essieu"]):
        return ("Goods/services", "Transport and vehicle taxes", "Vehicle/transport-use taxes", row["tax_name"], "Direct UK equivalent: vehicle/transport taxes.")
    if has_any(label_text, ["spectacles", "cinema", "movie", "entertainment", "professional services", "services professionnels", "electronic communications"]):
        return ("Goods/services", "Specific services and media taxes", "Services/media/entertainment", row["tax_name"], "Specific consumption/service tax.")

    if has_any(label_text, ["emissions", "co2"]):
        return ("Environmental", "Carbon and emissions taxes", "CO2/ETS-style levies", row["tax_name"], "UK-equivalent treatment: carbon/emissions taxes sit with environmental taxes.")
    if has_any(label_text, ["water", "gemapi", "flood", "aquatic", "l'eau", "eaux"]):
        return ("Environmental", "Water and flood levies", "Water/flood/resource levies", row["tax_name"], "UK-equivalent treatment: water/resource charges sit with environmental taxes.")
    if has_any(label_text, ["pollution"]):
        return ("Environmental", "Pollution taxes", "Pollution levies", row["tax_name"], "UK-equivalent treatment: pollution charges sit with environmental taxes.")
    if has_any(label_text, ["pylones", "pylons"]):
        return ("Environmental", "Energy-network environmental levies", "Energy infrastructure/environmental levies", row["tax_name"], "Classified with environmental taxes because Eurostat marks it with an energy/environmental tag.")

    if name == "autres taxes":
        return ("Other", "Residual other taxes", "Eurostat residual other-tax lines", row["tax_name"], "Grouped Eurostat 'other taxes' residual without a more specific label.")

    if sto.startswith("D91"):
        return ("Wealth", "Capital taxes", "Capital transfers and penalties", row["tax_name"], "ESA capital-tax line.")
    if sto.startswith("D59"):
        return ("Wealth", "Other capital/current wealth taxes", "Other wealth/capital taxes", row["tax_name"], "ESA current wealth/capital line not otherwise split.")
    if sto.startswith("D214") or sto.startswith("D212"):
        return ("Goods/services", "Other consumption taxes", "Other goods/services taxes", row["tax_name"], "Residual ESA product/service-tax line.")
    if sto.startswith("D29"):
        return ("Business", "Other production taxes", "Other business/production taxes", row["tax_name"], "Residual ESA production-tax line.")
    if sto.startswith("D51"):
        return ("Business", "Other income/profit taxes", "Other income/profit taxes", row["tax_name"], "Residual ESA income-tax line.")

    return ("Other", "Unclassified Eurostat row", "Needs review", row["tax_name"], "Fallback classification.")


def classify_cour(row):
    name = ntext(row["tax_name"])
    english = ntext(row["tax_name_english"])
    explanation = ntext(row["english_explanation"])
    notes = ntext(row["notes"])
    text = f"{name} {english} {explanation} {notes}"

    if name.startswith("less: cour low-yield"):
        return ("Other", "Reconciliation adjustments", "Cour/Eurostat overlap", "", "Generated non-tax adjustment; not a chart leaf.")

    if has_any(text, ["droits de plaidoirie", "matieres d'or et d'argent", "permis de chasse", "cynegetiques"]):
        return ("Other", "Service-related tax-like charges", "Low-yield administrative/service charges", row["tax_name"], "Cour service-related row classified from legal label.")

    if has_any(text, ["masse salariale", "payroll", "employeur", "employers", "formation professionnelle", "apprentissage", "stock-options", "main d'oeuvre", "travail temporaire", "preretraite", "retraite"]):
        return ("Employment", "Employer payroll and labour levies", "Low-yield payroll/workforce levies", row["tax_name"], "Cour low-yield row classified from base/payer/legal label.")

    if has_any(text, ["produits de tabac", "tabac", "tabacs"]):
        return ("Goods/services", "Alcohol, tobacco and drinks duties", "Low-yield tobacco levies", row["tax_name"], "Cour low-yield row classified from tobacco label.")

    if has_any(text, ["medicaments", "produits de sante", "pharmaceutiques"]):
        return ("Business", "Business production and sector levies", "Low-yield pharmaceutical/health-product levies", row["tax_name"], "Cour low-yield row classified from pharmaceutical/health-product label.")

    if has_any(text, ["assurance", "assurances"]) and not has_any(text, ["assurance-vie", "desherence", "reserve de capitalisation"]):
        return ("Goods/services", "Insurance taxes", "Low-yield insurance levies", row["tax_name"], "Cour low-yield row classified from insurance label.")

    if has_any(text, ["boissons", "tabac", "tabacs", "alcool", "vins", "produits energetiques", "electricite", "gaz naturel", "charbons", "petroliers", "sucres", "premix", "jeux", "paris", "casinos", "loterie", "vehicule", "transport", "permis de conduire", "navigation", "visa", "sejour", "naturalisation", "certificats", "spectacles", "audiovisuels", "publicite", "communications electroniques", "octroi de mer"]):
        sub = "Other goods/services taxes"
        if has_any(text, ["produits energetiques", "electricite", "gaz naturel", "charbons", "petroliers"]):
            sub = "Energy and fuel duties"
        elif has_any(text, ["boissons", "tabac", "tabacs", "alcool", "vins", "sucres", "premix"]):
            sub = "Alcohol, tobacco and drinks duties"
        elif has_any(text, ["jeux", "paris", "casinos", "loterie"]):
            sub = "Betting, gaming and lottery"
        elif has_any(text, ["vehicule", "transport", "permis de conduire", "navigation"]):
            sub = "Transport and vehicle taxes"
        elif has_any(text, ["visa", "sejour", "naturalisation"]):
            sub = "Immigration/nationality charges classified as taxes"
        elif has_any(text, ["audiovisuels", "spectacles", "communications electroniques", "publicite"]):
            sub = "Specific services and media taxes"
        return ("Goods/services", sub, "Low-yield consumption/service levies", row["tax_name"], "Cour low-yield row classified from legal label and base.")

    if has_any(text, ["pollution", "tgap", "dechets", "lessives", "phytosanitaires"]):
        return ("Environmental", "Pollution taxes", "Low-yield pollution levies", row["tax_name"], "Cour low-yield row classified from pollution label.")
    if has_any(text, ["l'eau", "eaux", "aquatique", "agences de l'eau", "veterinaire", "vegetaux"]):
        return ("Environmental", "Water, plant and animal inspection levies", "Low-yield water/agri-food inspection levies", row["tax_name"], "Cour low-yield row classified from water/agri-food inspection label.")
    if has_any(text, ["emissions", "hydrocarbures", "extraction", "renouvelable", "energie renouvelable", "eoliennes", "hydroliennes"]):
        return ("Environmental", "Carbon, energy-transition and extraction levies", "Low-yield emissions/resource levies", row["tax_name"], "Cour low-yield row classified from carbon/resource/energy-transition label.")
    if has_any(text, ["installations nucleaires", "reacteurs nucleaires", "surete nucleaire", "radioprotection"]):
        return ("Environmental", "Nuclear safety and radioprotection levies", "Low-yield nuclear safety levies", row["tax_name"], "Cour low-yield row classified from nuclear safety/radioprotection label.")

    if has_any(text, ["foncier", "logements vacants", "bureaux", "locaux", "loyers", "construction", "terrains", "immeubles", "archeologie preventive", "droit de bail", "plus-values immobilieres", "mines d'or", "ouvrages d'art"]):
        return ("Land", "Land, buildings and development levies", "Low-yield property/development taxes", row["tax_name"], "Cour low-yield row classified from land/property label.")

    if has_any(text, ["successions", "biens confisques"]):
        return ("Wealth", "Inheritance and gifts", "Low-yield inheritance/gift/capital-transfer levies", row["tax_name"], "Cour low-yield row classified from capital-transfer label.")
    if has_any(text, ["trust", "metaux precieux", "carried-interests", "fcp", "fcpi", "haute frequence", "produits de placement"]):
        return ("Wealth", "Financial capital taxes", "Low-yield financial-capital levies", row["tax_name"], "Cour low-yield row classified from financial-capital label.")
    if has_any(text, ["capital", "fortune", "assurances de dommages", "reserves de capitalisation"]):
        return ("Wealth", "Other capital taxes", "Low-yield capital/wealth levies", row["tax_name"], "Cour low-yield row classified from Cour capital base.")

    if has_any(text, ["benefice", "profits", "laboratoires", "pharmaceutiques", "dispositifs medicaux", "entreprises", "societes", "chambre de commerce", "chambre de metiers", "agriculteurs", "professionnels", "commissaires aux comptes", "opérateurs", "operateurs", "sncf", "ferroviaires", "securite privee", "travail", "cinematographiques", "diffuseurs", "producteurs", "exploitants", "concessionnaires"]):
        return ("Business", "Business production and sector levies", "Low-yield sector/professional levies", row["tax_name"], "Cour low-yield row classified from business/professional label.")

    if has_any(text, ["service rendu", "service-related"]):
        return ("Other", "Service-related tax-like charges", "Low-yield administrative/service charges", row["tax_name"], "Cour service-related row without clearer UK-equivalent category.")

    if has_any(text, ["consommation", "consumption"]):
        return ("Goods/services", "Other consumption taxes", "Low-yield consumption levies", row["tax_name"], "Cour low-yield row classified from Cour base.")
    if has_any(text, ["production"]):
        return ("Business", "Business production and sector levies", "Low-yield production levies", row["tax_name"], "Cour low-yield row classified from Cour base.")

    return ("Other", "Other low-yield taxes", "Unclassified low-yield taxes", row["tax_name"], "Fallback classification.")


def classify(row):
    if is_eurostat(row):
        return classify_eurostat(row)
    if is_cour(row):
        return classify_cour(row)
    return ("Other", "Unknown source", "Needs review", row["tax_name"], "Fallback classification.")


def is_global_overlap_adjustment(row):
    return row["tax_name"] == "Less: Cour low-yield taxes already included in Eurostat aggregates"


def make_cour_layer_adjustments(rows, fieldnames):
    grouped = defaultdict(int)
    for row in rows:
        if not is_cour(row) or is_global_overlap_adjustment(row) or not row["revenue_eur"]:
            continue
        value = int(row["revenue_eur"])
        if value <= 0:
            continue
        key = (row["layer_1"], row["layer_2"])
        grouped[key] += value

    adjustments = []
    for (layer_1, layer_2), value in sorted(grouped.items()):
        row = {field: "" for field in fieldnames + LAYER_FIELDS}
        row.update({
            "tax_name": f"Less: Cour low-yield taxes already included in Eurostat aggregates - {layer_1} / {layer_2}",
            "tax_name_english": f"Less: Cour low-yield taxes already included in Eurostat aggregates - {layer_1} / {layer_2}",
            "english_explanation": "Layer-specific negative overlap adjustment so layer totals do not double-count Cour low-yield taxes already included within Eurostat national-accounts rows.",
            "revenue_eur": str(-value),
            "revenue_pct_gdp": f"{(-value) / GDP_EUR * 100:.6f}",
            "source_for_data": "Cour des comptes low-yield inventory; generated layer reconciliation adjustment",
            "notes": "This is not a separate tax and should not be charted as a leaf. It offsets known-yield Cour rows in this layer because those rows are included for visibility but are already contained within Eurostat aggregate rows.",
            "layer_1": layer_1,
            "layer_2": layer_2,
            "layer_3": "Cour/Eurostat overlap adjustment",
            "layer_4": "",
            "classification_notes": "Generated layer-specific reconciliation adjustment.",
        })
        adjustments.append(row)
    return adjustments


def revenue_value(row):
    return int(row["revenue_eur"]) if row.get("revenue_eur") else 0


def init_chart_fields(row):
    value = revenue_value(row)
    row["netted_adjustments_eur"] = "0"
    row["netting_notes"] = ""
    if value > 0:
        row["chart_include"] = "yes"
        row["chart_revenue_eur"] = str(value)
        row["chart_revenue_pct_gdp"] = f"{value / GDP_EUR * 100:.6f}"
    else:
        row["chart_include"] = "no"
        row["chart_revenue_eur"] = ""
        row["chart_revenue_pct_gdp"] = ""
        if value < 0:
            row["netting_notes"] = "Negative source/reconciliation row excluded from chart and used only to reduce positive comparable rows."


def apply_deduction(row, amount, note):
    current = int(row["chart_revenue_eur"] or "0")
    if amount > current:
        raise ValueError(f"Cannot deduct EUR {amount:,} from {row['tax_name']} with chart value EUR {current:,}")
    new_value = current - amount
    row["chart_revenue_eur"] = str(new_value)
    row["chart_revenue_pct_gdp"] = f"{new_value / GDP_EUR * 100:.6f}"
    row["netted_adjustments_eur"] = str(int(row["netted_adjustments_eur"] or "0") - amount)
    row["netting_notes"] = f"{row['netting_notes']} {note}".strip()
    if new_value == 0:
        row["chart_include"] = "no"


def find_target_by_name(rows, needles):
    for row in rows:
        if not is_eurostat(row) or row["chart_include"] != "yes":
            continue
        label = ntext(f"{row['tax_name']} {row['tax_name_english']}")
        if all(needle in label for needle in needles):
            return row
    return None


def apply_d995_netting(rows):
    targets = [
        ("cotisations sociales effectives a la charge des employeurs dues non recouvrables", ["cotisations sociales effectives obligatoires a la charge des employeurs"]),
        ("cotisations sociales effectives a la charge des salaries dues non recouvrables", ["cotisations sociales effectives obligatoires a la charge des salaries"]),
        ("cotisations sociales effectives a la charge des travailleurs independants dues non recouvrables", ["travailleurs independants"]),
        ("cotisations sociales effectives a la charge des personnes n'occupant pas d'emploi dues non recouvrables", ["personnes n'occupant pas d'emploi"]),
        ("impots sur le revenu dus non recouvrables", ["impot sur le revenu"]),
    ]
    for negative in [row for row in rows if revenue_value(row) < 0 and is_eurostat(row)]:
        name = ntext(negative["tax_name"]).removeprefix("less: ").strip()
        amount = abs(revenue_value(negative))
        target = None
        for negative_name, target_needles in targets:
            if negative_name in name:
                target = find_target_by_name(rows, target_needles)
                break
        if target is None and "autres impots sur la production" in name:
            target = max(
                (
                    row for row in rows
                    if is_eurostat(row)
                    and row["layer_1"] == "Business"
                    and row["layer_2"] in {"Business production and sector levies", "Other production taxes"}
                    and row["chart_include"] == "yes"
                ),
                key=lambda row: int(row["chart_revenue_eur"]),
            )
        if target is None and "autres impots courants" in name:
            target = max(
                (row for row in rows if is_eurostat(row) and row["layer_1"] == "Wealth" and row["chart_include"] == "yes"),
                key=lambda row: int(row["chart_revenue_eur"]),
            )
        if target is None:
            raise ValueError(f"No D995 netting target found for {negative['tax_name']}")
        apply_deduction(target, amount, f"Netted D995 uncollectible adjustment from {negative['tax_name']}.")


def target_priority(row):
    label = ntext(f"{row['tax_name']} {row['tax_name_english']}")
    if "autres taxes" in label or "other taxes" in label:
        return 0
    if "autres" in label or "other" in label or "diverses" in label:
        return 1
    return 2


def allocate_cour_overlap(rows):
    grouped = defaultdict(int)
    for row in rows:
        if not is_cour(row) or is_global_overlap_adjustment(row):
            continue
        value = revenue_value(row)
        if value > 0:
            grouped[(row["layer_1"], row["layer_2"])] += value

    for (layer_1, layer_2), amount in sorted(grouped.items()):
        remaining = amount
        candidates = [
            row for row in rows
            if is_eurostat(row)
            and row["chart_include"] == "yes"
            and row["layer_1"] == layer_1
            and row["layer_2"] == layer_2
        ]
        if not candidates:
            candidates = [
                row for row in rows
                if is_eurostat(row)
                and row["chart_include"] == "yes"
                and row["layer_1"] == layer_1
            ]
        candidates.sort(key=lambda row: (target_priority(row), -int(row["chart_revenue_eur"])))
        for target in candidates:
            if remaining <= 0:
                break
            deduction = min(remaining, int(target["chart_revenue_eur"]))
            apply_deduction(
                target,
                deduction,
                f"Netted Cour known-yield overlap for {layer_1} / {layer_2}.",
            )
            remaining -= deduction
        if remaining:
            raise ValueError(f"Could not allocate Cour overlap EUR {remaining:,} for {layer_1} / {layer_2}")


def main():
    with INPUT.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [row for row in reader if not is_global_overlap_adjustment(row)]
        fieldnames = list(reader.fieldnames or [])

    for row in rows:
        layer_1, layer_2, layer_3, layer_4, classification_notes = classify(row)
        row.update({
            "chart_label_en": "",
            "layer_1": layer_1,
            "layer_2": layer_2,
            "layer_3": layer_3,
            "layer_4": layer_4,
            "classification_notes": classification_notes,
        })
        init_chart_fields(row)

    apply_d995_netting(rows)
    allocate_cour_overlap(rows)
    for row in rows:
        row["chart_label_en"] = label_from_french_name(row)
    dedupe_labels(rows)
    for row in rows:
        row["display_explanation"] = display_explanation(row)

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames + LAYER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {OUTPUT}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
