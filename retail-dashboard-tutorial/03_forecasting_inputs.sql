-- Replace YOUR_PROJECT_ID. This file deliberately invents NO sales history.
CREATE TABLE IF NOT EXISTS `YOUR_PROJECT_ID.retail_demo.sales_daily` (
  sku STRING, store STRING, sale_date DATE, units_sold FLOAT64
);

-- Load real daily history before training. Each store-SKU-date must be unique.
-- A true zero-sales day is 0; an unknown/missing day must be investigated.
-- JSON of named fields gives a collision-safe combined series identifier.
CREATE OR REPLACE VIEW `YOUR_PROJECT_ID.retail_demo.sales_training` AS
SELECT TO_JSON_STRING(STRUCT(store AS store, sku AS sku)) AS series_id,
  store, sku, sale_date AS date, units_sold
FROM `YOUR_PROJECT_ID.retail_demo.sales_daily`;

-- Google requires >= 1,000 training rows. This is a minimum, not a quality target.
SELECT COUNT(*) AS training_rows,
  COUNTIF(sku IS NULL OR store IS NULL OR sale_date IS NULL
    OR units_sold IS NULL OR units_sold < 0
    OR IS_NAN(units_sold) OR IS_INF(units_sold)) AS invalid_rows
FROM `YOUR_PROJECT_ID.retail_demo.sales_daily`;

-- This query must return NO rows before you train or request a batch prediction.
SELECT sku, store, sale_date, COUNT(*) AS rows_per_day
FROM `YOUR_PROJECT_ID.retail_demo.sales_daily`
GROUP BY sku, store, sale_date
HAVING COUNT(*) != 1;

-- Use a model trained with Daily granularity, context window 56, horizon 30.
-- Future units_sold are genuinely unknown, so they are NULL, never fabricated.
CREATE OR REPLACE VIEW `YOUR_PROJECT_ID.retail_demo.forecasting_batch_input` AS
SELECT t.series_id, t.store, t.sku, t.date, t.units_sold
FROM `YOUR_PROJECT_ID.retail_demo.sales_training` AS t
JOIN `YOUR_PROJECT_ID.retail_demo.inventory` AS i USING (sku, store)
WHERE t.date BETWEEN DATE_SUB(i.as_of, INTERVAL 55 DAY) AND i.as_of
UNION ALL
SELECT TO_JSON_STRING(STRUCT(i.store AS store, i.sku AS sku)),
  i.store, i.sku, DATE_ADD(i.as_of, INTERVAL day_offset DAY),
  CAST(NULL AS FLOAT64)
FROM `YOUR_PROJECT_ID.retail_demo.inventory` AS i
CROSS JOIN UNNEST(GENERATE_ARRAY(1, 30)) AS day_offset;

-- All five series must report 56 valid history days and 30 future rows.
-- With an empty sales_daily table, history_rows = 0: STOP and load real history.
-- Do not submit the batch input until this readiness check passes for every SKU.
SELECT i.sku, i.store,
  COUNTIF(b.date <= i.as_of) AS history_rows,
  COUNT(DISTINCT IF(b.date <= i.as_of, b.date, NULL)) AS distinct_history_days,
  COUNTIF(b.date <= i.as_of AND (
    b.units_sold IS NULL OR b.units_sold < 0
    OR IS_NAN(b.units_sold) OR IS_INF(b.units_sold)
  )) AS invalid_history_rows,
  COUNTIF(b.date > i.as_of AND b.units_sold IS NULL) AS future_rows
FROM `YOUR_PROJECT_ID.retail_demo.inventory` AS i
JOIN `YOUR_PROJECT_ID.retail_demo.forecasting_batch_input` AS b USING (sku, store)
GROUP BY i.sku, i.store;

-- Run the full file AFTER loading history. These checks stop an empty or
-- incomplete dataset before it can become a model input.
ASSERT (
  SELECT COUNT(*) >= 1000 AND COUNTIF(
    sku IS NULL OR TRIM(sku) = '' OR store IS NULL OR TRIM(store) = ''
    OR sale_date IS NULL OR units_sold IS NULL OR units_sold < 0
    OR IS_NAN(units_sold) OR IS_INF(units_sold)
  ) = 0
  FROM `YOUR_PROJECT_ID.retail_demo.sales_daily`
) AS 'Load at least 1000 valid real sales rows before creating model inputs.';

ASSERT NOT EXISTS (
  SELECT sku, store, sale_date
  FROM `YOUR_PROJECT_ID.retail_demo.sales_daily`
  GROUP BY sku, store, sale_date
  HAVING COUNT(*) != 1
) AS 'Remove duplicate store-SKU dates before training.';

ASSERT NOT EXISTS (
  SELECT i.sku, i.store
  FROM `YOUR_PROJECT_ID.retail_demo.inventory` AS i
  LEFT JOIN `YOUR_PROJECT_ID.retail_demo.forecasting_batch_input` AS b
    USING (sku, store)
  GROUP BY i.sku, i.store, i.as_of
  HAVING COUNTIF(b.date <= i.as_of) != 56
    OR COUNT(DISTINCT IF(b.date <= i.as_of, b.date, NULL)) != 56
    OR COUNTIF(b.date <= i.as_of AND (
      b.units_sold IS NULL OR b.units_sold < 0
      OR IS_NAN(b.units_sold) OR IS_INF(b.units_sold)
    )) > 0
    OR COUNTIF(b.date > i.as_of AND b.units_sold IS NULL) != 30
) AS 'Each inventory series needs 56 valid history days and 30 future rows.';

-- Use physical tables as model inputs after the checks pass.
CREATE OR REPLACE TABLE `YOUR_PROJECT_ID.retail_demo.sales_training_export` AS
SELECT * FROM `YOUR_PROJECT_ID.retail_demo.sales_training`;

CREATE OR REPLACE TABLE `YOUR_PROJECT_ID.retail_demo.forecasting_batch_input_export` AS
SELECT * FROM `YOUR_PROJECT_ID.retail_demo.forecasting_batch_input`;
