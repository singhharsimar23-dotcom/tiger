import os
import sys
import re
from pathlib import Path
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

def extract_query_names(gsql_text: str):
    # Matches: CREATE [OR REPLACE] QUERY <query_name>
    pattern = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?QUERY\s+([a-zA-Z0-9_]+)", re.IGNORECASE)
    return pattern.findall(gsql_text)

def install_all_queries():
    conn = get_tg_conn()
    queries_dir = Path(__file__).resolve().parent

    gsql_files = sorted(list(queries_dir.glob("*.gsql")))
    if not gsql_files:
        print(f"[WARNING] No .gsql files found in {queries_dir}")
        return

    print(f"=== Installing GSQL Queries from {queries_dir} ===")
    all_query_names = []

    for gsql_file in gsql_files:
        content = gsql_file.read_text(encoding="utf-8")
        query_names = extract_query_names(content)
        all_query_names.extend(query_names)

        print(f"\nCreating query definition(s) from {gsql_file.name} -> {query_names}...")
        try:
            res = conn.gsql(content)
            print(f"[CREATE RESULT] {res.strip()}")
        except Exception as e:
            print(f"[ERROR] Failed to create query from {gsql_file.name}: {e}")

    # Install queries
    unique_queries = sorted(list(set(all_query_names)))
    print(f"\n--- Installing {len(unique_queries)} Queries ---")
    for q_name in unique_queries:
        print(f"Compiling & installing query '{q_name}'...")
        try:
            install_cmd = f"USE GRAPH FraudGraph\nINSTALL QUERY {q_name}"
            res = conn.gsql(install_cmd)
            print(f"[INSTALL RESULT] {q_name}: {res.strip()}")
        except Exception as e:
            print(f"[ERROR] Could not install {q_name}: {e}")

    # Verify installed
    print("\n--- Verifying Installed Queries ---")
    try:
        installed = conn.getInstalledQueries()
        print(f"Total Installed Queries ({len(installed)}): {installed}")
        for q_name in unique_queries:
            if q_name in installed:
                print(f"  [PASS] {q_name} is active.")
            else:
                print(f"  [MISSING] {q_name} not found in installed queries.")
    except Exception as e:
        print(f"Error checking installed queries: {e}")

if __name__ == "__main__":
    install_all_queries()
