# BasketCraft Dashboard

**Live app:** https://etimber-sys-basket-craft-dashboard-app-cl2xwe.streamlit.app/

A Streamlit dashboard connected to a Snowflake data warehouse, built for BasketCraft e-commerce analytics.

## Features

- **Headline metrics** — Total revenue, orders, average order value, and items sold with month-over-month deltas
- **Revenue trend** — Interactive daily revenue line chart with a date range filter
- **Top products** — Bar chart of top 10 products by revenue (respects date filter)
- **Bundle finder** — Co-purchase analysis: pick any product and see what customers most often buy with it

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create `.streamlit/secrets.toml` with your Snowflake credentials:
   ```toml
   [snowflake]
   account   = "your_account"
   user      = "your_user"
   password  = "your_password"
   role      = "your_role"
   warehouse = "your_warehouse"
   database  = "your_database"
   schema    = "your_schema"
   ```

3. Run locally:
   ```bash
   streamlit run app.py
   ```
