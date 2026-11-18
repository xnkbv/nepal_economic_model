import pandas as pd
from pathlib import Path

RAW_FILE = Path("data/raw/nrb/nrb_cmefs_tables_annual_2082-83.xlsx")
OUT_FILE = Path("data/processed/nrb_annual_indicators.csv")


def read_annual_sheet(sheet, first_data_row, columns):
    """Read one NRB annual annex sheet and return it in long format."""
    # Read without headers, starting at the first row of data
    df = pd.read_excel(RAW_FILE, sheet_name=sheet, header=None, skiprows=first_data_row - 1)

    # Keep only the columns we named, and apply our names
    df = df.iloc[:, :len(columns)]
    df.columns = columns

    # Year labels can look like "2025/26 P" or "2010/11*"
    year_label = df["fy_ad"].astype(str).str.strip()
    df["status"] = (year_label.str.extract(r"([RP])$")[0]
                    .map({"R": "revised", "P": "preliminary"})
                    .fillna("final"))
    df["fy_ad"] = year_label.str.extract(r"^(\d{4}/\d{2})")[0]
    df["fy_bs"] = df["fy_bs"].astype(str).str.extract(r"(\d{4}/\d{2})")[0]

    # Rows without a valid year are footnotes -> drop them
    df = df.dropna(subset=["fy_ad"])

    # Columns starting with "_" are ones we deliberately don't keep
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])

    # Wide -> long
    long = df.melt(id_vars=["fy_ad", "fy_bs", "status"], var_name="indicator", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")   # "-" becomes empty
    long["source_sheet"] = sheet.strip()
    return long


# ---------- Sheets ----------

# A26: ratios to GDP. Its GDP column duplicates A1, so we skip it here.
credit_pct = read_annual_sheet("A26.Monetary Ind. % of GDP ", 5, [
    "fy_ad", "fy_bs", "m1_pct_gdp", "m2_pct_gdp", "domestic_credit_pct_gdp",
    "private_credit_pct_gdp", "deposits_pct_gdp", "_blank", "_gdp_duplicate"])

# A1: GDP. Real GDP level mixes base years, so we keep only growth rates.
gdp = read_annual_sheet("A1.GDP-annex ", 6, [
    "fy_ad", "fy_bs", "gdp_nominal_npr_bn", "_real_gdp_mixed_base",
    "gdp_nominal_growth_pct", "gdp_real_growth_pct"])

# A25.1: money and credit in Rs. million, plus annual growth rates
money = read_annual_sheet("A25.1Monetary Indicators (A)", 6, [
    "fy_ad", "fy_bs", "m1_npr_bn", "m2_npr_bn", "domestic_credit_npr_bn",
    "private_credit_npr_bn", "deposits_npr_bn", "m1_growth_pct", "m2_growth_pct",
    "domestic_credit_growth_pct", "private_credit_growth_pct", "deposits_growth_pct"])

# ---------- Combine and fix units ----------
data = pd.concat([credit_pct, gdp, money], ignore_index=True)

# NRB publishes rupee amounts in millions -> convert to billions
in_millions = data["indicator"].str.endswith("_npr_bn")
data.loc[in_millions, "value"] = data.loc[in_millions, "value"] / 1000

data.to_csv(OUT_FILE, index=False)
print(f"{len(data)} rows saved to {OUT_FILE}\n")

# ---------- Validation ----------

# Check 1: coverage per indicator
summary = data.groupby("indicator").agg(
    years=("fy_ad", "nunique"), first=("fy_ad", "min"),
    last=("fy_ad", "max"), missing=("value", lambda v: v.isna().sum()))
print(summary, "\n")

# Check 2: each indicator appears once per year
assert not data.duplicated(["fy_ad", "indicator"]).any(), "Duplicate year-indicator rows!"

# Check 3: cross-check two sheets against each other
#   private credit (A25.1) / nominal GDP (A1) x 100 should equal the ratio in A26
wide = data.pivot(index="fy_ad", columns="indicator", values="value")
recomputed = wide["private_credit_npr_bn"] / wide["gdp_nominal_npr_bn"] * 100
gap = (recomputed - wide["private_credit_pct_gdp"]).abs().loc["2011/12":]
print(f"Cross-check, largest gap since 2011/12: {gap.max():.4f} percentage points")
assert gap.max() < 0.01, "A25.1 and A26 disagree!"

print("All checks passed.")