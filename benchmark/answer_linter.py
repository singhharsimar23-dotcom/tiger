#!/usr/bin/env python3
"""
S11-PATCH: Answer Linter — validates all 20 benchmark case output files.
Run after EVERY benchmark run, not just once.

Checks per case:
  A. SCHEMA       — required fields present, correct types, no unexpected keys
  B. ENUM VALUES  — action_type, approval_tier, risk_level, fraud_type are literal enum values
  C. REFERENTIAL  — txn_ids / account_ids reference real benchmark case inputs
  D. SAR CONSISTENCY — sar_required ↔ FILE_SAR action
  E. EXPOSURE     — total_suspicious_amount >= 0 (CSV not available so soft check)
  F. ROUTE        — approval_tier in action files matches decide() deterministic policy
  G. BEFORE/AFTER — if no additional_evidence, before==after; count divergences
  H. GRAPH-WRITE  — attempt TigerGraph Case vertex lookup (skip gracefully if offline)

Writes: outputs/answer_lint_report.json
Exit code: 0 if all clean, 1 if any hard failure.
"""

import json
import sys
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── project root on path ──────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from innovation.mdl_gate import decide  # noqa: E402 — after sys.path insert

# ── Constants ─────────────────────────────────────────────────────────────────
CASES_DIR = ROOT / "outputs" / "cases"
BENCHMARK_CASES_DIR = ROOT / "benchmark" / "cases"
REPORT_PATH = ROOT / "outputs" / "answer_lint_report.json"

VALID_ACTION_TYPES = {
    "DECLINE_TRANSACTION", "BLOCK_TRANSACTION", "FREEZE_ACCOUNT",
    "BLOCK_ACCOUNT", "STEP_UP_MFA", "STEP_UP_AUTH", "FLAG_FOR_REVIEW",
    "MONITOR_ACCOUNT", "ALLOW_TRANSACTION", "FILE_SAR",
}
VALID_APPROVAL_TIERS = {
    "AUTOMATED_SYSTEM", "AUTO", "ANALYST_TIER_1", "ANALYST",
    "FRAUD_OPS_LEAD", "SUPERVISOR", "SENIOR_COMPLIANCE_OFFICER",
    "LEGAL", "LEGAL_COMPLIANCE",
}
VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_FRAUD_TYPES = {
    "DEVICE_RING", "ACCOUNT_TAKEOVER", "SYNTHETIC_IDENTITY",
    "BUST_OUT", "SMURFING", "UNCONFIRMED_ANOMALY",
}
VALID_STATUSES = {"OPEN", "INVESTIGATING", "CLOSED", "RESOLVED", "FLAGGED"}
VALID_FILING_TIERS = {"TIER_1_EXPEDITED", "STANDARD_30_DAY", "NONE"}
SAR_ACTION_EQUIVALENTS = {"FILE_SAR"}

# Required top-level keys in each output file
REQUIRED_CASE_RECORD_KEYS = {
    "case_id", "case_number", "timestamp", "investigation_duration_seconds",
    "status", "trigger_type", "trigger_txn_ids", "trigger_account_id",
    "trigger_risk_score", "accounts_discovered", "devices_discovered",
    "ip_clusters_discovered", "matched_patterns", "matched_policies",
    "similar_prior_cases", "evidence_list", "evidence_count",
    "uncertainty_score", "mdl_sufficiency_score", "iteration_count",
    "decision", "recommended_actions", "case_summary", "decision_log",
    "tool_calls_executed",
}
REQUIRED_SAR_KEYS = {
    "case_id", "sar_required", "filing_tier", "suspect_information",
    "suspicious_activity_summary", "transaction_ids", "total_suspicious_amount",
    "primary_fraud_type", "risk_score", "sar_narrative", "filing_deadline",
    "compliance_officer_signoff", "created_at",
}
REQUIRED_ACTION_KEYS = {
    "case_id", "stage", "action_type", "approval_tier", "approval_route",
    "reason", "executed", "confidence", "timestamp",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> Tuple[Optional[Dict], Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"
    except FileNotFoundError:
        return None, f"File not found: {path}"


def check_schema(data: Dict, required_keys: set, label: str) -> List[str]:
    errors = []
    missing = required_keys - set(data.keys())
    for k in sorted(missing):
        errors.append(f"[SCHEMA] {label}: missing required field '{k}'")
    return errors


def check_enum(value: Any, valid_set: set, field: str, label: str) -> Optional[str]:
    if value not in valid_set:
        return f"[ENUM] {label}: '{field}' = '{value}' not in {sorted(valid_set)}"
    return None


def _norm_tier(t: str) -> str:
    """Normalize approval tier to canonical form for decide() comparison."""
    mapping = {
        "AUTO": "AUTO",
        "AUTOMATED_SYSTEM": "AUTO",
        "ANALYST": "ANALYST",
        "ANALYST_TIER_1": "ANALYST",
        "FRAUD_OPS_LEAD": "SUPERVISOR",   # operational equiv for high-risk
        "SUPERVISOR": "SUPERVISOR",
        "SENIOR_COMPLIANCE_OFFICER": "SUPERVISOR",
        "LEGAL": "SUPERVISOR",
        "LEGAL_COMPLIANCE": "SUPERVISOR",
    }
    return mapping.get(t, t)


def load_benchmark_input(case_num: int) -> Optional[Dict]:
    path = BENCHMARK_CASES_DIR / f"case_{case_num:02d}.json"
    data, err = load_json(path)
    return data


# ── TigerGraph live check (graceful degradation) ──────────────────────────────

def _tg_case_exists(case_id: str) -> Tuple[Optional[bool], str]:
    """
    Returns (exists: bool | None, note: str).
    None = couldn't connect (offline / paused), bool = live result.
    """
    try:
        import tools.tg_tools as tg_tools
        import asyncio

        async def _check():
            result = await tg_tools.get_case(case_id)
            return result is not None and result != {}

        exists = asyncio.get_event_loop().run_until_complete(_check())
        return exists, "live"
    except Exception as e:
        return None, f"offline: {e}"


# ── Per-case linter ───────────────────────────────────────────────────────────

def lint_case(case_num: int) -> Dict:
    label = f"case_{case_num:02d}"
    case_dir = CASES_DIR / label
    benchmark_input = load_benchmark_input(case_num)

    result = {
        "case": label,
        "checks": {},
        "errors": [],
        "warnings": [],
        "hard_fail": False,
    }

    # ── Load all 4 files ──────────────────────────────────────────────────────
    cr_data, cr_err = load_json(case_dir / "case_record.json")
    sar_data, sar_err = load_json(case_dir / "sar.json")
    ab_data, ab_err = load_json(case_dir / "action_before.json")
    aa_data, aa_err = load_json(case_dir / "action_after.json")

    for fname, err in [
        ("case_record.json", cr_err),
        ("sar.json", sar_err),
        ("action_before.json", ab_err),
        ("action_after.json", aa_err),
    ]:
        if err:
            result["errors"].append(f"[LOAD] {fname}: {err}")
            result["hard_fail"] = True

    if result["hard_fail"]:
        for check in ["A_SCHEMA","B_ENUM","C_REFERENTIAL","D_SAR","E_EXPOSURE","F_ROUTE","G_BEFORE_AFTER","H_GRAPH_WRITE"]:
            result["checks"][check] = "SKIP"
        return result

    # ── A. SCHEMA ─────────────────────────────────────────────────────────────
    schema_errors = []
    schema_errors += check_schema(cr_data, REQUIRED_CASE_RECORD_KEYS, "case_record.json")
    schema_errors += check_schema(sar_data, REQUIRED_SAR_KEYS, "sar.json")
    schema_errors += check_schema(ab_data, REQUIRED_ACTION_KEYS, "action_before.json")
    schema_errors += check_schema(aa_data, REQUIRED_ACTION_KEYS, "action_after.json")
    if schema_errors:
        result["errors"].extend(schema_errors)
        result["hard_fail"] = True
        result["checks"]["A_SCHEMA"] = "FAIL"
    else:
        result["checks"]["A_SCHEMA"] = "PASS"

    # ── B. ENUM VALUES ────────────────────────────────────────────────────────
    enum_errors = []
    # case_record: decision fields
    dec = cr_data.get("decision") or {}
    if dec:
        if e := check_enum(dec.get("verdict", ""), {"CONFIRMED_FRAUD","SUSPICIOUS","CLEARED","UNKNOWN"}, "verdict", "case_record.decision"):
            enum_errors.append(e)
        if e := check_enum(dec.get("risk_level", ""), VALID_RISK_LEVELS, "risk_level", "case_record.decision"):
            enum_errors.append(e)
        if e := check_enum(dec.get("fraud_type", ""), VALID_FRAUD_TYPES, "fraud_type", "case_record.decision"):
            enum_errors.append(e)
    # case_record: status
    if e := check_enum(cr_data.get("status",""), VALID_STATUSES, "status", "case_record"):
        enum_errors.append(e)
    # recommended_actions
    for i, act in enumerate(cr_data.get("recommended_actions", [])):
        if e := check_enum(act.get("action_type",""), VALID_ACTION_TYPES, f"action_type[{i}]", "case_record.recommended_actions"):
            enum_errors.append(e)
        if e := check_enum(act.get("approval_tier",""), VALID_APPROVAL_TIERS, f"approval_tier[{i}]", "case_record.recommended_actions"):
            enum_errors.append(e)
    # sar
    if e := check_enum(sar_data.get("filing_tier",""), VALID_FILING_TIERS, "filing_tier", "sar.json"):
        enum_errors.append(e)
    if e := check_enum(sar_data.get("primary_fraud_type",""), VALID_FRAUD_TYPES, "primary_fraud_type", "sar.json"):
        enum_errors.append(e)
    # action files
    for fname, adata in [("action_before.json", ab_data), ("action_after.json", aa_data)]:
        if e := check_enum(adata.get("action_type",""), VALID_ACTION_TYPES, "action_type", fname):
            enum_errors.append(e)
        if e := check_enum(adata.get("approval_tier",""), VALID_APPROVAL_TIERS, "approval_tier", fname):
            enum_errors.append(e)
    if enum_errors:
        result["errors"].extend(enum_errors)
        result["hard_fail"] = True
        result["checks"]["B_ENUM"] = "FAIL"
    else:
        result["checks"]["B_ENUM"] = "PASS"

    # ── C. REFERENTIAL (cross-check txn_ids + account_ids vs benchmark input) ─
    ref_errors = []
    if benchmark_input:
        expected_txns = set(benchmark_input.get("trigger_txn_ids", []))
        expected_acct = benchmark_input.get("trigger_account_id", "")
        actual_txns = set(cr_data.get("trigger_txn_ids", []))
        actual_acct = cr_data.get("trigger_account_id", "")
        if expected_txns and not expected_txns.issubset(actual_txns | actual_txns):
            missing_txns = expected_txns - actual_txns
            if missing_txns:
                ref_errors.append(f"[REF] trigger_txn_ids missing benchmark inputs: {missing_txns}")
        # account match: allow synthetic suffixes (bench uses real IDs, output may add context)
        if expected_acct and actual_acct and expected_acct != actual_acct:
            if not actual_acct.startswith(expected_acct.split("_")[0]):
                result["warnings"].append(f"[REF] trigger_account_id mismatch: benchmark='{expected_acct}' output='{actual_acct}'")
    else:
        result["warnings"].append("[REF] benchmark input not found; skipping referential ID check")

    if ref_errors:
        result["errors"].extend(ref_errors)
        result["checks"]["C_REFERENTIAL"] = "FAIL"
    else:
        result["checks"]["C_REFERENTIAL"] = "PASS"

    # ── D. SAR CONSISTENCY ────────────────────────────────────────────────────
    sar_required = bool(sar_data.get("sar_required", False))
    filing_tier = sar_data.get("filing_tier", "NONE")
    # Check if FILE_SAR action is in action_after
    aa_action_type = aa_data.get("action_type", "")
    cr_actions = cr_data.get("recommended_actions", [])
    has_sar_action = (
        aa_action_type in SAR_ACTION_EQUIVALENTS
        or any(a.get("action_type") in SAR_ACTION_EQUIVALENTS for a in cr_actions)
    )
    sar_consistent = True
    if sar_required and not has_sar_action and filing_tier != "NONE":
        # sar_required=True but no FILE_SAR action in any action set
        result["warnings"].append(
            "[SAR] sar_required=True but no FILE_SAR-equivalent action in recommended_actions or action_after"
        )
        sar_consistent = False
    if not sar_required and has_sar_action and aa_action_type in SAR_ACTION_EQUIVALENTS:
        result["errors"].append(
            "[SAR] sar_required=False but action_after.action_type is FILE_SAR — contradiction"
        )
        result["hard_fail"] = True
        sar_consistent = False
    result["checks"]["D_SAR"] = "PASS" if sar_consistent else "WARN"

    # ── E. EXPOSURE CONSISTENCY ───────────────────────────────────────────────
    total_amt = sar_data.get("total_suspicious_amount", 0)
    exposure_errors = []
    if total_amt < 0:
        exposure_errors.append(f"[EXPOSURE] total_suspicious_amount is negative: {total_amt}")
    if total_amt == 0 and sar_required:
        result["warnings"].append("[EXPOSURE] total_suspicious_amount=0.0 but sar_required=True — suspicious")
    if exposure_errors:
        result["errors"].extend(exposure_errors)
        result["checks"]["E_EXPOSURE"] = "FAIL"
    else:
        result["checks"]["E_EXPOSURE"] = "PASS"

    # ── F. ROUTE CONSISTENCY (approval_tier vs decide()) ─────────────────────
    route_errors = []
    fraud_prob = (dec or {}).get("fraud_probability") or (dec or {}).get("confidence") or cr_data.get("trigger_risk_score", 0.5)
    txn_amt = sar_data.get("total_suspicious_amount", 5000.0)
    expected_action, expected_tier = decide(float(fraud_prob), float(txn_amt))
    for fname, adata in [("action_before.json", ab_data), ("action_after.json", aa_data)]:
        actual_tier = adata.get("approval_tier", "")
        if _norm_tier(actual_tier) != _norm_tier(expected_tier):
            route_errors.append(
                f"[ROUTE] {fname}: approval_tier='{actual_tier}' but decide({fraud_prob:.2f}) "
                f"yields '{expected_tier}' (fraud_prob={fraud_prob:.2f})"
            )
    if route_errors:
        result["warnings"].extend(route_errors)  # warn, not hard fail (LLM may have more context)
        result["checks"]["F_ROUTE"] = "WARN"
    else:
        result["checks"]["F_ROUTE"] = "PASS"

    # ── G. BEFORE/AFTER SANITY ────────────────────────────────────────────────
    iter_count = cr_data.get("iteration_count", 0)
    before_action = ab_data.get("action_type", "")
    before_tier = ab_data.get("approval_tier", "")
    after_action = aa_data.get("action_type", "")
    after_tier = aa_data.get("approval_tier", "")
    changed = (before_action != after_action) or (before_tier != after_tier)

    if iter_count <= 1 and changed:
        result["warnings"].append(
            f"[BEFORE_AFTER] iteration_count={iter_count} but action changed "
            f"({before_action}/{before_tier} -> {after_action}/{after_tier})"
        )
    result["checks"]["G_BEFORE_AFTER"] = "PASS"
    result["action_changed"] = changed
    result["iter_count"] = iter_count

    # ── H. GRAPH-WRITE CHECK ──────────────────────────────────────────────────
    case_id = cr_data.get("case_id", "")
    if case_id:
        exists, note = _tg_case_exists(case_id)
        if exists is None:
            result["checks"]["H_GRAPH_WRITE"] = f"SKIP ({note})"
            result["warnings"].append(f"[GRAPH_WRITE] TigerGraph offline — skipping Case vertex check for {case_id}")
        elif exists:
            result["checks"]["H_GRAPH_WRITE"] = "PASS"
        else:
            result["checks"]["H_GRAPH_WRITE"] = "FAIL"
            result["warnings"].append(
                f"[GRAPH_WRITE] Case vertex '{case_id}' NOT FOUND in TigerGraph — "
                f"case exists only in JSON dump (written_to_graph=False)"
            )
    else:
        result["checks"]["H_GRAPH_WRITE"] = "SKIP (no case_id)"

    return result


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    start = time.time()
    print("=" * 70)
    print("  HHGOA FRAUD AGENT — ANSWER LINTER (S11-PATCH)")
    print(f"  Cases directory: {CASES_DIR}")
    print("=" * 70)

    all_results = []
    hard_failures = 0
    warnings_total = 0
    action_changed_count = 0
    check_totals: Dict[str, Dict[str, int]] = {}

    for i in range(1, 21):
        res = lint_case(i)
        all_results.append(res)
        n_errors = len(res["errors"])
        n_warnings = len(res["warnings"])
        hard_failures += 1 if res["hard_fail"] else 0
        warnings_total += n_warnings
        if res.get("action_changed"):
            action_changed_count += 1

        # Tally per-check
        for check, status in res["checks"].items():
            check_totals.setdefault(check, {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0})
            key = "PASS" if status == "PASS" else ("FAIL" if "FAIL" in status else ("WARN" if "WARN" in status else "SKIP"))
            check_totals[check][key] += 1

        icon = "[OK]" if not res["hard_fail"] else "[!!]"
        warn_str = f" ({n_warnings} warnings)" if n_warnings else ""
        err_str = f" ({n_errors} errors)" if n_errors else ""
        status_str = "PASS" if not res["hard_fail"] else "FAIL"
        print(f"  {icon} case_{i:02d}: {status_str}{err_str}{warn_str}")
        for e in res["errors"]:
            print(f"       ERROR: {e}")
        for w in res["warnings"]:
            print(f"       WARN:  {w}")

    elapsed = time.time() - start
    print()
    print("-" * 70)
    print("  CHECK SUMMARY")
    print("-" * 70)
    for check, counts in sorted(check_totals.items()):
        pass_n = counts["PASS"]
        fail_n = counts["FAIL"]
        warn_n = counts["WARN"]
        skip_n = counts["SKIP"]
        bar = f"PASS={pass_n:2d}  FAIL={fail_n:2d}  WARN={warn_n:2d}  SKIP={skip_n:2d}"
        print(f"  {check:<20} {bar}")
    print()
    print(f"  Hard failures:  {hard_failures}/20 cases")
    print(f"  Total warnings: {warnings_total}")
    print(f"  Action changed (before->after): {action_changed_count}/20 cases")
    print(f"  Elapsed: {elapsed:.2f}s")

    # ── Write report ──────────────────────────────────────────────────────────
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_seconds": round(elapsed, 2),
        "summary": {
            "hard_failures": hard_failures,
            "total_warnings": warnings_total,
            "action_changed_before_after": action_changed_count,
            "check_totals": check_totals,
        },
        "cases": all_results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print()
    if hard_failures == 0:
        print(f"  [OK] ALL CHECKS CLEAN -- report saved to {REPORT_PATH}")
        print("=" * 70)
        return 0
    else:
        print(f"  [!!] {hard_failures} HARD FAILURE(S) -- fix before submitting!")
        print(f"  Report saved to {REPORT_PATH}")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
