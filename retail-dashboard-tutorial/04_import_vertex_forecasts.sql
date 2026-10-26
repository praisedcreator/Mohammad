-- USER-ADAPTED NORMALIZATION TEMPLATE. Do not run unchanged.
-- Replace YOUR_PROJECT_ID and each YOUR_VERTEX_OUTPUT_DATASET / job timestamp.
-- Inspect the actual Vertex job's export location and generated table schemas.
-- The model target must be units_sold, with 30 future null-target rows per series.
-- If its output structure differs, adapt predicted_units_sold.value below.

-- Strict first checks: failed/omitted forecasts must be investigated, not set to 0.
-- Adapt these identifiers to the error tables created by YOUR batch job.
ASSERT (SELECT COUNT(*) = 0
  FROM `YOUR_PROJECT_ID.YOUR_VERTEX_OUTPUT_DATASET.errors_validation_YOUR_JOB_TIMESTAMP`)
  AS 'Stop: batch input validation errors exist. Inspect the error table.';
ASSERT (SELECT COUNT(*) = 0
  FROM `YOUR_PROJECT_ID.YOUR_VERTEX_OUTPUT_DATASET.errors_YOUR_JOB_TIMESTAMP`)
  AS 'Stop: batch inference errors exist. Inspect the error table.';

-- Stage only the inventory series and dates required by this dashboard.
-- A failed CAST or missing output table stops the script before forecast replacement.
CREATE OR REPLACE TABLE `YOUR_PROJECT_ID.retail_demo.vertex_forecast_staging` AS
WITH series_map AS (
  SELECT sku, store, as_of,
    TO_JSON_STRING(STRUCT(store AS store, sku AS sku)) AS series_id
  FROM `YOUR_PROJECT_ID.retail_demo.inventory`
)
SELECT m.sku, m.store, CAST(p.date AS DATE) AS forecast_date,
  CAST(p.predicted_units_sold.value AS FLOAT64) AS units,
  'VERTEX_AUTOML' AS forecast_source
FROM `YOUR_PROJECT_ID.YOUR_VERTEX_OUTPUT_DATASET.predictions_YOUR_JOB_TIMESTAMP` AS p
JOIN series_map AS m ON p.series_id = m.series_id
WHERE CAST(p.date AS DATE) BETWEEN DATE_ADD(m.as_of, INTERVAL 1 DAY)
                              AND DATE_ADD(m.as_of, INTERVAL 30 DAY);

ASSERT (SELECT COUNT(*) > 0 FROM `YOUR_PROJECT_ID.retail_demo.inventory`)
  AS 'Stop: inventory has no series to validate.';

-- Every inventory series needs exactly 30 unique dates with finite nonnegative units.
-- Nothing is padded, interpolated, clipped, averaged, or silently replaced with zero.
ASSERT NOT EXISTS (
  SELECT i.sku, i.store, i.as_of
  FROM `YOUR_PROJECT_ID.retail_demo.inventory` AS i
  LEFT JOIN `YOUR_PROJECT_ID.retail_demo.vertex_forecast_staging` AS f
    ON f.sku = i.sku AND f.store = i.store
    AND f.forecast_date BETWEEN DATE_ADD(i.as_of, INTERVAL 1 DAY)
                           AND DATE_ADD(i.as_of, INTERVAL 30 DAY)
  GROUP BY i.sku, i.store, i.as_of
  HAVING COUNT(f.forecast_date) != 30 OR COUNT(DISTINCT f.forecast_date) != 30
    OR COUNTIF(f.forecast_date IS NOT NULL AND (
      f.units IS NULL OR f.units < 0 OR IS_NAN(f.units) OR IS_INF(f.units)
    )) > 0
) AS 'Stop: a series has missing, duplicate, null, negative, or nonfinite predictions.';

-- This replacement occurs ONLY after all preceding assertions succeed.
-- Save the previous forecast table separately first if you need an audit trail.
CREATE OR REPLACE TABLE `YOUR_PROJECT_ID.retail_demo.forecast_daily` AS
SELECT sku, store, forecast_date, units, forecast_source
FROM `YOUR_PROJECT_ID.retail_demo.vertex_forecast_staging`;

SELECT sku, product, forecast_source, forecast_days, forecast_valid, exception_flags
FROM `YOUR_PROJECT_ID.retail_demo.inventory_exceptions`
ORDER BY sku;
