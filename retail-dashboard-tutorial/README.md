# Retail Inventory Decision Dashboard

A Streamlit and BigQuery prototype for inspecting inventory exceptions. It shows stockout risk, excess inventory, late orders, the demand source and underlying purchase-order evidence. An optional Gemini/Vertex AI adapter explains the selected evidence without placing or changing orders.

## Components

- `01_demo_data.sql`: practice tables and demonstration data.
- `02_exception_view.sql`: validation, daily stock projections and exception flags.
- `03_forecasting_inputs.sql`: preparation for a separately configured forecast workflow.
- `04_import_vertex_forecasts.sql`: template for importing an actual forecast result.
- `app.py`: dashboard, parameterized order lookup and optional model inspection.
- `Dockerfile`: container configuration for the dashboard.

## Setup

1. Use your own Google Cloud project. Enable the required BigQuery and model services and select approved processing locations.
2. Replace `YOUR_PROJECT_ID` in the SQL templates. Read each file before executing it. Create the practice data with file 01 and the exception view with file 02.
3. Configure local Application Default Credentials or an appropriate workload identity. Set `GOOGLE_CLOUD_PROJECT` and, where needed, `BIGQUERY_LOCATION`, `GOOGLE_CLOUD_LOCATION` and `GEMINI_MODEL`.
4. Install the project dependencies in a separate virtual environment and run `python -m streamlit run app.py`.

`GEMINI_MODEL` must identify a supported model in your account. Leaving it unset disables the AI inspection action; the dashboard still requires its BigQuery data. The Dockerfile exposes the app on port 8080 and supports a hosting platform's `PORT` setting.

## Interpretation

`DEMO_ESTIMATE` is a demonstration demand estimate, not a trained model forecast. The view separately labels imported forecast sources. Forecasts remain uncertain and require quality evaluation. Invalid inventory or forecast rows produce data-quality flags rather than invented projections. Confirmed future receipts are counted on their scheduled date; late unreceived orders do not become available supply.

The repository contains source and deployment configuration, not evidence of a live cloud deployment. Read [deployment and troubleshooting guidance](../docs/deployment-guide.md) before connecting an account.
