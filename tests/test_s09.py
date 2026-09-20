"""
Unit tests for S09: MDL Evidence Sufficiency Gate.
Validates information-theoretic entropy calculations, expected information gain,
and MDL sufficiency stopping conditions.
"""

import math
import pytest
from innovation.mdl_gate import (
    binary_entropy,
    compute_expected_ig,
    compute_sufficiency,
    interpret_sufficiency,
    MDL_THRESHOLD,
    EVIDENCE_COST,
)


def test_binary_entropy_max_uncertainty():
    """Assertion 1: binary_entropy(0.5) ≈ 1.0 (max uncertainty)."""
    val = binary_entropy(0.5)
    assert math.isclose(val, 1.0, rel_tol=1e-3), f"Expected H(0.5) ≈ 1.0, got {val}"


def test_binary_entropy_near_certainty_low():
    """Assertion 2: binary_entropy(0.01) < 0.1 (near certainty)."""
    val = binary_entropy(0.01)
    assert val < 0.1, f"Expected H(0.01) < 0.1, got {val}"


def test_binary_entropy_near_certainty_high():
    """Assertion 3: binary_entropy(0.99) < 0.1."""
    val = binary_entropy(0.99)
    assert val < 0.1, f"Expected H(0.99) < 0.1, got {val}"


def test_compute_sufficiency_should_gather_more():
    """Assertion 4: compute_sufficiency(0.5, 0.0, 0) > MDL_THRESHOLD (should gather more)."""
    score = compute_sufficiency(0.5, 0.0, 0)
    assert score > MDL_THRESHOLD, f"Expected sufficiency > {MDL_THRESHOLD}, got {score}"


def test_compute_sufficiency_already_certain():
    """Assertion 5: compute_sufficiency(0.99, 0.0, 0) == 0.0 (already certain, don't gather)."""
    score = compute_sufficiency(0.99, 0.0, 0)
    assert score == 0.0, f"Expected sufficiency == 0.0, got {score}"


def test_compute_sufficiency_iteration_limit():
    """Assertion 6: compute_sufficiency(0.5, 0.0, 3) == 0.0 (iteration limit hit)."""
    score = compute_sufficiency(0.5, 0.0, 3)
    assert score == 0.0, f"Expected sufficiency == 0.0, got {score}"


def test_compute_expected_ig():
    """Assertion 7: compute_expected_ig(0.5, 'STEP_UP_AUTH') > 0."""
    ig = compute_expected_ig(0.5, "STEP_UP_AUTH")
    assert ig > 0.0, f"Expected expected_ig > 0, got {ig}"


def test_edge_cases_and_interpretation():
    """Additional edge cases verification (NaN, 0, 1) and interpret_sufficiency."""
    assert binary_entropy(0.0) == 0.0
    assert binary_entropy(1.0) == 0.0
    assert binary_entropy(float("nan")) == 0.0
    assert binary_entropy(None) == 0.0

    # Human-readable interpretation tests
    res_act = interpret_sufficiency(0.1, 0)
    assert res_act["recommended_action"] == "ACT"

    res_gather = interpret_sufficiency(0.4, 1)
    assert res_gather["recommended_action"] == "GATHER_MORE"

    res_limit = interpret_sufficiency(0.4, 3)
    assert res_limit["recommended_action"] == "ACT"
