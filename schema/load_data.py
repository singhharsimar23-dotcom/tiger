"""
HHGOA Ground Truth Corrected — Master Data Loading Pipeline
Reads directly from D:\\ (CSV files confirmed at D:\\transactions.csv etc.)
Writes to TigerGraph FraudGraph using corrected schema vertex/edge names.

Run order: transactions → identity (DeviceProfile + email/billing edges) →
           build_next_edges → closed_cases → policy → (verify_load)

NOTE: derived_edges.py is DELETED — SHARES_* edges are retired.
      Sharing signals are discovered via live graph traversal.
"""

import os
import sys
import json
import time
import math
import hashlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration — CSVs live on D:\\ (confirmed)
# ---------------------------------------------------------------------------
DATASET_PATH = Path(os.getenv("DATASET_PATH", "D:\\"))
TXN_FILE     = DATASET_PATH / "transactions.csv"
IDENT_FILE   = DATASET_PATH / "identity.csv"
CC_FILE      = DATASET_PATH / "closed_cases_history.csv"
CASE_PACK    = DATASET_PATH / "case_pack.csv"

TG_HOST      = os.getenv("TG_HOST",      "http://127.0.0.1:14240")
TG_GRAPHNAME = os.getenv("TG_GRAPHNAME", "FraudGraph")
TG_USERNAME  = os.getenv("TG_USERNAME",  "tigergraph")
TG_PASSWORD  = os.getenv("TG_PASSWORD",  "tigergraph")
TG_SECRET    = os.getenv("TG_SECRET",    "")
TG_TOKEN     = os.getenv("TG_TOKEN",     "")

CHECKPOINT_DIR = Path("./checkpoints")
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE  = 10_000
BATCH_LIMIT = 5_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_checkpoint_done(step_name: str) -> bool:
    return (CHECKPOINT_DIR / f"checkpoint_{step_name}.done").exists()


def set_checkpoint_done(step_name: str, count: int = 0):
    cp = CHECKPOINT_DIR / f"checkpoint_{step_name}.done"
    cp.write_text(f"DONE:{count}\nTimestamp:{time.time()}\n", encoding="utf-8")
    print(f"[CHECKPOINT] {step_name} marked DONE ({count} records)")


def clean_val(val):
    if val is None:
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return round(val, 4)
    if isinstance(val, str):
        s = val.strip()
        return s[:200] if len(s) > 200 else s
    return val


def device_profile_id(device_info: str, os_: str, browser: str, screen: str) -> str:
    """Deterministic hash of (DeviceInfo + OS + browser + screen) → device_profile_id."""
    raw = f"{device_info}|{os_}|{browser}|{screen}"
    return "dp_" + hashlib.sha1(raw.encode()).hexdigest()[:16]


def upsert_flush(conn, vertex_batches: dict, edge_batches: list):
    """Upsert all accumulated vertex and edge batches then clear them."""
    for vtype, records in vertex_batches.items():
        if records:
            conn.upsertVertices(vtype, list(records.items()))
    for src_type, edge_type, edges in edge_batches:
        if edges:
            conn.upsertEdges(src_type, edge_type, edges)
    for v in vertex_batches.values():
        v.clear()
    for batch in edge_batches:
        batch[2].clear()


def get_tg_conn():
    try:
        import pyTigerGraph as tg
    except ImportError:
        print("[ERROR] pyTigerGraph required. Run: pip install pyTigerGraph")
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


# ---------------------------------------------------------------------------
# S03-A  Load transactions → Customer, Card, Transaction vertices
#         + OWNS, MADE, PURCHASER_EMAIL, BILLED_IN edges
# ---------------------------------------------------------------------------

def load_transactions(conn):
    step = "transactions"
    if is_checkpoint_done(step):
        print(f"[SKIP] {step} already done.")
        return

    if not TXN_FILE.is_file():
        print(f"[ERROR] {TXN_FILE} not found. Place transactions.csv on D:\\ first.")
        return

    import pandas as pd
    print(f"[START] Loading {TXN_FILE} ...")

    # Vertex and edge accumulators
    customers:      dict = {}   # customer_id → {}
    cards:          dict = {}   # card_id → attrs
    txns:           dict = {}   # txn_id → attrs
    email_domains:  dict = {}   # domain → {}
    billing_regions: dict = {}  # region_code → {country_code}

    owns_edges:     list = []   # (customer_id, card_id, {})
    made_edges:     list = []   # (card_id, txn_id, {})
    email_edges:    list = []   # (txn_id, domain, {})
    billing_edges:  list = []   # (txn_id, region_code, {})

    total_loaded = 0

    for chunk in pd.read_csv(TXN_FILE, chunksize=CHUNK_SIZE, low_memory=False):
        for _, row in chunk.iterrows():
            # ---- customer & card ----
            cust_id = clean_val(row.get("customer_id")) or ""
            # card_id is the full "C12382-K1" style string from the dataset
            card_id = clean_val(row.get("card_id")) or ""  # present in enriched file
            if not card_id and cust_id:
                # Fallback: synthesise from customer_id + card1 suffix
                card_id = f"{cust_id}-K{int(row.get('card1', 0) or 0)}"

            if cust_id and cust_id not in customers:
                customers[cust_id] = {}

            if card_id and card_id not in cards:
                cards[card_id] = {
                    "card1": int(row.get("card1") or 0),
                    "card2": clean_val(row.get("card2")),
                    "card3": clean_val(row.get("card3")),
                    "card4": clean_val(row.get("card4")),
                    "card5": clean_val(row.get("card5")),
                    "card6": clean_val(row.get("card6")),
                }
                if cust_id:
                    owns_edges.append((cust_id, card_id, {}))

            # ---- transaction ----
            raw_txn_id = str(row["TransactionID"])
            txn_id = f"T{raw_txn_id}"

            # Pack feature groups as JSON
            c_cols = {f"C{i}": clean_val(row.get(f"C{i}"))
                      for i in range(1, 15) if f"C{i}" in row and clean_val(row.get(f"C{i}")) is not None}
            d_cols = {f"D{i}": clean_val(row.get(f"D{i}"))
                      for i in range(1, 16) if f"D{i}" in row and clean_val(row.get(f"D{i}")) is not None}

            m_cols = {}
            for i in range(1, 10):
                col = f"M{i}"
                if col in row:
                    v = row[col]
                    import pandas as _pd
                    if _pd.isna(v) or v is None:
                        m_cols[col] = -1
                    elif str(v).upper() in ("T", "TRUE", "1"):
                        m_cols[col] = 1
                    else:
                        m_cols[col] = 0

            v_cols = {f"V{i}": clean_val(row.get(f"V{i}"))
                      for i in range(1, 340) if f"V{i}" in row and clean_val(row.get(f"V{i}")) is not None}

            # ts comes from the enriched dataset as a real timestamp string
            ts_raw = clean_val(row.get("ts")) or ""

            txns[txn_id] = {
                "transaction_dt":  int(row.get("TransactionDT") or 0),
                "ts":              ts_raw,
                "transaction_amt": clean_val(row.get("TransactionAmt")),
                "product_cd":      clean_val(row.get("ProductCD")),
                "channel":         clean_val(row.get("channel")) or "unknown",
                "risk_score":      clean_val(row.get("risk_score")),
                "addr1":           clean_val(row.get("addr1")),
                "addr2":           clean_val(row.get("addr2")),
                "dist1":           clean_val(row.get("dist1")),
                "dist2":           clean_val(row.get("dist2")),
                "p_emaildomain":   clean_val(row.get("P_emaildomain")),
                "r_emaildomain":   clean_val(row.get("R_emaildomain")),
                "c_features_json": json.dumps(c_cols),
                "d_features_json": json.dumps(d_cols),
                "m_features_json": json.dumps(m_cols),
                "v_features_json": json.dumps(v_cols),
            }

            if card_id:
                made_edges.append((card_id, txn_id, {}))

            # ---- EmailDomain edge ----
            p_dom = clean_val(row.get("P_emaildomain"))
            if p_dom:
                email_domains[p_dom] = {}
                email_edges.append((txn_id, p_dom, {}))

            # ---- BillingRegion edge ----
            addr1_val = clean_val(row.get("addr1"))
            addr2_val = clean_val(row.get("addr2"))
            if addr1_val is not None:
                region_code = str(int(addr1_val)) if isinstance(addr1_val, float) else str(addr1_val)
                billing_regions[region_code] = {"country_code": addr2_val or 0.0}
                billing_edges.append((txn_id, region_code, {}))

            # ---- Flush batch ----
            if len(txns) >= BATCH_LIMIT:
                conn.upsertVertices("Customer",      [(k, v) for k, v in customers.items()])
                conn.upsertVertices("Card",          [(k, v) for k, v in cards.items()])
                conn.upsertVertices("Transaction",   [(k, v) for k, v in txns.items()])
                conn.upsertVertices("EmailDomain",   [(k, v) for k, v in email_domains.items()])
                conn.upsertVertices("BillingRegion", [(k, v) for k, v in billing_regions.items()])
                conn.upsertEdges("Customer",    "OWNS",           [(s, t, a) for s, t, a in owns_edges])
                conn.upsertEdges("Card",        "MADE",           [(s, t, a) for s, t, a in made_edges])
                conn.upsertEdges("Transaction", "PURCHASER_EMAIL",[(s, t, a) for s, t, a in email_edges])
                conn.upsertEdges("Transaction", "BILLED_IN",      [(s, t, a) for s, t, a in billing_edges])
                total_loaded += len(txns)
                print(f"  → {total_loaded:,} transactions loaded")
                customers.clear(); cards.clear(); txns.clear()
                email_domains.clear(); billing_regions.clear()
                owns_edges.clear(); made_edges.clear()
                email_edges.clear(); billing_edges.clear()
                time.sleep(0.05)

    # Final flush
    if txns:
        conn.upsertVertices("Customer",      [(k, v) for k, v in customers.items()])
        conn.upsertVertices("Card",          [(k, v) for k, v in cards.items()])
        conn.upsertVertices("Transaction",   [(k, v) for k, v in txns.items()])
        conn.upsertVertices("EmailDomain",   [(k, v) for k, v in email_domains.items()])
        conn.upsertVertices("BillingRegion", [(k, v) for k, v in billing_regions.items()])
        conn.upsertEdges("Customer",    "OWNS",            [(s, t, a) for s, t, a in owns_edges])
        conn.upsertEdges("Card",        "MADE",            [(s, t, a) for s, t, a in made_edges])
        conn.upsertEdges("Transaction", "PURCHASER_EMAIL", [(s, t, a) for s, t, a in email_edges])
        conn.upsertEdges("Transaction", "BILLED_IN",       [(s, t, a) for s, t, a in billing_edges])
        total_loaded += len(txns)

    set_checkpoint_done(step, total_loaded)
    print(f"[DONE] load_transactions: {total_loaded:,} records.")


# ---------------------------------------------------------------------------
# S03-B  Load identity.csv → DeviceProfile vertices + FROM_DEVICE edges
# ---------------------------------------------------------------------------

def load_identity(conn):
    step = "identity"
    if is_checkpoint_done(step):
        print(f"[SKIP] {step} already done.")
        return

    if not IDENT_FILE.is_file():
        print(f"[ERROR] {IDENT_FILE} not found.")
        return

    import pandas as pd
    print(f"[START] Loading {IDENT_FILE} ...")

    device_profiles: dict = {}
    from_device_edges: list = []
    total_loaded = 0

    for chunk in pd.read_csv(IDENT_FILE, chunksize=CHUNK_SIZE, low_memory=False):
        for _, row in chunk.iterrows():
            raw_txn_id = str(row["TransactionID"])
            txn_id = f"T{raw_txn_id}"

            dev_info = str(row.get("DeviceInfo", "") or "")[:50]
            os_      = str(row.get("id_30", "") or "")[:30]
            browser  = str(row.get("id_31", "") or "")[:30]
            screen   = str(row.get("id_33", "") or "")[:20]
            dp_id    = device_profile_id(dev_info, os_, browser, screen)

            # Pack id_01-id_11 numeric ratings
            id_feats = {f"id_{i:02d}": clean_val(row.get(f"id_{i:02d}") or row.get(f"id_0{i}"))
                        for i in range(1, 12) if f"id_{i:02d}" in row or f"id_0{i}" in row}

            device_profiles[dp_id] = {
                "device_type":     clean_val(row.get("DeviceType")),
                "device_info":     dev_info,
                "os":              os_,
                "browser":         browser,
                "screen":          screen,
                "proxy_flag":      clean_val(row.get("id_23")) or "none",
                "device_match":    clean_val(row.get("id_15")) or "",
                "id_features_json": json.dumps(id_feats),
            }
            from_device_edges.append((txn_id, dp_id, {}))

            if len(device_profiles) >= BATCH_LIMIT:
                conn.upsertVertices("DeviceProfile",  [(k, v) for k, v in device_profiles.items()])
                conn.upsertEdges("Transaction", "FROM_DEVICE", [(s, t, a) for s, t, a in from_device_edges])
                total_loaded += len(device_profiles)
                print(f"  → {total_loaded:,} device profiles loaded")
                device_profiles.clear(); from_device_edges.clear()
                time.sleep(0.05)

    if device_profiles:
        conn.upsertVertices("DeviceProfile",  [(k, v) for k, v in device_profiles.items()])
        conn.upsertEdges("Transaction", "FROM_DEVICE", [(s, t, a) for s, t, a in from_device_edges])
        total_loaded += len(device_profiles)

    set_checkpoint_done(step, total_loaded)
    print(f"[DONE] load_identity: {total_loaded:,} records.")


# ---------------------------------------------------------------------------
# S03-C  Build NEXT edges — temporal chain per card, ordered by ts
#         Run AFTER load_transactions so all Transaction vertices exist.
# ---------------------------------------------------------------------------

def build_next_edges(conn):
    step = "next_edges"
    if is_checkpoint_done(step):
        print(f"[SKIP] {step} already done.")
        return

    if not TXN_FILE.is_file():
        print(f"[ERROR] {TXN_FILE} not found.")
        return

    import pandas as pd
    print("[START] Building NEXT chain edges ...")

    # Load only the columns we need — memory efficient
    cols_needed = ["TransactionID", "TransactionDT", "card_id", "customer_id", "card1"]
    try:
        df = pd.read_csv(TXN_FILE, usecols=cols_needed, low_memory=False)
    except ValueError:
        # Fallback if card_id column not present
        df = pd.read_csv(TXN_FILE, usecols=["TransactionID", "TransactionDT", "customer_id", "card1"],
                         low_memory=False)
        df["card_id"] = df["customer_id"].astype(str) + "-K" + df["card1"].fillna(0).astype(int).astype(str)

    df["txn_id"] = "T" + df["TransactionID"].astype(str)
    df = df.sort_values("TransactionDT")

    next_edges = []
    total_edges = 0

    for _, grp in df.groupby("card_id"):
        txn_ids = grp["txn_id"].tolist()
        for i in range(len(txn_ids) - 1):
            next_edges.append((txn_ids[i], txn_ids[i + 1], {}))
            if len(next_edges) >= BATCH_LIMIT:
                conn.upsertEdges("Transaction", "NEXT", [(s, t, a) for s, t, a in next_edges])
                total_edges += len(next_edges)
                next_edges.clear()
                time.sleep(0.05)

    if next_edges:
        conn.upsertEdges("Transaction", "NEXT", [(s, t, a) for s, t, a in next_edges])
        total_edges += len(next_edges)

    set_checkpoint_done(step, total_edges)
    print(f"[DONE] build_next_edges: {total_edges:,} NEXT edges written.")


# ---------------------------------------------------------------------------
# S03-D  Load closed_cases_history.csv → ClosedCase vertices
#         + CC_INVOLVES, CC_ON_CARD, CC_CONNECTED_TO edges
# ---------------------------------------------------------------------------

def load_closed_cases(conn):
    step = "closed_cases"
    if is_checkpoint_done(step):
        print(f"[SKIP] {step} already done.")
        return

    if not CC_FILE.is_file():
        print(f"[ERROR] {CC_FILE} not found.")
        return

    import pandas as pd
    print(f"[START] Loading {CC_FILE} ...")

    df = pd.read_csv(CC_FILE, low_memory=False)
    case_vertices = []
    involves_edges = []    # ClosedCase → Transaction
    on_card_edges  = []    # ClosedCase → Card (primary)
    connected_edges = []   # ClosedCase → Card (connected)
    total = 0

    for _, row in df.iterrows():
        case_id = str(row["case_id"])

        # pipe-separated txn_ids → JSON array
        raw_txns = str(row.get("txn_ids", "") or "")
        txn_list = [t.strip() for t in raw_txns.split("|") if t.strip()]
        txn_ids_json = json.dumps(txn_list)

        # pipe-separated connected_card_ids
        raw_connected = str(row.get("connected_card_ids", "") or "")
        connected_list = [c.strip() for c in raw_connected.split("|") if c.strip()]

        case_vertices.append((case_id, {
            "customer_id":          str(row.get("customer_id", "") or ""),
            "card_id":              str(row.get("card_id", "") or ""),
            "opened_at":            str(row.get("opened_at", "") or ""),
            "closed_at":            str(row.get("closed_at", "") or ""),
            "outcome":              clean_val(row.get("outcome")) or "",
            "pattern":              clean_val(row.get("pattern")) or "none",
            "first_fraud_txn_id":   str(row.get("first_fraud_txn_id", "") or ""),
            "txn_ids_json":         txn_ids_json,
            "n_txns":               int(row.get("n_txns", 0) or 0),
            "exposure_usd":         float(row.get("exposure_usd", 0.0) or 0.0),
            "connected_card_ids_json": json.dumps(connected_list),
            "actions_taken":        clean_val(row.get("actions_taken")) or "",
            "report_filed":         bool(row.get("report_filed", False)),
            "analyst_notes":        clean_val(row.get("analyst_notes")) or "",
            "notes_embedding":      [],  # populated at runtime by retrieval layer
        }))

        # CC_INVOLVES — one edge per txn in the case
        for txn_id in txn_list:
            involves_edges.append((case_id, f"T{txn_id}" if not txn_id.startswith("T") else txn_id, {}))

        # CC_ON_CARD — primary card
        primary_card = str(row.get("card_id", "") or "")
        if primary_card:
            on_card_edges.append((case_id, primary_card, {}))

        # CC_CONNECTED_TO — all connected cards
        for c_id in connected_list:
            connected_edges.append((case_id, c_id, {}))

        total += 1

    # Upsert all at once (5,565 rows is small enough)
    conn.upsertVertices("ClosedCase", case_vertices)
    conn.upsertEdges("ClosedCase", "CC_INVOLVES",     [(s, t, a) for s, t, a in involves_edges])
    conn.upsertEdges("ClosedCase", "CC_ON_CARD",      [(s, t, a) for s, t, a in on_card_edges])
    conn.upsertEdges("ClosedCase", "CC_CONNECTED_TO", [(s, t, a) for s, t, a in connected_edges])

    set_checkpoint_done(step, total)
    print(f"[DONE] load_closed_cases: {total:,} cases loaded.")


# ---------------------------------------------------------------------------
# S03-E  Load policy rules (R1-R10) — delegated to policy_loader.py
#         Calling it here keeps the pipeline self-contained.
# ---------------------------------------------------------------------------

def load_policy(conn):
    step = "policy"
    if is_checkpoint_done(step):
        print(f"[SKIP] {step} already done.")
        return
    try:
        from schema.policy_loader import load_policy_rules
        load_policy_rules(conn)
    except ImportError:
        # Inline fallback
        from agent.state import POLICY_RULES
        rule_vertices = [
            (rule_id, {"rule_text": rule_text, "rule_embedding": []})
            for rule_id, rule_text in POLICY_RULES.items()
        ]
        conn.upsertVertices("PolicyRule", rule_vertices)
        print(f"[DONE] load_policy (inline): {len(rule_vertices)} rules loaded.")
    set_checkpoint_done(step, 10)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== HHGOA Fraud Agent: Ground-Truth-Corrected Data Loading Pipeline ===")
    print(f"  transactions.csv : {TXN_FILE} ({'EXISTS' if TXN_FILE.exists() else 'MISSING'})")
    print(f"  identity.csv     : {IDENT_FILE} ({'EXISTS' if IDENT_FILE.exists() else 'MISSING'})")
    print(f"  closed_cases     : {CC_FILE} ({'EXISTS' if CC_FILE.exists() else 'MISSING'})")
    print()

    conn = get_tg_conn()

    load_transactions(conn)    # Customer, Card, Transaction, EmailDomain, BillingRegion
    load_identity(conn)        # DeviceProfile + FROM_DEVICE edges
    build_next_edges(conn)     # NEXT temporal chain per card
    load_closed_cases(conn)    # ClosedCase + CC_* edges
    load_policy(conn)          # PolicyRule R1-R10

    print("\n--- Final Graph Statistics ---")
    try:
        counts = conn.getVertexCount("*")
        print("Vertex Counts:", counts)
    except Exception as e:
        print(f"Could not fetch counts: {e}")
    print("=== Pipeline Complete ===")


if __name__ == "__main__":
    main()
