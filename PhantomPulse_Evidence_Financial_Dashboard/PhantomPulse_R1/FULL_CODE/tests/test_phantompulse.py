"""Check the main ranking, demand fallback and estimate calculations."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import phantompulse as pp


def test_base_demand_uses_first_available_nonnegative_rate():
    row = pd.Series({"pre_run_rate": np.nan, "same_weekday_rate": 2.5, "avg28": 4.0,
                     "avg14": 3.0, "avg7": 1.0})
    assert pp.base_demand(row) == 2.5


def test_base_demand_returns_zero_when_rates_missing():
    row = pd.Series({"pre_run_rate": np.nan, "same_weekday_rate": np.nan, "avg28": np.nan,
                     "avg14": np.nan, "avg7": np.nan})
    assert pp.base_demand(row) == 0.0


def test_rank_top20_orders_by_risk_and_limits_each_store_day():
    frame = pd.DataFrame({
        "date": [pd.Timestamp("2026-09-03")] * 23,
        "store_id": ["STR-1"] * 23,
        "sku_id": [f"SKU-{i:02d}" for i in range(23)],
        "risk": np.linspace(0.01, 0.99, 23),
        "zero_run": [3] * 23, "pre_run_rate": [2.0] * 23,
        "same_weekday_rate": [2.0] * 23, "avg28": [2.0] * 23,
        "avg14": [2.0] * 23, "avg7": [2.0] * 23,
        "stock": [6.0] * 23, "on_promo_target": [0] * 23,
        "stock_persistence7": [0.8] * 23,
    })
    ranked = pp.rank_top20(frame)
    assert len(ranked) == 20
    assert ranked["rank"].tolist() == list(range(1, 21))
    assert ranked.iloc[0]["sku_id"] == "SKU-22"
    assert ranked["confidence"].between(0, 1).all()


def test_financial_estimates_are_nonnegative_and_use_assumption():
    frame = pd.DataFrame({"pre_run_rate": [2.0], "same_weekday_rate": [1.0], "avg28": [1.0],
                          "avg14": [1.0], "avg7": [1.0], "zero_run": [5],
                          "unit_price_inr": [10.0]})
    out = pp.add_financial_estimates(frame, 0.6)
    assert out.loc[0, "estimated_missed_units_to_date"] == 10.0
    assert out.loc[0, "estimated_lost_revenue_to_date_inr"] == 100.0
    assert out.loc[0, "estimated_recoverable_revenue_to_date_inr"] == 60.0
