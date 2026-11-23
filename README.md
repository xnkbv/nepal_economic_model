# Nepal Debt Cycle Monitor

**Is Nepal's spending boom built on production, or on remittances and debt?**

An end-to-end data pipeline (Python → PostgreSQL → Power BI) that applies Ray Dalio's debt-cycle framework to Nepal's economy, using official Nepal Rastra Bank (NRB) data from FY 2011/12 to 2025/26.

---

## The idea

Dalio's *How the Economic Machine Works* rests on a few rules:

- **One person's spending is another person's income.**
- **Living standards rise sustainably only when productivity grows.**
- **Credit lets spending run ahead of income for a while, but it has to be paid back.** That creates cycles of boom, deleveraging and recovery.

Nepal is an unusual case. A large share of household income is earned abroad (remittances reached **35.8% of GDP** in 2025/26), and much of that money leaves again through imports. Bank credit roughly doubled relative to the economy in a decade, then stalled.

This project asks **where Nepal sits in its debt cycle** and **how fragile household spending is**, and answers with data instead of opinion.

## Hypotheses

Each hypothesis can be proven wrong by the data. Each one has its own SQL view.

| | Question | Hypothesis | View |
|---|---|---|---|
| **H1** | Where is Nepal in the debt cycle? | Private credit/GDP peaked in 2020/21 and has stalled since: a deleveraging, not a crash. | `v_h1_debt_cycle` |
| **H2** | Was the credit productive? | Credit went mostly to real estate and consumption, not production. | *planned (needs sector credit data)* |
| **H3** | Is money cheap but unwanted? | Interest rates fell after 2023, yet credit demand stayed weak. | `v_h3_money_demand` |
| **H4** | Is spending funded from abroad? | Remittances fund most of the trade deficit. | `v_h4_external_funding` |
| **H5** | Are workers better off? | Real wages have barely grown. | `v_h5_real_wages`, `v_h5_wages_by_province` |

## Findings so far

| | Result |
|---|---|
| **H1** | A full cycle. **Boom:** private credit rose from 46% to **95% of GDP** (2011/12 → 2020/21), growing 7–16 points faster than GDP each year. **Deleveraging:** it then grew *slower* than GDP for three years (2021/22 – 2023/24). **Stall:** since 2024/25 the gap is about zero, with credit flat at about **91% of GDP**. |
| **H3** | The average lending rate fell to **7.1%** in 2025/26, the lowest in the series, yet loans grew **7.4 points slower than deposits**. Deposits have outgrown loans for four years running: banks are filling up with money nobody borrows. |
| **H4** | Remittances covered **59%** of the trade deficit at the 2021/22 import peak, and **133%** in 2025/26. They now exceed total imports. The current account is in surplus (**14% of GDP**). |
| **H5** | Real wages rose about **25% over 14 years** (roughly 1.6% a year) and fell in 2023/24 and 2024/25. In the latest year, wages grew **11.3% in Gandaki** but only **1.3% in Karnali**. |

**Reading these carefully:** the numbers are NRB's, and the pipeline checks that they were read correctly. The *explanations* are hypotheses that fit the data, not proof. Weak loan demand could also reflect political uncertainty or NRB lending rules. The 37% jump in remittances in 2025/26 may partly reflect money moving from informal (*hundi*) channels into banks, or a weaker rupee, rather than higher real income. 2021/22–2024/25 figures are revised, and 2025/26 figures are preliminary.

---

## Data source

All data comes from **Nepal Rastra Bank**, the central bank of Nepal.

| | |
|---|---|
| **Publication** | *Current Macroeconomic and Financial Situation – Tables (Based on Annual Data of 2025/26)* |
| **Published** | 26 August 2026 |
| **Where** | [nrb.org.np](https://www.nrb.org.np) → search "Current Macroeconomic" → the "Tables" item → Excel download |
| **File in repo** | `data/raw/nrb/nrb_cmefs_tables_annual_2082-83.xlsx` (unchanged original) |

NRB republishes GDP figures from Nepal's **National Statistics Office (NSO)**, so one file covers credit, GDP, prices, wages and trade.

### Sheets used

| Sheet | Contents | Frequency | Coverage |
|---|---|---|---|
| `A1` GDP annex | Nominal GDP, nominal and real GDP growth | Annual | 1974/75 – 2025/26 |
| `A2` CPI annual | Consumer price index (2023/24 = 100), inflation | Annual | 1972/73 – 2025/26 |
| `A7` SWI provincial series | Salary & wage index: Nepal and 7 provinces | Quarterly | 2004/05 – 2025/26 |
| `A11` Trade annex | Exports, imports, trade balance | Annual | 1974/75 – 2025/26 |
| `A13` BoP annex | Remittances, current account, balance of payments | Annual | 1974/75 – 2025/26 (remittances from 2000/01) |
| `A24` Interest rates | Interbank, 91-day T-bill, deposit, lending and base rates | Monthly | 2016/17 – 2025/26 |
| `A25.1` Monetary indicators | M1, M2, domestic and private credit, deposits (Rs.), growth | Annual | 1974/75 – 2025/26 |
| `A26` Monetary indicators % of GDP | The same, as % of GDP | Annual | 1974/75 – 2025/26 |

---

## Pipeline

```
  EXTRACT                  TRANSFORM                     LOAD                    ANALYZE              VISUALIZE
  ───────                  ─────────                     ────                    ───────              ─────────
  nrb.org.np        →   clean, reshape, validate   →   PostgreSQL          →   SQL views per   →   Power BI
  (Excel tables)        (Python / pandas)               star schema             hypothesis
       │                        │                            │                       │                   │
  extract_nrb.py       transform_nrb.py               load_postgres.py         02_views.sql      nepal_debt_cycle.pbix
  data/raw/            data/processed/*.csv           01_schema.sql
```

### 1. Extract: `etl/extract/extract_nrb.py`
Uses `requests` and `BeautifulSoup` to read NRB's search results and list the links to each report's statistical tables. NRB links each search result to a detail page, which holds the Excel file under `/contents/uploads/YEAR/MONTH/`. The current version lists the links, and the file was downloaded once and kept unchanged in `data/raw/`.

### 2. Transform: `etl/transform/transform_nrb.py`
Turns sheets built for people to read into tidy tables:
- skips title rows and footnotes, and names columns explicitly (several sheets have two-row headers)
- strips markers like `2010/11*` and keeps NRB's **R** (revised) / **P** (preliminary) flags in a `status` column
- converts all rupee amounts from Rs. million to **NPR billion**
- reshapes wide sheets into **long format** (one row per year per indicator)
- maps monthly and quarterly rows to Nepal's fiscal year (mid-July to mid-July) and builds real dates
- computes annual averages of interest rates (12 months) and wages (4 quarters), and refuses incomplete years

**Output:** 2,320 annual, 600 monthly and 704 quarterly rows, covering 55 indicators.

### 3. Load: `sql/01_schema.sql` + `etl/load/load_postgres.py`
Loads the CSVs into a PostgreSQL **star schema** in a single transaction, then checks row counts and spot-checks a known value inside the database.

```
        dim_fiscal_year (54 years)        dim_indicator (55 indicators)
              │        \                    /        │
              │         fact_annual  (2,320 rows)     │
              │         fact_monthly   (600 rows)     │
              └──────── fact_quarterly (704 rows) ────┘
```

- **Primary keys** stop duplicate values, and **foreign keys** stop orphan rows.
- `dim_fiscal_year.is_comparable` marks years from 2011/12 onwards (see *Methodology*).
- Indicator names, categories and units are worked out from consistent column naming (`_npr_bn`, `_pct_gdp`, `_growth_pct`, …).

### 4. Analyze: `sql/02_views.sql`
A base view pivots the long facts into one row per year (`v_annual_wide`). Each hypothesis view builds on it, using window functions (`LAG`) for year-on-year changes.

### 5. Visualize: `powerbi/nepal_debt_cycle.pbix`
Power BI imports the views and links them in a star around `dim_fiscal_year` (many-to-one, single direction). Calculations stay in SQL, and Power BI only draws them. DAX measures use the latest year in the current selection, so the KPI cards stay correct after each data refresh.

---

## Validation

The pipeline checks its own output, and a run stops with an error if any check fails.

| Check | What it catches |
|---|---|
| Rows per year and indicator are unique | Duplicated or misaligned rows |
| Credit (A25.1) ÷ GDP (A1) equals NRB's ratio (A26) | Wrong units, shifted columns or mismatched years between sheets |
| Exports − imports = trade balance | Column shifts in the trade sheet |
| Remittances (A13) ÷ GDP (A1) equals A13's own % | Cross-sheet misalignment |
| CPI and wage index equal 100 in base year 2023/24 | Errors in averaging or fiscal-year mapping |
| Published inflation equals the % change of the CPI index | Index or year errors |
| 12 months / 4 quarters per year before averaging | Averages built on partial years |
| Interest rates stay between 0% and 25% | Implausible values |
| Database row counts equal CSV row counts | Rows lost during loading |
| Remittances 2025/26 equal Rs. 2,363.13 bn in the database | ID mapping errors in the star schema |

The province view independently reproduces NRB's published wage growth figures (Karnali 1.26%, Gandaki 11.32%).

## Methodology

- **Analysis starts in 2011/12.** 2010/11 is a series break: GDP was rebased, *and* credit figures began to include development banks and finance companies. NRB doesn't publish GDP growth across that break.
- **Credit growth is compared with *nominal* GDP growth.** Both are in current rupees, so inflation doesn't distort the credit gap.
- **Real growth uses the exact formula** `(1 + nominal) / (1 + inflation) − 1`, not the subtraction shortcut.
- **Real GDP levels are dropped.** They mix 2000/01 and 2010/11 price bases, so only real growth rates are used.
- **CPI before 2014/15 is a backlinked series.** NRB spliced it onto the 2023/24 base, so NRB's originally published inflation rates are used instead.
- **Interest rates are annual averages** of 12 mid-month observations, so they match annual credit data.
- **Remittances start in 2000/01.** Karnali has only 12 quarters of wage data.

---

## Project structure

```
nepal-economic-model/
├── data/
│   ├── raw/nrb/          original NRB Excel file (never edited)
│   └── processed/        clean CSVs from the transform step
├── etl/
│   ├── extract/          extract_nrb.py: find NRB report links
│   ├── transform/        transform_nrb.py: clean, reshape, validate
│   └── load/             db.py (connection), load_postgres.py
├── sql/
│   ├── 01_schema.sql     star schema
│   └── 02_views.sql      one view per hypothesis
├── powerbi/              nepal_debt_cycle.pbix
├── .env.example          database settings template
└── requirements.txt
```

## Tech stack

**Python** (pandas, openpyxl, requests, BeautifulSoup, SQLAlchemy, psycopg2, python-dotenv) · **PostgreSQL 18** · **SQL** (star schema, views, window functions) · **Power BI Desktop** (DAX)

## How to run

Requirements: Python 3.11, PostgreSQL, Power BI Desktop (Windows).

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

1. Create a database called `nepal_economy` in PostgreSQL.
2. Copy `.env.example` to `.env` and fill in your PostgreSQL password. `.env` is git-ignored.
3. Run the pipeline from the project root:

```bash
.venv\Scripts\python.exe etl\transform\transform_nrb.py
.venv\Scripts\python.exe etl\load\load_postgres.py
psql -U postgres -d nepal_economy -f sql\02_views.sql
```

4. Open `powerbi/nepal_debt_cycle.pbix` and click **Refresh**.

Re-running the loader rebuilds the tables, which also drops the views, so run `02_views.sql` again after it.

## Status

- [x] Extract, transform and validate 8 NRB sheets
- [x] PostgreSQL star schema and loader
- [x] SQL views for H1, H3, H4, H5
- [x] Power BI page 1: *The Debt Cycle*
- [ ] Power BI pages 2–4: *Cheap Money, No Borrowers* · *Funded From Abroad* · *Are Workers Better Off?*
- [ ] H2: credit by sector and product (NRB tables 52 and 54)
- [ ] Automated download of new NRB releases and a single "run everything" script
- [ ] Phase 2: province-level analysis and a Provincial Fragility Index (NSO provincial GDP, Census 2021, NLSS IV)

---

*Data: Nepal Rastra Bank, Current Macroeconomic and Financial Situation (Annual Data of 2025/26). This is an independent analysis, not affiliated with NRB.*
