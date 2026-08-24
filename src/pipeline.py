"""
Pipeline Orchestrator
-----------------------
Wires together Ingestion -> Core Detection -> Metrics -> NLG into a single
callable, so the Streamlit UI (and tests) don't duplicate this logic.
"""

from __future__ import annotations

import os
import pandas as pd

from src.ingestion.mock_generator import generate_all
from src.ingestion.config import REGIONS
from src.core.waste_detector import (
    detect_idle_instances,
    detect_stale_storage,
    validate_detection_accuracy,
)
from src.metrics.carbon_engine import (
    enrich_instances_with_carbon,
    enrich_storage_with_carbon,
    compute_fleet_sci,
    carbon_to_equivalents,
)
from src.metrics.cost_engine import (
    enrich_instances_with_cost,
    enrich_storage_with_cost,
    fleet_totals,
)
from src.nlg.recommender import generate_all_recommendations, generate_fleet_summary

RAW_DATA_DIR = "data/raw"


def ensure_data_exists(output_dir: str = RAW_DATA_DIR) -> None:
    required = ["instance_inventory.csv", "vm_hourly_utilization.csv", "storage_inventory.csv"]
    if not all(os.path.exists(os.path.join(output_dir, f)) for f in required):
        generate_all(output_dir)


def run_pipeline(data_dir: str = RAW_DATA_DIR) -> dict:
    """
    Runs the full pipeline and returns a dict of everything the UI (or a
    report) needs: raw data, all-instances/all-storage with evidence
    columns, flagged-only subsets enriched with cost+carbon, unified
    recommendations, fleet-level totals, and detection accuracy metrics.
    """
    ensure_data_exists(data_dir)

    inventory = pd.read_csv(os.path.join(data_dir, "instance_inventory.csv"))
    util = pd.read_csv(os.path.join(data_dir, "vm_hourly_utilization.csv"))
    storage = pd.read_csv(os.path.join(data_dir, "storage_inventory.csv"))

    # --- Core detection (all resources, with evidence columns) ---
    all_instances = detect_idle_instances(inventory, util)
    all_storage = detect_stale_storage(storage)

    # --- Accuracy validation against synthetic ground truth ---
    compute_accuracy = validate_detection_accuracy(
        all_instances, "is_flagged_idle", "_true_is_wasteful"
    )
    storage_accuracy = validate_detection_accuracy(
        all_storage, "is_flagged_stale", "_true_is_stale"
    )

    # --- Flagged-only subsets, enriched with cost + carbon ---
    flagged_instances = all_instances[all_instances["is_flagged_idle"]].copy()
    flagged_storage = all_storage[all_storage["is_flagged_stale"]].copy()

    flagged_instances = enrich_instances_with_cost(flagged_instances)
    flagged_instances = enrich_instances_with_carbon(flagged_instances, REGIONS)

    flagged_storage = enrich_storage_with_cost(flagged_storage)
    flagged_storage = enrich_storage_with_carbon(flagged_storage, REGIONS)

    # --- Fleet-level totals ---
    cost_totals = fleet_totals(flagged_instances, flagged_storage)
    total_carbon_kg = (
        flagged_instances["monthly_carbon_kg_co2e"].sum()
        if len(flagged_instances) > 0
        else 0.0
    ) + (
        flagged_storage["monthly_carbon_kg_co2e"].sum() if len(flagged_storage) > 0 else 0.0
    )
    n_flagged = len(flagged_instances) + len(flagged_storage)
    sci_score = compute_fleet_sci(total_carbon_kg, n_flagged)
    equivalents = carbon_to_equivalents(total_carbon_kg)

    # --- Recommendations (NLG) ---
    recommendations_df = generate_all_recommendations(flagged_instances, flagged_storage)
    fleet_summary_text = generate_fleet_summary(
        total_monthly_usd=cost_totals["total_monthly_waste_usd"],
        total_annual_usd=cost_totals["total_annual_waste_usd"],
        total_carbon_kg=total_carbon_kg,
        n_idle_instances=len(flagged_instances),
        n_stale_buckets=len(flagged_storage),
        equivalents=equivalents,
    )

    return {
        "inventory": inventory,
        "storage": storage,
        "util": util,
        "all_instances": all_instances,
        "all_storage": all_storage,
        "flagged_instances": flagged_instances,
        "flagged_storage": flagged_storage,
        "recommendations": recommendations_df,
        "cost_totals": cost_totals,
        "total_carbon_kg": round(float(total_carbon_kg), 3),
        "sci_score": sci_score,
        "equivalents": equivalents,
        "fleet_summary_text": fleet_summary_text,
        "compute_accuracy": compute_accuracy,
        "storage_accuracy": storage_accuracy,
    }


if __name__ == "__main__":
    result = run_pipeline()
    print(result["fleet_summary_text"])
    print()
    print("Compute detection accuracy:", result["compute_accuracy"])
    print("Storage detection accuracy:", result["storage_accuracy"])
