import os
import sys
import json
import time
import math
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Configuration
DATASET_PATH = Path(os.getenv("DATASET_PATH", "./data"))
TG_HOST = os.getenv("TG_HOST", "http://127.0.0.1:14240")
TG_GRAPHNAME = os.getenv("TG_GRAPHNAME", "FraudGraph")
TG_USERNAME = os.getenv("TG_USERNAME", "tigergraph")
TG_PASSWORD = os.getenv("TG_PASSWORD", "tigergraph")
TG_SECRET = os.getenv("TG_SECRET", "")
TG_TOKEN = os.getenv("TG_TOKEN", "")

CHECKPOINT_DIR = Path("./checkpoints")
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

def is_checkpoint_done(step_name: str) -> bool:
    cp = CHECKPOINT_DIR / f"checkpoint_{step_name}.done"
    return cp.exists()

def set_checkpoint_done(step_name: str, count: int = 0):
    cp = CHECKPOINT_DIR / f"checkpoint_{step_name}.done"
    cp.write_text(f"DONE:{count}\nTimestamp:{time.time()}\n", encoding="utf-8")
    print(f"[CHECKPOINT] {step_name} marked as DONE (Records: {count})")

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

def load_transactions(conn):
    step = "transactions"
    if is_checkpoint_done(step):
        print(f"[SKIP] Step '{step}' already completed according to checkpoint.")
        return

    import pandas as pd

    # Check for train_transaction.csv
    txn_candidates = [
        DATASET_PATH / "train_transaction.csv",
        DATASET_PATH / "HHGOA_IEEE" / "train_transaction.csv",
        Path("./data/train_transaction.csv"),
    ]
    txn_file = next((f for f in txn_candidates if f.is_file()), None)
    if not txn_file:
        print(f"[WARNING] train_transaction.csv not found in {DATASET_PATH}. Skipping transaction loading.")
        return

    print(f"[START] Loading transactions from {txn_file}...")
    chunksize = 10000
    batch_limit = 5000
    total_loaded = 0

    acc_batch = {}
    txn_batch = {}
    performed_batch = []

    for chunk in pd.read_csv(txn_file, chunksize=chunksize, low_memory=False):
        for _, row in chunk.iterrows():
            card1 = clean_val(row.get("card1")) or 0
            card2 = clean_val(row.get("card2")) or 0
            addr1 = clean_val(row.get("addr1")) or 0

            # Derived Account key
            acc_id = f"ACC_{int(card1)}_{int(card2)}_{int(addr1)}"
            if acc_id not in acc_batch:
                acc_batch[acc_id] = {
                    "p_emaildomain": clean_val(row.get("P_emaildomain")),
                    "addr1": clean_val(row.get("addr1")),
                    "addr2": clean_val(row.get("addr2")),
                    "card1": int(card1) if card1 else 0,
                    "card2": clean_val(row.get("card2")),
                    "risk_score": clean_val(row.get("risk_score")) or clean_val(row.get("FraudProbability")) or float(row.get("isFraud", 0)),
                }

            # Transaction features
            txn_id = str(row["TransactionID"])
            v_cols = {f"V{i}": clean_val(row.get(f"V{i}")) for i in range(1, 340) if f"V{i}" in row and clean_val(row.get(f"V{i}")) is not None}
            
            # M-features: encode T/F/NaN as 1/0/-1
            m_cols = {}
            for i in range(1, 10):
                col = f"M{i}"
                if col in row:
                    v = row[col]
                    if pd.isna(v) or v is None:
                        m_cols[col] = -1
                    elif str(v).upper() in ["T", "TRUE", "1"]:
                        m_cols[col] = 1
                    else:
                        m_cols[col] = 0

            txn_batch[txn_id] = {
                "is_fraud": int(row.get("isFraud", 0)),
                "txn_dt": int(row.get("TransactionDT", 0)),
                "amount": clean_val(row.get("TransactionAmt")),
                "product_cd": clean_val(row.get("ProductCD")),
                "card1": int(card1) if card1 else 0,
                "card2": clean_val(row.get("card2")),
                "card3": clean_val(row.get("card3")),
                "card4": clean_val(row.get("card4")),
                "card5": clean_val(row.get("card5")),
                "card6": clean_val(row.get("card6")),
                "addr1": clean_val(row.get("addr1")),
                "addr2": clean_val(row.get("addr2")),
                "dist1": clean_val(row.get("dist1")),
                "dist2": clean_val(row.get("dist2")),
                "p_emaildomain": clean_val(row.get("P_emaildomain")),
                "r_emaildomain": clean_val(row.get("R_emaildomain")),
                "risk_score": clean_val(row.get("risk_score")) or clean_val(row.get("FraudProbability")) or float(row.get("isFraud", 0)),
                "v_features_json": json.dumps(v_cols),
                "m_features_json": json.dumps(m_cols),
            }

            performed_batch.append((acc_id, txn_id, {"txn_dt": int(row.get("TransactionDT", 0))}))

            if len(txn_batch) >= batch_limit:
                conn.upsertVertices("Account", [(k, v) for k, v in acc_batch.items()])
                conn.upsertVertices("Transaction", [(k, v) for k, v in txn_batch.items()])
                conn.upsertEdges("Account", "PERFORMED", [(s, t, a) for s, t, a in performed_batch])
                total_loaded += len(txn_batch)
                print(f"Transactions loaded: {total_loaded}")
                acc_batch.clear()
                txn_batch.clear()
                performed_batch.clear()
                time.sleep(0.05)

    if txn_batch:
        conn.upsertVertices("Account", [(k, v) for k, v in acc_batch.items()])
        conn.upsertVertices("Transaction", [(k, v) for k, v in txn_batch.items()])
        conn.upsertEdges("Account", "PERFORMED", [(s, t, a) for s, t, a in performed_batch])
        total_loaded += len(txn_batch)

    set_checkpoint_done(step, total_loaded)
    print(f"[DONE] load_transactions: {total_loaded} records loaded.")

def load_identity(conn):
    step = "identity"
    if is_checkpoint_done(step):
        print(f"[SKIP] Step '{step}' already completed according to checkpoint.")
        return

    import pandas as pd
    id_candidates = [
        DATASET_PATH / "train_identity.csv",
        DATASET_PATH / "HHGOA_IEEE" / "train_identity.csv",
        Path("./data/train_identity.csv"),
    ]
    id_file = next((f for f in id_candidates if f.is_file()), None)
    if not id_file:
        print(f"[WARNING] train_identity.csv not found in {DATASET_PATH}. Skipping identity loading.")
        return

    print(f"[START] Loading identity from {id_file}...")
    chunksize = 10000
    batch_limit = 5000
    total_loaded = 0

    device_batch = {}
    ip_batch = {}
    used_dev_edges = []
    from_ip_edges = []

    for chunk in pd.read_csv(id_file, chunksize=chunksize, low_memory=False):
        for _, row in chunk.iterrows():
            txn_id = str(row["TransactionID"])
            dev_info = str(row.get("DeviceInfo", ""))[:50]
            id_31 = str(row.get("id_31", ""))[:20]
            dev_id = f"DEV_{dev_info}_{id_31}".strip("_")
            if not dev_id:
                dev_id = f"DEV_UNKNOWN_{txn_id}"

            device_batch[dev_id] = {
                "device_info": clean_val(dev_info),
                "device_type": clean_val(row.get("DeviceType")),
                "browser": clean_val(id_31),
            }
            used_dev_edges.append((txn_id, dev_id, {}))

            raw_ip = str(row.get("id_38", ""))[:10]
            ip_cluster_id = f"IP_{abs(hash(raw_ip)) % (10**8)}"
            ip_batch[ip_cluster_id] = {
                "ip_hash": str(hash(raw_ip)),
            }
            from_ip_edges.append((txn_id, ip_cluster_id, {}))

            if len(device_batch) >= batch_limit:
                conn.upsertVertices("Device", [(k, v) for k, v in device_batch.items()])
                conn.upsertVertices("IPCluster", [(k, v) for k, v in ip_batch.items()])
                conn.upsertEdges("Transaction", "USED_DEVICE", [(s, t, a) for s, t, a in used_dev_edges])
                conn.upsertEdges("Transaction", "FROM_IP_CLUSTER", [(s, t, a) for s, t, a in from_ip_edges])
                total_loaded += len(device_batch)
                print(f"Identity records loaded: {total_loaded}")
                device_batch.clear()
                ip_batch.clear()
                used_dev_edges.clear()
                from_ip_edges.clear()
                time.sleep(0.05)

    if device_batch:
        conn.upsertVertices("Device", [(k, v) for k, v in device_batch.items()])
        conn.upsertVertices("IPCluster", [(k, v) for k, v in ip_batch.items()])
        conn.upsertEdges("Transaction", "USED_DEVICE", [(s, t, a) for s, t, a in used_dev_edges])
        conn.upsertEdges("Transaction", "FROM_IP_CLUSTER", [(s, t, a) for s, t, a in from_ip_edges])
        total_loaded += len(device_batch)

    set_checkpoint_done(step, total_loaded)
    print(f"[DONE] load_identity: {total_loaded} records loaded.")

def load_closed_cases(conn):
    step = "closed_cases"
    if is_checkpoint_done(step):
        print(f"[SKIP] Step '{step}' already completed according to checkpoint.")
        return

    print("[START] Loading closed investigation cases...")
    # Baseline closed cases corpus
    sample_cases = [
        {
            "case_id": "CASE_2026_001",
            "status": "CLOSED",
            "disposition": "CONFIRMED_FRAUD_RING",
            "risk_score": 0.96,
            "created_at": "2026-01-15T10:00:00Z",
            "summary": "Multi-card synthetic identity syndicate operating across shared device fingerprints.",
            "account_id": "ACC_13926_0_315",
            "txn_id": "2987000",
            "evidences": [
                ("EVID_001", "DEVICE_COLLUSION", "5 accounts sharing identical hardware identifier", "GRAPH_EXPANSION", 0.95),
                ("EVID_002", "RAPID_VELOCITY", "8 consecutive withdrawals in 120 seconds", "LOG_ANALYSIS", 0.91)
            ]
        },
        {
            "case_id": "CASE_2026_002",
            "status": "CLOSED",
            "disposition": "ACCOUNT_TAKEOVER",
            "risk_score": 0.88,
            "created_at": "2026-02-10T14:30:00Z",
            "summary": "Compromised credential breach followed by immediate high-value purchase and address update.",
            "account_id": "ACC_4461_375_184",
            "txn_id": "2987001",
            "evidences": [
                ("EVID_003", "IP_GEO_MISMATCH", "Login from foreign proxy 4000km from historical activity", "IP_INTEL", 0.89)
            ]
        },
        {
            "case_id": "CASE_2026_003",
            "status": "CLOSED",
            "disposition": "FALSE_POSITIVE",
            "risk_score": 0.32,
            "created_at": "2026-03-05T09:15:00Z",
            "summary": "Legitimate business travel card usage confirmed by customer verification.",
            "account_id": "ACC_1804_161_269",
            "txn_id": "2987002",
            "evidences": [
                ("EVID_004", "CUSTOMER_ATTESTATION", "Customer verified transaction via two-factor phone verification", "CALL_CENTER", 0.10)
            ]
        }
    ]

    case_vertices = []
    case_txn_edges = []
    case_acc_edges = []
    evidence_vertices = []
    evidence_edges = []

    for c in sample_cases:
        case_vertices.append((c["case_id"], {
            "status": c["status"],
            "disposition": c["disposition"],
            "risk_score": c["risk_score"],
            "created_at": c["created_at"],
            "summary": c["summary"]
        }))
        case_acc_edges.append((c["case_id"], c["account_id"], {}))
        case_txn_edges.append((c["case_id"], c["txn_id"], {}))

        for evid_id, etype, desc, src, score in c["evidences"]:
            evidence_vertices.append((evid_id, {
                "evidence_type": etype,
                "description": desc,
                "source": src,
                "score": score
            }))
            evidence_edges.append((evid_id, c["case_id"], {}))

    conn.upsertVertices("Case", case_vertices)
    conn.upsertVertices("Evidence", evidence_vertices)
    conn.upsertEdges("Case", "CASE_TARGETS_ACCOUNT", [(s, t, a) for s, t, a in case_acc_edges])
    conn.upsertEdges("Case", "CASE_TARGETS_TXN", [(s, t, a) for s, t, a in case_txn_edges])
    conn.upsertEdges("Evidence", "EVIDENCE_FOR", [(s, t, a) for s, t, a in evidence_edges])

    set_checkpoint_done(step, len(case_vertices))
    print(f"[DONE] load_closed_cases: {len(case_vertices)} cases loaded.")

def load_policy(conn):
    step = "policy"
    if is_checkpoint_done(step):
        print(f"[SKIP] Step '{step}' already completed according to checkpoint.")
        return

    print("[START] Loading fraud policy rules...")
    policy_rules = [
        {
            "rule_id": "RULE_SAR_001",
            "name": "Mandatory Suspicious Activity Report (SAR) Filing",
            "category": "COMPLIANCE_AML",
            "trigger_condition": "risk_score >= 0.85 AND amount >= 10000.0",
            "action_type": "FILE_SAR",
            "approval_tier": "SENIOR_COMPLIANCE_OFFICER",
            "risk_threshold": 0.85,
            "amount_threshold": 10000.0,
            "regulatory_ref": "31_CFR_1020_320",
            "requires_sar": True,
        },
        {
            "rule_id": "RULE_BLOCK_ACC_002",
            "name": "Syndicated Ring Account Immediate Freeze",
            "category": "ACCOUNT_SECURITY",
            "trigger_condition": "shared_device_count >= 3 AND risk_score >= 0.75",
            "action_type": "FREEZE_ACCOUNT",
            "approval_tier": "FRAUD_OPS_LEAD",
            "risk_threshold": 0.75,
            "amount_threshold": 0.0,
            "regulatory_ref": "INTERNAL_RISK_POLICY_4.1",
            "requires_sar": True,
        },
        {
            "rule_id": "RULE_BLOCK_TXN_003",
            "name": "High-Risk Card Transaction Blocking",
            "category": "TRANSACTION_MONITORING",
            "trigger_condition": "risk_score >= 0.90",
            "action_type": "DECLINE_TRANSACTION",
            "approval_tier": "AUTOMATED_SYSTEM",
            "risk_threshold": 0.90,
            "amount_threshold": 50.0,
            "regulatory_ref": "PCI_DSS_REQUIREMENT_10",
            "requires_sar": False,
        },
        {
            "rule_id": "RULE_AUTH_STEPUP_004",
            "name": "Step-Up Multi-Factor Authentication",
            "category": "AUTHENTICATION_CHALLENGE",
            "trigger_condition": "new_device == TRUE OR geo_distance_km >= 500",
            "action_type": "STEP_UP_MFA",
            "approval_tier": "AUTOMATED_SYSTEM",
            "risk_threshold": 0.50,
            "amount_threshold": 100.0,
            "regulatory_ref": "NIST_SP_800_63B",
            "requires_sar": False,
        },
        {
            "rule_id": "RULE_MONITOR_005",
            "name": "Elevated Watchlist Monitoring",
            "category": "SURVEILLANCE",
            "trigger_condition": "risk_score >= 0.60 AND risk_score < 0.75",
            "action_type": "FLAG_FOR_REVIEW",
            "approval_tier": "ANALYST_TIER_1",
            "risk_threshold": 0.60,
            "amount_threshold": 0.0,
            "regulatory_ref": "FINCEN_ADVISORY_FIN_2021",
            "requires_sar": False,
        },
    ]

    rule_vertices = [
        (r["rule_id"], {
            "name": r["name"],
            "category": r["category"],
            "trigger_condition": r["trigger_condition"],
            "action_type": r["action_type"],
            "approval_tier": r["approval_tier"],
            "risk_threshold": r["risk_threshold"],
            "amount_threshold": r["amount_threshold"],
            "regulatory_ref": r["regulatory_ref"],
            "requires_sar": r["requires_sar"],
        })
        for r in policy_rules
    ]

    conn.upsertVertices("PolicyRule", rule_vertices)
    set_checkpoint_done(step, len(rule_vertices))
    print(f"[DONE] load_policy: {len(rule_vertices)} rules loaded.")

def load_patterns(conn):
    step = "patterns"
    if is_checkpoint_done(step):
        print(f"[SKIP] Step '{step}' already completed according to checkpoint.")
        return

    print("[START] Loading fraud pattern templates...")
    patterns = [
        {
            "pattern_id": "PAT_001_DEVICE_RING",
            "name": "Device Sharing Fraud Ring",
            "description": "Multiple distinct bank accounts transacting through a single shared physical device in a short temporal window.",
            "is_documented": True,
            "confidence": 1.0,
            "match_criteria_json": json.dumps({
                "logic": "AND",
                "conditions": [
                    {"feature": "shared_device_accounts", "op": ">=", "value": 2},
                    {"feature": "time_window_hours", "op": "<=", "value": 24}
                ]
            })
        },
        {
            "pattern_id": "PAT_002_VELOCITY_BUSTOUT",
            "name": "Velocity Bust-Out Attack",
            "description": "Rapid escalation of transaction frequency and amounts within hours prior to total credit line exhaustion.",
            "is_documented": True,
            "confidence": 1.0,
            "match_criteria_json": json.dumps({
                "logic": "AND",
                "conditions": [
                    {"feature": "txn_count_1h", "op": ">=", "value": 5},
                    {"feature": "cumulative_amount_ratio", "op": ">=", "value": 0.85}
                ]
            })
        },
        {
            "pattern_id": "PAT_003_DOMAIN_CLUSTER",
            "name": "Disposable Email Domain Syndicate",
            "description": "Syndicate opening disparate accounts utilizing uncommon or disposable email domains for coordinated identity creation.",
            "is_documented": True,
            "confidence": 1.0,
            "match_criteria_json": json.dumps({
                "logic": "AND",
                "conditions": [
                    {"feature": "shared_uncommon_domain_count", "op": ">=", "value": 3},
                    {"feature": "account_age_days", "op": "<=", "value": 7}
                ]
            })
        },
        {
            "pattern_id": "PAT_004_IMPOSSIBLE_TRAVEL",
            "name": "Geographic Distance Anomaly",
            "description": "Consecutive transactions occurring in physical locations that could not have been reached within the elapsed time.",
            "is_documented": True,
            "confidence": 1.0,
            "match_criteria_json": json.dumps({
                "logic": "AND",
                "conditions": [
                    {"feature": "implied_speed_kmh", "op": ">=", "value": 800},
                    {"feature": "time_delta_minutes", "op": "<=", "value": 60}
                ]
            })
        },
        {
            "pattern_id": "PAT_005_MICRO_SMURFING",
            "name": "Structured Micro-Transactions (Smurfing)",
            "description": "High volume of sub-threshold transfers designed to evade regulatory anti-money laundering and SAR reporting thresholds.",
            "is_documented": True,
            "confidence": 1.0,
            "match_criteria_json": json.dumps({
                "logic": "AND",
                "conditions": [
                    {"feature": "amount", "op": "<", "value": 10000.0},
                    {"feature": "amount", "op": ">=", "value": 9000.0},
                    {"feature": "repetition_count", "op": ">=", "value": 3}
                ]
            })
        }
    ]

    pattern_vertices = [
        (p["pattern_id"], {
            "name": p["name"],
            "description": p["description"],
            "is_documented": p["is_documented"],
            "confidence": p["confidence"],
            "match_criteria_json": p["match_criteria_json"]
        })
        for p in patterns
    ]

    conn.upsertVertices("PatternTemplate", pattern_vertices)
    set_checkpoint_done(step, len(pattern_vertices))
    print(f"[DONE] load_patterns: {len(pattern_vertices)} pattern templates loaded.")

def main():
    print("=== HHGOA Fraud Agent: Master Data Loading Pipeline ===")
    conn = get_tg_conn()

    load_transactions(conn)
    load_identity(conn)
    load_closed_cases(conn)
    load_policy(conn)
    load_patterns(conn)

    print("\n--- Final Graph Statistics ---")
    counts = conn.getVertexCount("*")
    print("Vertex Counts:", counts)
    print("=== Master Data Loading Pipeline Completed ===")

if __name__ == "__main__":
    main()
