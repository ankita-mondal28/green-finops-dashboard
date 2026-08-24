"""
Recommendation Generator (NLG layer)
--------------------------------------
Turns flagged waste + computed metrics into plain-English, actionable
sentences — the "why AI/logic is needed" layer that makes raw numbers into
a decision a developer can act on immediately.

Deliberately template-based rather than calling a paid LLM API: it keeps
the project at zero marginal cost, keeps output deterministic/auditable
(important for a FinOps tool where a false claim has real consequences),
and is still a legitimate form of "AI-adjacent" automation — natural
language generation from structured data is a standard NLG technique.
"""

from __future__ import annotations

import pandas as pd


def _severity_label(monthly_waste_usd: float) -> str:
    if monthly_waste_usd >= 100:
        return "Critical"
    elif monthly_waste_usd >= 30:
        return "High"
    else:
        return "Moderate"


def generate_instance_recommendation(row: pd.Series) -> str:
    severity = _severity_label(row["monthly_waste_usd"])
    return (
        f"[{severity}] Shut down idle instance {row['instance_id']} "
        f"({row['instance_type']}, {row['region']}) — averaging "
        f"{row['mean_cpu_pct']:.1f}% CPU for {row['idle_hour_fraction']*100:.0f}% "
        f"of observed hours. Saves an estimated ${row['monthly_waste_usd']:.2f}/mo "
        f"(${row['annual_waste_usd']:.2f}/yr) and avoids "
        f"{row['monthly_carbon_kg_co2e']:.2f} kg CO2e/mo."
    )


def generate_storage_recommendation(row: pd.Series) -> str:
    severity = _severity_label(row["monthly_waste_usd"])
    return (
        f"[{severity}] Archive or delete bucket {row['bucket_id']} "
        f"({row['region']}, {row['size_gb']:.1f} GB) — untouched for "
        f"{row['last_accessed_days_ago']} days. Saves an estimated "
        f"${row['monthly_waste_usd']:.2f}/mo (${row['annual_waste_usd']:.2f}/yr) "
        f"and avoids {row['monthly_carbon_kg_co2e']:.3f} kg CO2e/mo."
    )


def generate_all_recommendations(
    flagged_instances_df: pd.DataFrame,
    flagged_storage_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Returns a unified, priority-sorted DataFrame of recommendations ready
    for direct display in the dashboard's action feed.
    """
    records = []

    for _, row in flagged_instances_df.iterrows():
        records.append(
            {
                "resource_id": row["instance_id"],
                "resource_type": "Compute (VM)",
                "region": row["region"],
                "severity": _severity_label(row["monthly_waste_usd"]),
                "monthly_waste_usd": row["monthly_waste_usd"],
                "annual_waste_usd": row["annual_waste_usd"],
                "monthly_carbon_kg_co2e": row["monthly_carbon_kg_co2e"],
                "recommendation": generate_instance_recommendation(row),
            }
        )

    for _, row in flagged_storage_df.iterrows():
        records.append(
            {
                "resource_id": row["bucket_id"],
                "resource_type": "Storage (Bucket)",
                "region": row["region"],
                "severity": _severity_label(row["monthly_waste_usd"]),
                "monthly_waste_usd": row["monthly_waste_usd"],
                "annual_waste_usd": row["annual_waste_usd"],
                "monthly_carbon_kg_co2e": row["monthly_carbon_kg_co2e"],
                "recommendation": generate_storage_recommendation(row),
            }
        )

    df = pd.DataFrame(records)
    if len(df) > 0:
        df = df.sort_values("monthly_waste_usd", ascending=False).reset_index(drop=True)
    return df


def generate_fleet_summary(
    total_monthly_usd: float,
    total_annual_usd: float,
    total_carbon_kg: float,
    n_idle_instances: int,
    n_stale_buckets: int,
    equivalents: dict,
) -> str:
    return (
        f"This month, {n_idle_instances} idle instance(s) and {n_stale_buckets} "
        f"stale storage bucket(s) are costing an estimated ${total_monthly_usd:,.2f} "
        f"(${total_annual_usd:,.2f}/yr) while emitting {total_carbon_kg:.2f} kg CO2e/mo "
        f"— roughly equivalent to driving {equivalents['km_driven_equivalent']:.0f} km "
        f"in an average car, or {equivalents['tree_months_to_offset']:.1f} tree-months "
        f"of carbon offset. Acting on the recommendations below eliminates this waste "
        f"immediately."
    )
