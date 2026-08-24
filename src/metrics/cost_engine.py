"""
Cost Metrics Engine
---------------------
Converts flagged wasted resources into $ figures. Kept deliberately simple
and transparent: for a resource that is confirmed idle/stale for the full
observation window, its ENTIRE running cost is "waste" (it delivered no
value while costing money) — this mirrors how AWS Trusted Advisor / cost
tools define "idle resource cost."
"""

from __future__ import annotations

import pandas as pd

HOURS_PER_MONTH = 730.0  # standard average used across cloud billing tooling


def enrich_instances_with_cost(flagged_instances_df: pd.DataFrame) -> pd.DataFrame:
    df = flagged_instances_df.copy()
    df["monthly_waste_usd"] = df["hourly_cost_usd"] * HOURS_PER_MONTH
    df["annual_waste_usd"] = df["monthly_waste_usd"] * 12
    return df


def enrich_storage_with_cost(flagged_storage_df: pd.DataFrame) -> pd.DataFrame:
    df = flagged_storage_df.copy()
    df["monthly_waste_usd"] = df["monthly_cost_usd"]
    df["annual_waste_usd"] = df["monthly_waste_usd"] * 12
    return df


def fleet_totals(*dfs: pd.DataFrame) -> dict:
    """Sums monthly/annual waste $ across any number of enriched DataFrames."""
    total_monthly = sum(df["monthly_waste_usd"].sum() for df in dfs if len(df) > 0)
    total_annual = sum(df["annual_waste_usd"].sum() for df in dfs if len(df) > 0)
    return {
        "total_monthly_waste_usd": round(float(total_monthly), 2),
        "total_annual_waste_usd": round(float(total_annual), 2),
    }
