"""
Standalone Entry Point: Unsupervised Pattern Discovery.
Run once after data loading. Fully idempotent: checks for existing discovered patterns
before executing DBSCAN clustering.
"""

import sys
import asyncio
from pathlib import Path
from tools import tg_tools
from retrieval.embedder import Embedder
from innovation.pattern_discovery import run_pattern_discovery

CHECKPOINT_FILE = Path("./data/checkpoint_discovery.done")


def check_existing_discovered_patterns() -> bool:
    """Returns True if any PatternTemplate with is_documented=FALSE already exists."""
    if CHECKPOINT_FILE.is_file():
        return True

    conn = tg_tools._get_tg_conn()
    if conn:
        try:
            pats = conn.getVertices("PatternTemplate")
            for p in pats:
                attrs = p.get("attributes", {})
                if not attrs.get("is_documented", True):
                    return True
        except Exception as e:
            print(f"[NOTE] Could not check PatternTemplate vertices in TG: {e}", file=sys.stderr)

    return False


async def main() -> dict:
    """Main discovery runner."""
    print("=================================================================")
    print("        HHGOA FRAUD AGENT — PATTERN DISCOVERY ENGINE             ")
    print("=================================================================")

    if check_existing_discovered_patterns():
        print("[SKIP] Discovered patterns (is_documented=FALSE) already exist. Skipping discovery.")
        return {"status": "SKIPPED", "reason": "Already executed"}

    embedder = Embedder()
    summary = await run_pattern_discovery(embedder=embedder)

    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(f"discovered_patterns={summary.get('new_candidates', 0)}\n")

    print("\n--- Pattern Discovery Summary Report ---")
    print(f"Total Confirmed Fraud Cases Analyzed : {summary.get('cases_count', 0)}")
    print(f"Total Clusters Formed (DBSCAN)       : {summary.get('clusters_found', 0)}")
    print(f"Noise Outliers Discarded             : {summary.get('noise_points', 0)}")
    print(f"Clusters Covered by Documented Rules : {summary.get('covered_by_docs', 0)}")
    print(f"New Novel Typologies Discovered      : {summary.get('new_candidates', 0)}")

    for pat in summary.get("discovered_patterns", []):
        print(f"\n* [{pat['pattern_id']}] {pat['name']}")
        print(f"  Cases in Cluster: {pat['case_count']}")
        print(f"  Description: {pat['description'][:180]}...")
        top_disc = list(pat.get("discriminating_features", {}).keys())
        print(f"  Key Discriminating Features: {', '.join(top_disc)}")

    print("=================================================================")
    return summary


async def run_discovery_if_needed(embedder=None) -> dict:
    """Wrapper ensuring discovery has run."""
    return await main(embedder=embedder)


if __name__ == "__main__":
    asyncio.run(main())
