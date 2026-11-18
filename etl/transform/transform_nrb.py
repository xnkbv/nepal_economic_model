import pandas as pd
from pathlib import Path

RAW_FILE = Path("data/raw/nrb/nrb_cmefs_tables_annual_2082-83.xlsx")
OUT_FILE = Path("data/processed/nrb_monetary_pct_gdp.csv")

# 1. Read the sheet (column names are on row 4)
df = pd.read_excel(RAW_FILE, sheet_name="A26.Monetary Ind. % of GDP ", header=3)

# 2. Clean the year labels ("2010/11*" -> "2010/11"), then keep only real data rows
df["Fiscal Year"] = df["Fiscal Year"].astype(str).str.replace("*", "", regex=False).str.strip()
df = df[df["Fiscal Year"].str.match(r"^\d{4}/\d{2}$")]

# 3. Drop the empty column
df = df.drop(columns=["Unnamed: 7"])

# 4. Convert GDP from Rs. million to Rs. billion
df["GDP"] = df["GDP"] / 1000

# 5. Rename columns to clean, SQL-friendly names
df = df.rename(columns={
    "Fiscal Year": "fy_ad",
    "Nepalese Year": "fy_bs",
    "M1": "m1_pct_gdp",
    "M2": "m2_pct_gdp",
    "Domestic Credit": "domestic_credit_pct_gdp",
    "Claims on Private Sector": "private_credit_pct_gdp",
    "Deposits": "deposits_pct_gdp",
    "GDP": "gdp_nominal_npr_bn",
})

# 6. Reshape wide -> long: one row per year per indicator
long = df.melt(id_vars=["fy_ad", "fy_bs"], var_name="indicator", value_name="value")

# 7. Save
long.to_csv(OUT_FILE, index=False)
print(long.head(10))
print(f"{len(long)} rows saved to {OUT_FILE}")

# 8. Sanity check
years = long["fy_ad"].nunique()
print(f"Years: {years} ({long['fy_ad'].min()} to {long['fy_ad'].max()})")
assert years == 52, f"Expected 52 years, got {years}"