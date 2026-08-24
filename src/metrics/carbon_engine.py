"""
Carbon Metrics Engine
----------------------
Converts wasted compute/storage into estimated kgCO2e using the same
methodology family used by the open-source Cloud Carbon Footprint (CCF)
tool and Etsy's "Cloud Jewels" model (the de facto reference approach for
cloud carbon estimation, also cited in GSF/SCI-adjacent literature):

  1. Average Watts = MinWatts + (CPU Utilization Fraction) * (MaxWatts - MinWatts)
     -- a server draws a baseline ("idle") wattage even at 0% CPU, and
        power draw scales roughly linearly with utilization up to MaxWatts
        at 100%. This linear approximation is exactly what CCF/Cloud
        Jewels uses (see cloudcarbonfootprint.org/docs/methodology).

  2. Energy (kWh) = Average Watts * vCPUs * Hours / 1000 * PUE
     -- PUE (Power Usage Effectiveness) accounts for data-center overhead
        (cooling, power delivery) beyond the server itself. We use 1.58,
        the global average PUE reported by the Uptime Institute, which is
        also CCF's documented on-premise/default assumption.

  3. Carbon (kgCO2e) = Energy (kWh) * Grid Carbon Intensity (gCO2/kWh) / 1000
     -- grid intensity varies by region; we use illustrative regional
        averages (see src/ingestion/config.py) in place of a live,
        paid grid-intensity API (e.g. Electricity Maps), consistent with
        the project's zero-cost constraint.

Storage energy uses Cloud Jewels' published SSD storage coefficient of
1.52 Watt-hours per Terabyte-hour.

We also compute a simplified Software Carbon Intensity (SCI) score
following the Green Software Foundation's specification:

    SCI = ((E * I) + M) / R

Where E = energy consumed, I = grid carbon intensity, M = embodied
emissions, and R = functional unit. We treat M (embodied/manufacturing
emissions) as out of scope here — it requires hardware lifecycle data we
don't have access to for free — and document that omission explicitly
rather than fabricating a number. R is defined as "per flagged wasted
resource," so SCI here reads as: average kgCO2e wasted per idle
resource in the fleet.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Cloud Jewels / CCF-style linear power model coefficients
# ---------------------------------------------------------------------------
MIN_WATTS_PER_VCPU = 0.71   # baseline/idle draw per vCPU
MAX_WATTS_PER_VCPU = 3.50   # peak draw per vCPU at 100% utilization
PUE = 1.58                  # Uptime Institute global average PUE
STORAGE_WATT_HOURS_PER_TB_HOUR = 1.52  # Cloud Jewels SSD storage coefficient


def compute_instance_energy_and_carbon(
    vcpu: int,
    mean_cpu_utilization_pct: float,
    hours: float,
    grid_intensity_g_per_kwh: float,
) -> tuple[float, float]:
    """Returns (energy_kwh, carbon_kg) for a single compute instance."""
    cpu_fraction = mean_cpu_utilization_pct / 100.0
    avg_watts = vcpu * (
        MIN_WATTS_PER_VCPU + cpu_fraction * (MAX_WATTS_PER_VCPU - MIN_WATTS_PER_VCPU)
    )
    energy_kwh = (avg_watts * hours / 1000.0) * PUE
    carbon_kg = energy_kwh * grid_intensity_g_per_kwh / 1000.0
    return energy_kwh, carbon_kg


def compute_storage_energy_and_carbon(
    size_gb: float,
    hours: float,
    grid_intensity_g_per_kwh: float,
) -> tuple[float, float]:
    """Returns (energy_kwh, carbon_kg) for a storage bucket over `hours`."""
    size_tb = size_gb / 1000.0
    energy_kwh = (size_tb * hours * STORAGE_WATT_HOURS_PER_TB_HOUR) / 1000.0
    carbon_kg = energy_kwh * grid_intensity_g_per_kwh / 1000.0
    return energy_kwh, carbon_kg


def enrich_instances_with_carbon(
    flagged_instances_df: pd.DataFrame,
    regions_config: dict,
    hours_per_month: float = 730.0,
) -> pd.DataFrame:
    """
    Adds energy/carbon columns to flagged instance data. Uses the OBSERVED
    mean CPU utilization but projects to a standard month (730h) so figures
    are comparable to the monthly $ waste figures from the cost engine.
    """
    df = flagged_instances_df.copy()

    energies, carbons = [], []
    for _, row in df.iterrows():
        intensity = regions_config[row["region"]]["grid_carbon_intensity_gco2_per_kwh"]
        energy_kwh, carbon_kg = compute_instance_energy_and_carbon(
            vcpu=row["vcpu"],
            mean_cpu_utilization_pct=row["mean_cpu_pct"],
            hours=hours_per_month,
            grid_intensity_g_per_kwh=intensity,
        )
        energies.append(energy_kwh)
        carbons.append(carbon_kg)

    df["monthly_energy_kwh"] = energies
    df["monthly_carbon_kg_co2e"] = carbons
    df["annual_carbon_kg_co2e"] = df["monthly_carbon_kg_co2e"] * 12
    return df


def enrich_storage_with_carbon(
    flagged_storage_df: pd.DataFrame,
    regions_config: dict,
    hours_per_month: float = 730.0,
) -> pd.DataFrame:
    df = flagged_storage_df.copy()

    energies, carbons = [], []
    for _, row in df.iterrows():
        intensity = regions_config[row["region"]]["grid_carbon_intensity_gco2_per_kwh"]
        energy_kwh, carbon_kg = compute_storage_energy_and_carbon(
            size_gb=row["size_gb"],
            hours=hours_per_month,
            grid_intensity_g_per_kwh=intensity,
        )
        energies.append(energy_kwh)
        carbons.append(carbon_kg)

    df["monthly_energy_kwh"] = energies
    df["monthly_carbon_kg_co2e"] = carbons
    df["annual_carbon_kg_co2e"] = df["monthly_carbon_kg_co2e"] * 12
    return df


def compute_fleet_sci(total_monthly_carbon_kg: float, num_flagged_resources: int) -> float:
    """
    Simplified SCI score: kgCO2e wasted per flagged wasted resource per
    month. Embodied emissions (M) are explicitly excluded (see module
    docstring) rather than estimated without data.
    """
    if num_flagged_resources == 0:
        return 0.0
    return round(total_monthly_carbon_kg / num_flagged_resources, 4)


# Real-world equivalence conversions for human-readable impact statements.
# Sources: EPA Greenhouse Gas Equivalencies Calculator (average passenger
# vehicle ~ 0.404 kg CO2e/mile driven -> ~0.251 kg CO2e/km); a mature tree
# offsets roughly ~21 kg CO2 per year (commonly cited EPA/USDA Forest
# Service approximation, ~1.75 kg/month).
KG_CO2_PER_KM_DRIVEN = 0.251
KG_CO2_OFFSET_PER_TREE_MONTH = 1.75


def carbon_to_equivalents(carbon_kg: float) -> dict:
    return {
        "km_driven_equivalent": round(carbon_kg / KG_CO2_PER_KM_DRIVEN, 1),
        "tree_months_to_offset": round(carbon_kg / KG_CO2_OFFSET_PER_TREE_MONTH, 1),
    }
