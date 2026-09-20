"""
output/validator.py — Pre-submission Hard Validator (Section 4)

Run this before submitting benchmark results. Every assertion here reflects
a graded check from the brief. Failing cases score zero on affected fields.

Usage:
    python output/validator.py                  # validates all cases/
    python output/validator.py HHG-001.json     # validates single file
"""

import json
import sys
import csv
from pathlib import Path
from typing import Optional


CASES_DIR      = Path("cases")
CASE_PACK_FILE = Path("D:/case_pack.csv")   # confirmed location

# Attempt fallback to local copy
if not CASE_PACK_FILE.exists():
    CASE_PACK_FILE = Path("data/case_pack.csv")

VALID_ACTIONS = {
    "ALLOW_TRANSACTION", "DECLINE_TRANSACTION", "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS", "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH", "BLOCK_CARD", "BLOCK_ALL_CARDS", "GENERATE_REPORT",
    "CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST", "CLOSE_NO_FRAUD",
}

VALID_ROUTES   = {"auto", "L1", "L2"}
VALID_VERDICTS = {"fraud", "legitimate", "uncertain"}
VALID_PATTERNS = {
    "card_testing", "card_not_present_fraud", "card_not_present_new_device",
    "out_of_region_use", "account_takeover", "undocumented", "none",
}
VALID_STATUSES = {"open", "closed_fraud", "closed_legitimate", "escalated"}
VALID_SOURCES  = {"graph", "document", "customer", "external"}
VALID_EV_TYPES = {"customer_validation", "step_up_auth", "analyst_info"}


def load_case_pack() -> dict:
    """Returns {case_id: row_dict} for all rows in case_pack.csv."""
    if not CASE_PACK_FILE.exists():
        print(f"[WARNING] case_pack.csv not found at {CASE_PACK_FILE}. case_id check skipped.")
        return {}
    with open(CASE_PACK_FILE, encoding="utf-8") as f:
        return {row["case_id"]: row for row in csv.DictReader(f)}


def validate_case(path: Path, known_case_ids: set, errors: list) -> int:
    """Validates a single case JSON file. Returns number of errors found."""
    n_errors = 0

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        errors.append(f"[{path.name}] Cannot parse JSON: {e}")
        return 1

    case_id = data.get("case_id", "")

    def err(msg: str):
        nonlocal n_errors
        n_errors += 1
        errors.append(f"[{case_id or path.stem}] {msg}")

    # ---- 1. case_id matches filename ----
    expected_stem = path.stem   # e.g. "HHG-001"
    if case_id != expected_stem:
        err(f"case_id '{case_id}' does not match filename '{expected_stem}.json'")

    # ---- 2. case_id exists in case_pack ----
    if known_case_ids and case_id not in known_case_ids:
        err(f"case_id '{case_id}' not found in case_pack.csv")

    case = data.get("case", {})
    sar  = data.get("sar", {})
    nba  = data.get("next_best_actions", {})
    final_actions = [a.get("action", "") for a in nba.get("final", [])]

    # ---- 3. status ----
    status = case.get("status", "")
    if status not in VALID_STATUSES:
        err(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}")

    # ---- 4. verdict ----
    verdict = case.get("verdict", "")
    if verdict not in VALID_VERDICTS:
        err(f"Invalid verdict '{verdict}'. Must be one of {VALID_VERDICTS}")

    # ---- 5. pattern ----
    pattern = case.get("pattern", "")
    if pattern not in VALID_PATTERNS:
        err(f"Invalid pattern '{pattern}'. Must be one of {VALID_PATTERNS}")

    # ---- 6. undocumented requires description ----
    if pattern == "undocumented" and not case.get("pattern_description", "").strip():
        err("pattern='undocumented' but pattern_description is empty")

    # ---- 7. legitimate verdict constraints ----
    if verdict == "legitimate":
        if case.get("affected_txn_ids"):
            err("verdict=legitimate but affected_txn_ids is non-empty")
        if float(case.get("exposure_usd", 0)) != 0.0:
            err(f"verdict=legitimate but exposure_usd={case.get('exposure_usd')}")
        if sar.get("file"):
            err("verdict=legitimate but sar.file=True")

    # ---- 8. SAR ↔ FILE_REPORT agreement ----
    sar_file = sar.get("file", False)
    if sar_file and "FILE_REPORT" not in final_actions:
        err("sar.file=True but FILE_REPORT not in next_best_actions.final")
    if not sar_file and "FILE_REPORT" in final_actions:
        err("FILE_REPORT in final actions but sar.file=False")

    # ---- 9. SAR narrative required when file=True ----
    if sar_file and not sar.get("narrative", "").strip():
        err("sar.file=True but sar.narrative is empty")

    # ---- 10. fraud_probability range ----
    fp = float(case.get("fraud_probability", -1))
    if not (0.0 <= fp <= 1.0):
        err(f"fraud_probability={fp} out of range [0, 1]")

    # ---- 11. Valid action strings ----
    for action_block in ["initial", "final"]:
        for ar in nba.get(action_block, []):
            act = ar.get("action", "")
            if act not in VALID_ACTIONS:
                err(f"Invalid action '{act}' in next_best_actions.{action_block}")
            route = ar.get("route", "")
            if route not in VALID_ROUTES:
                err(f"Invalid route '{route}' for action '{act}'")
            reason = ar.get("reason", "")
            if not any(reason.startswith(f"R{i}:") or f"R{i}" in reason for i in range(1, 11)):
                err(f"action '{act}' reason does not cite a rule number (R1-R10): '{reason[:80]}'")

    # ---- 12. Evidence sources ----
    for ev in case.get("evidence", []):
        src = ev.get("source", "")
        if src not in VALID_SOURCES:
            err(f"Invalid evidence source '{src}'. Must be one of {VALID_SOURCES}")

    # ---- 13. Evidence request types ----
    for er in data.get("evidence_requests", []):
        et = er.get("type", "")
        if et not in VALID_EV_TYPES:
            err(f"Invalid evidence_request type '{et}'. Must be one of {VALID_EV_TYPES}")

    # ---- 14. Required fields present ----
    for field in ["stop_reason", "tool_calls", "tokens", "latency_s"]:
        if field not in data:
            err(f"Missing required top-level field '{field}'")

    return n_errors


def validate_all(cases_dir: Optional[Path] = None, targets: Optional[list] = None) -> bool:
    target_dir = cases_dir or CASES_DIR
    known_case_ids = set(load_case_pack().keys())
    if not known_case_ids:
        print("[WARNING] No case_pack.csv loaded — case_id existence checks skipped.")

    if targets:
        files = [Path(t) if Path(t).is_absolute() else target_dir / t for t in targets]
    else:
        files = sorted(target_dir.glob("*.json"))

    if not files:
        print(f"[ERROR] No JSON files found in {target_dir}/")
        return False

    all_errors = []
    total_cases = 0
    total_errors = 0

    for f in files:
        if not f.exists():
            print(f"[MISSING] {f}")
            continue
        n = validate_case(f, known_case_ids, all_errors)
        total_errors += n
        total_cases += 1

    print(f"\n{'='*60}")
    print(f"Validated {total_cases} case(s). Total errors: {total_errors}")
    print(f"{'='*60}")
    if all_errors:
        for e in all_errors:
            print(f"  [FAIL] {e}")
        print()
        return False
    else:
        print("  [PASS] All cases pass validation.")
        return True


def main(targets: Optional[list] = None):
    success = validate_all(targets=targets)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main(sys.argv[1:] if len(sys.argv) > 1 else None)

