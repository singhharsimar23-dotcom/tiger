"""
innovation/statistical_baseline.py -- S19 Statistical Grounding Layer

Computes per-card behavioral baseline from prior transaction history.
Every number is mechanically derived from graph data -- NOT LLM opinion.
"""
import math, statistics
from typing import Optional


def compute_card_baseline(card_id: str, exclude_txn_id: str,
                          all_card_txns: list) -> Optional[dict]:
    """
    Returns behavioral baseline for card from prior txn history,
    excluding the flagged txn.
    Returns None if fewer than 3 prior txns -- insufficient history.
    Callers must NOT infer legitimacy or fraud from a None return.
    """
    prior = [t for t in all_card_txns if t.get("txn_id") != exclude_txn_id]
    n = len(prior)
    if n < 3:
        return None
    amounts = [float(t.get("amount", 0)) for t in prior]
    amt_mean = statistics.mean(amounts)
    amt_std = statistics.stdev(amounts) if n >= 2 else 0.0
    known_product_cds = {str(t.get("product_cd", "")).strip() for t in prior if t.get("product_cd")}
    known_regions = {str(t.get("addr1", "")).strip() for t in prior if t.get("addr1")}
    ch_counts: dict = {}
    for t in prior:
        ch = str(t.get("channel", "unknown")).strip().lower()
        ch_counts[ch] = ch_counts.get(ch, 0) + 1
    dominant_channel = max(ch_counts, key=ch_counts.get) if ch_counts else "unknown"
    return {
        "amt_mean": round(amt_mean, 4),
        "amt_std": round(amt_std, 4),
        "known_product_cds": known_product_cds,
        "known_regions": known_regions,
        "dominant_channel": dominant_channel,
        "n_prior_txns": n,
    }


def score_transaction_anomaly(txn: dict, baseline: Optional[dict]) -> dict:
    """
    Returns explainable anomaly breakdown. statistical_anomaly_score = signals_triggered / 4.
    If baseline is None: score is None, explanation states insufficient history.
    """
    if baseline is None:
        return {
            "amt_zscore": None,
            "product_cd_novel": False,
            "region_novel": False,
            "channel_shift": False,
            "signals_triggered": 0,
            "statistical_anomaly_score": None,
            "explanation": (
                "Insufficient transaction history for this card to establish a baseline"
                " -- treat as informational absence, not as evidence of legitimacy or fraud."
            ),
        }
    txn_amount = float(txn.get("amount", 0))
    txn_product = str(txn.get("product_cd", "")).strip()
    txn_region = str(txn.get("addr1", "")).strip()
    txn_channel = str(txn.get("channel", "")).strip().lower()
    amt_std = baseline["amt_std"]
    amt_zscore = ((txn_amount - baseline["amt_mean"]) / amt_std) if amt_std > 0 else 0.0
    amt_anomalous = abs(amt_zscore) > 2.0
    product_cd_novel = bool(txn_product and baseline["known_product_cds"] and txn_product not in baseline["known_product_cds"])
    region_novel = bool(txn_region and baseline["known_regions"] and txn_region not in baseline["known_regions"])
    channel_shift = bool(txn_channel and baseline["dominant_channel"] != "unknown" and txn_channel != baseline["dominant_channel"])
    signals_triggered = sum([amt_anomalous, product_cd_novel, region_novel, channel_shift])
    return {
        "amt_zscore": round(amt_zscore, 4),
        "product_cd_novel": product_cd_novel,
        "region_novel": region_novel,
        "channel_shift": channel_shift,
        "signals_triggered": signals_triggered,
        "statistical_anomaly_score": round(signals_triggered / 4.0, 4),
        "explanation": (
            f"amt z={amt_zscore:.2f}{'[ANOMALOUS]' if amt_anomalous else ''}; "
            f"product_cd {'novel' if product_cd_novel else 'matches history'}; "
            f"region {'novel' if region_novel else 'matches history'}; "
            f"channel {'shifted' if channel_shift else 'consistent'}. {signals_triggered}/4 signals fired."
        ),
    }


def check_disagreement_and_escalate(llm_p: float, stat_score: Optional[float],
                                     threshold: float = 0.4) -> dict:
    """
    If |llm_p - stat_score| > threshold: override to uncertain, force R8 escalation.
    Returns dict with should_escalate, disagreement, log_message.
    """
    if stat_score is None:
        return {"should_escalate": False, "disagreement": None,
                "log_message": "No statistical baseline -- disagreement check skipped."}
    disagreement = abs(llm_p - stat_score)
    if disagreement > threshold:
        return {
            "should_escalate": True,
            "disagreement": round(disagreement, 4),
            "log_message": (
                f"ESCALATING PER R8: LLM={llm_p:.2f}, statistical={stat_score:.2f}, "
                f"gap={disagreement:.2f} > {threshold} unexplained by cited evidence."
            ),
        }
    return {"should_escalate": False, "disagreement": round(disagreement, 4),
            "log_message": f"LLM={llm_p:.2f}, stat={stat_score:.2f}, gap={disagreement:.2f} -- no escalation."}
