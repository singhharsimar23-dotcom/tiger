"""
Unit tests for S09-REPLACEMENT: Decision-Relevant (VOI) Evidence Gate.
Replaces the mathematically defective Shannon entropy MDL gate with a Value of
Information (VOI) stopping rule that directly asks: "would asking change what we'd do?"
"""

import pytest
from innovation.mdl_gate import (
    decide,
    compute_voi,
    compute_sufficiency,
    interpret_sufficiency,
    VOI_THRESHOLD,
    MAX_COST_BUDGET,
    BRANCH_PROBS,
    POSTERIOR_SHIFT,
    EVIDENCE_COST,
)


def test_decide_policy_mapping():
    """
    Validates deterministic policy-as-code mappings mirroring Section 2.5 approval tiers.
    """
    # Boundary: p < 0.15 -> ALLOW_TRANSACTION / AUTO
    assert decide(0.05, 1000) == ("ALLOW_TRANSACTION", "AUTO")

    # Boundary: 0.15 <= p < 0.40 -> MONITOR_ACCOUNT / ANALYST
    assert decide(0.20, 1000) == ("MONITOR_ACCOUNT", "ANALYST")

    # Boundary: 0.40 <= p < 0.70 -> STEP_UP_AUTH / AUTO
    assert decide(0.50, 1000) == ("STEP_UP_AUTH", "AUTO")

    # Boundary: 0.70 <= p < 0.90 -> BLOCK_TRANSACTION / ANALYST
    assert decide(0.75, 1000) == ("BLOCK_TRANSACTION", "ANALYST")

    # Boundary: p >= 0.90 -> BLOCK_ACCOUNT / SUPERVISOR
    assert decide(0.95, 1000) == ("BLOCK_ACCOUNT", "SUPERVISOR")

    # Policy override: confirmed fraud neighbor immediately escalates to SUPERVISOR
    assert decide(0.05, 1000, confirmed_fraud_neighbor=True) == ("BLOCK_ACCOUNT", "SUPERVISOR")


def test_compute_voi_decision_boundary():
    """
    Validates VOI near decision boundaries:
    - p=0.40 is the STEP_UP_AUTH / MONITOR_ACCOUNT boundary.
    - Assert compute_voi(0.40, 1000, "STEP_UP_AUTH") > 0.
    - Assert compute_voi(0.50, 1000, "STEP_UP_AUTH")[0] > 0.
    """
    voi_boundary = compute_voi(0.40, 1000, "STEP_UP_AUTH")
    assert voi_boundary > 0, f"Expected VOI at boundary > 0, got {voi_boundary}"
    assert voi_boundary[0] > 0

    voi_50 = compute_voi(0.50, 1000, "STEP_UP_AUTH")
    assert voi_50 > 0, f"Expected VOI at p=0.50 > 0, got {voi_50}"
    assert voi_50[0] > 0


def test_compute_sufficiency_near_certainty():
    """
    Validates stopping at near-certainty:
    p=0.02 is already certain legitimate; score should be 0.0 with no evidence needed.
    """
    score, best_type = compute_sufficiency(0.02, 0.0, 0)
    assert score == 0.0, f"Expected score == 0.0 for near-certain legitimate, got {score}"
    assert best_type is None, f"Expected best_type is None, got {best_type}"

    # Also test near-certain fraud (p=0.99)
    score_fraud, best_type_fraud = compute_sufficiency(0.99, 0.0, 0)
    assert score_fraud == 0.0
    assert best_type_fraud is None


def test_compute_sufficiency_budget_and_iteration_limits():
    """
    Validates bounded deliberation constraints:
    - iteration_count >= 3 stops immediately.
    - gathered_cost >= MAX_COST_BUDGET stops immediately.
    """
    score_iter, best_type_iter = compute_sufficiency(0.50, 0.0, 3)
    assert score_iter == 0.0
    assert best_type_iter is None

    score_cost, best_type_cost = compute_sufficiency(0.50, MAX_COST_BUDGET, 0)
    assert score_cost == 0.0
    assert best_type_cost is None


def test_compute_sufficiency_corroborating_signals_override():
    """
    Validates brief's rule: don't ask if already near-certain with >= 2 corroborating signals.
    """
    score, best_type = compute_sufficiency(0.88, 0.0, 0, corroborating_signal_count=2)
    assert score == 0.0
    assert best_type is None


def test_interpret_sufficiency_actions():
    """
    Validates human-readable compliance interpretation.
    """
    interp_gather = interpret_sufficiency(0.7938, "STEP_UP_AUTH", 0)
    assert interp_gather["recommended_action"] == "GATHER_MORE"
    assert interp_gather["next_evidence_type"] == "STEP_UP_AUTH"
    assert interp_gather["stop_reason"] is None

    interp_act = interpret_sufficiency(0.05, "STEP_UP_AUTH", 0)
    assert interp_act["recommended_action"] == "ACT"
    assert "VOI below threshold" in interp_act["stop_reason"]

    interp_exhausted = interpret_sufficiency(0.0, None, 1)
    assert interp_exhausted["recommended_action"] == "ACT"
    assert "further evidence unlikely to change the decision" in interp_exhausted["stop_reason"]


def test_sufficiency_table_sweep():
    """
    Prints comparative sweep at p = 0.1, 0.3, 0.5, 0.7, 0.9.
    Demonstrates gate responsiveness across the decision spectrum.
    """
    probabilities = [0.1, 0.3, 0.5, 0.7, 0.9]
    print("\n" + "=" * 70)
    print(f"{'p_fraud':>7} | {'base_action':<26} | {'best_type':<16} | {'VOI':>6} | {'ask?':<5}")
    print("-" * 70)

    for p in probabilities:
        action, tier = decide(p, 1000)
        base_str = f"{action}/{tier}"
        score, best_type = compute_sufficiency(p, 0.0, 0, txn_amt=1000)
        interp = interpret_sufficiency(score, best_type, 0)
        ask = "YES" if interp["recommended_action"] == "GATHER_MORE" else "NO"
        print(f"{p:>7.2f} | {base_str:<26} | {str(best_type):<16} | {score:>6.3f} | {ask:<5}")
        assert score > VOI_THRESHOLD, f"Expected gate to fire at p={p}, score was {score}"
        assert ask == "YES"

    print("=" * 70)


if __name__ == "__main__":
    pytest.main(["-s", __file__])
