-- =====================================================================
-- Nepal Debt Cycle Monitor: star schema
-- Running this file rebuilds every table from scratch.
-- =====================================================================

DROP TABLE IF EXISTS fact_quarterly, fact_monthly, fact_annual,
                     dim_indicator, dim_fiscal_year CASCADE;

-- ---------- Dimension: fiscal years ----------
-- Nepal's fiscal year runs mid-July to mid-July.
-- fy_id is the calendar year the fiscal year starts in (2025 for 2025/26).
CREATE TABLE dim_fiscal_year (
    fy_id          SMALLINT    PRIMARY KEY,
    fy_ad          VARCHAR(7)  NOT NULL UNIQUE,   -- '2025/26'
    fy_bs          VARCHAR(7),                    -- '2082/83'
    fy_end_year    SMALLINT    NOT NULL,          -- 2026
    is_comparable  BOOLEAN     NOT NULL           -- TRUE from 2011/12 (after the 2010/11 break)
);

-- ---------- Dimension: indicators ----------
CREATE TABLE dim_indicator (
    indicator_id    SMALLINT     PRIMARY KEY,
    indicator_code  VARCHAR(60)  NOT NULL UNIQUE, -- 'private_credit_pct_gdp'
    indicator_name  VARCHAR(120) NOT NULL,        -- 'Private credit (% of GDP)'
    category        VARCHAR(30)  NOT NULL,        -- 'Credit', 'Trade', ...
    unit            VARCHAR(40)  NOT NULL,        -- '% of GDP', 'NPR billion', ...
    frequency       VARCHAR(10)  NOT NULL,        -- 'annual', 'monthly', 'quarterly'
    source_sheet    VARCHAR(80)  NOT NULL
);

-- ---------- Facts ----------
CREATE TABLE fact_annual (
    fy_id         SMALLINT NOT NULL REFERENCES dim_fiscal_year (fy_id),
    indicator_id  SMALLINT NOT NULL REFERENCES dim_indicator (indicator_id),
    value         DOUBLE PRECISION,
    status        VARCHAR(12) NOT NULL CHECK (status IN ('final', 'revised', 'preliminary')),
    PRIMARY KEY (fy_id, indicator_id)
);

CREATE TABLE fact_monthly (
    obs_date      DATE     NOT NULL,
    fy_id         SMALLINT NOT NULL REFERENCES dim_fiscal_year (fy_id),
    indicator_id  SMALLINT NOT NULL REFERENCES dim_indicator (indicator_id),
    value         DOUBLE PRECISION,
    PRIMARY KEY (obs_date, indicator_id)
);

CREATE TABLE fact_quarterly (
    obs_date      DATE        NOT NULL,
    fy_id         SMALLINT    NOT NULL REFERENCES dim_fiscal_year (fy_id),
    region        VARCHAR(20) NOT NULL,           -- 'nepal' or a province
    indicator_id  SMALLINT    NOT NULL REFERENCES dim_indicator (indicator_id),
    value         DOUBLE PRECISION,
    status        VARCHAR(12) NOT NULL CHECK (status IN ('final', 'revised', 'preliminary')),
    PRIMARY KEY (obs_date, region, indicator_id)
);
