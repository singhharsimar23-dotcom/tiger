"""
Decision-Relevant (VOI) Evidence Gate — Replaces MDL Entropy Gate.
Evaluates Value of Information (VOI) by computing the exact probability
that gathering an additional piece of evidence will flip the deterministic
policy decision (action type and approval tier).
"""

import math
from typing import Dict, Any, Union, Tuple, Optional, Set


class VOIFloat(float):
    """Float that allows [0] indexing for backwards/toy compatibility."""
    def __getitem__(self, idx: int) -> float:
        if idx == 0:
            return float(self)
        raise IndexError("tuple index out of range")


class SufficiencyResult(tuple):
    """
    2-tuple subclass returning (score, best_evidence_type) while maintaining
    direct float comparison compatibility with legacy call sites.
    """
    def __new__(cls, score: float, best_type: Optional[str]):
        return super().__new__(cls, (score, best_type))

    @property
    def score(self) -> float:
        return self[0]

    @property
    def best_type(self) -> Optional[str]:
        return self[1]

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self[0] > other
        return super().__gt__(other)

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self[0] < other
        return super().__lt__(other)

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self[0] >= other
        return super().__ge__(other)

    def __le__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self[0] <= other
        return super().__le__(other)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self[0] == other
        return super().__eq__(other)

    def __float__(self) -> float:
        return float(self[0])


def decide(fraud_probability: float, txn_amt: float = 0.0,
           confirmed_fraud_neighbor: bool = False) -> Tuple[str, str]:
    """
    PURE deterministic function: facts in, (action_type, approval_tier) out.
    This IS your policy-as-code layer (also referenced by S16) — the LLM
    NEVER picks the action; it only estimates fraud_probability from evidence.
    Mirrors PROJECT.md Section 2.5's approval tier table exactly.
    """
    if confirmed_fraud_neighbor or fraud_probability >= 0.90:
        return ("BLOCK_ACCOUNT", "SUPERVISOR")
    if fraud_probability >= 0.70:
        return ("BLOCK_TRANSACTION", "AUTO" if fraud_probability > 0.9 else "ANALYST")
    if fraud_probability >= 0.40:
        return ("STEP_UP_AUTH", "AUTO")
    if fraud_probability >= 0.15:
        return ("MONITOR_ACCOUNT", "ANALYST")
    return ("ALLOW_TRANSACTION", "AUTO")


# Per-evidence-type branch distributions, calibrated from the SAME stub
# functions used in gather_more_evidence_node (Section 2.6):
#   STEP_UP_AUTH: {"pass": 0.85, "fail": 0.15}          (matches stub_seed > 150 threshold)
#   CUSTOMER_CONTACT: {"confirm": 0.70, "deny": 0.30}    (matches stub_seed < 700 threshold)
#   ANALYST_QUERY: {"corroborate": 0.5, "clear": 0.5}    (no stub bias; symmetric is fine here)
BRANCH_PROBS: Dict[str, Dict[str, float]] = {
    "STEP_UP_AUTH":     {"pass": 0.85, "fail": 0.15},
    "CUSTOMER_CONTACT":  {"confirm": 0.70, "deny": 0.30},
    "ANALYST_QUERY":     {"corroborate": 0.5, "clear": 0.5},
}

# Posterior shift per branch, per evidence type. Hand-set from the weight heuristics
# in EVIDENCE_SYNTHESIS_PROMPT (Section 8.1) so numbers and LLM evidence weights agree.
POSTERIOR_SHIFT = {
    ("STEP_UP_AUTH", "fail"):        lambda p: min(0.97, p + (1 - p) * 0.4),
    ("STEP_UP_AUTH", "pass"):        lambda p: max(0.02, p * 0.85),
    ("CUSTOMER_CONTACT", "deny"):    lambda p: min(0.97, p + (1 - p) * 0.6),
    ("CUSTOMER_CONTACT", "confirm"): lambda p: max(0.02, p * 0.25),
    ("ANALYST_QUERY", "corroborate"):lambda p: min(0.95, p + (1 - p) * 0.3),
    ("ANALYST_QUERY", "clear"):      lambda p: max(0.05, p * 0.5),
}

EVIDENCE_COST: Dict[str, float] = {
    "STEP_UP_AUTH": 1.5,
    "ANALYST_QUERY": 3.0,
    "CUSTOMER_CONTACT": 3.5,
}
MAX_COST_BUDGET: float = 8.0
VOI_THRESHOLD: float = 0.15   # ask only if there's a >=15% chance the decision itself flips
MDL_THRESHOLD: float = VOI_THRESHOLD
MAX_ITERATIONS: int = 3


def compute_voi(fraud_probability: float, txn_amt: float = 0.0,
                 evidence_type: str = "STEP_UP_AUTH",
                 confirmed_fraud_neighbor: bool = False) -> VOIFloat:
    """Probability that gathering `evidence_type` changes (action, tier)."""
    base = decide(fraud_probability, txn_amt, confirmed_fraud_neighbor)
    branches = BRANCH_PROBS.get(evidence_type, {"yes": 0.5, "no": 0.5})
    changed_mass = 0.0
    for branch, pr in branches.items():
        shift_fn = POSTERIOR_SHIFT.get((evidence_type, branch))
        p_after = shift_fn(fraud_probability) if shift_fn else fraud_probability
        if decide(p_after, txn_amt, confirmed_fraud_neighbor) != base:
            changed_mass += pr
    return VOIFloat(changed_mass)


def compute_sufficiency(fraud_probability: float, gathered_cost: float = 0.0,
                         iteration_count: int = 0, txn_amt: float = 0.0,
                         confirmed_fraud_neighbor: bool = False,
                         corroborating_signal_count: int = 0,
                         excluded_types: Optional[Set[str]] = None) -> SufficiencyResult:
    """
    DROP-IN REPLACEMENT for the old signature (adds optional kwargs with
    defaults so existing call sites in nodes.py keep working unmodified).
    Returns (score, best_evidence_type_to_gather_next).
    """
    if iteration_count >= 3 or gathered_cost >= MAX_COST_BUDGET:
        return SufficiencyResult(0.0, None)
    if fraud_probability is None or fraud_probability <= 0.02 or fraud_probability >= 0.98:
        return SufficiencyResult(0.0, None)
    # Brief's own override: don't ask if already near-certain with >=2 corroborating signals
    if (fraud_probability >= 0.85 or fraud_probability <= 0.15) and corroborating_signal_count >= 2:
        return SufficiencyResult(0.0, None)

    best_score, best_type = 0.0, None
    for etype, cost in EVIDENCE_COST.items():
        if excluded_types and etype in excluded_types:
            continue
        v = compute_voi(fraud_probability, txn_amt, etype, confirmed_fraud_neighbor)
        net = float(v) - (cost / MAX_COST_BUDGET) * 0.3   # cost still discounts, doesn't dominate
        if net > best_score:
            best_score, best_type = net, etype
    return SufficiencyResult(best_score, best_type)


def interpret_sufficiency(score: Union[float, SufficiencyResult, Tuple[float, Any]],
                          best_type: Any = None,
                          iteration_count: int = 0) -> Dict[str, Any]:
    """
    Translates sufficiency score and recommendation into audit-ready decision records.
    Accommodates both new signature (score, best_type, iteration_count) and legacy
    signature (score, iteration_count).
    """
    if isinstance(best_type, int) and iteration_count == 0:
        iteration_count = best_type
        best_type = "ADDITIONAL_EVIDENCE"

    if isinstance(score, (tuple, SufficiencyResult)):
        score_val = float(score[0])
        if (best_type is None or best_type == "ADDITIONAL_EVIDENCE") and len(score) > 1:
            best_type = score[1]
    else:
        score_val = float(score)

    if score_val < VOI_THRESHOLD or best_type is None or iteration_count >= 3:
        stop_reason = (
            "further evidence unlikely to change the decision"
            if best_type is None
            else f"VOI below threshold ({score_val:.2f} < {VOI_THRESHOLD})"
        )
        return {
            "score": round(score_val, 4),
            "recommended_action": "ACT",
            "next_evidence_type": None,
            "stop_reason": stop_reason,
            "interpretation": f"Evidence sufficiency threshold met (score={score_val:.3f})",
            "reasoning": stop_reason
        }

    return {
        "score": round(score_val, 4),
        "recommended_action": "GATHER_MORE",
        "next_evidence_type": best_type,
        "stop_reason": None,
        "reasoning": f"gathering {best_type} has an estimated "
                     f"{score_val:.0%} chance of flipping the recommended action/route",
        "interpretation": f"Additional evidence recommended ({best_type}, score={score_val:.3f})"
    }


# Backwards compatibility helpers for legacy unit tests and diagnostics
def binary_entropy(p: Optional[float]) -> float:
    if p is None:
        return 0.0
    try:
        if math.isnan(p) or math.isinf(p):
            return 0.0
    except TypeError:
        return 0.0
    if p <= 0.0 or p >= 1.0:
        return 0.0
    p = max(1e-12, min(1.0 - 1e-12, p))
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def compute_expected_ig(p: float, action_type: str = "STEP_UP_AUTH") -> float:
    return float(compute_voi(p, 0.0, action_type))
