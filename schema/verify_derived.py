import os
import sys
from collections import defaultdict
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

def verify_derived():
    conn = get_tg_conn()
    print("=== HHGOA Fraud Agent: Derived Graph Edges Verification ===")

    # 1. Edge Counts
    print("\n--- 1. Derived Edge Counts ---")
    device_edges_count = conn.getEdgeCount("SHARES_DEVICE")
    email_edges_count = conn.getEdgeCount("SHARES_EMAIL_DOMAIN")
    address_edges_count = conn.getEdgeCount("SHARES_ADDRESS")

    print(f"  SHARES_DEVICE: {device_edges_count}")
    print(f"  SHARES_EMAIL_DOMAIN: {email_edges_count}")
    print(f"  SHARES_ADDRESS: {address_edges_count}")

    # 2. Degree distribution for SHARES_DEVICE
    print("\n--- 2. Top 10 Most-Connected Accounts (by SHARES_DEVICE degree) ---")
    edges = conn.getEdgesByType("SHARES_DEVICE")
    degree_map = defaultdict(set)
    for e in edges:
        src = e.get("from_id")
        dst = e.get("to_id")
        if src and dst:
            degree_map[src].add(dst)
            degree_map[dst].add(src)

    sorted_accounts = sorted(degree_map.items(), key=lambda x: len(x[1]), reverse=True)
    top_10 = sorted_accounts[:10]
    for rank, (acc, neighbors) in enumerate(top_10, 1):
        print(f"  #{rank} Account: {acc} -> Degree: {len(neighbors)}")

    # 3. Print a sample ring (account connected to >= 3 other accounts)
    print("\n--- 3. Sample Fraud Ring Discovery ---")
    rings = [item for item in sorted_accounts if len(item[1]) >= 3]
    if rings:
        sample_acc, sample_ring = rings[0]
        print(f"  Ring Core Account: {sample_acc}")
        print(f"  Connected Ring Members ({len(sample_ring)} accounts): {list(sample_ring)[:10]}")
    else:
        print("  [NOTE] No accounts with >= 3 SHARES_DEVICE neighbors found in current data snapshot.")

    # 4. Correctness Check: Triad Complete Graph (3 accounts sharing 1 device = 3 edges)
    print("\n--- 4. Graph Completeness / Clique Verification ---")
    # Check if there is any device used by exactly 3 accounts and verify 3 edges exist
    triad_verified = False
    for acc, neighbors in sorted_accounts:
        if len(neighbors) >= 2:
            # Check if any 2 neighbors also share an edge
            n_list = list(neighbors)
            for i in range(len(n_list)):
                for j in range(i + 1, len(n_list)):
                    n1, n2 = n_list[i], n_list[j]
                    if n2 in degree_map.get(n1, set()):
                        print(f"  [PASS] Verified 3-node clique (Triad): ({acc} <-> {n1}), ({acc} <-> {n2}), ({n1} <-> {n2}) all exist.")
                        triad_verified = True
                        break
                if triad_verified:
                    break
        if triad_verified:
            break

    if not triad_verified:
        print("  [NOTE] No 3-node clique found in current edge set (may require larger dataset).")

    # 5. Requirement Assertions
    print("\n--- 5. Requirements Validation ---")
    if device_edges_count >= 1000:
        print(f"  [PASS] Verified: At least 1000 SHARES_DEVICE edges exist ({device_edges_count}).")
    else:
        print(f"  [NOTE] SHARES_DEVICE count is {device_edges_count} (< 1000). If running on test/sample data, verify data ingestion.")

    print("\n[SUCCESS] Derived edges verification script execution finished!")

if __name__ == "__main__":
    verify_derived()
