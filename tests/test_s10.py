"""
Unit tests for S10: Pattern Discovery Engine.
Validates 21-dimensional feature vector extraction, cluster coverage evaluation,
discriminating feature calculation, and DBSCAN pipeline execution.
"""

import math
import json
import pytest
import numpy as np
from innovation.pattern_discovery import (
    build_feature_vector,
    is_cluster_covered_by_docs,
    compute_discriminating_features,
    run_pattern_discovery,
    FEATURE_NAMES
)


def test_build_feature_vector():
    """Test build_feature_vector with mock transaction data -> assert 21-dim float list."""
    mock_txns = [
        {
            "amount": 100.0,
            "c1": 1.0, "c2": 2.0, "c3": 0.0, "c4": 1.0, "c5": 0.0, "c6": 3.0, "c7": 0.0,
            "c8": 0.0, "c9": 1.0, "c10": 0.0, "c11": 1.0, "c12": 0.0, "c13": 2.0, "c14": 1.0,
            "d1": 10.0,
            "device_type": "desktop",
            "risk_score": 0.80
        },
        {
            "amount": 300.0,
            "c1": 3.0, "c2": 4.0, "c3": 2.0, "c4": 3.0, "c5": 2.0, "c6": 5.0, "c7": 2.0,
            "c8": 0.0, "c9": 3.0, "c10": 2.0, "c11": 3.0, "c12": 2.0, "c13": 4.0, "c14": 3.0,
            "d1": 20.0,
            "device_type": "desktop",
            "risk_score": 0.90
        }
    ]

    vec = build_feature_vector(mock_txns, case_risk_score=0.85)

    assert isinstance(vec, list), "Expected return type to be a list"
    assert len(vec) == 21, f"Expected 21 dimensions, got {len(vec)}"
    assert all(isinstance(x, float) for x in vec), "All vector elements must be floats"

    # Verify key computed statistics
    assert math.isclose(vec[0], 200.0, rel_tol=1e-3), f"Expected mean_txn_amt=200.0, got {vec[0]}"
    assert math.isclose(vec[2], 300.0, rel_tol=1e-3), f"Expected max_txn_amt=300.0, got {vec[2]}"
    assert math.isclose(vec[3], 2.0, rel_tol=1e-3), f"Expected mean_c1=2.0, got {vec[3]}"
    assert math.isclose(vec[17], 10.0, rel_tol=1e-3), f"Expected min_d1=10.0, got {vec[17]}"
    assert math.isclose(vec[18], 15.0, rel_tol=1e-3), f"Expected mean_d1=15.0, got {vec[18]}"
    assert math.isclose(vec[19], 0.0, abs_tol=1e-3), f"Expected device_type_encoded=0.0 (desktop), got {vec[19]}"
    assert math.isclose(vec[20], 0.85, rel_tol=1e-3), f"Expected mean_risk_score=0.85, got {vec[20]}"


def test_build_feature_vector_empty():
    """Test build_feature_vector handles empty transaction list gracefully."""
    vec = build_feature_vector([], case_risk_score=0.7)
    assert len(vec) == 21
    assert vec[19] == -1.0  # Null device encoding
    assert vec[20] == 0.7   # Fallback case risk score


def test_is_cluster_covered_by_docs():
    """Test is_cluster_covered_by_docs with mock pattern and stats -> assert bool."""
    mock_documented_patterns = [
        {
            "pattern_id": "PAT_001_HIGH_VALUE",
            "name": "High Value Attack",
            "match_criteria_json": json.dumps({
                "logic": "AND",
                "conditions": [
                    {"feature": "amount", "op": ">=", "value": 500.0},
                    {"feature": "risk_score", "op": ">=", "value": 0.80}
                ]
            })
        }
    ]

    # Case A: Matches both conditions (100% > 70%) -> Covered (True)
    covered_stats = {
        "mean_txn_amt": 650.0,
        "mean_risk_score": 0.88
    }
    is_covered = is_cluster_covered_by_docs(covered_stats, mock_documented_patterns)
    assert isinstance(is_covered, bool)
    assert is_covered is True, "Expected cluster to be covered by PAT_001_HIGH_VALUE"

    # Case B: Fails conditions -> Not Covered (False)
    uncovered_stats = {
        "mean_txn_amt": 120.0,
        "mean_risk_score": 0.40
    }
    is_uncovered = is_cluster_covered_by_docs(uncovered_stats, mock_documented_patterns)
    assert isinstance(is_uncovered, bool)
    assert is_uncovered is False, "Expected cluster to be uncovered by documented patterns"


def test_compute_discriminating_features():
    """Test compute_discriminating_features with mock feature matrix -> assert dict."""
    np.random.seed(42)

    # 100 overall samples with mean 10.0 and std 2.0 across all 21 features
    all_features = np.random.normal(loc=10.0, scale=2.0, size=(100, 21))

    # Cluster of 10 samples where feature 0 (mean_txn_amt) is heavily elevated to 50.0 (> 1.5 std deviation)
    cluster_features = np.random.normal(loc=10.0, scale=2.0, size=(10, 21))
    cluster_features[:, 0] = np.random.normal(loc=50.0, scale=1.0, size=10)

    result = compute_discriminating_features(cluster_features, all_features, FEATURE_NAMES)

    assert isinstance(result, dict), "Expected result to be a dictionary"
    assert "discriminating_features" in result
    assert "match_criteria" in result
    assert "cluster_stats" in result

    disc = result["discriminating_features"]
    assert "mean_txn_amt" in disc, "mean_txn_amt should be detected as discriminating (>1.5 std)"
    assert disc["mean_txn_amt"]["z_score"] > 1.5

    criteria = result["match_criteria"]
    assert criteria["logic"] == "AND"
    assert any(c["feature"] == "mean_txn_amt" for c in criteria["conditions"])


@pytest.mark.asyncio
async def test_run_pattern_discovery_constraint_check():
    """Verifies that fewer than 50 confirmed fraud cases skips DBSCAN gracefully."""
    few_cases = [
        {"case_id": f"CASE_{i}", "risk_score": 0.9, "disposition": "CONFIRMED_FRAUD", "transactions": []}
        for i in range(10)
    ]
    summary = await run_pattern_discovery(cases_override=few_cases)
    assert summary["cases_count"] == 10
    assert summary["clusters_found"] == 0
    assert summary["new_candidates"] == 0


@pytest.mark.asyncio
async def test_run_pattern_discovery_end_to_end_mock():
    """Verifies DBSCAN clustering and novel pattern synthesis with simulated mock cases."""
    np.random.seed(42)
    mock_cases = []

    # 45 background fraud cases around baseline
    for i in range(45):
        mock_cases.append({
            "case_id": f"CASE_BASE_{i}",
            "risk_score": 0.85,
            "disposition": "CONFIRMED_FRAUD",
            "transactions": [
                {"amount": 50.0 + np.random.normal(0, 5), "c1": 1.0, "d1": 5.0, "device_type": "mobile", "risk_score": 0.85}
            ]
        })

    # 15 synthetic clustered fraud cases (novel high-amount desktop syndicate)
    for i in range(15):
        mock_cases.append({
            "case_id": f"CASE_SYNDICATE_{i}",
            "risk_score": 0.98,
            "disposition": "CONFIRMED_FRAUD",
            "transactions": [
                {"amount": 8000.0 + np.random.normal(0, 10), "c1": 15.0, "d1": 0.0, "device_type": "desktop", "risk_score": 0.99}
            ]
        })

    summary = await run_pattern_discovery(cases_override=mock_cases)
    assert summary["cases_count"] == 60
    assert summary["clusters_found"] >= 1
    assert "discovered_patterns" in summary
