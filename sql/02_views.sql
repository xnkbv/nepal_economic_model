-- =====================================================================
-- Nepal Debt Cycle Monitor: analysis views
-- One view per hypothesis. Run this AFTER loading the data.
-- Re-running the loader drops these views, so run this file again after it.
-- =====================================================================

DROP VIEW IF EXISTS v_h5_wages_by_province, v_h5_real_wages, v_h4_external_funding,
                    v_h3_money_demand, v_h1_debt_cycle, v_annual_wide CASCADE;

-- ---------- Base view: one row per year, key indicators as columns ----------
-- Pivots the long fact table so the hypothesis views can do simple arithmetic.
CREATE VIEW v_annual_wide AS
SELECT
    y.fy_id,
    y.fy_ad,
    y.fy_bs,
    y.is_comparable,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'private_credit_npr_bn')      AS private_credit_npr_bn,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'private_credit_pct_gdp')     AS private_credit_pct_gdp,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'private_credit_growth_pct')  AS private_credit_growth_pct,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'deposits_growth_pct')        AS deposits_growth_pct,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'gdp_nominal_npr_bn')         AS gdp_nominal_npr_bn,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'gdp_nominal_growth_pct')     AS gdp_nominal_growth_pct,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'gdp_real_growth_pct')        AS gdp_real_growth_pct,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'cpi_overall_index')          AS cpi_index,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'cpi_overall_inflation_pct')  AS cpi_inflation_pct,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'wage_index_avg')             AS wage_index,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'lending_rate_wavg_avg_pct')  AS lending_rate_pct,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'deposit_rate_wavg_avg_pct')  AS deposit_rate_pct,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'interbank_rate_avg_pct')     AS interbank_rate_pct,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'remittances_npr_bn')         AS remittances_npr_bn,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'remittances_pct_gdp')        AS remittances_pct_gdp,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'imports_npr_bn')             AS imports_npr_bn,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'exports_npr_bn')             AS exports_npr_bn,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'trade_balance_npr_bn')       AS trade_balance_npr_bn,
    MAX(f.value) FILTER (WHERE i.indicator_code = 'current_account_pct_gdp')    AS current_account_pct_gdp,
    -- the most cautious data flag of the year: preliminary > revised > final
    CASE WHEN BOOL_OR(f.status = 'preliminary') THEN 'preliminary'
         WHEN BOOL_OR(f.status = 'revised')     THEN 'revised'
         ELSE 'final' END                                                       AS data_status
FROM fact_annual f
JOIN dim_indicator   i ON i.indicator_id = f.indicator_id
JOIN dim_fiscal_year y ON y.fy_id = f.fy_id
GROUP BY y.fy_id, y.fy_ad, y.fy_bs, y.is_comparable;

-- ---------- H1: Where is Nepal in the debt cycle? ----------
-- Debt cycle signal: is private credit growing faster than the economy?
--   credit_gap_pp > 0  -> debt rising relative to income (boom)
--   credit_gap_pp < 0  -> debt shrinking relative to income (deleveraging)
-- Nominal credit is compared with NOMINAL GDP, so inflation does not distort the gap.
CREATE VIEW v_h1_debt_cycle AS
SELECT
    fy_id, fy_ad, is_comparable, data_status,
    private_credit_pct_gdp,
    private_credit_pct_gdp
        - LAG(private_credit_pct_gdp) OVER (ORDER BY fy_id)                     AS credit_to_gdp_change_pp,
    private_credit_growth_pct,
    gdp_nominal_growth_pct,
    private_credit_growth_pct - gdp_nominal_growth_pct                         AS credit_gap_pp,
    ((1 + private_credit_growth_pct / 100) / (1 + cpi_inflation_pct / 100) - 1) * 100
                                                                               AS real_credit_growth_pct,
    gdp_real_growth_pct
FROM v_annual_wide;

-- ---------- H3: Is money cheap but nobody wants to borrow? ----------
-- Real lending rate = what borrowing costs after inflation.
-- Loans growing slower than deposits = banks fill up with unlent money.
CREATE VIEW v_h3_money_demand AS
SELECT
    fy_id, fy_ad, is_comparable, data_status,
    lending_rate_pct,
    deposit_rate_pct,
    interbank_rate_pct,
    cpi_inflation_pct,
    lending_rate_pct - cpi_inflation_pct                                       AS real_lending_rate_pct,
    lending_rate_pct
        - LAG(lending_rate_pct) OVER (ORDER BY fy_id)                          AS lending_rate_change_pp,
    private_credit_growth_pct,
    deposits_growth_pct,
    private_credit_growth_pct - deposits_growth_pct                            AS loan_minus_deposit_growth_pp
FROM v_annual_wide
WHERE lending_rate_pct IS NOT NULL;           -- interest rate data starts in 2016/17

-- ---------- H4: Is household spending funded from abroad? ----------
CREATE VIEW v_h4_external_funding AS
SELECT
    fy_id, fy_ad, is_comparable, data_status,
    remittances_npr_bn,
    imports_npr_bn,
    exports_npr_bn,
    -trade_balance_npr_bn                                                      AS trade_deficit_npr_bn,
    remittances_npr_bn / NULLIF(-trade_balance_npr_bn, 0) * 100                AS remittance_cover_of_deficit_pct,
    remittances_npr_bn / NULLIF(imports_npr_bn, 0) * 100                       AS remittances_to_imports_pct,
    exports_npr_bn / NULLIF(imports_npr_bn, 0) * 100                           AS export_cover_of_imports_pct,
    (remittances_npr_bn / NULLIF(LAG(remittances_npr_bn) OVER (ORDER BY fy_id), 0) - 1) * 100
                                                                               AS remittance_growth_pct,
    remittances_pct_gdp,
    current_account_pct_gdp
FROM v_annual_wide
WHERE remittances_npr_bn IS NOT NULL;          -- remittance data starts in 2000/01

-- ---------- H5: Are workers better off? ----------
-- Both indices use 2023/24 = 100, so wage_index / cpi_index * 100 is a real wage index.
CREATE VIEW v_h5_real_wages AS
SELECT
    fy_id, fy_ad, is_comparable, data_status,
    wage_index,
    cpi_index,
    (wage_index / NULLIF(LAG(wage_index) OVER (ORDER BY fy_id), 0) - 1) * 100  AS wage_growth_pct,
    cpi_inflation_pct,
    ((wage_index / NULLIF(LAG(wage_index) OVER (ORDER BY fy_id), 0))
        / (1 + cpi_inflation_pct / 100) - 1) * 100                             AS real_wage_growth_pct,
    wage_index / cpi_index * 100                                               AS real_wage_index
FROM v_annual_wide
WHERE wage_index IS NOT NULL;                  -- wage data starts in 2004/05

-- ---------- H5 by province: year-on-year wage growth each quarter ----------
CREATE VIEW v_h5_wages_by_province AS
SELECT
    q.obs_date,
    y.fy_ad,
    q.region,
    q.status,
    q.value                                                                    AS wage_index,
    (q.value / NULLIF(LAG(q.value, 4) OVER (PARTITION BY q.region ORDER BY q.obs_date), 0) - 1) * 100
                                                                               AS wage_growth_yoy_pct
FROM fact_quarterly q
JOIN dim_indicator   i ON i.indicator_id = q.indicator_id
JOIN dim_fiscal_year y ON y.fy_id = q.fy_id
WHERE i.indicator_code = 'wage_index';