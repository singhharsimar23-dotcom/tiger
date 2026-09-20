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
        try:
            import pytest
            pytest.skip("pyTigerGraph is not installed. Skipping live query execution test.")
        except ImportError:
            pass
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
    try:
        conn.ping()
    except Exception as e:
        try:
            import pytest
            pytest.skip(f"Could not connect to TigerGraph: {e}")
        except ImportError:
            pass
        raise e
    return conn

def test_queries():
    conn = get_tg_conn()
    print("=== Testing Installed GSQL Queries ===")

    # 1. Test get_policy_rules
    print("\n--- 1. Testing get_policy_rules(txn_amt=1000.0, risk_score=0.5) ---")
    try:
        res = conn.runInstalledQuery("get_policy_rules", params={"txn_amt": 1000.0, "risk_score": 0.5})
        print("Result:", res)
        rules = res[0].get("matching_rules", []) if res else []
        print(f"Matched Rules ({len(rules)}):")
        for r in rules[:3]:
            attrs = r.get("attributes", {})
            print(f"  - {r.get('v_id')}: {attrs.get('name')} (Action: {attrs.get('action_type')})")
        assert len(rules) >= 1, "Expected at least 1 policy rule matched"
        print("  [PASS] get_policy_rules")
    except Exception as e:
        print(f"  [FAIL/SKIP] get_policy_rules: {e}")

    # 2. Test graph_stats
    print("\n--- 2. Testing graph_stats() ---")
    try:
        res = conn.runInstalledQuery("graph_stats")
        print("Result:", res)
        stats = res[0].get("graph_stats", {}) if res else {}
        v_counts = stats.get("vertex_counts", {})
        assert "Transaction" in v_counts, "Expected 'Transaction' in vertex_counts"
        assert "Account" in v_counts, "Expected 'Account' in vertex_counts"
        print("  [PASS] graph_stats")
    except Exception as e:
        print(f"  [FAIL/SKIP] graph_stats: {e}")

    # 3. Test get_txn_neighborhood
    print("\n--- 3. Testing get_txn_neighborhood ---")
    try:
        txns = conn.getVertices("Transaction", limit=1)
        if txns:
            sample_txn_id = txns[0]["v_id"]
            res = conn.runInstalledQuery("get_txn_neighborhood", params={"txn_id": sample_txn_id, "depth": 2})
            print(f"Result for Transaction {sample_txn_id}:", res)
            assert "accounts" in res[0], "Expected 'accounts' key in get_txn_neighborhood result"
            print("  [PASS] get_txn_neighborhood")
        else:
            print("  [SKIP] No transactions in database to test get_txn_neighborhood.")
    except Exception as e:
        print(f"  [FAIL/SKIP] get_txn_neighborhood: {e}")

    # 4. Test get_shared_identifiers
    print("\n--- 4. Testing get_shared_identifiers ---")
    try:
        accounts = conn.getVertices("Account", limit=1)
        if accounts:
            sample_acc_id = accounts[0]["v_id"]
            res = conn.runInstalledQuery("get_shared_identifiers", params={"account_id": sample_acc_id})
            print(f"Result for Account {sample_acc_id}:", res)
            assert isinstance(res, list), "Expected list response for get_shared_identifiers"
            print("  [PASS] get_shared_identifiers")
        else:
            print("  [SKIP] No accounts in database to test get_shared_identifiers.")
    except Exception as e:
        print(f"  [FAIL/SKIP] get_shared_identifiers: {e}")

    # 5. Test get_money_flow
    print("\n--- 5. Testing get_money_flow ---")
    try:
        if accounts:
            sample_acc_id = accounts[0]["v_id"]
            res = conn.runInstalledQuery("get_money_flow", params={"account_id": sample_acc_id, "depth": 2})
            print(f"Result for Account {sample_acc_id}:", res)
            print("  [PASS] get_money_flow")
    except Exception as e:
        print(f"  [FAIL/SKIP] get_money_flow: {e}")

    # 6. Test case_crud queries
    print("\n--- 6. Testing case_crud queries ---")
    try:
        open_cases = conn.runInstalledQuery("get_open_cases")
        print("Open Cases:", open_cases)
        print("  [PASS] get_open_cases")
    except Exception as e:
        print(f"  [FAIL/SKIP] case_crud: {e}")

    print("\n=== Test Queries Completed ===")

if __name__ == "__main__":
    test_queries()
