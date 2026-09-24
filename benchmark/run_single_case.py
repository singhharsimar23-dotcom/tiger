"""
benchmark/run_single_case.py — Live Single-Case Execution Pipeline (S17 Fix 4).
Runs the full LangGraph investigation pipeline for an individual case with verbose logging.
"""

import os
import sys
import csv
import json
import time
import argparse
import asyncio
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import agent.llm as agent_llm
from agent.graph import run_investigation
from output.formatter import OutputFormatter
from tools import tg_tools

CASE_PACK_PATHS = [
    Path("data/case_pack.csv"),
    Path("D:/case_pack.csv"),
]


def normalize_case_id(raw_id: str) -> str:
    """Normalize input like '5', '005', 'HHG-5', 'case_05' to 'HHG-005'."""
    clean = str(raw_id).strip().upper()
    if clean.startswith("HHG-"):
        try:
            num = int(clean.split("-")[1])
            return f"HHG-{num:03d}"
        except ValueError:
            return clean
    if clean.lower().startswith("case_"):
        try:
            num = int(clean[5:])
            return f"HHG-{num:03d}"
        except ValueError:
            pass
    try:
        num = int(clean)
        return f"HHG-{num:03d}"
    except ValueError:
        return clean


def load_case_row(case_id: str) -> dict:
    """Find the specific case row in case_pack.csv."""
    norm_id = normalize_case_id(case_id)
    for p in CASE_PACK_PATHS:
        if p.exists():
            with open(p, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cid = row.get("case_id", "").strip()
                    if normalize_case_id(cid) == norm_id:
                        return row
    raise ValueError(f"Case {case_id} ({norm_id}) not found in case_pack.csv")


async def run_single_case(case_id: str, verbose: bool = False):
    norm_id = normalize_case_id(case_id)
    row = load_case_row(norm_id)

    if verbose:
        print(f"=================================================================")
        print(f"  LIVE RE-RUN: {norm_id} (Trigger: {row.get('trigger_type')})")
        print(f"=================================================================")

        # Register MCP tool call verbose logger
        def _verbose_tool_log(tool_name: str, args: dict, result: any):
            print(f"[MCP TOOL] tigergraph__{tool_name} args={args}")
            preview = str(result)[:140].replace("\n", " ")
            print(f"           -> {preview}...")

        tg_tools.set_tool_call_callback(_verbose_tool_log)

        # Wrap LLM call to print verbose notifications
        _orig_call_llm_json = agent_llm.call_llm_json

        async def _verbose_llm_call(*args, **kwargs):
            role = kwargs.get("role", "fast")
            print(f"[LLM CALL] Starting live LLM invocation (role={role})...")
            start = time.time()
            res = await _orig_call_llm_json(*args, **kwargs)
            duration = time.time() - start
            keys = list(res.keys()) if isinstance(res, dict) else []
            print(f"[LLM CALL] Completed in {duration:.2f}s | Result keys: {keys}")
            return res

        agent_llm.call_llm_json = _verbose_llm_call

    flagged_txn = row.get("flagged_txn_id", "")
    card_id = row.get("card_id", "")
    cust_id = row.get("customer_id", "")
    r_score = float(row.get("risk_score") or 0.0)
    ttype = row.get("trigger_type", "risk_score")
    ttext = row.get("trigger_text", "")

    trigger = {
        "case_id": norm_id,
        "trigger_type": ttype,
        "flagged_txn_id": flagged_txn,
        "card_id": card_id,
        "customer_id": cust_id,
        "risk_score": r_score,
        "trigger_text": ttext,
    }

    start_time = time.time()
    state = await run_investigation(trigger)
    elapsed = time.time() - start_time

    # Persist official JSON dossier
    formatter = OutputFormatter(output_dir="cases")
    out_path = formatter.format_and_save(state)

    if verbose:
        print(f"\n=================================================================")
        print(f"  INVESTIGATION COMPLETE: {norm_id}")
        print(f"  Verdict:           {state.verdict}")
        print(f"  Fraud Probability: {state.fraud_probability:.4f}")
        print(f"  Pattern:           {state.pattern}")
        print(f"  Exposure USD:      ${state.exposure_usd:.2f}")
        print(f"  Initial Actions:   {[a.action for a in state.initial_actions]}")
        print(f"  Final Actions:     {[a.action for a in state.final_actions]}")
        print(f"  SAR Filed:         {state.sar_file}")
        print(f"  Connected Cards:   {state.connected_card_ids}")
        print(f"  Elapsed Time:      {elapsed:.2f}s")
        print(f"  File Written:      {out_path}")
        print(f"=================================================================")

    return state, out_path


def main():
    parser = argparse.ArgumentParser(description="Live investigation runner for a single benchmark case.")
    parser.add_argument("case_id", type=str, help="Case ID to run (e.g. HHG-005, 5, case_05)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose MCP tool and LLM calls")
    args = parser.parse_args()

    asyncio.run(run_single_case(args.case_id, verbose=args.verbose))


if __name__ == "__main__":
    main()
