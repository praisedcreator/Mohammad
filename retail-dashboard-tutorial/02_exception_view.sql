-- Replace YOUR_PROJECT_ID. Run after 01_demo_data.sql.
-- Snapshot convention: as_of is the stock cut-off date. Forecasting starts tomorrow.
-- Confirmed FUTURE receipts arrive before demand on their expected date.
-- Due-today, overdue, and unconfirmed orders never become assumed supply.
-- This prototype supports replenishment lead times of 1-30 days; extend both the
-- forecast horizon and validation rules before using longer replenishment periods.
CREATE OR REPLACE VIEW `YOUR_PROJECT_ID.retail_demo.inventory_exceptions` AS
WITH forecast_stats AS (
  SELECT i.sku, i.store, i.as_of,
    COUNT(f.forecast_date) AS forecast_rows,
    COUNT(DISTINCT f.forecast_date) AS forecast_days,
    COUNTIF(f.forecast_date IS NOT NULL AND (
      f.units IS NULL OR f.units < 0 OR IS_NAN(f.units) OR IS_INF(f.units)
      OR f.forecast_source IS NULL OR TRIM(f.forecast_source) = ''
    )) AS invalid_forecast_rows,
    SUM(f.units) AS total_demand,
    STRING_AGG(DISTINCT f.forecast_source, ', ' ORDER BY f.forecast_source)
      AS forecast_source
  FROM `YOUR_PROJECT_ID.retail_demo.inventory` AS i
  LEFT JOIN `YOUR_PROJECT_ID.retail_demo.forecast_daily` AS f
    ON f.sku = i.sku AND f.store = i.store
    AND f.forecast_date BETWEEN DATE_ADD(i.as_of, INTERVAL 1 DAY)
                           AND DATE_ADD(i.as_of, INTERVAL 30 DAY)
  GROUP BY i.sku, i.store, i.as_of
), order_stats AS (
  SELECT i.sku, i.store, i.as_of,
    COUNTIF(o.status IN ('OPEN', 'PARTIALLY_RECEIVED')
      AND o.quantity > 0 AND o.expected_date < i.as_of) AS late_order_count,
    COUNTIF(o.order_id IS NOT NULL
      AND o.status IN ('OPEN', 'PARTIALLY_RECEIVED') AND (
        o.quantity IS NULL OR o.quantity < 0
        OR (o.quantity > 0 AND (o.expected_date IS NULL OR o.confirmed IS NULL))
      )) AS order_data_issue_count
  FROM `YOUR_PROJECT_ID.retail_demo.inventory` AS i
  LEFT JOIN `YOUR_PROJECT_ID.retail_demo.orders` AS o
    ON o.sku = i.sku AND o.store = i.store
  GROUP BY i.sku, i.store, i.as_of
), validated AS (
  SELECT i.*, COALESCE(f.forecast_days, 0) AS forecast_days,
    COALESCE(f.forecast_source, 'UNKNOWN') AS forecast_source, f.total_demand,
    COALESCE(o.late_order_count, 0) AS late_order_count,
    COALESCE(o.order_data_issue_count, 0) AS order_data_issue_count,
    COALESCE(
      i.as_of IS NOT NULL
      AND i.sku IS NOT NULL AND TRIM(i.sku) != ''
      AND i.store IS NOT NULL AND TRIM(i.store) != ''
      AND COUNT(*) OVER (PARTITION BY i.sku, i.store) = 1
      AND i.on_hand >= 0 AND i.reserved >= 0 AND i.blocked >= 0
      AND i.reserved + i.blocked <= i.on_hand
      AND i.lead_time_days BETWEEN 1 AND 30
      AND i.target_max_cover_days >= i.lead_time_days
      AND i.safety_stock >= 0 AND i.unit_cost >= 0
      AND NOT IS_NAN(i.unit_cost) AND NOT IS_INF(i.unit_cost), FALSE
    ) AS inventory_valid,
    COALESCE(f.forecast_rows = 30 AND f.forecast_days = 30
      AND f.invalid_forecast_rows = 0, FALSE) AS forecast_valid
  FROM `YOUR_PROJECT_ID.retail_demo.inventory` AS i
  LEFT JOIN forecast_stats AS f USING (sku, store, as_of)
  LEFT JOIN order_stats AS o USING (sku, store, as_of)
), base AS (
  SELECT *,
    IF(inventory_valid, on_hand - reserved - blocked, NULL) AS sellable_stock,
    IF(forecast_valid, SAFE_DIVIDE(total_demand, 30), NULL)
      AS average_daily_demand
  FROM validated
), receipts AS (
  SELECT i.sku, i.store, i.as_of, o.expected_date AS receipt_date,
    SUM(o.quantity) AS receipt_units
  FROM `YOUR_PROJECT_ID.retail_demo.inventory` AS i
  JOIN `YOUR_PROJECT_ID.retail_demo.orders` AS o
    ON o.sku = i.sku AND o.store = i.store
  WHERE o.status IN ('OPEN', 'PARTIALLY_RECEIVED')
    AND o.confirmed IS TRUE AND o.quantity > 0
    AND o.expected_date BETWEEN DATE_ADD(i.as_of, INTERVAL 1 DAY)
                            AND DATE_ADD(i.as_of, INTERVAL 30 DAY)
  GROUP BY i.sku, i.store, i.as_of, receipt_date
), projection AS (
  SELECT b.sku, b.store, b.as_of, f.forecast_date,
    b.sellable_stock + SUM(COALESCE(r.receipt_units, 0) - f.units) OVER (
      PARTITION BY b.sku, b.store, b.as_of
      ORDER BY f.forecast_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS projected_stock
  FROM base AS b
  JOIN `YOUR_PROJECT_ID.retail_demo.forecast_daily` AS f
    ON f.sku = b.sku AND f.store = b.store
    AND f.forecast_date BETWEEN DATE_ADD(b.as_of, INTERVAL 1 DAY)
                           AND DATE_ADD(b.as_of, INTERVAL 30 DAY)
  LEFT JOIN receipts AS r
    ON r.sku = b.sku AND r.store = b.store AND r.as_of = b.as_of
    AND r.receipt_date = f.forecast_date
  WHERE b.inventory_valid AND b.forecast_valid
), projected_stats AS (
  SELECT sku, store, as_of,
    -- Negative balance means unmet demand. Exactly zero means depleted stock.
    MIN(IF(projected_stock < 0, forecast_date, NULL)) AS first_stockout_date,
    MIN(projected_stock) AS minimum_projected_stock
  FROM projection
  GROUP BY sku, store, as_of
), metrics AS (
  SELECT b.*, p.first_stockout_date, p.minimum_projected_stock,
    IF(b.inventory_valid AND b.forecast_valid AND b.average_daily_demand > 0,
      SAFE_DIVIDE(b.sellable_stock, b.average_daily_demand), NULL) AS days_of_cover,
    -- Demo policy: max coverage stock plus separately stated safety stock.
    -- Zero demand needs review; it is not treated as a calculable coverage ratio.
    IF(b.inventory_valid AND b.forecast_valid AND b.average_daily_demand > 0,
      GREATEST(b.sellable_stock - b.average_daily_demand * b.target_max_cover_days
        - b.safety_stock, 0), NULL) AS excess_units
  FROM base AS b
  LEFT JOIN projected_stats AS p USING (sku, store, as_of)
)
SELECT sku, product, store, as_of, on_hand, reserved, blocked,
  sellable_stock, average_daily_demand, days_of_cover,
  lead_time_days, target_max_cover_days, safety_stock, unit_cost,
  forecast_source, forecast_days, first_stockout_date, minimum_projected_stock,
  excess_units, late_order_count, inventory_valid, forecast_valid,
  ARRAY_CONCAT(
    IF(NOT inventory_valid, ['DATA_ISSUE'], ARRAY<STRING>[]),
    IF(NOT forecast_valid, ['FORECAST_DATA_ISSUE'], ARRAY<STRING>[]),
    IF(inventory_valid AND sellable_stock = 0,
      ['OUT_OF_STOCK'], ARRAY<STRING>[]),
    IF(inventory_valid AND forecast_valid AND first_stockout_date IS NOT NULL,
      ['STOCKOUT_RISK'], ARRAY<STRING>[]),
    IF(inventory_valid AND forecast_valid AND excess_units > 0,
      ['OVERSTOCK'], ARRAY<STRING>[]),
    IF(inventory_valid AND forecast_valid AND average_daily_demand = 0,
      ['NO_FORECAST_DEMAND'], ARRAY<STRING>[]),
    IF(late_order_count > 0, ['LATE_RECEIPT'], ARRAY<STRING>[]),
    IF(order_data_issue_count > 0, ['ORDER_DATA_ISSUE'], ARRAY<STRING>[])
  ) AS exception_flags
FROM metrics;

-- Inspect results. [] means no exception was detected in this demo's rules.
-- Expected after 01: milk first shortage = as_of + 2 days; eggs = as_of + 1 day.
-- Rice first shortage = as_of + 6 days, late_order_count = 1; its 120 late units
-- are excluded from supply. Oil excess_units = 180 and has no projected shortage.
-- Yogurt has DATA_ISSUE and null sellable stock / stock projections / excess.
SELECT * FROM `YOUR_PROJECT_ID.retail_demo.inventory_exceptions`
ORDER BY store, sku;
