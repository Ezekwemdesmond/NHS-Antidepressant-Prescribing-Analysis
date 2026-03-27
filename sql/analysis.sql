

USE nhs_prescribing;



-- SECTION 1 — NATIONAL OVERVIEW

-- 1.1 Total items and total cost nationally across the entire period

SELECT
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS overall_mean_cost_per_item
FROM prescriptions p;


-- 1.2 Total items and total cost by year — national annual summary

SELECT
    d.`year`,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item
FROM prescriptions p
JOIN dates d ON p.date_id = d.date_id
GROUP BY d.`year`
ORDER BY d.`year`;


-- 1.3 Annual mean monthly cost — how average monthly spend changed per year

SELECT
    d.`year`,
    ROUND(SUM(p.nic) / COUNT(DISTINCT d.year_month), 2) AS mean_monthly_cost_gbp
FROM prescriptions p
JOIN dates d ON p.date_id = d.date_id
GROUP BY d.`year`
ORDER BY d.`year`;


-- 1.4 Annual min, max, and mean monthly cost — distribution by year

SELECT
    d.`year`,
    ROUND(MIN(monthly.monthly_cost), 2)     AS min_monthly_cost,
    ROUND(MAX(monthly.monthly_cost), 2)     AS max_monthly_cost,
    ROUND(AVG(monthly.monthly_cost), 2)     AS mean_monthly_cost
FROM (
    SELECT
        d.`year`,
        d.year_month,
        SUM(p.nic) AS monthly_cost
    FROM prescriptions p
    JOIN dates d ON p.date_id = d.date_id
    GROUP BY d.`year`, d.year_month
) AS monthly
JOIN dates d ON monthly.year_month = d.year_month
GROUP BY d.`year`
ORDER BY d.`year`;



-- SECTION 2 — MONTHLY TRENDS


-- 2.1 Monthly national total items and cost — full time series

SELECT
    d.year_month,
    d.`year`,
    d.month_name,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item
FROM prescriptions p
JOIN dates d ON p.date_id = d.date_id
GROUP BY d.year_month, d.`year`, d.month_name
ORDER BY d.year_month;


-- 2.2 Year-over-year change in monthly cost
-- Identifies when the cost reduction happened most sharply.

SELECT
    this_year.year_month,
    ROUND(this_year.monthly_cost, 2)                                        AS current_cost,
    ROUND(last_year.monthly_cost, 2)                                        AS prior_year_cost,
    ROUND(this_year.monthly_cost - last_year.monthly_cost, 2)               AS cost_change,
    ROUND(
        (this_year.monthly_cost - last_year.monthly_cost)
        / last_year.monthly_cost * 100
    , 1)                                                                    AS pct_change
FROM (
    SELECT d.year_month, d.`year`, d.`month`, SUM(p.nic) AS monthly_cost
    FROM prescriptions p
    JOIN dates d ON p.date_id = d.date_id
    GROUP BY d.year_month, d.`year`, d.`month`
) AS this_year
LEFT JOIN (
    SELECT d.year_month, d.`year`, d.`month`, SUM(p.nic) AS monthly_cost
    FROM prescriptions p
    JOIN dates d ON p.date_id = d.date_id
    GROUP BY d.year_month, d.`year`, d.`month`
) AS last_year
    ON  this_year.`month` = last_year.`month`
    AND this_year.`year`  = last_year.`year` + 1
ORDER BY this_year.year_month;



-- SECTION 3 — DRUG-LEVEL ANALYSIS


-- 3.1 Top 10 most prescribed antidepressants by total items (2021–2025)

SELECT
    dr.bnf_chemical_substance,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item
FROM prescriptions p
JOIN drugs dr ON p.drug_id = dr.drug_id
GROUP BY dr.bnf_chemical_substance
ORDER BY total_items DESC
LIMIT 10;


-- 3.2 Top 10 most expensive antidepressants by total cost (2021–2025)
-- Highlights drugs like Venlafaxine that are expensive despite lower volume.

SELECT
    dr.bnf_chemical_substance,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item
FROM prescriptions p
JOIN drugs dr ON p.drug_id = dr.drug_id
GROUP BY dr.bnf_chemical_substance
ORDER BY total_cost_gbp DESC
LIMIT 10;


-- 3.3 Items and cost percentage contribution for every drug
-- Shows which drugs are cost-efficient vs expensive.

SELECT
    dr.bnf_chemical_substance,
    SUM(p.items)                                                        AS total_items,
    ROUND(SUM(p.nic), 2)                                                AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)                                 AS mean_cost_per_item,
    ROUND(SUM(p.items) * 100.0 / SUM(SUM(p.items)) OVER (), 2)         AS pct_of_total_items,
    ROUND(SUM(p.nic)   * 100.0 / SUM(SUM(p.nic))   OVER (), 2)         AS pct_of_total_cost
FROM prescriptions p
JOIN drugs dr ON p.drug_id = dr.drug_id
GROUP BY dr.bnf_chemical_substance
ORDER BY total_items DESC;


-- 3.4 Annual trend for the top 5 drugs by items

SELECT
    d.`year`,
    dr.bnf_chemical_substance,
    SUM(p.items)                AS total_items,
    ROUND(SUM(p.nic), 2)        AS total_cost_gbp
FROM prescriptions p
JOIN dates d  ON p.date_id = d.date_id
JOIN drugs dr ON p.drug_id = dr.drug_id
WHERE dr.bnf_chemical_substance IN (
    SELECT bnf_chemical_substance
    FROM (
        SELECT dr2.bnf_chemical_substance
        FROM prescriptions p2
        JOIN drugs dr2 ON p2.drug_id = dr2.drug_id
        GROUP BY dr2.bnf_chemical_substance
        ORDER BY SUM(p2.items) DESC
        LIMIT 5
    ) AS top5
)
GROUP BY d.`year`, dr.bnf_chemical_substance
ORDER BY d.`year`, total_items DESC;


-- SECTION 4 — REGIONAL ANALYSIS


-- 4.1 Annual items and cost by region

SELECT
    r.region_name,
    d.`year`,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item
FROM prescriptions p
JOIN dates   d ON p.date_id   = d.date_id
JOIN regions r ON p.region_id = r.region_id
GROUP BY r.region_name, d.`year`
ORDER BY r.region_name, d.`year`;


-- 4.2 Percentage change in items and cost per region (2021 vs 2025)
SELECT
    r.region_name,
    SUM(CASE WHEN d.`year` = 2021 THEN p.items ELSE 0 END)          AS items_2021,
    SUM(CASE WHEN d.`year` = 2025 THEN p.items ELSE 0 END)          AS items_2025,
    ROUND(
        (SUM(CASE WHEN d.`year` = 2025 THEN p.items ELSE 0 END) -
         SUM(CASE WHEN d.`year` = 2021 THEN p.items ELSE 0 END))
        / SUM(CASE WHEN d.`year` = 2021 THEN p.items ELSE 0 END) * 100
    , 1)                                                             AS items_pct_change,
    ROUND(SUM(CASE WHEN d.`year` = 2021 THEN p.nic ELSE 0 END), 2)  AS cost_2021,
    ROUND(SUM(CASE WHEN d.`year` = 2025 THEN p.nic ELSE 0 END), 2)  AS cost_2025,
    ROUND(
        (SUM(CASE WHEN d.`year` = 2025 THEN p.nic ELSE 0 END) -
         SUM(CASE WHEN d.`year` = 2021 THEN p.nic ELSE 0 END))
        / SUM(CASE WHEN d.`year` = 2021 THEN p.nic ELSE 0 END) * 100
    , 1)                                                             AS cost_pct_change
FROM prescriptions p
JOIN dates   d ON p.date_id   = d.date_id
JOIN regions r ON p.region_id = r.region_id
WHERE d.`year` IN (2021, 2025)
GROUP BY r.region_name
ORDER BY items_pct_change DESC;


-- 4.3 Monthly items and cost by region — full time series

SELECT
    d.year_month,
    d.`year`,
    r.region_name,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item
FROM prescriptions p
JOIN dates   d ON p.date_id   = d.date_id
JOIN regions r ON p.region_id = r.region_id
GROUP BY d.year_month, d.`year`, r.region_name
ORDER BY d.year_month, r.region_name;


-- SECTION 5 — SERTRALINE DEEP DIVE


-- 5.1 Sertraline overall summary — items, cost, and contribution percentages

SELECT
    dr.bnf_chemical_substance,
    SUM(p.items)                                                            AS total_items,
    ROUND(SUM(p.nic), 2)                                                    AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)                                     AS mean_cost_per_item,
    ROUND(SUM(p.items) * 100.0 / (SELECT SUM(items) FROM prescriptions), 2) AS pct_of_total_items,
    ROUND(SUM(p.nic)   * 100.0 / (SELECT SUM(nic)   FROM prescriptions), 2) AS pct_of_total_cost
FROM prescriptions p
JOIN drugs dr ON p.drug_id = dr.drug_id
WHERE dr.bnf_chemical_substance = 'Sertraline hydrochloride';


-- 5.2 Sertraline annual cost trend

SELECT
    d.`year`,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item
FROM prescriptions p
JOIN dates d  ON p.date_id = d.date_id
JOIN drugs dr ON p.drug_id = dr.drug_id
WHERE dr.bnf_chemical_substance = 'Sertraline hydrochloride'
GROUP BY d.`year`
ORDER BY d.`year`;


-- 5.3 Sertraline monthly cost trend — full time series

SELECT
    d.year_month,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item
FROM prescriptions p
JOIN dates d  ON p.date_id = d.date_id
JOIN drugs dr ON p.drug_id = dr.drug_id
WHERE dr.bnf_chemical_substance = 'Sertraline hydrochloride'
GROUP BY d.year_month
ORDER BY d.year_month;


-- 5.4 Sertraline mean cost per item by region

SELECT
    r.region_name,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item
FROM prescriptions p
JOIN regions r ON p.region_id = r.region_id
JOIN drugs  dr ON p.drug_id   = dr.drug_id
WHERE dr.bnf_chemical_substance = 'Sertraline hydrochloride'
GROUP BY r.region_name
ORDER BY mean_cost_per_item DESC;


-- 5.5 All drugs — cost per item vs national average
-- Negative pct_above_below_national_avg means cheaper than average.

SELECT
    dr.bnf_chemical_substance,
    SUM(p.items)                                AS total_items,
    ROUND(SUM(p.nic), 2)                        AS total_cost_gbp,
    ROUND(SUM(p.nic) / SUM(p.items), 2)         AS mean_cost_per_item,
    ROUND(
        (SUM(p.nic) / SUM(p.items)) /
        (SELECT SUM(nic) / SUM(items) FROM prescriptions)
        * 100 - 100
    , 1)                                        AS pct_above_below_national_avg
FROM prescriptions p
JOIN drugs dr ON p.drug_id = dr.drug_id
GROUP BY dr.bnf_chemical_substance
ORDER BY total_items DESC
LIMIT 10;


-- SECTION 6 — FORECAST QUERIES
-- Requires 04_forecast_schema.sql to have been run and forecast.py output
-- loaded into MySQL via loader.py before these queries will return results.


-- 6.1 Full forecast table — historical fitted values and 12-month forecast
-- is_forecast=0 for historical rows, is_forecast=1 for forecast rows.

SELECT
    `year_month`,
    actual_items,
    ROUND(actual_nic, 2)         AS actual_nic,
    ROUND(actual_cpi, 4)         AS actual_cpi,
    ROUND(items_forecast, 0)     AS items_forecast,
    ROUND(nic_forecast, 2)       AS nic_forecast,
    ROUND(cpi_forecast, 4)       AS cpi_forecast,
    is_forecast
FROM forecast
ORDER BY `year_month`;


-- 6.2 12-month forward forecast only — the projected period
-- Shows items, cost and cost per item with 80% confidence intervals.

SELECT
    `year_month`,
    ROUND(items_forecast, 0)     AS items_forecast,
    ROUND(items_lower, 0)        AS items_lower_80,
    ROUND(items_upper, 0)        AS items_upper_80,
    ROUND(nic_forecast, 2)       AS nic_forecast,
    ROUND(nic_lower, 2)          AS nic_lower_80,
    ROUND(nic_upper, 2)          AS nic_upper_80,
    ROUND(cpi_forecast, 4)       AS cpi_forecast,
    ROUND(cpi_lower, 4)          AS cpi_lower_80,
    ROUND(cpi_upper, 4)          AS cpi_upper_80
FROM forecast
WHERE is_forecast = 1
ORDER BY `year_month`;


-- 6.3 Forecast summary — total projected items and cost for the 12-month period
-- Provides the headline numbers for the Forecast KPI cards in Power BI.

SELECT
    COUNT(*)                         AS forecast_months,
    ROUND(SUM(items_forecast), 0)    AS total_forecast_items,
    ROUND(SUM(nic_forecast), 2)      AS total_forecast_nic,
    ROUND(
        SUM(nic_forecast) / SUM(items_forecast), 4
    )                                AS avg_forecast_cpi
FROM forecast
WHERE is_forecast = 1;


-- 6.4 Actual vs forecast comparison — model accuracy on historical period
-- Compares actual values against Prophet fitted values for the training period.
-- Lower mean absolute percentage error (MAPE) = better model accuracy.

SELECT
    `year_month`,
    actual_items,
    ROUND(items_forecast, 0)                                AS fitted_items,
    ROUND(
        ABS(actual_items - items_forecast)
        / actual_items * 100
    , 2)                                                    AS items_abs_pct_error,
    ROUND(actual_nic, 2)                                    AS actual_nic,
    ROUND(nic_forecast, 2)                                  AS fitted_nic,
    ROUND(
        ABS(actual_nic - nic_forecast)
        / actual_nic * 100
    , 2)                                                    AS nic_abs_pct_error
FROM forecast
WHERE is_forecast = 0
  AND actual_items IS NOT NULL
ORDER BY `year_month`;