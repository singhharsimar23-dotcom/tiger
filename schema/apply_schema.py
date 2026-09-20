import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TG_HOST = os.getenv("TG_HOST", "http://127.0.0.1:14240")
TG_GRAPHNAME = os.getenv("TG_GRAPHNAME", "FraudGraph")
TG_USERNAME = os.getenv("TG_USERNAME", "tigergraph")
TG_PASSWORD = os.getenv("TG_PASSWORD", "tigergraph")
TG_SECRET = os.getenv("TG_SECRET", "")
TG_TOKEN = os.getenv("TG_TOKEN", "")

# Ground Truth Corrected — vertex and edge names match schema.gsql exactly
EXPECTED_VERTICES = {
    "Customer",
    "Card",
    "Transaction",
    "DeviceProfile",
    "EmailDomain",
    "BillingRegion",
    "ClosedCase",
    "Case",
    "PolicyRule",
}

EXPECTED_EDGES = {
    "OWNS",
    "MADE",
    "FROM_DEVICE",
    "PURCHASER_EMAIL",
    "BILLED_IN",
    "NEXT",
    "CC_INVOLVES",
    "CC_ON_CARD",
    "CC_CONNECTED_TO",
    "CASE_INVOLVES",
    "CASE_ON_CARD",
    "CASE_CONNECTED_TO",
    "CASE_SIMILAR_TO",
}

def get_connection():
    try:
        import pyTigerGraph as tg
    except ImportError:
        print("[ERROR] pyTigerGraph is not installed. Please run: pip install pyTigerGraph")
        sys.exit(1)

    print(f"Connecting to TigerGraph at {TG_HOST} (Graph: {TG_GRAPHNAME})...")
    is_cloud = "tgcloud.io" in TG_HOST
    conn = tg.TigerGraphConnection(
        host=TG_HOST,
        graphname=TG_GRAPHNAME,
        username=TG_USERNAME,
        password=TG_PASSWORD or "",
        gsqlSecret=TG_SECRET if TG_SECRET else "",
        apiToken=TG_TOKEN if TG_TOKEN else "",
        tgCloud=is_cloud,
    )
    if TG_SECRET and not conn.apiToken:
        try:
            tok = conn.getToken(secret=TG_SECRET)
            conn.apiToken = tok[0] if isinstance(tok, tuple) else tok
        except Exception as te:
            print(f"[WARNING] getToken failed: {te}")

    # Ping check with auto-wait if stopped/starting
    retries = 3
    for attempt in range(retries):
        try:
            conn.ping()
            print("[SUCCESS] Successfully connected to TigerGraph.")
            break
        except Exception as e:
            print(f"[WARNING] Ping attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                print("Waiting 30 seconds for TigerGraph instance to wake up...")
                time.sleep(30)
            else:
                print("[ERROR] Could not connect to TigerGraph instance.")
                raise e

    return conn

def apply_schema():
    conn = get_connection()
    schema_path = Path(__file__).resolve().parent / "schema.gsql"
    if not schema_path.is_file():
        print(f"[ERROR] Schema file not found: {schema_path}")
        sys.exit(1)

    gsql_content = schema_path.read_text(encoding="utf-8")
    print(f"Applying schema DDL from {schema_path}...")

    # Run GSQL script
    res = conn.gsql(gsql_content)
    print("GSQL Execution Output:\n", res)

    # Vectors are declared inline in schema.gsql WITH VECTOR=...
    # No separate ALTER VERTEX commands needed.

    # Verification
    print("\n--- Schema Verification ---")
    current_vertices = set(conn.getVertexTypes())
    current_edges = set(conn.getEdgeTypes())

    print(f"Vertex Types ({len(current_vertices)}): {sorted(list(current_vertices))}")
    print(f"Edge Types ({len(current_edges)}): {sorted(list(current_edges))}")

    missing_vertices = EXPECTED_VERTICES - current_vertices
    missing_edges = EXPECTED_EDGES - current_edges

    if missing_vertices:
        print(f"[ERROR] Missing vertex types: {missing_vertices}")
    if missing_edges:
        print(f"[ERROR] Missing edge types: {missing_edges}")

    if missing_vertices or missing_edges:
        print("[FAIL] Schema verification failed!")
        sys.exit(1)

    print("[SUCCESS] All vertex types and edge types successfully applied and verified!")

if __name__ == "__main__":
    apply_schema()
