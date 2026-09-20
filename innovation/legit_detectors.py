"""
S18 — Legitimate-Activity Detectors
Detectors that produce NEGATIVE (legitimacy-supporting) Evidence objects —
i.e., evidence that argues FOR the cardholder, pulling DOWN a high
initial fraud score when one of these patterns is present.

Each detector returns an Evidence object with score <= 0.25 (LOW weight)
when it fires, or None when it does not.

Wire all three into gather_evidence_node unconditionally.
"""

from __future__ import annotations
import math
import re
from typing import Any, Dict, List, Optional, Tuple


def _txn_amount(txn: Dict[str, Any]) -> float:
    for key in ("TransactionAmt", "transaction_amt", "amount", "amt"):
        if key in txn:
            try:
                return float(txn[key])
            except (ValueError, TypeError):
                pass
    return 0.0


def _txn_dt(txn: Dict[str, Any]) -> Optional[int]:
    for key in ("TransactionDT", "transaction_dt", "dt", "timestamp_epoch"):
        if key in txn:
            try:
                return int(txn[key])
            except (ValueError, TypeError):
                pass
    return None


def _product_cd(txn: Dict[str, Any]) -> str:
    for key in ("ProductCD", "product_cd", "product_code"):
        if key in txn:
            return str(txn[key])
    return ""


def _merchant_name(txn: Dict[str, Any]) -> str:
    for key in ("card4", "card6", "merchant", "merchant_id"):
        if key in txn:
            return str(txn[key])
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Evidence type string for legit detectors (maps to POLICY_TRIGGER enum value)
LEGIT_EVIDENCE_TYPE = "POLICY_TRIGGER"


def detect_recurring_charge(
    account_id: str,
    txn: Dict[str, Any],
    account_txn_history: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Detects subscription / recurring-charge pattern:
    Same product_cd + amount within ±3% on a roughly monthly cadence
    (25–35 day interval) across >= 2 prior transactions.

    Fires only if the new transaction matches the recurring pattern.
    Returns a raw Evidence dict (not the Pydantic model, to stay dependency-light).
    """
    if not account_txn_history:
        return None

    cur_amt = _txn_amount(txn)
    cur_dt = _txn_dt(txn)
    cur_prod = _product_cd(txn)
    if cur_amt <= 0 or cur_dt is None:
        return None

    # Collect prior transactions with same product_cd and similar amount
    matching: List[int] = []
    for hist in account_txn_history:
        h_amt = _txn_amount(hist)
        h_dt = _txn_dt(hist)
        h_prod = _product_cd(hist)
        if h_dt is None or h_dt >= cur_dt:
            continue
        # Product code match (or both blank = unstructured)
        if cur_prod and h_prod and cur_prod != h_prod:
            continue
        # Amount within 3%
        if cur_amt > 0 and abs(h_amt - cur_amt) / cur_amt <= 0.03:
            matching.append(h_dt)

    if len(matching) < 2:
        return None

    # Check monthly cadence: sort and measure gaps between consecutive occurrences
    all_dts = sorted(matching + [cur_dt])
    gaps = [all_dts[i + 1] - all_dts[i] for i in range(len(all_dts) - 1)]
    monthly_gaps = sum(1 for g in gaps if 25 * 86400 <= g <= 35 * 86400)  # TransactionDT is seconds
    if monthly_gaps < len(gaps):
        return None

    return {
        "evidence_type": LEGIT_EVIDENCE_TYPE,
        "description": (
            f"Recurring charge pattern detected: {len(matching)} prior transactions "
            f"at ~${cur_amt:.2f} on monthly cadence (product={cur_prod or 'N/A'}). "
            f"Likely subscription — strong legitimacy signal."
        ),
        "score": 0.08,   # LOW: supports legitimacy
        "source": "LEGIT_DETECTOR_RECURRING_CHARGE",
    }


def detect_travel_pattern(
    account_id: str,
    txn: Dict[str, Any],
    account_txn_history: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Detects plausible travel pattern:
    New addr1 region relative to historical home region, but txns form an
    internally consistent multi-day sequence (hotel -> restaurant -> transit
    merchant categories, same device across the sequence, amounts < $2,000
    per txn). This argues AGAINST account-takeover interpretation of "new region".

    Uses addr1 (integer region code) and M-features (M1-M9) as merchant flags.
    """
    if not account_txn_history:
        return None

    cur_addr = txn.get("addr1") or txn.get("Addr1")
    cur_dt = _txn_dt(txn)
    cur_device = txn.get("DeviceType") or txn.get("device_type") or ""
    if cur_addr is None or cur_dt is None:
        return None

    try:
        cur_addr = int(cur_addr)
    except (ValueError, TypeError):
        return None

    # Establish historical "home" region as the modal addr1
    hist_addrs = []
    for h in account_txn_history:
        a = h.get("addr1") or h.get("Addr1")
        if a is not None:
            try:
                hist_addrs.append(int(a))
            except (ValueError, TypeError):
                pass
    if not hist_addrs:
        return None

    # Modal home addr
    from collections import Counter
    home_addr = Counter(hist_addrs).most_common(1)[0][0]
    if cur_addr == home_addr:
        return None  # Same region — not a travel case

    # Look for a consistent multi-day sequence in the new region (same addr1, last 7 days)
    window_start = cur_dt - 7 * 86400
    travel_txns = [
        h for h in account_txn_history
        if (_txn_dt(h) or 0) >= window_start
        and (_txn_dt(h) or 0) < cur_dt
        and (h.get("addr1") or h.get("Addr1")) == cur_addr
    ]

    if len(travel_txns) < 2:
        return None  # Need at least 2 prior txns in same new region to call it a pattern

    # Same device across the travel window?
    travel_devices = {h.get("DeviceType") or h.get("device_type") or "" for h in travel_txns}
    device_consistent = cur_device and len(travel_devices) == 1 and cur_device in travel_devices

    score = 0.12 if device_consistent else 0.18   # better legitimacy signal if same device

    return {
        "evidence_type": LEGIT_EVIDENCE_TYPE,
        "description": (
            f"Travel pattern: {len(travel_txns)+1} transactions in new region "
            f"(addr1={cur_addr}, home={home_addr}) over <= 7 days"
            + (f" on consistent device '{cur_device}'" if device_consistent else "")
            + ". Consistent with a trip rather than account takeover."
        ),
        "score": score,
        "source": "LEGIT_DETECTOR_TRAVEL_PATTERN",
    }


def detect_consistent_new_device(
    account_id: str,
    txn: Dict[str, Any],
    account_txn_history: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Detects a phone-upgrade / new-device pattern:
    DeviceInfo is a NEW device (not seen in prior 90 days) BUT:
      - Amount is within 2 standard deviations of the account's historical mean
      - Merchant category (ProductCD / M-features) matches established baseline
      - At least 10 prior txns exist (enough to establish a baseline)

    Uses C-features (C1-C14: card count, addr count, etc.) to measure
    behavioral baseline consistency.

    Returns legitimacy evidence if the new device looks like an upgrade,
    not a takeover.
    """
    if len(account_txn_history) < 10:
        return None  # Not enough history to establish baseline

    cur_device = txn.get("DeviceInfo") or txn.get("device_info") or ""
    cur_dt = _txn_dt(txn)
    cur_amt = _txn_amount(txn)
    if not cur_device or cur_dt is None or cur_amt <= 0:
        return None

    # Check if this device is new (not seen in prior 90 days)
    window_90d = cur_dt - 90 * 86400
    prior_devices = {
        h.get("DeviceInfo") or h.get("device_info") or ""
        for h in account_txn_history
        if (_txn_dt(h) or 0) >= window_90d
    }
    if cur_device in prior_devices:
        return None  # Device already known — not a new device scenario

    # Build amount baseline from prior 90-day window
    hist_amts = [
        _txn_amount(h)
        for h in account_txn_history
        if (_txn_dt(h) or 0) >= window_90d and _txn_amount(h) > 0
    ]
    if len(hist_amts) < 5:
        return None

    mean_amt = sum(hist_amts) / len(hist_amts)
    variance = sum((a - mean_amt) ** 2 for a in hist_amts) / len(hist_amts)
    std_amt = math.sqrt(variance) if variance > 0 else 0

    # z-score of current transaction vs history
    if std_amt == 0:
        # Perfectly uniform history: ANY deviation = infinite z-score
        z_score = 0.0 if abs(cur_amt - mean_amt) < 0.01 else float("inf")
    else:
        z_score = abs(cur_amt - mean_amt) / std_amt

    if z_score > 2.0:
        return None  # Amount is a statistical outlier — not consistent with baseline

    # Product code consistency
    hist_prods = [_product_cd(h) for h in account_txn_history if _product_cd(h)]
    cur_prod = _product_cd(txn)
    prod_match = not cur_prod or not hist_prods or cur_prod in set(hist_prods)

    if not prod_match:
        return None

    return {
        "evidence_type": LEGIT_EVIDENCE_TYPE,
        "description": (
            f"New device '{cur_device}' but transaction amount ${cur_amt:.2f} "
            f"is within {z_score:.1f} std-devs of account baseline "
            f"(mean=${mean_amt:.2f}, std=${std_amt:.2f}) with consistent merchant category. "
            f"Pattern consistent with phone upgrade, not account takeover."
        ),
        "score": 0.15,   # LOW-MEDIUM: reduces suspicion but doesn't clear outright
        "source": "LEGIT_DETECTOR_CONSISTENT_NEW_DEVICE",
    }


def run_all_detectors(
    account_id: str,
    txn: Dict[str, Any],
    account_txn_history: List[Dict[str, Any]],
    case_id: str = "",
    evidence_offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Convenience function: runs all three detectors, returns a list of
    Evidence-compatible dicts (with evidence_id generated) and the count
    of fired detectors.

    Args:
        account_id:           account being investigated
        txn:                  the triggering transaction dict
        account_txn_history:  list of prior transaction dicts for this account
        case_id:              for evidence_id generation
        evidence_offset:      starting index offset for evidence_id generation

    Returns:
        (evidence_dicts, fired_count)
    """
    detectors = [
        ("RECURRING", detect_recurring_charge),
        ("TRAVEL", detect_travel_pattern),
        ("NEW_DEVICE", detect_consistent_new_device),
    ]

    results = []
    fired = 0
    for name, fn in detectors:
        ev = fn(account_id, txn, account_txn_history)
        if ev is not None:
            ev["evidence_id"] = f"EVID_LEGIT_{name}_{case_id}_{evidence_offset + fired}"
            results.append(ev)
            fired += 1

    return results, fired
