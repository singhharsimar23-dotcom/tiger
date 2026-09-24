#!/usr/bin/env python3
"""
S23 Part 7 — Deployment Preparation Script
Bundles the 20 fixed case JSON files into dashboard/static/data/
and generates a static case index so the frontend works without any
live backend call (TigerGraph can be asleep during judging).

Run from the project root:
    python scripts/bundle_cases_for_deploy.py

Then deploy with:
    cd dashboard && vercel --prod
"""

import json
import glob
import shutil
import hashlib
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "cases"
STATIC_DATA_DIR = ROOT / "dashboard" / "static" / "data"


def bundle_cases():
    STATIC_DATA_DIR.mkdir(parents=True, exist_ok=True)

    case_files = sorted(CASES_DIR.glob("HHG-*.json"))
    if not case_files:
        print(f"[ERROR] No case files found in {CASES_DIR}. Run the benchmark first.")
        return False

    index_entries = []
    bundled = 0

    for src in case_files:
        dst = STATIC_DATA_DIR / src.name
        shutil.copy2(src, dst)
        bundled += 1

        # Build index entry from the case file
        try:
            with open(src, encoding="utf-8") as f:
                data = json.load(f)
            case_block = data.get("case", data)
            index_entries.append({
                "case_id": case_block.get("case_id", src.stem),
                "verdict": case_block.get("verdict", "unknown"),
                "pattern": case_block.get("pattern", "none"),
                "fraud_probability": case_block.get("fraud_probability", 0.0),
                "exposure_usd": case_block.get("exposure_usd", 0.0),
                "sar_file": case_block.get("sar_file", False),
                "status": case_block.get("status", "unknown"),
                "trigger_type": case_block.get("trigger_type", ""),
                "card_id": case_block.get("card_id", ""),
                "customer_id": case_block.get("customer_id", ""),
                "summary": (case_block.get("summary", "") or "")[:200],
            })
        except Exception as e:
            print(f"  [WARN] Could not parse {src.name}: {e}")

        print(f"  Bundled {src.name} -> {dst}")

    # Write static index
    index_path = STATIC_DATA_DIR / "cases_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at_utc": datetime.datetime.utcnow().isoformat(),
            "session": "S23",
            "case_count": len(index_entries),
            "cases": index_entries,
        }, f, indent=2)
    print(f"\n  Index written: {index_path} ({len(index_entries)} cases)")

    # Compute manifest with SHA256 of all bundled files
    manifest = {
        "generated_at_utc": datetime.datetime.utcnow().isoformat(),
        "session": "S23",
        "files": {}
    }
    for f_path in sorted((STATIC_DATA_DIR).glob("*.json")):
        sha = hashlib.sha256(f_path.read_bytes()).hexdigest()
        manifest["files"][f_path.name] = sha

    manifest_path = ROOT / "manifest_s23.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n  Manifest written: {manifest_path}")
    print(f"\n[DONE] {bundled} cases bundled into {STATIC_DATA_DIR}")
    print("\nManifest (paste this as S23 proof):")
    print(json.dumps(manifest, indent=2))
    return True


if __name__ == "__main__":
    success = bundle_cases()
    if not success:
        raise SystemExit(1)
