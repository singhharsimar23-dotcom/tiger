"""
Output Completeness & Compliance Validator for HHGOA Fraud Agent.
Validates all 20 benchmark case output folders and artifacts:
- case_record.json
- sar.json
- action_before.json
- action_after.json
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REQUIRED_FILES = [
    "case_record.json",
    "sar.json",
    "action_before.json",
    "action_after.json"
]

REQUIRED_FIELDS = {
    "case_record.json": [
        "case_id", "case_number", "status", "trigger_type",
        "decision", "uncertainty_score", "mdl_sufficiency_score"
    ],
    "sar.json": [
        "case_id", "sar_required", "filing_tier",
        "suspect_information", "primary_fraud_type", "risk_score"
    ],
    "action_before.json": [
        "case_id", "stage", "action_type", "approval_tier", "reason"
    ],
    "action_after.json": [
        "case_id", "stage", "action_type", "approval_tier", "reason"
    ]
}


def validate_case_directory(case_dir: Path, case_num: int) -> dict:
    result = {
        "case_num": case_num,
        "case_dir": str(case_dir),
        "exists": case_dir.is_dir(),
        "files_valid": {},
        "missing_files": [],
        "invalid_json": [],
        "missing_fields": {},
        "passed": False
    }

    if not case_dir.is_dir():
        return result

    for fname in REQUIRED_FILES:
        fpath = case_dir / fname
        if not fpath.is_file():
            result["missing_files"].append(fname)
            continue

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            missing = [k for k in REQUIRED_FIELDS[fname] if k not in data]
            if missing:
                result["missing_fields"][fname] = missing
            else:
                result["files_valid"][fname] = True

        except Exception as e:
            result["invalid_json"].append((fname, str(e)))

    has_all_files = len(result["missing_files"]) == 0
    has_no_json_errors = len(result["invalid_json"]) == 0
    has_no_missing_fields = len(result["missing_fields"]) == 0

    result["passed"] = has_all_files and has_no_json_errors and has_no_missing_fields
    return result


def validate_all_outputs(base_dir: str = "outputs/cases", expected_cases: int = 20) -> bool:
    base_path = Path(base_dir)
    print("=================================================================")
    print("        HHGOA FRAUD AGENT — BENCHMARK OUTPUT VALIDATOR           ")
    print(f"Directory: {base_path.resolve()}")
    print("=================================================================")

    if not base_path.exists():
        print(f"[FAIL] Output directory {base_path} does not exist!")
        return False

    all_passed = True
    passed_count = 0
    validation_table = []

    for i in range(1, expected_cases + 1):
        case_dir = base_path / f"case_{i:02d}"
        res = validate_case_directory(case_dir, i)

        status_str = "[PASS]" if res["passed"] else "[FAIL]"
        if res["passed"]:
            passed_count += 1
        else:
            all_passed = False

        details = []
        if res["missing_files"]:
            details.append(f"Missing: {', '.join(res['missing_files'])}")
        if res["invalid_json"]:
            details.append(f"Bad JSON: {res['invalid_json']}")
        if res["missing_fields"]:
            details.append(f"Missing fields: {res['missing_fields']}")

        detail_str = "; ".join(details) if details else "All 4 files complete and valid"
        validation_table.append((f"Case {i:02d}", status_str, detail_str))

    # Print table
    print(f"\n{'CASE':<10} | {'STATUS':<8} | {'DETAILS'}")
    print("-" * 65)
    for c_id, stat, det in validation_table:
        print(f"{c_id:<10} | {stat:<8} | {det}")

    print("-" * 65)
    score_pct = (passed_count / expected_cases) * 100
    print(f"Validation Score: {passed_count}/{expected_cases} ({score_pct:.1f}%)")

    if all_passed:
        print("[SUCCESS] All 20 benchmark case outputs are complete, compliant, and valid JSON!")
    else:
        print(f"[FAIL] {expected_cases - passed_count} cases failed output validation.")

    return all_passed


if __name__ == "__main__":
    success = validate_all_outputs()
    sys.exit(0 if success else 1)
