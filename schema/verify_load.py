import os
import sys
from dotenv import load_dotenv

load_dotenv()

TG_HOST = os.getenv("TG_HOST", "http://127.0.0.1:14240")
TG_GRAPHNAME = os.getenv("TG_GRAPHNAME", "FraudGraph")
TG_USERNAME = os.getenv("TG_USERNAME", "tigergraph")
TG_PASSWORD = os.getenv("TG_PASSWORD", "tigergraph")
TG_SECRET = os.getenv("TG_SECRET", "")
TG_TOKEN = os.getenv("TG_TOKEN", "")

def get_tg_conn():
    try:
        import pyTigerGraph as tg
    except ImportError:
        print("[ERROR] pyTigerGraph is required. Run: pip install pyTigerGraph")
        sys.exit(1)

    conn = tg.TigerGraphConnection(
        host=TG_HOST,
        graphname=TG_GRAPHNAME,
        username=TG_USERNAME,
        password=TG_PASSWORD,
        secret=TG_SECRET if TG_SECRET else None,
        apiToken=TG_TOKEN if TG_TOKEN else None,
    )
    conn.ping()
    return conn

def verify_load():
    conn = get_tg_conn()
    print("=== HHGOA Fraud Agent: Verification of Data Load ===")

    # 1. Print vertex counts
    counts = conn.getVertexCount("*")
    print("\n--- Vertex Counts by Type ---")
    if isinstance(counts, dict):
        for vtype, cnt in counts.items():
            print(f"  {vtype}: {cnt}")
    else:
        print(f"  Total vertices: {counts}")

    # 2. Print sample 3 Account vertices
    print("\n--- Sample 3 Account Vertices ---")
    acc_samples = conn.getVertices("Account", limit=3)
    for acc in acc_samples:
        print(f"  Account ID: {acc.get('v_id')}, Attributes: {acc.get('attributes')}")

    # 3. Print sample 3 Transaction vertices
    print("\n--- Sample 3 Transaction Vertices ---")
    txn_samples = conn.getVertices("Transaction", limit=3)
    for txn in txn_samples:
        print(f"  Transaction ID: {txn.get('v_id')}, Attributes: {txn.get('attributes')}")

    # 4. Print sample 3 PatternTemplate vertices
    print("\n--- Sample 3 PatternTemplate Vertices ---")
    pat_samples = conn.getVertices("PatternTemplate", limit=3)
    for pat in pat_samples:
        print(f"  Pattern ID: {pat.get('v_id')}, Name: {pat.get('attributes', {}).get('name')}, Criteria: {pat.get('attributes', {}).get('match_criteria_json')}")

    # 5. Verifications
    pattern_count = conn.getVertexCount("PatternTemplate")
    policy_count = conn.getVertexCount("PolicyRule")
    txn_count = conn.getVertexCount("Transaction")

    print("\n--- Assertions ---")
    print(f"  PatternTemplate Count: {pattern_count} (Requirement: >= 5)")
    assert pattern_count >= 5, f"Expected at least 5 PatternTemplates, found {pattern_count}"

    print(f"  PolicyRule Count: {policy_count} (Requirement: >= 5)")
    assert policy_count >= 5, f"Expected at least 5 PolicyRules, found {policy_count}"

    print(f"  Transaction Count: {txn_count}")
    if txn_count < 500000:
        print(f"  [NOTE] Transaction count is {txn_count} (< 500,000 expected in full production dataset). If running on mini/sample data, this is acceptable.")
    else:
        print(f"  [PASS] Full 500k+ dataset detected.")

    print("\n[SUCCESS] Verification completed successfully!")

if __name__ == "__main__":
    verify_load()
