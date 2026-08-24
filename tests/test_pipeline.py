"""
Test suite — validates that:
  1. The mock generator produces the expected data shape.
  2. The waste detector achieves acceptable accuracy against the
     synthetic ground truth (this is the "keep accuracy in mind" check).
  3. Cost and carbon figures are non-negative and internally consistent
     (annual = 12x monthly, etc).
"""

import pandas as pd
import pytest

from src.ingestion.mock_generator import generate_all
from src.core.waste_detector import (
    detect_idle_instances,
    detect_stale_storage,
    validate_detection_accuracy,
)
from src.metrics.carbon_engine import enrich_instances_with_carbon, enrich_storage_with_carbon
from src.metrics.cost_engine import enrich_instances_with_cost, enrich_storage_with_cost
from src.ingestion.config import REGIONS, NUM_INSTANCES, NUM_STORAGE_BUCKETS, SIMULATION_DAYS

TEST_DATA_DIR = "data/raw"

MIN_ACCEPTABLE_PRECISION = 0.85
MIN_ACCEPTABLE_RECALL = 0.85


@pytest.fixture(scope="module")
def pipeline_data():
    generate_all(TEST_DATA_DIR)
    inventory = pd.read_csv(f"{TEST_DATA_DIR}/instance_inventory.csv")
    util = pd.read_csv(f"{TEST_DATA_DIR}/vm_hourly_utilization.csv")
    storage = pd.read_csv(f"{TEST_DATA_DIR}/storage_inventory.csv")
    return inventory, util, storage


def test_generated_data_shape(pipeline_data):
    inventory, util, storage = pipeline_data
    assert len(inventory) == NUM_INSTANCES
    assert len(storage) == NUM_STORAGE_BUCKETS
    assert len(util) == NUM_INSTANCES * SIMULATION_DAYS * 24
    assert set(["instance_id", "instance_type", "region", "hourly_cost_usd"]).issubset(inventory.columns)


def test_idle_instance_detection_accuracy(pipeline_data):
    inventory, util, storage = pipeline_data
    flagged = detect_idle_instances(inventory, util)
    metrics = validate_detection_accuracy(flagged, "is_flagged_idle", "_true_is_wasteful")
    assert metrics["precision"] >= MIN_ACCEPTABLE_PRECISION, f"Precision too low: {metrics}"
    assert metrics["recall"] >= MIN_ACCEPTABLE_RECALL, f"Recall too low: {metrics}"


def test_stale_storage_detection_accuracy(pipeline_data):
    inventory, util, storage = pipeline_data
    flagged = detect_stale_storage(storage)
    metrics = validate_detection_accuracy(flagged, "is_flagged_stale", "_true_is_stale")
    assert metrics["precision"] >= MIN_ACCEPTABLE_PRECISION, f"Precision too low: {metrics}"
    assert metrics["recall"] >= MIN_ACCEPTABLE_RECALL, f"Recall too low: {metrics}"


def test_cost_engine_consistency(pipeline_data):
    inventory, util, storage = pipeline_data
    flagged = detect_idle_instances(inventory, util)
    flagged = flagged[flagged["is_flagged_idle"]]
    enriched = enrich_instances_with_cost(flagged)

    assert (enriched["monthly_waste_usd"] >= 0).all()
    assert (enriched["annual_waste_usd"] == enriched["monthly_waste_usd"] * 12).all()


def test_carbon_engine_non_negative(pipeline_data):
    inventory, util, storage = pipeline_data
    flagged = detect_idle_instances(inventory, util)
    flagged = flagged[flagged["is_flagged_idle"]]
    enriched = enrich_instances_with_carbon(flagged, REGIONS)

    assert (enriched["monthly_carbon_kg_co2e"] >= 0).all()
    assert (enriched["monthly_energy_kwh"] >= 0).all()


def test_storage_carbon_engine_non_negative(pipeline_data):
    inventory, util, storage = pipeline_data
    flagged = detect_stale_storage(storage)
    flagged = flagged[flagged["is_flagged_stale"]]
    enriched = enrich_storage_with_carbon(flagged, REGIONS)

    assert (enriched["monthly_carbon_kg_co2e"] >= 0).all()
