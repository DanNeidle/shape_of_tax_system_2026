# The shape of the tax system

Code and data behind Tax Policy Associates' charts of the UK, French and German tax systems, and of the number of UK taxes over time.

| Folder | What it builds |
|---|---|
| `uk_current_tax/` | The sunburst chart of every UK tax in 2025-26, from OBR, ONS and HMRC figures. |
| `historic_uk_tax/` | The number of UK taxes in each year since 1000, the timeline of every tax, and tax as a share of GDP. |
| `france_current_tax/` | The sunburst chart of the French tax system, 2024. |
| `germany_current_tax/` | The sunburst chart of the German tax system, 2024. |
| `oecd_current_tax/` | The comparison of how many taxes each country has. |

## Rebuilding the charts

You need Python 3 with `openpyxl`, `pandas` and `odfpy`. Each script reads the files in its own folder and needs no internet access.

```bash
cd uk_current_tax && python3 build_tax_system_chart.py

cd historic_uk_tax
python3 code/uk/build_uk_tax_receipts_gdp_series.py
python3 code/uk/build_tax_lifespan_count_chart.py
python3 code/uk/build_tax_lifespan_count_gdp_chart.py
python3 code/uk/build_tax_lifespan_timeline_chart.py
```

The UK sunburst script checks that every breakdown adds back to the OBR's totals, and stops if one doesn't.

The outputs are [Apache ECharts](https://echarts.apache.org/) option files (JSON). Some use tooltip hooks that are specific to our website.

## The UK figures

The UK sunburst starts from the OBR's "National Accounts taxes" for 2025-26 in its October 2026 forecast. We leave out VAT refunds to public bodies. We add three levies that are being charged but aren't yet in the official figures: the capacity market and the Sizewell C levy (from the OBR's own footnote) and packaging fees (from the OBR's March 2026 forecast, because there is no actual figure). The articles explain the method in full.

The history dataset is `historic_uk_tax/code/data/uk_tax/uk_tax_lifespans_broad.tsv`, with one row for each period a tax was in force. Its README explains the fields, how we count, and what we know is weak. Corrections are very welcome.

## Licence

Our code, the tax history dataset and the chart files are copyright (c) 2026 Tax Policy Associates Ltd and released under the MIT licence (see `LICENSE`).

The OBR, ONS and HMRC files are Crown copyright, published under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). The French, German, Eurostat and OECD files are subject to their publishers' terms.
