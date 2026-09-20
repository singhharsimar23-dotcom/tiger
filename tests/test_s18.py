"""
S18 tests: Legitimate-Activity Detectors
Each detector must fire on its positive control and NOT fire on its negative control.
"""

import pytest
from innovation.legit_detectors import (
    detect_recurring_charge,
    detect_travel_pattern,
    detect_consistent_new_device,
    run_all_detectors,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

SECONDS_PER_DAY = 86400
BASE_DT = 1_600_000_000  # arbitrary epoch baseline


def make_txn(dt_offset_days=0, amount=99.99, product="W", addr1=100,
             device_info="iPhone14,3", device_type="mobile"):
    return {
        "TransactionDT": BASE_DT + dt_offset_days * SECONDS_PER_DAY,
        "TransactionAmt": amount,
        "ProductCD": product,
        "addr1": addr1,
        "DeviceInfo": device_info,
        "DeviceType": device_type,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test A: detect_recurring_charge
# ─────────────────────────────────────────────────────────────────────────────

def test_recurring_charge_fires():
    """
    POSITIVE: Three prior monthly charges at ~$99.99, new charge at $99.99.
    Detector should fire and return low-score legitimacy evidence.
    """
    history = [
        make_txn(dt_offset_days=0, amount=99.99),
        make_txn(dt_offset_days=30, amount=99.99),
        make_txn(dt_offset_days=60, amount=99.99),
    ]
    txn = make_txn(dt_offset_days=90, amount=99.99)
    result = detect_recurring_charge("ACC_001", txn, history)
    assert result is not None, "Expected recurring charge detector to fire"
    assert result["score"] <= 0.25, f"Legit score must be LOW (<= 0.25), got {result['score']}"
    assert "recurring" in result["description"].lower() or "subscription" in result["description"].lower()
    assert result["source"] == "LEGIT_DETECTOR_RECURRING_CHARGE"


def test_recurring_charge_no_fire_different_amounts():
    """
    NEGATIVE: History has varying amounts — no recurring pattern.
    Detector must NOT fire.
    """
    history = [
        make_txn(dt_offset_days=0, amount=50.00),
        make_txn(dt_offset_days=30, amount=200.00),
        make_txn(dt_offset_days=60, amount=175.00),
    ]
    txn = make_txn(dt_offset_days=90, amount=99.99)
    result = detect_recurring_charge("ACC_001", txn, history)
    assert result is None, "Detector should NOT fire when amounts vary wildly"


def test_recurring_charge_no_fire_insufficient_history():
    """
    NEGATIVE: Only 1 prior matching transaction — not enough to establish pattern.
    """
    history = [make_txn(dt_offset_days=0, amount=99.99)]
    txn = make_txn(dt_offset_days=30, amount=99.99)
    result = detect_recurring_charge("ACC_001", txn, history)
    assert result is None, "Need >= 2 prior matches; should not fire with 1"


# ─────────────────────────────────────────────────────────────────────────────
# Test B: detect_travel_pattern
# ─────────────────────────────────────────────────────────────────────────────

def test_travel_pattern_fires():
    """
    POSITIVE: Home addr1=100, 3 prior travel txns in addr1=200 in the last 5 days,
    same device. New txn also in addr1=200.
    """
    # Establish home region
    home_history = [make_txn(dt_offset_days=i, addr1=100) for i in range(20)]
    # Travel sequence in new region
    travel_history = [
        make_txn(dt_offset_days=25, addr1=200, device_type="mobile"),
        make_txn(dt_offset_days=26, addr1=200, device_type="mobile"),
    ]
    history = home_history + travel_history
    txn = make_txn(dt_offset_days=27, addr1=200, device_type="mobile")
    result = detect_travel_pattern("ACC_002", txn, history)
    assert result is not None, "Expected travel pattern detector to fire"
    assert result["score"] <= 0.25
    assert "travel" in result["description"].lower() or "trip" in result["description"].lower()


def test_travel_pattern_no_fire_same_region():
    """
    NEGATIVE: All transactions in the same region — no "new region" to detect.
    """
    history = [make_txn(dt_offset_days=i, addr1=100) for i in range(10)]
    txn = make_txn(dt_offset_days=11, addr1=100)
    result = detect_travel_pattern("ACC_002", txn, history)
    assert result is None, "Should NOT fire when region hasn't changed"


def test_travel_pattern_no_fire_single_new_txn():
    """
    NEGATIVE: Only 1 prior transaction in the new region — not enough to call it a trip.
    """
    home_history = [make_txn(dt_offset_days=i, addr1=100) for i in range(10)]
    travel_history = [make_txn(dt_offset_days=11, addr1=200)]
    txn = make_txn(dt_offset_days=12, addr1=200)
    result = detect_travel_pattern("ACC_002", txn, travel_history + home_history)
    assert result is None, "Need >= 2 prior travel txns; should not fire with 1"


# ─────────────────────────────────────────────────────────────────────────────
# Test C: detect_consistent_new_device
# ─────────────────────────────────────────────────────────────────────────────

def test_consistent_new_device_fires():
    """
    POSITIVE: 15 prior txns at ~$100 ± small variance with known device.
    New transaction has a DIFFERENT device but same amount/category.
    """
    history = [
        make_txn(dt_offset_days=i, amount=100.0 + (i % 5),
                 device_info="SamsungGalaxyS21", product="C")
        for i in range(15)
    ]
    txn = make_txn(dt_offset_days=16, amount=101.00,
                   device_info="SamsungGalaxyS24", product="C")
    result = detect_consistent_new_device("ACC_003", txn, history)
    assert result is not None, "Expected new-device detector to fire"
    assert result["score"] <= 0.25
    assert "new device" in result["description"].lower() or "upgrade" in result["description"].lower()


def test_consistent_new_device_no_fire_amount_outlier():
    """
    NEGATIVE: New device AND amount is 5x the historical mean — both anomalies together
    should NOT produce a legitimacy signal.
    """
    history = [
        make_txn(dt_offset_days=i, amount=50.0, device_info="OldPhone", product="W")
        for i in range(15)
    ]
    txn = make_txn(dt_offset_days=16, amount=5000.0,  # z-score >> 2
                   device_info="NewPhone", product="W")
    result = detect_consistent_new_device("ACC_003", txn, history)
    assert result is None, "Should NOT fire when amount is a major outlier alongside new device"


def test_consistent_new_device_no_fire_known_device():
    """
    NEGATIVE: Device was seen in the last 90 days — it's not actually new.
    """
    history = [
        make_txn(dt_offset_days=i, amount=100.0, device_info="iPhone14,3")
        for i in range(15)
    ]
    txn = make_txn(dt_offset_days=16, amount=100.0, device_info="iPhone14,3")
    result = detect_consistent_new_device("ACC_003", txn, history)
    assert result is None, "Should NOT fire when device is already known"


# ─────────────────────────────────────────────────────────────────────────────
# Test D: run_all_detectors integration
# ─────────────────────────────────────────────────────────────────────────────

def test_run_all_detectors_returns_list():
    """run_all_detectors always returns (list, int), never raises."""
    evs, count = run_all_detectors("ACC_X", make_txn(), [], case_id="CASE_TEST")
    assert isinstance(evs, list)
    assert isinstance(count, int)
    assert count == len(evs)


def test_run_all_detectors_fires_recurring():
    """With a proper recurring pattern, at least 1 detector should fire."""
    history = [
        make_txn(dt_offset_days=i * 30, amount=49.99)
        for i in range(3)
    ]
    txn = make_txn(dt_offset_days=90, amount=49.99)
    evs, count = run_all_detectors("ACC_X", txn, history, case_id="CASE_T1")
    assert count >= 1, "Expected at least recurring detector to fire"
    # All fired evidences must have low legitimacy scores
    for ev in evs:
        assert ev["score"] <= 0.25, f"Legit evidence score must be <= 0.25, got {ev['score']}"
        assert "evidence_id" in ev


if __name__ == "__main__":
    pytest.main(["-v", __file__])
