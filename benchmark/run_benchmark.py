"""
Benchmark Runner for HHGOA Fraud Investigation Agent — Ground Truth S12.
Orchestrates autonomous investigations against the 20 benchmark cases from case_pack.csv.
Produces exactly one validated JSON file per case: cases/{case_id}.json.
Runs the pre-submission validator at the end to guarantee 100% compliance.
"""

import os
import sys
import csv
import json
import time
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from agent.graph import run_investigation
from output.formatter import OutputFormatter
from output.validator import validate_all
from tools import tg_tools

CASE_PACK_PATHS = [
    Path("D:/case_pack.csv"),
    Path("data/case_pack.csv"),
]
CASES_DIR = Path("cases")
SUMMARY_PATH = Path("outputs/benchmark_summary.json")
SESSION_LOG_PATH = Path("SESSION_LOG.md")


def load_case_pack_records() -> list[dict]:
    """Load all benchmark cases directly from case_pack.csv."""
    for p in CASE_PACK_PATHS:
        if p.exists():
            records = []
            with open(p, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)
            print(f"[BENCHMARK] Loaded {len(records)} cases from {p}")
            return records
    raise FileNotFoundError("case_pack.csv not found on D:/ or data/")


async def check_tigergraph_health() -> bool:
    """Check TigerGraph health before starting cases."""
    conn = tg_tools._get_tg_conn()
    if conn:
        try:
            conn.ping()
            print("[TG HEALTH] Connected to TigerGraph Cloud successfully.")
            return True
        except Exception as e:
            print(f"[TG HEALTH NOTE] TigerGraph ping returned: {e}. Standalone simulation active.")
            return False
    print("[TG HEALTH NOTE] TigerGraph offline/paused. Standalone high-fidelity simulation active.")
    return False


async def run_benchmark(limit: int = 20):
    formatter = OutputFormatter(output_dir="cases")
    CASES_DIR.mkdir(parents=True, exist_ok=True)

    print("=================================================================")
    print("      HHGOA FRAUD AGENT — BENCHMARK RUN (case_pack.csv)         ")
    print("=================================================================")

    # Step 0: Check TigerGraph
    await check_tigergraph_health()

    # Step 1: Load cases
    records = load_case_pack_records()
    if limit > 0:
        records = records[:limit]

    results_summary = []
    total_start_time = time.time()

    for idx, row in enumerate(records, start=1):
        cid = row.get("case_id", f"HHG-{idx:03d}")
        ttype = row.get("trigger_type", "risk_score")
        flagged_txn = row.get("flagged_txn_id", "")
        card_id = row.get("card_id", "")
        cust_id = row.get("customer_id", "")
        r_score = float(row.get("risk_score") or 0.0)
        t_text = row.get("trigger_text", "")

        print(f"\n[{idx:02d}/{len(records)}] Investigating {cid} ({ttype}) | Txn: {flagged_txn} | Card: {card_id} | Score: {r_score}")

        trigger = {
            "case_id": cid,
            "trigger_type": ttype,
            "flagged_txn_id": flagged_txn,
            "card_id": card_id,
            "customer_id": cust_id,
            "risk_score": r_score,
            "trigger_text": t_text,
        }

        start = time.time()
        try:
            state = await run_investigation(trigger)
            out_path = formatter.format_and_save(state)
            duration = round(time.time() - start, 2)

            final_actions = [a.action for a in state.final_actions]
            first_action = final_actions[0] if final_actions else "CLOSE_NO_FRAUD"
            first_route = state.final_actions[0].route if state.final_actions else "auto"

            res_entry = {
                "case_number": idx,
                "case_id": cid,
                "trigger_type": ttype,
                "verdict": state.verdict,
                "fraud_probability": state.fraud_probability,
                "pattern": state.pattern,
                "exposure_usd": state.exposure_usd,
                "final_action": first_action,
                "final_route": first_route,
                "sar_file": state.sar_file,
                "duration_seconds": duration,
                "output_file": str(out_path),
                "status": "SUCCESS",
            }
            print(f"  --> [PASS] Verdict={state.verdict.upper()} | P={state.fraud_probability:.2f} | Action={first_action} [{first_route}] | SAR={state.sar_file} | Time={duration}s")
            results_summary.append(res_entry)

        except Exception as e:
            duration = round(time.time() - start, 2)
            print(f"  --> [FAIL] Error in {cid}: {e}")
            import traceback
            traceback.print_exc()
            results_summary.append({
                "case_number": idx,
                "case_id": cid,
                "status": "ERROR",
                "error": str(e),
                "duration_seconds": duration,
            })

        # Brief rate limit sleep for LLM API stability
        await asyncio.sleep(0.5)

    total_duration = round(time.time() - total_start_time, 2)

    # Step 3: Run Output Validator on all output JSONs
    print("\n=================================================================")
    print("             PRE-SUBMISSION VALIDATION (14 RULES)                ")
    print("=================================================================")
    val_ok = validate_all(CASES_DIR)

    # Save summary
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "total_cases": len(results_summary),
            "successful_runs": sum(1 for r in results_summary if r.get("status") == "SUCCESS"),
            "validator_passed": val_ok,
            "total_duration_s": total_duration,
            "results": results_summary,
        }, f, indent=2)

    print("\n=================================================================")
    print("                    BENCHMARK RUN SUMMARY                        ")
    print("=================================================================")
    success_count = sum(1 for r in results_summary if r.get("status") == "SUCCESS")
    print(f"Total Cases Evaluated   : {len(results_summary)}")
    print(f"Successful Runs         : {success_count}/{len(results_summary)}")
    print(f"Validator Status        : {'PASS (100% compliant)' if val_ok else 'FAIL'}")
    print(f"Total Run Time          : {total_duration}s")
    print(f"Output Artifacts        : {CASES_DIR}/*.json")
    print(f"Summary JSON            : {SUMMARY_PATH}")

    return val_ok


if __name__ == "__main__":
    asyncio.run(run_benchmark())
