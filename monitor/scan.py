#!/usr/bin/env python3
"""
S21 — Monitor Mode: unattended scan of the unlabeled dataset window.

Runs a lightweight screening pass (investigate_node + gather_evidence_node only,
NO full agentic loop) across every transaction in the unlabeled months of the
IEEE-CIS dataset. Surfaces cases where the AGENT's calibrated model score
DISAGREES most with the BANK's own risk_score — specifically: agent thinks it's
riskier than the bank does.

Top-N disagreements then receive a FULL investigation run.

Usage:
    python monitor/scan.py [--top-n 10] [--full-run] [--dry-run]

Output:
    monitor/outputs/disagreement_summary.json
    monitor/outputs/top_N/          (full investigation outputs for top-N)

The "unlabeled window" is everything BEYOND the labeled training split.
For this dataset that is TransactionDT >= 15_897_600.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import pandas as pd

from agent.state import InvestigationState, CaseStatus, ActionType, approval_route
from agent.nodes import investigate_node, gather_evidence_node
from tools import tg_tools
from innovation.legit_detectors import run_all_detectors as _run_legit_detectors

def decide(score: float, exposure_usd: float = 0.0) -> tuple:
    if score >= 0.70:
        act = ActionType.BLOCK_CARD
    elif score >= 0.40:
        act = ActionType.VERIFY_WITH_CUSTOMER
    else:
        act = ActionType.ALLOW_TRANSACTION
    return act.value, approval_route(act, exposure_usd).value

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DATASET_PATH = Path(os.getenv("DATASET_PATH", str(ROOT / "data")))
TRANSACTION_FILE = DATASET_PATH / "transactions.csv"
IDENTITY_FILE = DATASET_PATH / "identity.csv"

# Dataset test split boundary (TransactionDT epoch offset)
# Training data covers DT 86400 – 15897600 (~184 days)
# We treat the final 20% (DT >= 12718080) as the "unlabeled window"
UNLABELED_DT_START = int(os.getenv("MONITOR_DT_START", "12718080"))

MONITOR_OUT = ROOT / "monitor" / "outputs"
MONITOR_OUT.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Data loading helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_unlabeled_transactions(max_rows: int = 50_000) -> pd.DataFrame:
    """
    Load the unlabeled (later-month) transactions from the IEEE-CIS CSV.
    Columns used: TransactionID, TransactionDT, TransactionAmt, isFraud (label),
    card1-card6, addr1, addr2, P_emaildomain, R_emaildomain, DeviceType, DeviceInfo,
    ProductCD, and the bank's own risk proxy (we use TransactionAmt + card-level
    velocity as a risk heuristic since the bank's score isn't a named column in the
    public dataset — see note below).

    NOTE on "bank risk score":
    The IEEE-CIS public dataset does NOT include an explicit "bank risk_score" column.
    We proxy the bank's score using the LABEL column (isFraud) where available,
    and a simple heuristic (high-amount + new region = 0.7) for unlabeled rows.
    For a real production deployment, substitute your institution's model output here.
    """
    if not TRANSACTION_FILE.exists():
        print(f"[MONITOR] WARNING: dataset not found at {TRANSACTION_FILE}")
        print("[MONITOR] Running in SYNTHETIC mode (50 fake transactions)")
        return _synthetic_transactions(50)

    print(f"[MONITOR] Loading transactions from {TRANSACTION_FILE} ...")
    df = pd.read_csv(
        TRANSACTION_FILE,
        usecols=lambda c: c in {
            "TransactionID", "TransactionDT", "TransactionAmt",
            "ProductCD", "card1", "card4", "addr1", "addr2",
            "P_emaildomain", "R_emaildomain", "DeviceType", "DeviceInfo",
            "isFraud", "C1", "C14",
        },
        nrows=max_rows,
    )
    # Filter to unlabeled window
    unlabeled = df[df["TransactionDT"] >= UNLABELED_DT_START].copy()
    if unlabeled.empty:
        print("[MONITOR] No rows in unlabeled window — using full dataset tail")
        unlabeled = df.tail(min(len(df), 5000)).copy()

    print(f"[MONITOR] {len(unlabeled)} transactions in unlabeled window")
    return unlabeled


def _synthetic_transactions(n: int = 50) -> pd.DataFrame:
    """Synthetic fallback when no CSV is present."""
    import random
    random.seed(42)
    rows = []
    base_dt = UNLABELED_DT_START
    for i in range(n):
        rows.append({
            "TransactionID": 3_000_000 + i,
            "TransactionDT": base_dt + i * 3600,
            "TransactionAmt": round(random.uniform(5.0, 5000.0), 2),
            "ProductCD": random.choice(["W", "H", "C", "S", "R"]),
            "card1": random.randint(1000, 9999),
            "card4": random.choice(["visa", "mastercard", "discover"]),
            "addr1": random.choice([100, 200, 300, 400] + [500] * 10),  # bias home
            "DeviceType": random.choice(["desktop", "mobile", None]),
            "DeviceInfo": random.choice(["Windows", "iOS Device", "MacOS", None]),
            "isFraud": random.choices([0, 1], weights=[0.97, 0.03])[0],
            "C1": random.randint(0, 10),
            "C14": random.randint(0, 15),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Bank-score proxy
# ─────────────────────────────────────────────────────────────────────────────

def bank_score_proxy(row: Dict[str, Any]) -> float:
    """
    Heuristic bank risk score for the IEEE-CIS public dataset
    (substitute with real bank model output in production).

    Uses: isFraud label (if available) as a perfect proxy, otherwise
    derives from amount percentile + region novelty.
    """
    if "isFraud" in row and row["isFraud"] is not None and not _is_nan(row["isFraud"]):
        return float(row["isFraud"])  # perfect proxy where labelled

    # Heuristic for unlabeled rows
    amt = float(row.get("TransactionAmt") or 0)
    score = 0.0
    if amt > 2000:
        score += 0.35
    elif amt > 500:
        score += 0.15
    addr1 = row.get("addr1")
    if addr1 and not _is_nan(addr1):
        score += 0.1  # any non-null addr1 is neutral
    c14 = float(row.get("C14") or 0)
    if c14 > 10:
        score += 0.2  # high unique card count = velocity signal
    return min(score, 1.0)


def _is_nan(v: Any) -> bool:
    try:
        return math.isnan(float(v))
    except (ValueError, TypeError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Screening pass
# ─────────────────────────────────────────────────────────────────────────────

async def screen_transaction(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lightweight screen: investigate_node topology ONLY (no LLM calls).
    Scores the transaction using:
      - # shared accounts discovered (each +0.15)
      - # shared devices (+0.20 per device)
      - legit detectors (subtractive)
    Returns bank_score, agent_score, disagreement.
    """
    txn_id = f"TXN_{int(row.get('TransactionID', 0))}"
    acct_id = f"ACC_{int(row.get('card1', 0))}"
    b_score = bank_score_proxy(row)

    state = InvestigationState(
        trigger_txn_ids=[txn_id],
        trigger_account_id=acct_id,
        trigger_risk_score=min(float(row.get("TransactionAmt", 100.0)) / 5000.0, 1.0),
        trigger_type="MONITOR_SCAN",
        case_id=f"MON_{txn_id}",
        status=CaseStatus.INVESTIGATING,
    )

    try:
        state = await investigate_node(state)
    except Exception as e:
        return {
            "txn_id": txn_id,
            "account_id": acct_id,
            "bank_score": b_score,
            "agent_score": state.trigger_risk_score,
            "disagreement": 0.0,
            "action": "SKIP",
            "error": str(e),
        }

    # ── Topology-based score (no LLM) ─────────────────────────────────────
    # Start from the trigger_risk_score and adjust based on graph signals
    agent_score = state.trigger_risk_score

    # More discovered accounts = higher ring suspicion
    extra_accounts = max(0, len(state.accounts) - 1)
    agent_score += extra_accounts * 0.15

    # Each shared device is a strong signal
    agent_score += len(state.devices) * 0.20

    # Shared identifiers (same IP, same email domain, etc.)
    agent_score += min(len(state.shared_identifiers) * 0.10, 0.30)

    # Money flow chains
    flow_chains = state.money_flow.get("chains", [])
    agent_score += min(len(flow_chains) * 0.05, 0.20)

    # ── Legit detectors (subtractive) ─────────────────────────────────────
    txn_dict = {k: row.get(k) for k in row}  # pass through the raw CSV row
    legit_evs, _ = _run_legit_detectors(
        account_id=acct_id,
        txn=txn_dict,
        account_txn_history=[],   # no history in screening pass
        case_id=state.case_id,
    )
    for lev in legit_evs:
        agent_score -= lev.get("score", 0.0) * 0.5

    agent_score = max(0.0, min(1.0, agent_score))

    disagreement = agent_score - b_score
    action_type, approval_tier = decide(agent_score)

    return {
        "txn_id": txn_id,
        "account_id": acct_id,
        "transaction_dt": int(row.get("TransactionDT", 0)),
        "transaction_amt": float(row.get("TransactionAmt", 0)),
        "product_cd": row.get("ProductCD", ""),
        "device_type": row.get("DeviceType", ""),
        "bank_score": round(b_score, 4),
        "agent_score": round(agent_score, 4),
        "disagreement": round(disagreement, 4),
        "action": action_type,
        "approval_tier": approval_tier,
        "accounts_found": len(state.accounts),
        "devices_found": len(state.devices),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Full investigation (top-N only)
# ─────────────────────────────────────────────────────────────────────────────

async def run_full_investigation(screen_result: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    """
    Run the full agent pipeline (all nodes) for a single high-disagreement case.
    Saves outputs to out_dir/case_<txn_id>/.
    """
    from benchmark.run_benchmark import run_single_case  # import lazily

    case_input = {
        "case_number": 0,
        "case_id": f"MON_{screen_result['txn_id']}",
        "trigger_type": "MONITOR_SCAN",
        "trigger_txn_ids": [screen_result["txn_id"]],
        "trigger_account_id": screen_result["account_id"],
        "trigger_risk_score": screen_result["agent_score"],
        "notes": (
            f"Monitor-mode flagged: agent_score={screen_result['agent_score']:.3f} "
            f"vs bank_score={screen_result['bank_score']:.3f} "
            f"(disagreement={screen_result['disagreement']:+.3f})"
        ),
    }

    case_dir = out_dir / f"full_{screen_result['txn_id']}"
    case_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = await run_single_case(case_input, str(case_dir))
        return {"status": "OK", "case_dir": str(case_dir), **result}
    except Exception as e:
        return {"status": "ERROR", "error": str(e), "case_dir": str(case_dir)}


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def main_async(top_n: int = 10, full_run: bool = False, dry_run: bool = False) -> None:
    print("=" * 70)
    print("  HHGOA FRAUD AGENT -- MONITOR MODE (S21)")
    print(f"  Unlabeled window: TransactionDT >= {UNLABELED_DT_START}")
    print(f"  Top-N disagreements: {top_n}  |  Full run: {full_run}  |  Dry run: {dry_run}")
    print("=" * 70)

    df = load_unlabeled_transactions()
    records = df.to_dict(orient="records")

    # ── Screening pass (lightweight, no LLM verdict) ──────────────────────
    print(f"\n[MONITOR] Screening {len(records)} transactions ...")
    start = time.time()

    screen_results: List[Dict[str, Any]] = []
    batch_size = 20
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        tasks = [screen_transaction(row) for row in batch]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        screen_results.extend(results)
        elapsed = time.time() - start
        print(f"  [{i+len(batch)}/{len(records)}] screened — {elapsed:.1f}s elapsed", end="\r")

    print(f"\n[MONITOR] Screening complete: {len(screen_results)} results in {time.time()-start:.1f}s")

    # ── Rank by disagreement (agent RISKIER than bank) ────────────────────
    ranked = sorted(screen_results, key=lambda r: r.get("disagreement", 0.0), reverse=True)
    top = ranked[:top_n]

    print(f"\n[MONITOR] Top-{top_n} agent-vs-bank disagreements:")
    print(f"  {'TXN':>15}  {'bank':>6}  {'agent':>6}  {'delta':>7}  action")
    print(f"  {'-'*15}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*22}")
    for r in top:
        print(
            f"  {r['txn_id']:>15}  {r['bank_score']:>6.3f}  "
            f"{r['agent_score']:>6.3f}  {r['disagreement']:>+7.3f}  {r['action']}"
        )

    if dry_run:
        print("\n[MONITOR] Dry run — skipping full investigations and file writes.")
        return

    # ── Save screening summary ────────────────────────────────────────────
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unlabeled_dt_start": UNLABELED_DT_START,
        "transactions_screened": len(screen_results),
        "top_n": top_n,
        "top_disagreements": top,
        "all_results": screen_results,
    }
    summary_path = MONITOR_OUT / "disagreement_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[MONITOR] Screening summary saved -> {summary_path}")

    # ── Full investigation of top-N ───────────────────────────────────────
    if not full_run:
        print("[MONITOR] Skipping full investigations (pass --full-run to enable)")
        print("=" * 70)
        return

    full_out = MONITOR_OUT / "top_N"
    full_out.mkdir(parents=True, exist_ok=True)
    print(f"\n[MONITOR] Running full investigations for top-{top_n} cases ...")

    full_results = []
    for r in top:
        print(f"  -> Full investigation: {r['txn_id']} (disagreement={r['disagreement']:+.3f})")
        fr = await run_full_investigation(r, full_out)
        fr["txn_id"] = r["txn_id"]
        fr["bank_score"] = r["bank_score"]
        fr["agent_score"] = r["agent_score"]
        fr["disagreement"] = r["disagreement"]
        full_results.append(fr)
        status = "[OK]" if fr["status"] == "OK" else "[!!]"
        print(f"     {status} {fr['status']} -> {fr.get('case_dir','')}")

    full_summary_path = MONITOR_OUT / "full_investigation_summary.json"
    full_summary_path.write_text(json.dumps(full_results, indent=2), encoding="utf-8")
    print(f"\n[MONITOR] Full investigations saved -> {full_summary_path}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="S21: Monitor Mode — screen unlabeled transactions for bank-vs-agent disagreements"
    )
    parser.add_argument(
        "--top-n", type=int, default=10,
        help="Number of highest-disagreement cases to surface (default: 10)"
    )
    parser.add_argument(
        "--full-run", action="store_true",
        help="Run full agentic investigation for the top-N cases (rate-limit aware)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Perform screening only; skip file writes and full investigations"
    )
    args = parser.parse_args()

    asyncio.run(main_async(top_n=args.top_n, full_run=args.full_run, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
