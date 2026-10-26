-- Run in the BigQuery SQL editor after replacing YOUR_PROJECT_ID everywhere.
-- EDUCATIONAL DEMO: rerunning this file resets these demo tables.
-- Use a separate retail_demo dataset, not your operational inventory dataset.
CREATE SCHEMA IF NOT EXISTS `YOUR_PROJECT_ID.retail_demo`
OPTIONS (location = 'US');

CREATE OR REPLACE TABLE `YOUR_PROJECT_ID.retail_demo.inventory` (
  sku STRING, product STRING, store STRING, as_of DATE,
  on_hand INT64, reserved INT64, blocked INT64,
  lead_time_days INT64, target_max_cover_days INT64,
  safety_stock INT64, unit_cost FLOAT64, updated_at TIMESTAMP
);

INSERT INTO `YOUR_PROJECT_ID.retail_demo.inventory`
VALUES
  ('MILK-001', 'Milk', 'Dubai-01', CURRENT_DATE('Asia/Dubai'),
   24, 6, 0, 3, 14, 0, 6.0, CURRENT_TIMESTAMP()),
  ('EGGS-001', 'Eggs', 'Dubai-01', CURRENT_DATE('Asia/Dubai'),
   0, 0, 0, 3, 20, 0, 12.0, CURRENT_TIMESTAMP()),
  ('RICE-001', 'Rice', 'Dubai-01', CURRENT_DATE('Asia/Dubai'),
   55, 5, 0, 7, 30, 0, 50.0, CURRENT_TIMESTAMP()),
  ('OIL-001', 'Cooking oil', 'Dubai-01', CURRENT_DATE('Asia/Dubai'),
   260, 0, 0, 7, 40, 0, 20.0, CURRENT_TIMESTAMP()),
  ('YOGURT-001', 'Yogurt', 'Dubai-01', CURRENT_DATE('Asia/Dubai'),
   -4, 0, 0, 3, 14, 0, 5.0, CURRENT_TIMESTAMP());

CREATE OR REPLACE TABLE `YOUR_PROJECT_ID.retail_demo.orders` (
  order_id STRING, sku STRING, store STRING, quantity INT64,
  expected_date DATE, confirmed BOOL, status STRING
);

-- quantity is REMAINING unreceived quantity, not the original ordered quantity.
-- Keep receipts and the stock snapshot synchronized to avoid double counting.
INSERT INTO `YOUR_PROJECT_ID.retail_demo.orders`
VALUES
  ('PO-MILK-001', 'MILK-001', 'Dubai-01', 80,
   DATE_ADD(CURRENT_DATE('Asia/Dubai'), INTERVAL 3 DAY), TRUE, 'OPEN'),
  ('PO-EGGS-001', 'EGGS-001', 'Dubai-01', 40,
   DATE_ADD(CURRENT_DATE('Asia/Dubai'), INTERVAL 2 DAY), TRUE, 'OPEN'),
  ('PO-RICE-001', 'RICE-001', 'Dubai-01', 120,
   DATE_SUB(CURRENT_DATE('Asia/Dubai'), INTERVAL 3 DAY), TRUE, 'OPEN');

CREATE OR REPLACE TABLE `YOUR_PROJECT_ID.retail_demo.forecast_daily` (
  sku STRING, store STRING, forecast_date DATE,
  units FLOAT64, forecast_source STRING
);

-- These are illustrative constant DEMO estimates, not Vertex model outputs.
INSERT INTO `YOUR_PROJECT_ID.retail_demo.forecast_daily`
SELECT i.sku, i.store, DATE_ADD(i.as_of, INTERVAL day_offset DAY),
  CASE i.sku
    WHEN 'MILK-001' THEN 12.0
    WHEN 'EGGS-001' THEN 10.0
    WHEN 'RICE-001' THEN 10.0
    WHEN 'OIL-001' THEN 2.0
    WHEN 'YOGURT-001' THEN 8.0
  END,
  'DEMO_ESTIMATE'
FROM `YOUR_PROJECT_ID.retail_demo.inventory` AS i
CROSS JOIN UNNEST(GENERATE_ARRAY(1, 30)) AS day_offset;

-- Expected totals: 5 inventory rows, 3 outstanding orders, 150 forecast rows.
SELECT 'inventory' AS table_name, COUNT(*) AS rows
FROM `YOUR_PROJECT_ID.retail_demo.inventory`
UNION ALL
SELECT 'orders', COUNT(*) FROM `YOUR_PROJECT_ID.retail_demo.orders`
UNION ALL
SELECT 'forecast_daily', COUNT(*) FROM `YOUR_PROJECT_ID.retail_demo.forecast_daily`;
