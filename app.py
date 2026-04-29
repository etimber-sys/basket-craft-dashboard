import os
from datetime import date, timedelta

import altair as alt
import pandas as pd
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="BasketCraft Dashboard", layout="wide")
st.title("BasketCraft Dashboard")


@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )


@st.cache_data(ttl=600)
def get_headline_metrics():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        WITH monthly AS (
            SELECT
                DATE_TRUNC('month', TO_TIMESTAMP(created_at / 1000000000)) AS month,
                SUM(price_usd)                   AS revenue,
                COUNT(order_id)                  AS orders,
                SUM(price_usd) / COUNT(order_id) AS aov,
                SUM(items_purchased)             AS items_sold
            FROM orders
            GROUP BY 1
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (ORDER BY month DESC) AS rn FROM monthly
        )
        SELECT month, revenue, orders, aov, items_sold
        FROM ranked
        WHERE rn <= 2
        ORDER BY rn
    """)
    rows = cur.fetchall()
    current = rows[0]
    prior = rows[1]
    return {
        "month": current[0].strftime("%B %Y"),
        "revenue":    {"current": float(current[1]), "prior": float(prior[1])},
        "orders":     {"current": int(current[2]),   "prior": int(prior[2])},
        "aov":        {"current": float(current[3]), "prior": float(prior[3])},
        "items_sold": {"current": int(current[4]),   "prior": int(prior[4])},
    }


@st.cache_data(ttl=600)
def get_top_products(start: date, end: date, limit: int = 10) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            p.product_name,
            SUM(oi.price_usd) AS revenue
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        JOIN orders   o ON oi.order_id   = o.order_id
        WHERE TO_TIMESTAMP(o.created_at / 1000000000)::DATE BETWEEN %s AND %s
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT %s
    """, (start.isoformat(), end.isoformat(), limit))
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["product", "revenue"]).astype({"revenue": float})


@st.cache_data(ttl=600)
def get_revenue_trend(start: date, end: date) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            TO_TIMESTAMP(created_at / 1000000000)::DATE AS day,
            SUM(price_usd)                              AS revenue
        FROM orders
        WHERE TO_TIMESTAMP(created_at / 1000000000)::DATE BETWEEN %s AND %s
        GROUP BY 1
        ORDER BY 1
    """, (start.isoformat(), end.isoformat()))
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["day", "revenue"]).astype({"revenue": float})


@st.cache_data(ttl=600)
def get_all_products() -> list[tuple[int, str]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_id, product_name FROM products ORDER BY product_name")
    return cur.fetchall()


@st.cache_data(ttl=600)
def get_bundle_pairs(product_id: int) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        WITH target_orders AS (
            SELECT DISTINCT order_id
            FROM order_items
            WHERE product_id = %s
        ),
        co_purchased AS (
            SELECT
                oi.product_id,
                COUNT(DISTINCT oi.order_id) AS orders_together
            FROM target_orders t
            JOIN order_items oi ON t.order_id = oi.order_id
            WHERE oi.product_id != %s
            GROUP BY 1
        )
        SELECT
            p.product_name,
            c.orders_together,
            ROUND(c.orders_together * 100.0 / (SELECT COUNT(*) FROM target_orders), 1) AS pct_of_orders
        FROM co_purchased c
        JOIN products p ON c.product_id = p.product_id
        ORDER BY 2 DESC
        LIMIT 10
    """, (product_id, product_id))
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["product", "orders_together", "pct_of_orders"]).astype(
        {"orders_together": int, "pct_of_orders": float}
    )


def fmt_delta(current, prior, prefix="", suffix="", decimals=0):
    diff = current - prior
    sign = "+" if diff >= 0 else ""
    if decimals:
        return f"{sign}{prefix}{diff:,.{decimals}f}{suffix}"
    return f"{sign}{prefix}{diff:,.0f}{suffix}"


metrics = get_headline_metrics()
st.caption(f"Current month: {metrics['month']}  ·  vs prior month")

col1, col2, col3, col4 = st.columns(4)

with col1:
    r = metrics["revenue"]
    st.metric(
        "Total Revenue",
        f"${r['current']:,.2f}",
        delta=fmt_delta(r["current"], r["prior"], prefix="$", decimals=2),
    )

with col2:
    o = metrics["orders"]
    st.metric(
        "Total Orders",
        f"{o['current']:,}",
        delta=fmt_delta(o["current"], o["prior"]),
    )

with col3:
    a = metrics["aov"]
    st.metric(
        "Avg Order Value",
        f"${a['current']:,.2f}",
        delta=fmt_delta(a["current"], a["prior"], prefix="$", decimals=2),
    )

with col4:
    i = metrics["items_sold"]
    st.metric(
        "Items Sold",
        f"{i['current']:,}",
        delta=fmt_delta(i["current"], i["prior"]),
    )

st.divider()
st.subheader("Revenue Trend")

DATA_MIN = date(2023, 3, 19)
DATA_MAX = date(2026, 3, 19)
DEFAULT_START = DATA_MAX - timedelta(days=365)

date_range = st.date_input(
    "Date range",
    value=(DEFAULT_START, DATA_MAX),
    min_value=DATA_MIN,
    max_value=DATA_MAX,
    format="YYYY-MM-DD",
)

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
    trend_df = get_revenue_trend(start_date, end_date)
    products_df = get_top_products(start_date, end_date)

    trend_chart = (
        alt.Chart(trend_df)
        .mark_line(point=False, strokeWidth=2, color="#4C9BE8")
        .encode(
            x=alt.X(
                "day:T",
                title="Date",
                scale=alt.Scale(domain=[start_date.isoformat(), end_date.isoformat()]),
            ),
            y=alt.Y("revenue:Q", title="Revenue (USD)", axis=alt.Axis(format="$,.0f")),
            tooltip=[
                alt.Tooltip("day:T", title="Date", format="%b %d, %Y"),
                alt.Tooltip("revenue:Q", title="Revenue", format="$,.2f"),
            ],
        )
        .properties(height=350)
        .interactive()
    )
    st.altair_chart(trend_chart, use_container_width=True)

    st.subheader("Top Products by Revenue")
    bar_chart = (
        alt.Chart(products_df)
        .mark_bar(color="#4C9BE8")
        .encode(
            x=alt.X("revenue:Q", title="Revenue (USD)", axis=alt.Axis(format="$,.0f")),
            y=alt.Y("product:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("product:N", title="Product"),
                alt.Tooltip("revenue:Q", title="Revenue", format="$,.2f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(bar_chart, use_container_width=True)
else:
    st.info("Select a start and end date to display the charts.")

st.divider()
st.subheader("Bundle Finder")
st.caption("Which products are most often bought together?")

all_products = get_all_products()
product_map = {name: pid for pid, name in all_products}
product_names = list(product_map.keys())

selected_name = st.selectbox("Select a product", product_names)

if selected_name:
    selected_id = product_map[selected_name]
    bundle_df = get_bundle_pairs(selected_id)

    if bundle_df.empty:
        st.info(f"No co-purchase data found for **{selected_name}**.")
    else:
        top = bundle_df.iloc[0]
        st.metric(
            "Top pair",
            top["product"],
            delta=f"{top['pct_of_orders']:.1f}% of {selected_name} orders",
            delta_color="off",
        )

        bar = (
            alt.Chart(bundle_df)
            .mark_bar(color="#4C9BE8")
            .encode(
                x=alt.X("orders_together:Q", title="Orders containing both products"),
                y=alt.Y("product:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("product:N", title="Product"),
                    alt.Tooltip("orders_together:Q", title="Orders together", format=","),
                    alt.Tooltip("pct_of_orders:Q", title="% of anchor orders", format=".1f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(bar, use_container_width=True)
