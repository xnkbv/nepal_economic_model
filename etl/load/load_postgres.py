import pandas as pd
from pathlib import Path
from sqlalchemy import text

from db import get_engine

PROCESSED = Path("data/processed")
SCHEMA_FILE = Path("sql/01_schema.sql")

# ---------- 1. Read the cleaned CSVs ----------
annual = pd.read_csv(PROCESSED / "nrb_annual_indicators.csv")
monthly = pd.read_csv(PROCESSED / "nrb_monthly_indicators.csv", parse_dates=["date"])
quarterly = pd.read_csv(PROCESSED / "nrb_quarterly_wages.csv", parse_dates=["date"])

# ---------- 2. Build dim_fiscal_year ----------
all_years = pd.concat([annual["fy_ad"], monthly["fy_ad"], quarterly["fy_ad"]]).unique()
dim_year = pd.DataFrame({"fy_ad": sorted(all_years)})
dim_year["fy_id"] = dim_year["fy_ad"].str[:4].astype(int)
dim_year["fy_end_year"] = dim_year["fy_id"] + 1
dim_year["is_comparable"] = dim_year["fy_id"] >= 2011
bs = annual.dropna(subset=["fy_bs"]).drop_duplicates("fy_ad").set_index("fy_ad")["fy_bs"]
dim_year["fy_bs"] = dim_year["fy_ad"].map(bs)
dim_year = dim_year[["fy_id", "fy_ad", "fy_bs", "fy_end_year", "is_comparable"]]

# ---------- 3. Build dim_indicator ----------
CATEGORY_KEYWORDS = [            # first keyword found in the code wins
    ("remittance", "Remittances"),
    ("current_account", "Balance of payments"), ("bop_", "Balance of payments"),
    ("net_exports", "Balance of payments"),
    ("export", "Trade"), ("import", "Trade"), ("trade", "Trade"),
    ("credit", "Credit"), ("deposit_rate", "Interest rates"), ("deposits", "Deposits"),
    ("rate", "Interest rates"), ("m1", "Money supply"), ("m2", "Money supply"),
    ("gdp", "Output"), ("cpi", "Prices"), ("wage", "Wages"),
]
UNIT_SUFFIXES = [                # first suffix that matches wins
    ("_pct_gdp", "% of GDP"),
    ("_npr_bn", "NPR billion"),
    ("_growth_pct", "% change y/y"),
    ("_inflation_pct", "% change y/y"),
    ("_avg_pct", "% per year, annual average"),
    ("_pct", "% per year"),
    ("_index_avg", "Index (2023/24 = 100), annual average"),
    ("_index", "Index (2023/24 = 100)"),
]


NAME_WORDS = [                   # turn code fragments into readable labels, in this order
    ("_pct_gdp", " (% of GDP)"), ("_npr_bn", " (NPR bn)"),
    ("_growth_pct", " growth (%)"), ("_inflation_pct", " inflation (%)"),
    ("_avg_pct", " (annual avg, %)"), ("_index_avg", " index (annual avg)"), ("_pct", " (%)"),
    ("gdp_", "GDP "), ("cpi_", "CPI "), ("bop_", "BoP "), ("m1", "M1"), ("m2", "M2"),
    ("tbill_91d", "91-day T-bill"), ("_wavg", " weighted avg"), ("_gs", " goods & services"),
    ("nonfood", "non-food"), ("_", " "),
]


def describe(code):
    """Work out category, unit and a readable name from an indicator code."""
    category = next(cat for key, cat in CATEGORY_KEYWORDS if key in code)
    unit = next(u for suffix, u in UNIT_SUFFIXES if code.endswith(suffix))
    name = code
    for old, new in NAME_WORDS:
        name = name.replace(old, new)
    return category, unit, name[0].upper() + name[1:]


sources = pd.concat([
    annual[["indicator", "source_sheet"]].assign(frequency="annual"),
    monthly[["indicator", "source_sheet"]].assign(frequency="monthly"),
    quarterly[["indicator", "source_sheet"]].assign(frequency="quarterly"),
]).drop_duplicates("indicator").reset_index(drop=True)

dim_ind = sources.rename(columns={"indicator": "indicator_code"})
dim_ind[["category", "unit", "indicator_name"]] = dim_ind["indicator_code"].apply(
    lambda c: pd.Series(describe(c)))
dim_ind["indicator_id"] = dim_ind.index + 1
dim_ind = dim_ind[["indicator_id", "indicator_code", "indicator_name", "category",
                   "unit", "frequency", "source_sheet"]]

# ---------- 4. Build the fact tables (swap text labels for ids) ----------
ind_id = dim_ind.set_index("indicator_code")["indicator_id"]
year_id = dim_year.set_index("fy_ad")["fy_id"]

fact_annual = pd.DataFrame({
    "fy_id": annual["fy_ad"].map(year_id),
    "indicator_id": annual["indicator"].map(ind_id),
    "value": annual["value"],
    "status": annual["status"],
})
fact_monthly = pd.DataFrame({
    "obs_date": monthly["date"].dt.date,
    "fy_id": monthly["fy_ad"].map(year_id),
    "indicator_id": monthly["indicator"].map(ind_id),
    "value": monthly["value"],
})
fact_quarterly = pd.DataFrame({
    "obs_date": quarterly["date"].dt.date,
    "fy_id": quarterly["fy_ad"].map(year_id),
    "region": quarterly["region"],
    "indicator_id": quarterly["indicator"].map(ind_id),
    "value": quarterly["value"],
    "status": quarterly["status"],
})

# ---------- 5. Load: rebuild the schema, then insert, all in one transaction ----------
engine = get_engine()
tables = [("dim_fiscal_year", dim_year), ("dim_indicator", dim_ind),
          ("fact_annual", fact_annual), ("fact_monthly", fact_monthly),
          ("fact_quarterly", fact_quarterly)]

with engine.begin() as conn:
    # Run the schema file through the plain driver cursor (it treats "%" in comments as text)
    conn.connection.cursor().execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    for name, df in tables:
        df.to_sql(name, conn, if_exists="append", index=False, method="multi", chunksize=1000)

# ---------- 6. Verify what is now in the database ----------
with engine.connect() as conn:
    for name, df in tables:
        in_db = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
        print(f"{name:16} {in_db:5} rows")
        assert in_db == len(df), f"{name}: expected {len(df)} rows, found {in_db}"

    remit = conn.execute(text("""
        SELECT f.value
        FROM fact_annual f
        JOIN dim_indicator i  ON i.indicator_id = f.indicator_id
        JOIN dim_fiscal_year y ON y.fy_id = f.fy_id
        WHERE i.indicator_code = 'remittances_npr_bn' AND y.fy_ad = '2025/26'
    """)).scalar()
    print(f"\nSpot check, remittances 2025/26: Rs. {remit:,.2f} billion")
    assert abs(remit - 2363.13) < 0.01, "Remittance value changed during loading!"

print("Load complete. All checks passed.")
