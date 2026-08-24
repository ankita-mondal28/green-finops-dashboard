"""
Configuration constants for the mock cloud telemetry generator.

Pricing figures are approximate PUBLIC AWS on-demand rates (USD/hour, modeled
on us-east-1 class pricing) used purely to make the simulation realistic.
They are static reference values, not live-fetched from any billing API,
which keeps this module 100% free and offline-runnable. If you present this
project, note these as "reference on-demand pricing" rather than live billing
data.

Source basis: publicly documented AWS EC2 On-Demand pricing tiers and S3
storage class pricing tiers (general public knowledge, not scraped).
"""

# ---------------------------------------------------------------------------
# Compute instance catalog
# ---------------------------------------------------------------------------
INSTANCE_TYPES = {
    "t3.micro":   {"vcpu": 2, "mem_gib": 1,  "hourly_usd": 0.0104, "family": "burstable"},
    "t3.medium":  {"vcpu": 2, "mem_gib": 4,  "hourly_usd": 0.0416, "family": "burstable"},
    "t3.large":   {"vcpu": 2, "mem_gib": 8,  "hourly_usd": 0.0832, "family": "burstable"},
    "m5.large":   {"vcpu": 2, "mem_gib": 8,  "hourly_usd": 0.0960, "family": "general_purpose"},
    "m5.xlarge":  {"vcpu": 4, "mem_gib": 16, "hourly_usd": 0.1920, "family": "general_purpose"},
    "c5.large":   {"vcpu": 2, "mem_gib": 4,  "hourly_usd": 0.0850, "family": "compute_optimized"},
    "c5.xlarge":  {"vcpu": 4, "mem_gib": 8,  "hourly_usd": 0.1700, "family": "compute_optimized"},
    "r5.large":   {"vcpu": 2, "mem_gib": 16, "hourly_usd": 0.1260, "family": "memory_optimized"},
}

# ---------------------------------------------------------------------------
# Regions (with approximate average grid carbon intensity, gCO2eq/kWh).
# These are illustrative regional averages used later by the carbon metrics
# engine (Step 3) — kept here since region assignment happens at ingestion.
# Broad public-knowledge figures reflecting typical grid mixes; the metrics
# engine step will cite the specific methodology (e.g., Cloud Carbon
# Footprint / Green Software Foundation regional grid data) more precisely.
# ---------------------------------------------------------------------------
REGIONS = {
    "us-east-1": {"display_name": "US East (N. Virginia)", "grid_carbon_intensity_gco2_per_kwh": 379.0},
    "us-west-2": {"display_name": "US West (Oregon)",       "grid_carbon_intensity_gco2_per_kwh": 136.0},
    "eu-west-1": {"display_name": "EU (Ireland)",            "grid_carbon_intensity_gco2_per_kwh": 316.0},
    "ap-south-1": {"display_name": "Asia Pacific (Mumbai)",  "grid_carbon_intensity_gco2_per_kwh": 632.0},
}

# ---------------------------------------------------------------------------
# Storage classes
# ---------------------------------------------------------------------------
STORAGE_CLASSES = {
    "standard":            {"usd_per_gb_month": 0.0230},
    "infrequent_access":   {"usd_per_gb_month": 0.0125},
    "glacier":             {"usd_per_gb_month": 0.0040},
}

# ---------------------------------------------------------------------------
# Simulation parameters
# ---------------------------------------------------------------------------
NUM_INSTANCES = 40
NUM_STORAGE_BUCKETS = 25
SIMULATION_DAYS = 30
WASTEFUL_INSTANCE_RATIO = 0.30   # ~30% of fleet simulated as idle/forgotten
STALE_BUCKET_RATIO = 0.35        # ~35% of buckets simulated as stale/forgotten
RANDOM_SEED = 42
