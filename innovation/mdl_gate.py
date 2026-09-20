"""
Minimum Description Length (MDL) Information-Theoretic Evidence Sufficiency Gate.
Provides an information-theoretic framework to determine whether an investigation has
sufficient evidence to transition from hypothesis exploration to enforcement actions.
"""

import math
from typing import Dict, Any, Union

# Module Constants
MDL_THRESHOLD = 0.25
MAX_ITERATIONS = 3

class _EvidenceCostDict(dict):
    def get(self, key: Any, default: float = 1.0) -> float:
        k = getattr(key, "value", key)
        return super().get(k, super().get(key, default))

    def __getitem__(self, key: Any) -> float:
        k = getattr(key, "value", key)
        if k in self:
            return super().__getitem__(k)
        return super().__getitem__(key)

# Information acquisition costs per evidence category (normalized)
EVIDENCE_COST: Dict[Any, float] = _EvidenceCostDict({
    "GRAPH_NEIGHBORHOOD": 0.05,
    "SHARED_DEVICE": 0.10,
    "SHARED_DOMAIN": 0.10,
    "SHARED_ADDRESS": 0.10,
    "PATTERN_MATCH": 0.15,
    "POLICY_TRIGGER": 0.05,
    "PRIOR_CASE_SIMILARITY": 0.20,
    "DEEP_EXPANSION": 0.30,
})

def binary_entropy(p: float) -> float:
    """
    Computes Shannon binary entropy H(p) = -p*log2(p) - (1-p)*log2(1-p).
    Handles edge cases: p <= 0, p >= 1, NaN -> returns 0.0.
    """
    if p is None:
        return 0.0
    try:
        if math.isnan(p) or math.isinf(p):
            return 0.0
    except TypeError:
        return 0.0

    if p <= 0.0 or p >= 1.0:
        return 0.0

    # Strict clamping for floating-point safety
    p = max(1e-12, min(1.0 - 1e-12, p))
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))

def compute_expected_ig(p: float, action_type: str = "STEP_UP_AUTH") -> float:
    """
    Computes expected Information Gain (IG) from acquiring additional evidence.
    Modeled as the expected reduction in binary entropy given signal reliability.
    """
    current_h = binary_entropy(p)
    if current_h == 0.0:
        return 0.0

    # Estimated likelihood ratio / signal strength by investigative action
    signal_strengths = {
        "STEP_UP_AUTH": 0.85,
        "DEEP_GRAPH_EXPANSION": 0.80,
        "IDENTITY_CORRELATION": 0.75,
        "ACCOUNT_HISTORY": 0.65,
    }
    alpha = signal_strengths.get(action_type, 0.70)

    # Expected posterior probabilities given positive or negative test outcome
    # P(pos) = alpha*p + (1-alpha)*(1-p)
    p_pos = alpha * p + (1.0 - alpha) * (1.0 - p)
    p_neg = 1.0 - p_pos

    # Posteriors via Bayes rule
    post_pos = (alpha * p) / max(p_pos, 1e-12)
    post_neg = ((1.0 - alpha) * p) / max(p_neg, 1e-12)

    expected_posterior_h = p_pos * binary_entropy(post_pos) + p_neg * binary_entropy(post_neg)
    ig = current_h - expected_posterior_h
    return max(0.0, ig)

def compute_sufficiency(p: float, gathered_cost: float, iters: int) -> float:
    """
    Evaluates evidence sufficiency under the Minimum Description Length principle:
      Net Gain = Expected Information Gain - Marginal Cost Penalty
    
    Returns:
      Sufficiency score (expected net gain). If score < MDL_THRESHOLD or iters >= MAX_ITERATIONS,
      the system has reached evidence sufficiency (should ACT).
    """
    # 1. Hard iteration limit (bounded deliberation)
    if iters >= MAX_ITERATIONS:
        return 0.0

    # 2. Certainty boundary conditions (p >= 0.98 or p <= 0.02)
    if p is None or p >= 0.98 or p <= 0.02:
        return 0.0

    current_h = binary_entropy(p)
    if current_h < 0.15:
        # Near certainty; description length already minimized
        return 0.0

    # 3. Expected Information Gain from deepening investigation
    expected_ig = compute_expected_ig(p, action_type="DEEP_GRAPH_EXPANSION")

    # 4. Description length cost regularization: penalize redundant sampling
    cost_penalty = 0.10 * math.sqrt(gathered_cost + 0.1) * (iters * 0.5 + 0.5)

    net_gain = expected_ig - cost_penalty
    return max(0.0, net_gain)

def interpret_sufficiency(score: float, iteration_count: int) -> Dict[str, Any]:
    """
    Returns a human-readable interpretation for the compliance and case record.
    """
    if score < MDL_THRESHOLD or iteration_count >= MAX_ITERATIONS:
        return {
            "score": round(score, 4),
            "recommended_action": "ACT",
            "interpretation": f"Evidence sufficiency threshold met (score={score:.3f})",
            "reasoning": "Expected information gain from additional evidence below cost threshold"
        }
    else:
        return {
            "score": round(score, 4),
            "recommended_action": "GATHER_MORE",
            "interpretation": f"Additional evidence recommended (score={score:.3f})",
            "reasoning": f"Expected gain {score:.3f} > threshold {MDL_THRESHOLD}"
        }
