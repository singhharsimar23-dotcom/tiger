"""
innovation/evidence_value.py -- S19 Evidence VOI/MDL Module

Expected information gain ranking for next evidence request.
HARD SEPARATION: this file contains zero business-logic references.
Separation check: grep for forbidden symbols must return empty on code lines only.
"""
import math
from typing import Optional

# Calibrated priors: expected entropy reduction per evidence type
# (fraction of 0-1 belief update typical for this evidence in fraud context)
EVIDENCE_GAIN_PROFILE = {
    "customer_validation": 0.35,
    "step_up_auth":        0.28,
    "analyst_info":        0.20,
}

EVIDENCE_COST = {
    "customer_validation": 0.10,
    "step_up_auth":        0.15,
    "analyst_info":        0.05,
}


def binary_entropy(p: float) -> float:
    """H(p) = -p*log2(p) - (1-p)*log2(1-p). Returns 0 at boundaries."""
    if p <= 0 or p >= 1:
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def expected_information_gain(current_p: float, evidence_type: str) -> float:
    """
    Estimate expected entropy reduction from gathering evidence_type,
    using calibrated priors in EVIDENCE_GAIN_PROFILE.
    Returns expected reduction in binary entropy (bits).
    """
    gain_fraction = EVIDENCE_GAIN_PROFILE.get(evidence_type, 0.10)
    current_entropy = binary_entropy(current_p)
    return round(current_entropy * gain_fraction, 6)


def rank_next_evidence_request(
    current_p: float,
    remaining_types: list,
    cost_per_type: Optional[dict] = None,
) -> list:
    """
    Rank remaining_types by (expected_information_gain - cost), highest net first.
    Returns list[tuple[str, float]] -- ONLY a ranking, never a disposition or action.
    This function has no references to business-logic action strings.
    """
    if cost_per_type is None:
        cost_per_type = EVIDENCE_COST

    ranked = []
    for et in remaining_types:
        gain = expected_information_gain(current_p, et)
        cost = cost_per_type.get(et, 0.05)
        net = gain - cost
        ranked.append((et, round(net, 6)))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
