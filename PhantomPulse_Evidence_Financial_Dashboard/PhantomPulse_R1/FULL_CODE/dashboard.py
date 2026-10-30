#!/usr/bin/env python3
"""Public, read-only PhantomPulse dashboard for saved R1 predictions."""
from pathlib import Path
import json
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission" / "R1_predictions.csv"
VALIDATION = ROOT / "outputs" / "validation_score.json"

st.set_page_config(page_title="PhantomPulse | Store Alert Desk", page_icon="📦", layout="wide")
st.title("PhantomPulse | Store Alert Desk")
st.caption("A ranked daily shelf-check list. Alerts are investigation priorities, not proof of missing stock.")

if not SUBMISSION.exists():
    st.error(f"Saved predictions file not found: {SUBMISSION.relative_to(ROOT)}")
    st.stop()

pred = pd.read_csv(SUBMISSION, dtype={"store_id": str, "sku_id": str})
required = {"date", "store_id", "sku_id", "rank", "confidence", "reason"}
missing = required - set(pred.columns)
if missing:
    st.error("Predictions file is missing required columns: " + ", ".join(sorted(missing)))
    st.stop()
pred["date"] = pd.to_datetime(pred["date"], errors="coerce")
pred["rank"] = pd.to_numeric(pred["rank"], errors="coerce")
pred["confidence"] = pd.to_numeric(pred["confidence"], errors="coerce")
pred = pred.dropna(subset=["date", "rank", "confidence"])
pred["rank"] = pred["rank"].astype(int)
pred["confidence"] = pred["confidence"].clip(0, 1)
pred["reason"] = pred["reason"].fillna("No explanation supplied.")

min_date, max_date = pred["date"].min().date(), pred["date"].max().date()
f1, f2 = st.columns(2)
with f1:
    selected_date = st.date_input("Business date", value=max_date, min_value=min_date, max_value=max_date)
day = pred[pred["date"].dt.date == selected_date].copy()
stores = sorted(day["store_id"].astype(str).unique())
with f2:
    selected_store = st.selectbox("Store", stores) if stores else None
if not selected_store:
    st.warning("No saved alerts are available for this date.")
    st.stop()
store_day = day[day["store_id"].astype(str) == selected_store].sort_values("rank")

a, b, c, d = st.columns(4)
a.metric("Items to check", len(store_day))
b.metric("Top-five alerts", int((store_day["rank"] <= 5).sum()))
c.metric("Average ranking score", f"{store_day['confidence'].mean():.3f}" if len(store_day) else "—")
d.metric("Store-days in file", f"{pred[['date','store_id']].drop_duplicates().shape[0]:,}")

st.subheader("Daily manager checklist")
display_cols = ["rank", "store_id", "sku_id", "confidence", "reason"]
st.dataframe(store_day[display_cols], use_container_width=True, hide_index=True,
             column_config={
                 "rank": st.column_config.NumberColumn("Rank", format="%d"),
                 "confidence": st.column_config.ProgressColumn("Ranking score", min_value=0, max_value=1, format="%.3f"),
                 "reason": st.column_config.TextColumn("Why check this SKU?", width="large"),
             })
st.download_button("Download this store's daily checklist (CSV)",
                   store_day[display_cols].to_csv(index=False).encode("utf-8"),
                   file_name=f"phantompulse_{selected_date}_{selected_store}.csv",
                   mime="text/csv")

st.subheader("Alert evidence: sales versus recorded stock")
st.write("Choose a flagged SKU, then provide the authorised historical inventory file. The dashboard will plot sales and recorded stock for the selected store/SKU.")
labels = [f"#{int(r.rank)} · {r.sku_id} · score {r.confidence:.3f}" for r in store_day.itertuples()]
choice = st.selectbox("Select a flagged SKU", labels)
alert = store_day.iloc[labels.index(choice)]
st.markdown(f"**{alert['sku_id']}** — {alert['reason']}")

with st.expander("Add historical evidence data", expanded=True):
    hist_file = st.file_uploader("Upload daily_sales_inventory.parquet or .csv", type=["parquet", "csv"], key="history")
    sku_file = st.file_uploader("Optional: upload sku_master.csv if unit_price_inr is not in the history file", type=["csv"], key="sku_master")
    st.caption("Use only organiser-authorised data. Do not upload confidential/customer information. Uploaded files are used for this session and are not added to the GitHub repository.")

hist = None
unit_price = None
if hist_file is not None:
    try:
        if hist_file.name.lower().endswith(".parquet"):
            hist = pd.read_parquet(hist_file)
        else:
            hist = pd.read_csv(hist_file)
        needed = {"date", "store_id", "sku_id", "units_sold", "on_hand_eod"}
        absent = needed - set(hist.columns)
        if absent:
            st.error("History file is missing columns: " + ", ".join(sorted(absent)))
            hist = None
        else:
            hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
            hist["store_id"] = hist["store_id"].astype(str)
            hist["sku_id"] = hist["sku_id"].astype(str)
            hist["units_sold"] = pd.to_numeric(hist["units_sold"], errors="coerce").fillna(0)
            hist["on_hand_eod"] = pd.to_numeric(hist["on_hand_eod"], errors="coerce")
            hist = hist[(hist["store_id"] == str(selected_store)) &
                        (hist["sku_id"] == str(alert["sku_id"])) &
                        (hist["date"] < pd.Timestamp(alert["date"]))].sort_values("date")
            if "unit_price_inr" in hist.columns:
                prices = pd.to_numeric(hist["unit_price_inr"], errors="coerce").dropna()
                if len(prices):
                    unit_price = float(prices.iloc[-1])
    except Exception as exc:
        st.error(f"Could not read historical data: {exc}")
        hist = None

if hist is not None:
    if hist.empty:
        st.warning("No historical rows found for this store/SKU before the selected alert date.")
    else:
        # Find the current zero-sales streak, then estimate baseline only from days before it began.
        hist = hist.dropna(subset=["date"]).copy()
        hist = hist.sort_values("date")
        streak = 0
        for value in hist["units_sold"].iloc[::-1]:
            if value <= 0:
                streak += 1
            else:
                break
        pre_streak = hist.iloc[:len(hist)-streak] if streak else hist
        baseline_window = pre_streak.tail(28)
        baseline_daily = float(baseline_window["units_sold"].mean()) if len(baseline_window) else 0.0

        chart = make_subplots(specs=[[{"secondary_y": True}]])
        chart.add_trace(go.Bar(x=hist["date"], y=hist["units_sold"], name="Actual units sold", opacity=0.65), secondary_y=False)
        if baseline_daily > 0:
            chart.add_trace(go.Scatter(x=hist["date"], y=[baseline_daily]*len(hist),
                name="Pre-streak baseline (units/day)", mode="lines", line={"dash":"dash"}), secondary_y=False)
        chart.add_trace(go.Scatter(x=hist["date"], y=hist["on_hand_eod"], name="Recorded stock (units)",
            mode="lines+markers", line={"width":2}), secondary_y=True)
        chart.update_layout(title=f"Sales and recorded stock — {selected_store} / {alert['sku_id']}",
                            legend_title="", hovermode="x unified", margin={"l":10,"r":10,"t":55,"b":10})
        chart.update_yaxes(title_text="Units sold per day", secondary_y=False)
        chart.update_yaxes(title_text="Recorded units on hand", secondary_y=True)
        st.plotly_chart(chart, use_container_width=True)
        st.caption("Sales and stock are plotted from the uploaded history. The dashed line is the mean daily sales in up to 28 available days before the current zero-sales streak; it is a simple reference, not a causal estimate.")

        if unit_price is None and sku_file is not None:
            try:
                sku = pd.read_csv(sku_file, dtype={"sku_id": str})
                if {"sku_id", "unit_price_inr"}.issubset(sku.columns):
                    match = sku[sku["sku_id"].astype(str) == str(alert["sku_id"])]
                    if len(match):
                        unit_price = float(pd.to_numeric(match["unit_price_inr"], errors="coerce").dropna().iloc[0])
            except Exception as exc:
                st.warning(f"Could not read SKU price file: {exc}")

        st.subheader("Illustrative annual rupees recoverable")
        recovery_rate = st.slider("Assumed recovery rate", min_value=0.0, max_value=1.0, value=0.60, step=0.05,
                                  help="Scenario assumption, not a measured recovery rate.")
        if unit_price is None or not pd.notna(unit_price) or unit_price < 0:
            st.info("Upload a SKU master containing sku_id and unit_price_inr, or use a history file containing unit_price_inr, to calculate rupees.")
        elif baseline_daily <= 0:
            st.info("The pre-streak history does not provide a positive daily sales baseline, so a rupee estimate cannot be calculated.")
        else:
            daily_gross = baseline_daily * unit_price
            annual_recoverable = daily_gross * recovery_rate * 365
            zero_streak_opportunity = baseline_daily * streak * unit_price * recovery_rate
            st.metric("Illustrative annualized recoverable value", f"₹{annual_recoverable:,.0f}")
            st.write("**Arithmetic (single SKU, this store):**")
            st.latex(r"\text{Annual estimate} = \text{baseline units/day} \times \text{unit price} \times \text{recovery rate} \times 365")
            st.write(f"= {baseline_daily:.2f} units/day × ₹{unit_price:,.2f} × {recovery_rate:.0%} × 365")
            st.write(f"= **₹{annual_recoverable:,.0f} per year**")
            st.caption(f"Current zero-sales streak: {streak} days. Illustrative opportunity for this streak = {baseline_daily:.2f} × {streak} × ₹{unit_price:,.2f} × {recovery_rate:.0%} = ₹{zero_streak_opportunity:,.0f}. Annual figure assumes the pre-streak daily sales rate and recovery rate continue for 365 days; it is not actual recovered cash or a forecast.")
else:
    st.info("Upload the authorised historical sales/inventory file above to display the chart and calculate the estimate. The six-column submission CSV alone does not contain the time series or unit price needed.")

st.subheader("Model evaluation")
if VALIDATION.exists():
    try:
        score = json.loads(VALIDATION.read_text(encoding="utf-8"))
        if "primary_score" in score:
            m1, m2, m3 = st.columns(3)
            m1.metric("Mean Precision@20 / store-day", f"{score['primary_score']:.2%}")
            m2.metric("Row recall", f"{score['row_recall']:.2%}" if score.get("row_recall") is not None else "Not available")
            m3.metric("Episode recall", f"{score['episode_recall']:.2%}" if score.get("episode_recall") is not None else "Not available")
            st.caption("Development/validation metrics only. These are not hidden-test results.")
        else:
            st.info("Validation file exists but does not contain the expected evaluator fields.")
    except Exception as exc:
        st.warning(f"Could not read validation metrics: {exc}")
else:
    st.info("Validation metrics are not bundled. Hidden-test metrics must not be displayed unless released by the organiser.")

st.caption("Manager action: physically check the shelf, backroom and inventory record. A model alert is a prompt to investigate, not proof of an empty shelf, theft or recovered revenue.")
