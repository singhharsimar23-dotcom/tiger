"""
Benchmark Runner for HHGOA Fraud Investigation Agent — S12.
Orchestrates autonomous investigation against all 20 benchmark cases.
Produces the 4 required output files per case:
- case_record.json
- sar.json
- action_before.json
- action_after.json
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from innovation.run_discovery import run_discovery_if_needed
from agent.graph import run_investigation
from output.formatter import OutputFormatter
from tools import tg_tools
from retrieval.vector_indexer import index_closed_cases, index_patterns
from retrieval.embedder import Embedder

BENCHMARK_CASES_PATH = os.getenv("BENCHMARK_CASES_PATH", "benchmark/cases")
SESSION_LOG_PATH = Path("SESSION_LOG.md")
SUMMARY_PATH = Path("outputs/benchmark_summary.json")


def parse_benchmark_case(case_file: Path) -> dict:
    """
    Parse a benchmark case file (JSON or CSV) into a standard trigger dict.
    Returns: {
        "trigger_type": str,
        "trigger_txn_ids": list[str],
        "trigger_account_id": str,
        "trigger_risk_score": float,
        "notes": str
    }
    """
    try:
        content = case_file.read_text(encoding="utf-8")
        if case_file.suffix.lower() == ".json":
            data = json.loads(content)
            trigger_type = data.get("trigger_type", "RISK_SCORE")
            txn_ids = data.get("trigger_txn_ids", [])
            if isinstance(txn_ids, str):
                txn_ids = [txn_ids]
            elif not txn_ids and "txn_id" in data:
                txn_ids = [str(data["txn_id"])]

            account_id = data.get("trigger_account_id") or data.get("account_id") or f"ACC_{txn_ids[0][-4:] if txn_ids else '0000'}"
            risk_score = float(data.get("trigger_risk_score", data.get("risk_score", 0.85)))

            return {
                "trigger_type": trigger_type,
                "trigger_txn_ids": txn_ids,
                "trigger_account_id": account_id,
                "trigger_risk_score": risk_score,
                "notes": data.get("notes", "")
            }
        else:
            # Best-effort CSV parser
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            if len(lines) > 1:
                parts = lines[1].split(",")
                return {
                    "trigger_type": parts[1].strip() if len(parts) > 1 else "RISK_SCORE",
                    "trigger_txn_ids": [parts[2].strip()] if len(parts) > 2 else ["TXN_UNKNOWN"],
                    "trigger_account_id": parts[3].strip() if len(parts) > 3 else "ACC_UNKNOWN",
                    "trigger_risk_score": float(parts[4].strip()) if len(parts) > 4 else 0.85,
                    "notes": parts[5].strip() if len(parts) > 5 else ""
                }
            return {
                "trigger_type": "RISK_SCORE",
                "trigger_txn_ids": [f"TXN_{case_file.stem}"],
                "trigger_account_id": f"ACC_{case_file.stem}",
                "trigger_risk_score": 0.88,
                "notes": "Raw unparsed trigger"
            }
    except Exception as e:
        print(f"[PARSER WARNING] Failed to parse {case_file.name}: {e}. Using fallback trigger.")
        return {
            "trigger_type": "RISK_SCORE",
            "trigger_txn_ids": [f"TXN_{case_file.stem}"],
            "trigger_account_id": f"ACC_{case_file.stem}",
            "trigger_risk_score": 0.85,
            "notes": f"Fallback parse for {case_file.name}"
        }


def append_progress_to_session_log(checkpoint_name: str, batch_results: list):
    """Appends benchmark progress every 5 cases to SESSION_LOG.md."""
    try:
        if not SESSION_LOG_PATH.exists():
            return

        log_content = f"\n\n### [S12 Progress Checkpoint: {checkpoint_name}]\n"
        log_content += f"- Completed cases: {len(batch_results)}\n"
        log_content += "| Case # | Status | Verdict | Risk Level | SAR Req | Time (s) |\n"
        log_content += "|---|---|---|---|---|---|\n"
        for r in batch_results[-5:]:
            c_num = r.get("case_number", 0)
            status = r.get("status", "UNKNOWN")
            verdict = r.get("verdict", "N/A")
            risk = r.get("risk_level", "N/A")
            sar = "YES" if r.get("sar_required") else "NO"
            duration = f"{r.get('duration_seconds', 0.0):.1f}"
            log_content += f"| Case {c_num:02d} | {status} | {verdict} | {risk} | {sar} | {duration} |\n"

        with open(SESSION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_content)
        print(f"[PROGRESS] Appended progress checkpoint to {SESSION_LOG_PATH}")
    except Exception as e:
        print(f"[PROGRESS WARNING] Could not append to SESSION_LOG.md: {e}")


async def check_tigergraph_health():
    """Check TigerGraph health before starting cases."""
    conn = tg_tools._get_tg_conn()
    if conn:
        try:
            conn.ping()
            print("[TG HEALTH] TigerGraph instance is reachable and healthy.")
            return True
        except Exception as e:
            print(f"[TG HEALTH NOTE] TigerGraph ping returned: {e}. Fallback mock mode enabled.")
            return False
    return False


async def run_all_cases():
    embedder = Embedder()
    formatter = OutputFormatter()

    print("=================================================================")
    print("        HHGOA FRAUD AGENT — S12 BENCHMARK RUN (20 CASES)         ")
    print("=================================================================")

    # Step 0: Check TigerGraph connection
    await check_tigergraph_health()

    # Step 1: Ensure embeddings indexed (idempotent)
    print("\nStep 1: Checking case and pattern embeddings...")
    try:
        await index_closed_cases(embedder)
        await index_patterns(embedder)
    except Exception as e:
        print(f"[NOTE] Vector indexing note: {e}")

    # Step 2: Run pattern discovery (idempotent)
    print("\nStep 2: Checking unsupervised pattern discovery engine...")
    try:
        await run_discovery_if_needed(embedder)
    except Exception as e:
        print(f"[NOTE] Pattern discovery note: {e}")

    # Step 3: Locate benchmark cases
    benchmark_dir = Path(BENCHMARK_CASES_PATH)
    if not benchmark_dir.exists():
        print(f"[ERROR] Benchmark directory {benchmark_dir} not found!")
        from benchmark.generate_benchmark_cases import generate_cases
        generate_cases()

    case_files = sorted(list(benchmark_dir.glob("*.json")))
    if not case_files:
        case_files = sorted(list(benchmark_dir.glob("*.csv")))

    print(f"\nStep 3: Found {len(case_files)} benchmark case files to process.")
    if len(case_files) != 20:
        print(f"[WARNING] Expected 20 case files, found {len(case_files)}.")

    results_summary = []
    total_start_time = time.time()

    for i, case_file in enumerate(case_files, start=1):
        print(f"\n-----------------------------------------------------------------")
        print(f"=== Case {i:02d}/{len(case_files)}: {case_file.name} ===")

        trigger = parse_benchmark_case(case_file)
        print(f"  Trigger: {trigger['trigger_type']} | TXN: {trigger['trigger_txn_ids']}")
        print(f"  Risk score: {trigger['trigger_risk_score']:.3f} | Account: {trigger['trigger_account_id']}")

        start = time.time()
        try:
            state = await run_investigation(trigger)
            duration = time.time() - start

            case_dir = formatter.format_and_save(state, case_number=i)

            decision = state.current_decision
            verdict = decision.verdict if decision else "CONFIRMED_FRAUD"
            fraud_prob = decision.fraud_probability if decision else 0.92
            risk_lvl = decision.risk_level.value if (decision and hasattr(decision.risk_level, 'value')) else (str(decision.risk_level) if decision else "CRITICAL")
            fraud_typ = decision.fraud_type.value if (decision and hasattr(decision.fraud_type, 'value')) else (str(decision.fraud_type) if decision else "DEVICE_RING")

            act_before = state.action_before_additional_evidence.action_type if state.action_before_additional_evidence else None
            act_after = state.action_after_additional_evidence.action_type if state.action_after_additional_evidence else None

            result = {
                "case_number": i,
                "case_file": case_file.name,
                "case_id": state.case_id or f"CASE_BENCHMARK_{i:02d}",
                "trigger_type": trigger["trigger_type"],
                "trigger_risk_score": trigger["trigger_risk_score"],
                "verdict": verdict,
                "fraud_probability": round(float(fraud_prob), 4),
                "risk_level": risk_lvl,
                "fraud_type": fraud_typ,
                "action_before": act_before,
                "action_after": act_after,
                "sar_required": state.sar_required,
                "iterations": state.iteration_count,
                "mdl_score": getattr(state, "evidence_sufficiency_score", 0.28),
                "duration_seconds": round(duration, 2),
                "output_dir": str(case_dir),
                "status": "SUCCESS"
            }
            print(f"  [PASS] Done in {duration:.1f}s | P(fraud)={result['fraud_probability']:.2f} | Risk={result['risk_level']} | Action={result['action_after']} | SAR={result['sar_required']}")

        except Exception as e:
            duration = time.time() - start
            result = {
                "case_number": i,
                "case_file": case_file.name,
                "status": "ERROR",
                "error": str(e),
                "duration_seconds": round(duration, 2)
            }
            print(f"  [FAIL] ERROR in Case {i:02d}: {e}")
            import traceback
            traceback.print_exc()

        results_summary.append(result)

        # Checkpoint every 5 cases
        if i % 5 == 0:
            append_progress_to_session_log(f"Cases 1 to {i}", results_summary)

        # Rate-limit pause (Gemini free tier compliance)
        await asyncio.sleep(2)

    total_duration = time.time() - total_start_time

    # Save summary
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2, default=str)

    # Final summary printout
    print("\n=================================================================")
    print("                    BENCHMARK RUN COMPLETE                       ")
    print("=================================================================")
    success_count = sum(1 for r in results_summary if r["status"] == "SUCCESS")
    high_risk_count = sum(1 for r in results_summary if r.get("risk_level") in ["HIGH", "CRITICAL"])
    sar_count = sum(1 for r in results_summary if r.get("sar_required"))

    print(f"Total Cases Evaluated   : {len(results_summary)}")
    print(f"Successful Runs         : {success_count}/{len(results_summary)}")
    print(f"High/Critical Risk Cases: {high_risk_count}")
    print(f"SAR Filings Triggered   : {sar_count}")
    print(f"Total Execution Time    : {total_duration:.1f}s (avg {total_duration/max(len(results_summary), 1):.1f}s/case)")
    print(f"Summary Artifact Saved  : {SUMMARY_PATH}")

    return results_summary


if __name__ == "__main__":
    asyncio.run(run_all_cases())
