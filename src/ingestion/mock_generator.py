"""
Mock Cloud Telemetry Generator
-------------------------------
Ingestion layer for the Green FinOps Dashboard.

Generates realistic, offline, zero-cost synthetic data standing in for what
a real tool would pull from AWS CloudWatch / Cost Explorer:

  1. instance_inventory.csv   - static metadata for each VM
  2. vm_hourly_utilization.csv - 30 days x 24h CPU utilization per VM
  3. storage_inventory.csv    - static metadata + access recency for buckets

A deliberate fraction of resources are simulated as "wasteful" (idle 24/7
compute, stale/forgotten storage) so the waste-detection logic (Step 2) has
real, discoverable patterns instead of random noise.

A hidden validation column prefixed with "_true_" is included in the
inventory files. This is NOT fed to the detector — it exists purely so we
can later measure how accurately our rule-based/AI logic recovers the
ground truth, which is standard practice when building and validating a
detection system on synthetic data.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.ingestion.config import (
    INSTANCE_TYPES,
    REGIONS,
    STORAGE_CLASSES,
    NUM_INSTANCES,
    NUM_STORAGE_BUCKETS,
    SIMULATION_DAYS,
    WASTEFUL_INSTANCE_RATIO,
    STALE_BUCKET_RATIO,
    RANDOM_SEED,
)


class VMTelemetryGenerator:
    """Generates VM inventory metadata and hourly CPU utilization telemetry."""

    def __init__(
        self,
        num_instances: int = NUM_INSTANCES,
        days: int = SIMULATION_DAYS,
        wasteful_ratio: float = WASTEFUL_INSTANCE_RATIO,
        seed: int = RANDOM_SEED,
    ):
        self.num_instances = num_instances
        self.days = days
        self.hours = days * 24
        self.wasteful_ratio = wasteful_ratio
        self.rng = np.random.default_rng(seed)
        self.instance_types = list(INSTANCE_TYPES.keys())
        self.regions = list(REGIONS.keys())

    def _build_inventory(self) -> pd.DataFrame:
        records = []
        end_date = datetime(2026, 8, 22)  # simulation "today"

        for _ in range(self.num_instances):
            instance_type = self.rng.choice(self.instance_types)
            specs = INSTANCE_TYPES[instance_type]
            region = self.rng.choice(self.regions)
            is_wasteful = self.rng.random() < self.wasteful_ratio

            # Wasteful instances tend to have been launched long ago and
            # forgotten; healthy instances have a more varied launch history.
            if is_wasteful:
                days_ago = int(self.rng.integers(45, 240))
            else:
                days_ago = int(self.rng.integers(1, 120))
            launch_date = end_date - timedelta(days=days_ago)

            records.append(
                {
                    "instance_id": f"i-{uuid.uuid4().hex[:12]}",
                    "instance_type": instance_type,
                    "vcpu": specs["vcpu"],
                    "mem_gib": specs["mem_gib"],
                    "family": specs["family"],
                    "region": region,
                    "hourly_cost_usd": specs["hourly_usd"],
                    "launch_date": launch_date.strftime("%Y-%m-%d"),
                    "_true_is_wasteful": is_wasteful,
                }
            )

        return pd.DataFrame(records)

    def _simulate_cpu_series(self, is_wasteful: bool) -> np.ndarray:
        """Simulate one instance's hourly CPU utilization series (%)."""
        hours = np.arange(self.hours)

        if is_wasteful:
            # Idle / forgotten instance: low, flat utilization with small
            # noise, no meaningful business-hours pattern.
            baseline = self.rng.uniform(1.0, 7.0)
            noise = self.rng.normal(0, 1.2, size=self.hours)
            series = baseline + noise
        else:
            # Healthy instance: diurnal pattern (business-hours peak) plus
            # weekly seasonality plus noise.
            hour_of_day = hours % 24
            day_of_week = (hours // 24) % 7

            # Business-hours bump: peak around hour 14 (2pm UTC-ish), trough at night
            diurnal = 25 * np.exp(-((hour_of_day - 14) ** 2) / (2 * 4.0 ** 2))
            # Weekday boost, weekend dip
            weekday_factor = np.where(day_of_week < 5, 1.0, 0.4)
            base_load = self.rng.uniform(20.0, 45.0)

            noise = self.rng.normal(0, 5.0, size=self.hours)
            series = (base_load + diurnal) * weekday_factor + noise

        return np.clip(series, 0.0, 100.0)

    def generate(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Returns (instance_inventory_df, hourly_utilization_df)."""
        inventory_df = self._build_inventory()

        start_date = datetime(2026, 8, 22) - timedelta(days=self.days)
        timestamps = [start_date + timedelta(hours=h) for h in range(self.hours)]

        util_records = []
        for _, row in inventory_df.iterrows():
            cpu_series = self._simulate_cpu_series(row["_true_is_wasteful"])
            for ts, cpu in zip(timestamps, cpu_series):
                util_records.append(
                    {
                        "instance_id": row["instance_id"],
                        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                        "cpu_utilization_pct": round(float(cpu), 2),
                    }
                )

        util_df = pd.DataFrame(util_records)
        return inventory_df, util_df


class StorageTelemetryGenerator:
    """Generates storage bucket inventory with access-recency simulation."""

    def __init__(
        self,
        num_buckets: int = NUM_STORAGE_BUCKETS,
        stale_ratio: float = STALE_BUCKET_RATIO,
        seed: int = RANDOM_SEED + 1,
    ):
        self.num_buckets = num_buckets
        self.stale_ratio = stale_ratio
        self.rng = np.random.default_rng(seed)
        self.regions = list(REGIONS.keys())
        self.storage_classes = list(STORAGE_CLASSES.keys())

    def generate(self) -> pd.DataFrame:
        records = []
        end_date = datetime(2026, 8, 22)

        for _ in range(self.num_buckets):
            region = self.rng.choice(self.regions)
            storage_class = self.rng.choice(self.storage_classes)
            rate = STORAGE_CLASSES[storage_class]["usd_per_gb_month"]

            size_gb = float(self.rng.gamma(shape=2.0, scale=150.0))  # skewed sizes
            is_stale = self.rng.random() < self.stale_ratio

            if is_stale:
                last_accessed_days_ago = int(self.rng.integers(180, 720))
            else:
                last_accessed_days_ago = int(self.rng.integers(0, 30))

            created_days_ago = last_accessed_days_ago + int(self.rng.integers(10, 200))
            created_date = end_date - timedelta(days=created_days_ago)

            monthly_cost_usd = round(size_gb * rate, 2)

            records.append(
                {
                    "bucket_id": f"bkt-{uuid.uuid4().hex[:10]}",
                    "region": region,
                    "storage_class": storage_class,
                    "size_gb": round(size_gb, 2),
                    "monthly_cost_usd": monthly_cost_usd,
                    "created_date": created_date.strftime("%Y-%m-%d"),
                    "last_accessed_days_ago": last_accessed_days_ago,
                    "_true_is_stale": is_stale,
                }
            )

        return pd.DataFrame(records)


def generate_all(output_dir: str = "data/raw") -> None:
    """Orchestrates generation of all mock datasets and writes CSVs to disk."""
    os.makedirs(output_dir, exist_ok=True)

    print("Generating VM inventory + hourly utilization telemetry...")
    vm_gen = VMTelemetryGenerator()
    instance_inventory_df, vm_util_df = vm_gen.generate()

    print("Generating storage bucket inventory...")
    storage_gen = StorageTelemetryGenerator()
    storage_inventory_df = storage_gen.generate()

    instance_path = os.path.join(output_dir, "instance_inventory.csv")
    util_path = os.path.join(output_dir, "vm_hourly_utilization.csv")
    storage_path = os.path.join(output_dir, "storage_inventory.csv")

    instance_inventory_df.to_csv(instance_path, index=False)
    vm_util_df.to_csv(util_path, index=False)
    storage_inventory_df.to_csv(storage_path, index=False)

    print(f"Wrote {len(instance_inventory_df)} instances -> {instance_path}")
    print(f"Wrote {len(vm_util_df)} hourly readings -> {util_path}")
    print(f"Wrote {len(storage_inventory_df)} buckets -> {storage_path}")

    n_wasteful = int(instance_inventory_df["_true_is_wasteful"].sum())
    n_stale = int(storage_inventory_df["_true_is_stale"].sum())
    print(
        f"\nSimulation summary: {n_wasteful}/{len(instance_inventory_df)} instances "
        f"simulated as wasteful, {n_stale}/{len(storage_inventory_df)} buckets "
        f"simulated as stale."
    )


if __name__ == "__main__":
    generate_all()
