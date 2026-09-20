import os
import sys
import time
import itertools
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TG_HOST = os.getenv("TG_HOST", "http://127.0.0.1:14240")
TG_GRAPHNAME = os.getenv("TG_GRAPHNAME", "FraudGraph")
TG_USERNAME = os.getenv("TG_USERNAME", "tigergraph")
TG_PASSWORD = os.getenv("TG_PASSWORD", "tigergraph")
TG_SECRET = os.getenv("TG_SECRET", "")
TG_TOKEN = os.getenv("TG_TOKEN", "")

COMMON_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "protonmail.com",
}

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

def build_shares_device_edges(conn, use_gsql: bool = False):
    """
    Computes and materializes SHARES_DEVICE edges between accounts that share physical devices.
    Rules:
      - 2 <= distinct accounts <= 100 per device
      - Never create self-edges (a1 != a2)
      - Edge attributes: device_id=dev_id, shared_count=txn_count
    """
    print("\n--- 1. Building SHARES_DEVICE Edges ---")
    start_time = time.time()

    if use_gsql:
        print("Executing server-side GSQL query 'build_device_sharing_pairs'...")
        gsql_file = Path(__file__).resolve().parent / "derived_edges.gsql"
        if gsql_file.is_file():
            conn.gsql(gsql_file.read_text(encoding="utf-8"))
        res = conn.runInstalledQuery("build_device_sharing_pairs")
        print("GSQL Execution result:", res)
        elapsed = time.time() - start_time
        print(f"SHARES_DEVICE (GSQL) finished in {elapsed:.2f}s")
        return

    # pyTigerGraph batch approach
    print("Extracting Account -> Transaction -> Device mappings...")
    gsql_query = """
    INTERPRET QUERY () FOR GRAPH FraudGraph {
        MapAccum<STRING, SetAccum<STRING>> @@dev_accounts;
        MapAccum<STRING, SumAccum<INT>> @@dev_txns;

        Start = {Device.*};
        T = 
            SELECT dev
            FROM Account:a -(PERFORMED)-> Transaction:t -(USED_DEVICE)-> Device:dev
            ACCUM 
                @@dev_accounts += (dev.device_id -> a.account_id),
                @@dev_txns += (dev.device_id -> 1);

        PRINT @@dev_accounts, @@dev_txns;
    }
    """

    dev_accounts = defaultdict(set)
    dev_txns = defaultdict(int)

    try:
        res = conn.gsql(gsql_query)
        # Parse result if interpret query returned json
        import json
        parsed = json.loads(res) if isinstance(res, str) and res.strip().startswith("{") else {}
        results = parsed.get("results", [{}])[0]
        for dev_id, accs in results.get("@@dev_accounts", {}).items():
            dev_accounts[dev_id] = set(accs)
        for dev_id, cnt in results.get("@@dev_txns", {}).items():
            dev_txns[dev_id] = int(cnt)
    except Exception as e:
        print(f"[NOTE] Falling back to vertex & edge traversal via REST API: {e}")
        # Traversal fallback using getEdges
        used_edges = conn.getEdgesByType("USED_DEVICE")
        dev_to_txns = defaultdict(list)
        for edge in used_edges:
            txn_id = edge.get("from_id")
            dev_id = edge.get("to_id")
            if txn_id and dev_id:
                dev_to_txns[dev_id].append(txn_id)

        for dev_id, txns in dev_to_txns.items():
            dev_txns[dev_id] = len(txns)
            for t_id in txns:
                perf_edges = conn.getEdges("Transaction", t_id, edgeType="REVERSE_PERFORMED")
                for pe in perf_edges:
                    acc_id = pe.get("to_id")
                    if acc_id:
                        dev_accounts[dev_id].add(acc_id)

    print(f"Discovered {len(dev_accounts)} unique devices with active accounts.")

    # Generate edge pairs
    edge_batch = []
    total_edges = 0
    batch_limit = 5000

    for dev_id, accounts in dev_accounts.items():
        acc_count = len(accounts)
        if acc_count < 2 or acc_count > 100:
            continue

        txn_count = dev_txns.get(dev_id, acc_count)
        sorted_accs = sorted(list(accounts))

        for a1, a2 in itertools.combinations(sorted_accs, 2):
            if a1 == a2:
                continue
            edge_batch.append((a1, a2, {
                "device_id": str(dev_id),
                "shared_count": int(txn_count)
            }))

            if len(edge_batch) >= batch_limit:
                conn.upsertEdges("Account", "SHARES_DEVICE", edge_batch)
                total_edges += len(edge_batch)
                edge_batch.clear()
                time.sleep(0.02)

    if edge_batch:
        conn.upsertEdges("Account", "SHARES_DEVICE", edge_batch)
        total_edges += len(edge_batch)

    elapsed = time.time() - start_time
    print(f"[DONE] build_shares_device_edges: {total_edges} edges materialized in {elapsed:.2f}s.")

def build_shares_email_domain_edges(conn):
    """
    Computes and materializes SHARES_EMAIL_DOMAIN edges between accounts sharing uncommon email domains.
    Rules:
      - Domain NOT in COMMON_DOMAINS
      - 2 <= distinct accounts <= 100 per domain
      - Never create self-edges (a1 != a2)
    """
    print("\n--- 2. Building SHARES_EMAIL_DOMAIN Edges ---")
    start_time = time.time()

    print("Fetching Account vertices and email domains...")
    # Fetch accounts
    accounts_data = conn.getVertices("Account", limit=500000)
    domain_to_accounts = defaultdict(set)

    for acc in accounts_data:
        acc_id = acc.get("v_id")
        domain = acc.get("attributes", {}).get("p_emaildomain")
        if not domain or not isinstance(domain, str):
            continue
        domain_clean = domain.strip().lower()
        if not domain_clean or domain_clean in COMMON_DOMAINS:
            continue

        domain_to_accounts[domain_clean].add(acc_id)

    print(f"Discovered {len(domain_to_accounts)} uncommon email domains.")

    edge_batch = []
    total_edges = 0
    batch_limit = 5000

    for domain, accounts in domain_to_accounts.items():
        count = len(accounts)
        if count < 2 or count > 100:
            continue

        sorted_accs = sorted(list(accounts))
        for a1, a2 in itertools.combinations(sorted_accs, 2):
            if a1 == a2:
                continue
            edge_batch.append((a1, a2, {
                "domain": str(domain),
                "shared_count": int(count)
            }))

            if len(edge_batch) >= batch_limit:
                conn.upsertEdges("Account", "SHARES_EMAIL_DOMAIN", edge_batch)
                total_edges += len(edge_batch)
                edge_batch.clear()
                time.sleep(0.02)

    if edge_batch:
        conn.upsertEdges("Account", "SHARES_EMAIL_DOMAIN", edge_batch)
        total_edges += len(edge_batch)

    elapsed = time.time() - start_time
    print(f"[DONE] build_shares_email_domain_edges: {total_edges} edges materialized in {elapsed:.2f}s.")

def build_shares_address_edges(conn):
    """
    Computes and materializes SHARES_ADDRESS edges between accounts sharing physical address pairs.
    Rules:
      - Both addr1 and addr2 present and non-null
      - addr_key = f"{int(addr1)}_{int(addr2)}"
      - 2 <= distinct accounts <= 50 per address key
      - Never create self-edges (a1 != a2)
    """
    print("\n--- 3. Building SHARES_ADDRESS Edges ---")
    start_time = time.time()

    print("Fetching Account vertices and address coordinates...")
    accounts_data = conn.getVertices("Account", limit=500000)
    addr_to_accounts = defaultdict(set)

    for acc in accounts_data:
        acc_id = acc.get("v_id")
        attrs = acc.get("attributes", {})
        addr1 = attrs.get("addr1")
        addr2 = attrs.get("addr2")

        if addr1 is None or addr2 is None:
            continue
        try:
            a1_int = int(float(addr1))
            a2_int = int(float(addr2))
            addr_key = f"{a1_int}_{a2_int}"
            addr_to_accounts[addr_key].add(acc_id)
        except (ValueError, TypeError):
            continue

    print(f"Discovered {len(addr_to_accounts)} unique address clusters.")

    edge_batch = []
    total_edges = 0
    batch_limit = 5000

    for addr_key, accounts in addr_to_accounts.items():
        count = len(accounts)
        if count < 2 or count > 50:
            continue

        sorted_accs = sorted(list(accounts))
        for a1, a2 in itertools.combinations(sorted_accs, 2):
            if a1 == a2:
                continue
            edge_batch.append((a1, a2, {
                "addr_key": str(addr_key),
                "shared_count": int(count)
            }))

            if len(edge_batch) >= batch_limit:
                conn.upsertEdges("Account", "SHARES_ADDRESS", edge_batch)
                total_edges += len(edge_batch)
                edge_batch.clear()
                time.sleep(0.02)

    if edge_batch:
        conn.upsertEdges("Account", "SHARES_ADDRESS", edge_batch)
        total_edges += len(edge_batch)

    elapsed = time.time() - start_time
    print(f"[DONE] build_shares_address_edges: {total_edges} edges materialized in {elapsed:.2f}s.")

def main():
    print("=== HHGOA Fraud Agent: Materializing Derived Graph Edges ===")
    conn = get_tg_conn()

    build_shares_device_edges(conn, use_gsql=False)
    build_shares_email_domain_edges(conn)
    build_shares_address_edges(conn)

    print("\n=== Derived Graph Edges Completed ===")

if __name__ == "__main__":
    main()
