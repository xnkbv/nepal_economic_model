import pandas as pd
from pathlib import Path

RAW_FILE = Path("data/raw/nrb/nrb_cmefs_tables_annual_2082-83.xlsx")
OUT_ANNUAL = Path("data/processed/nrb_annual_indicators.csv")
OUT_MONTHLY = Path("data/processed/nrb_monthly_indicators.csv")
OUT_QUARTERLY = Path("data/processed/nrb_quarterly_wages.csv")

MONTHS = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
          "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12}


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


def read_monthly_sheet(sheet, first_data_row, columns):
    """Read an NRB monthly sheet where the fiscal year is written only on its first month."""
    df = pd.read_excel(RAW_FILE, sheet_name=sheet, header=None, skiprows=first_data_row - 1)
    df = df.iloc[:, :len(columns)]
    df.columns = columns

    # Drop empty rows at the bottom, then copy the fiscal year down to every month
    df = df.dropna(subset=["month"])
    df["fy_ad"] = df["fy_ad"].ffill()

    # Build a real date. Nepal's fiscal year runs mid-July to mid-July:
    # Aug-Dec belong to the first calendar year, Jan-Jul to the second.
    month_num = df["month"].str.strip().map(MONTHS)
    first_year = df["fy_ad"].str[:4].astype(int)
    year = first_year.where(month_num >= 8, first_year + 1)
    df["date"] = pd.to_datetime(dict(year=year, month=month_num, day=15))
    df = df.drop(columns=["month"])

    long = df.melt(id_vars=["date", "fy_ad"], var_name="indicator", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long["source_sheet"] = sheet.strip()
    return long


def read_quarterly_sheet(sheet, first_data_row, columns):
    """Read an NRB quarterly sheet whose rows are labelled like "2026 AprilR"."""
    df = pd.read_excel(RAW_FILE, sheet_name=sheet, header=None, skiprows=first_data_row - 1)
    df = df.iloc[:, :len(columns)]
    df.columns = columns
    df = df.dropna(subset=["period"])

    # "2026 AprilR" -> year 2026, month April, status revised
    label = df["period"].astype(str).str.strip()
    df["status"] = (label.str.extract(r"([RP])$")[0]
                    .map({"R": "revised", "P": "preliminary"})
                    .fillna("final"))
    year = label.str.extract(r"^(\d{4})")[0].astype(int)
    month_num = label.str.extract(r"^\d{4}\s+([A-Z][a-z]+)")[0].map(MONTHS)
    df["date"] = pd.to_datetime(dict(year=year, month=month_num, day=15))

    # Fiscal year: Aug-Dec start a new fiscal year, Jan-Jul end one
    first_year = year.where(month_num >= 8, year - 1)
    df["fy_ad"] = first_year.astype(str) + "/" + ((first_year + 1) % 100).astype(str).str.zfill(2)

    df = df.drop(columns=["period"] + [c for c in df.columns if c.startswith("_")])
    long = df.melt(id_vars=["date", "fy_ad", "status"], var_name="series", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long["source_sheet"] = sheet.strip()
    return long


# ---------- Annual sheets ----------

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

# A11: foreign trade in Rs. million (column A of this sheet is empty)
#   Growth of the trade balance is dropped: % change of a negative number is misleading.
trade = read_annual_sheet("A11.Trade_Annex_Annual", 5, [
    "_empty", "fy_ad", "fy_bs",
    "exports_npr_bn", "imports_npr_bn", "trade_balance_npr_bn", "total_trade_npr_bn",
    "exports_growth_pct", "imports_growth_pct", "_trade_balance_growth", "total_trade_growth_pct",
    "exports_pct_gdp", "imports_pct_gdp", "trade_balance_pct_gdp", "total_trade_pct_gdp"])

# A13: balance of payments in Rs. million (column A of this sheet is empty)
bop = read_annual_sheet("A.13BoP-annex-annual", 5, [
    "_empty", "fy_ad", "fy_bs",
    "net_exports_gs_npr_bn", "current_account_npr_bn", "bop_balance_npr_bn", "remittances_npr_bn",
    "net_exports_gs_pct_gdp", "current_account_pct_gdp", "bop_balance_pct_gdp", "remittances_pct_gdp"])

# A2: consumer price index (2023/24 = 100) and inflation
cpi = read_annual_sheet("A2.CPI_Annual ", 6, [
    "fy_ad", "fy_bs", "cpi_overall_index", "cpi_food_index", "cpi_nonfood_index",
    "cpi_overall_inflation_pct", "cpi_food_inflation_pct", "cpi_nonfood_inflation_pct"])

# ---------- Monthly sheets ----------

# A24: interest rates (% per year), mid-month, commercial banks
rates = read_monthly_sheet("A24.Interest Rates Series", 6, [
    "fy_ad", "month", "interbank_rate_pct", "tbill_91d_rate_pct",
    "deposit_rate_wavg_pct", "lending_rate_wavg_pct", "base_rate_pct"])

# Annual average of each rate, so it can sit next to the annual credit data
rates_annual = rates.groupby(["fy_ad", "indicator"], as_index=False).agg(
    value=("value", "mean"), months=("value", "count"))
assert (rates_annual["months"] == 12).all(), "A fiscal year does not have 12 months of rates!"
rates_annual = rates_annual.drop(columns="months")
rates_annual["indicator"] = rates_annual["indicator"].str.replace("_pct", "_avg_pct")
rates_annual["fy_bs"] = None
rates_annual["status"] = "final"
rates_annual["source_sheet"] = "A24.Interest Rates Series (annual average)"

# ---------- Quarterly sheets ----------

# A7: salary and wage index (2023/24 = 100) for Nepal and each province.
#   NRB's own % growth columns are dropped: we calculate growth ourselves in SQL.
wages = read_quarterly_sheet("A7.SWI-ProvincialSeries", 5, [
    "period", "_nepali_period",
    "koshi", "_g1", "madhesh", "_g2", "bagmati", "_g3", "gandaki", "_g4",
    "lumbini", "_g5", "karnali", "_g6", "sudurpashchim", "_g7", "nepal", "_g8"])
wages = wages.rename(columns={"series": "region"})
wages["indicator"] = "wage_index"

# Annual average of the national index (4 quarters per fiscal year)
national = wages[wages["region"] == "nepal"]
wages_annual = national.groupby("fy_ad", as_index=False).agg(
    value=("value", "mean"), quarters=("value", "count"),
    status=("status", lambda s: "preliminary" if (s == "preliminary").any()
            else "revised" if (s == "revised").any() else "final"))
assert (wages_annual["quarters"] == 4).all(), "A fiscal year does not have 4 quarters of wages!"
wages_annual = wages_annual.drop(columns="quarters")
wages_annual["indicator"] = "wage_index_avg"
wages_annual["source_sheet"] = "A7.SWI-ProvincialSeries (annual average, Nepal)"

# ---------- Combine and fix units ----------
data = pd.concat([credit_pct, gdp, money, trade, bop, cpi], ignore_index=True)

# NRB publishes rupee amounts in millions -> convert to billions
in_millions = data["indicator"].str.endswith("_npr_bn")
data.loc[in_millions, "value"] = data.loc[in_millions, "value"] / 1000

# Fill in the Nepali year for the rate averages from the other sheets
bs_lookup = data.drop_duplicates("fy_ad").set_index("fy_ad")["fy_bs"]
rates_annual["fy_bs"] = rates_annual["fy_ad"].map(bs_lookup)
wages_annual["fy_bs"] = wages_annual["fy_ad"].map(bs_lookup)
data = pd.concat([data, rates_annual, wages_annual], ignore_index=True)

data.to_csv(OUT_ANNUAL, index=False)
rates.to_csv(OUT_MONTHLY, index=False)
wages.to_csv(OUT_QUARTERLY, index=False)
print(f"{len(data)} annual rows saved to {OUT_ANNUAL}")
print(f"{len(rates)} monthly rows saved to {OUT_MONTHLY}")
print(f"{len(wages)} quarterly rows saved to {OUT_QUARTERLY}\n")

# ---------- Validation ----------

# Check 1: coverage per indicator
summary = data.groupby("indicator").agg(
    years=("fy_ad", "nunique"), first=("fy_ad", "min"),
    last=("fy_ad", "max"), missing=("value", lambda v: v.isna().sum()))
print(summary, "\n")

# Check 2: each indicator appears once per year (annual) and once per date (monthly)
assert not data.duplicated(["fy_ad", "indicator"]).any(), "Duplicate year-indicator rows!"
assert not rates.duplicated(["date", "indicator"]).any(), "Duplicate date-indicator rows!"

# Check 3: cross-check two sheets against each other
#   private credit (A25.1) / nominal GDP (A1) x 100 should equal the ratio in A26
wide = data.pivot(index="fy_ad", columns="indicator", values="value")
recomputed = wide["private_credit_npr_bn"] / wide["gdp_nominal_npr_bn"] * 100
gap = (recomputed - wide["private_credit_pct_gdp"]).abs().loc["2011/12":]
print(f"Cross-check, largest gap since 2011/12: {gap.max():.4f} percentage points")
assert gap.max() < 0.01, "A25.1 and A26 disagree!"

# Check 4: interest rates must be plausible (between 0% and 25%)
assert rates["value"].between(0, 25).all(), "An interest rate is outside 0-25%!"

# Check 5: trade balance must equal exports minus imports
balance_gap = (wide["exports_npr_bn"] - wide["imports_npr_bn"] - wide["trade_balance_npr_bn"]).abs()
assert balance_gap.max() < 0.01, "Trade balance is not exports minus imports!"

# Check 6: remittances as % of GDP (A13) must match remittances / GDP (A1)
remit_gap = (wide["remittances_npr_bn"] / wide["gdp_nominal_npr_bn"] * 100
             - wide["remittances_pct_gdp"]).abs().loc["2011/12":]
print(f"Remittance cross-check, largest gap since 2011/12: {remit_gap.max():.4f} percentage points")
assert remit_gap.max() < 0.01, "A13 and A1 disagree on remittances / GDP!"

# Check 7: both indices must equal 100 in their base year 2023/24
cpi_base = wide.loc["2023/24", "cpi_overall_index"]
wage_base = wide.loc["2023/24", "wage_index_avg"]
print(f"Base year 2023/24 -> CPI: {cpi_base:.2f}, wage index: {wage_base:.2f}")
assert abs(cpi_base - 100) < 0.5 and abs(wage_base - 100) < 0.5, "An index is not 100 in its base year!"

# Check 8: published inflation must equal the % change of the CPI index.
#   Before 2014/15 the index is "backlinked" (spliced onto the 2023/24 base), so it can
#   differ slightly from the inflation NRB originally published. We check from 2014/15.
recomputed_inflation = wide["cpi_overall_index"].pct_change() * 100
infl_gap = (recomputed_inflation - wide["cpi_overall_inflation_pct"]).abs().loc["2014/15":]
print(f"Inflation cross-check, largest gap since 2014/15: {infl_gap.max():.4f} percentage points")
assert infl_gap.max() < 0.01, "CPI inflation does not match the CPI index!"

# Check 9: no duplicate quarter-region rows
assert not wages.duplicated(["date", "region"]).any(), "Duplicate quarter-region rows!"

print("All checks passed.")