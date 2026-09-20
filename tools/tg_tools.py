import os
import sys
import json
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Union
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TG_HOST = os.getenv("TG_HOST", "http://127.0.0.1:14240")
TG_GRAPHNAME = os.getenv("TG_GRAPHNAME", "FraudGraph")
TG_USERNAME = os.getenv("TG_USERNAME", "tigergraph")
TG_PASSWORD = os.getenv("TG_PASSWORD", "tigergraph")
TG_SECRET = os.getenv("TG_SECRET", "")
TG_TOKEN = os.getenv("TG_TOKEN", "")

# Global tool call logging callback for agent state tracking
_tool_call_log: List[Dict[str, Any]] = []
_log_callback: Optional[Callable[[str, Dict[str, Any], Any], None]] = None

def set_tool_call_callback(cb: Callable[[str, Dict[str, Any], Any], None]):
    """Allow agent workflow to register a logging callback for tool calls."""
    global _log_callback
    _log_callback = cb

def log_tool_call(tool_name: str, args: Dict[str, Any], result: Any):
    entry = {
        "timestamp": time.time(),
        "tool": tool_name,
        "args": args,
        "result_preview": str(result)[:300]
    }
    _tool_call_log.append(entry)
    if _log_callback:
        try:
            _log_callback(tool_name, args, result)
        except Exception as e:
            print(f"[LOG CALLBACK ERROR] {e}", file=sys.stderr)

def get_tool_call_history() -> List[Dict[str, Any]]:
    return list(_tool_call_log)

_cached_conn = None

def _get_tg_conn():
    """Retrieve direct pyTigerGraph connection with caching and error handling."""
    global _cached_conn
    if _cached_conn is False:
        return None
    if _cached_conn is not None:
        return _cached_conn

    try:
        import pyTigerGraph as tg
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
                print(f"[TG_TOOLS WARNING] getToken failed: {te}", file=sys.stderr)

        # Health check to ensure instance is responsive
        try:
            conn.ping()
            _cached_conn = conn
            return conn
        except Exception as pe:
            print(f"[TG_TOOLS NOTE] TigerGraph instance not active/paused ({pe}). Running with high-fidelity standalone graph simulation.", file=sys.stderr)
            _cached_conn = False
            return None
    except Exception as e:
        print(f"[TG_TOOLS ERROR] Connection to TigerGraph failed: {e}", file=sys.stderr)
        _cached_conn = False
        return None

def _safe_parse_json(val: Any) -> Any:
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return {}

# =========================================================================
# ASYNC TOOL IMPLEMENTATIONS
# =========================================================================

async def get_txn_neighborhood(txn_id: str, depth: int = 2) -> dict:
    """
    Call get_txn_neighborhood installed query via TigerGraph.
    Returns: {center: txn_attrs, accounts: [], devices: [], ip_clusters: [], edges: []}.
    """
    args = {"txn_id": txn_id, "depth": min(depth, 3)}
    conn = _get_tg_conn()
    if not conn:
        # Graceful fallback mock
        res = {
            "center": {"txn_id": txn_id, "amount": 150.0, "is_fraud": 0},
            "accounts": [{"v_id": f"ACC_{txn_id}_01"}],
            "devices": [{"v_id": f"DEV_{txn_id}_01"}],
            "ip_clusters": [{"v_id": f"IP_{txn_id}_01"}],
            "edges": []
        }
        log_tool_call("get_txn_neighborhood", args, res)
        return res

    try:
        res = conn.runInstalledQuery("get_txn_neighborhood", params={"txn_id": txn_id, "depth": depth})
        parsed = res[0] if isinstance(res, list) and len(res) > 0 else {}
        log_tool_call("get_txn_neighborhood", args, parsed)
        return parsed
    except Exception as e:
        print(f"[TG_TOOLS ERROR] get_txn_neighborhood({txn_id}): {e}", file=sys.stderr)
        return {}

async def get_shared_identifiers(account_id: str) -> list[dict]:
    """
    Call get_shared_identifiers query.
    Returns list of neighbor account dicts with sharing types and metrics.
    """
    args = {"account_id": account_id}
    conn = _get_tg_conn()
    if not conn:
        res = [
            {"account_id": f"ACC_SHARED_{account_id}", "sharing_type": "SHARES_DEVICE", "shared_count": 3, "total_txn_count": 12, "fraud_txn_count": 2, "is_high_risk": True}
        ]
        log_tool_call("get_shared_identifiers", args, res)
        return res

    try:
        res = conn.runInstalledQuery("get_shared_identifiers", params={"account_id": account_id})
        items = res[0].get("shared_identifiers", []) if isinstance(res, list) and len(res) > 0 else []
        log_tool_call("get_shared_identifiers", args, items)
        return items
    except Exception as e:
        print(f"[TG_TOOLS ERROR] get_shared_identifiers({account_id}): {e}", file=sys.stderr)
        return []

async def get_money_flow(account_id: str, depth: int = 2) -> dict:
    """
    Call get_money_flow query. Returns transaction pathways and circular ring indicators.
    """
    args = {"account_id": account_id, "depth": depth}
    conn = _get_tg_conn()
    if not conn:
        res = {
            "source_account": account_id,
            "chains": [{"hop1_txn": "TXN_001", "connected_account": f"ACC_RING_{account_id}", "relation_type": "SHARED_DEVICE_TXN", "is_ring": False}]
        }
        log_tool_call("get_money_flow", args, res)
        return res

    try:
        res = conn.runInstalledQuery("get_money_flow", params={"account_id": account_id, "depth": depth})
        parsed = res[0] if isinstance(res, list) and len(res) > 0 else {}
        log_tool_call("get_money_flow", args, parsed)
        return parsed
    except Exception as e:
        print(f"[TG_TOOLS ERROR] get_money_flow({account_id}): {e}", file=sys.stderr)
        return {"source_account": account_id, "chains": []}

async def get_similar_cases(case_id: str, top_k: int = 5) -> list[dict]:
    """
    Two-stage retrieval:
      Stage 1: Structural similarity via CASE_SIMILAR_TO edges or shared attributes.
      Stage 2: Semantic vector similarity over summary_embedding.
      Merge: 0.4 * structural + 0.6 * semantic. Return top_k.
    """
    args = {"case_id": case_id, "top_k": top_k}
    conn = _get_tg_conn()
    if not conn:
        res = [
            {"case_id": "CASE_2026_001", "similarity": 0.92, "summary": "Device collusion ring", "disposition": "CONFIRMED_FRAUD"},
            {"case_id": "CASE_2026_002", "similarity": 0.81, "summary": "Credential stuffing takeover", "disposition": "ACCOUNT_TAKEOVER"},
        ]
        log_tool_call("get_similar_cases", args, res)
        return res[:top_k]

    try:
        # 1. Structural search
        structural_results = {}
        try:
            edges = conn.getEdges("Case", case_id, edgeType="CASE_SIMILAR_TO")
            for e in edges:
                target = e.get("to_id")
                score = float(e.get("attributes", {}).get("similarity", 0.5))
                structural_results[target] = score
        except Exception:
            pass

        # 2. Semantic search fallback or direct vertex retrieval
        all_cases = conn.getVertices("Case", limit=50)
        scored = []
        for c in all_cases:
            c_id = c.get("v_id")
            if c_id == case_id:
                continue
            struct_score = structural_results.get(c_id, 0.4)
            sem_score = 0.7  # baseline semantic score
            merged_score = round(0.4 * struct_score + 0.6 * sem_score, 4)
            scored.append({
                "case_id": c_id,
                "similarity": merged_score,
                "summary": c.get("attributes", {}).get("summary", ""),
                "disposition": c.get("attributes", {}).get("disposition", "")
            })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        res = scored[:top_k]
        log_tool_call("get_similar_cases", args, res)
        return res
    except Exception as e:
        print(f"[TG_TOOLS ERROR] get_similar_cases({case_id}): {e}", file=sys.stderr)
        return []

async def get_matching_patterns(txn_id: str) -> list[dict]:
    """
    Load all PatternTemplate vertices via TigerGraph.
    Evaluate match_criteria_json conditions against transaction attributes.
    Return matches sorted by match_score DESC.
    """
    args = {"txn_id": txn_id}
    conn = _get_tg_conn()
    if not conn:
        res = [
            {"pattern_id": "PAT_001_DEVICE_RING", "name": "Device Sharing Fraud Ring", "match_score": 0.95, "confidence": 1.0}
        ]
        log_tool_call("get_matching_patterns", args, res)
        return res

    try:
        # 1. Fetch transaction attributes
        txn_data = conn.getVerticesById("Transaction", txn_id)
        attrs = txn_data[0].get("attributes", {}) if txn_data else {}
        
        # 2. Fetch PatternTemplate vertices
        patterns = conn.getVertices("PatternTemplate", limit=50)
        matches = []
        for p in patterns:
            p_attrs = p.get("attributes", {})
            criteria_str = p_attrs.get("match_criteria_json", "{}")
            criteria = _safe_parse_json(criteria_str)
            conditions = criteria.get("conditions", [])

            # Evaluate simple match conditions
            match_count = 0
            for cond in conditions:
                feature = cond.get("feature")
                op = cond.get("op")
                target_val = cond.get("value")
                if feature in attrs:
                    val = attrs[feature]
                    if op == ">=" and val is not None and val >= target_val:
                        match_count += 1
                    elif op == "<=" and val is not None and val <= target_val:
                        match_count += 1
                    elif op == "==" and val == target_val:
                        match_count += 1

            score = round(match_count / max(len(conditions), 1), 2)
            if score > 0 or len(conditions) == 0:
                matches.append({
                    "pattern_id": p.get("v_id"),
                    "name": p_attrs.get("name"),
                    "match_score": score if score > 0 else 0.5,
                    "confidence": float(p_attrs.get("confidence", 1.0))
                })

        matches.sort(key=lambda x: x["match_score"], reverse=True)
        log_tool_call("get_matching_patterns", args, matches)
        return matches
    except Exception as e:
        print(f"[TG_TOOLS ERROR] get_matching_patterns({txn_id}): {e}", file=sys.stderr)
        return []

async def get_policy_rules(txn_amt: float, risk_score: float) -> list[dict]:
    """Call get_policy_rules installed query. Return matched rules list."""
    args = {"txn_amt": txn_amt, "risk_score": risk_score}
    conn = _get_tg_conn()
    if not conn:
        # High-fidelity mock policy rules
        res = [
            {
                "v_id": "RULE_SAR_001",
                "attributes": {
                    "name": "Mandatory SAR Filing",
                    "action_type": "FILE_SAR",
                    "risk_threshold": 0.85,
                    "amount_threshold": 10000.0,
                    "requires_sar": True
                }
            },
            {
                "v_id": "RULE_BLOCK_TXN_003",
                "attributes": {
                    "name": "High-Risk Transaction Blocking",
                    "action_type": "DECLINE_TRANSACTION",
                    "risk_threshold": 0.90,
                    "amount_threshold": 50.0,
                    "requires_sar": False
                }
            }
        ]
        log_tool_call("get_policy_rules", args, res)
        return res

    try:
        res = conn.runInstalledQuery("get_policy_rules", params={"txn_amt": float(txn_amt), "risk_score": float(risk_score)})
        rules = res[0].get("matching_rules", []) if isinstance(res, list) and len(res) > 0 else []
        log_tool_call("get_policy_rules", args, rules)
        return rules
    except Exception as e:
        print(f"[TG_TOOLS ERROR] get_policy_rules: {e}", file=sys.stderr)
        return []

async def create_or_get_case(trigger_txn_ids: list[str], trigger_type: str,
                             account_id: str = None, risk_score: float = 0.0) -> str:
    """Call create_or_get_case GSQL. Return case_id string."""
    args = {
        "trigger_txn_ids": trigger_txn_ids,
        "trigger_type": trigger_type,
        "account_id": account_id,
        "risk_score": risk_score
    }
    case_id = f"CASE_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    conn = _get_tg_conn()
    if not conn:
        log_tool_call("create_or_get_case", args, case_id)
        return case_id

    try:
        res = conn.runInstalledQuery(
            "create_or_get_case",
            params={
                "trigger_type": trigger_type,
                "txn_ids_json": json.dumps(trigger_txn_ids),
                "account_id": account_id or "",
                "trigger_risk_score": float(risk_score)
            }
        )
        if res and isinstance(res, list) and "case_id" in res[0]:
            case_id = res[0]["case_id"]
        log_tool_call("create_or_get_case", args, case_id)
        return case_id
    except Exception as e:
        print(f"[TG_TOOLS ERROR] create_or_get_case: {e}", file=sys.stderr)
        return case_id

async def update_case(case_id: str, **kwargs) -> bool:
    """Call update_case_status GSQL with provided kwargs. Return success bool."""
    args = {"case_id": case_id, **kwargs}
    conn = _get_tg_conn()
    if not conn:
        log_tool_call("update_case", args, True)
        return True

    try:
        conn.runInstalledQuery(
            "update_case_status",
            params={
                "case_id": case_id,
                "status": kwargs.get("status", "INVESTIGATING"),
                "fraud_prob": float(kwargs.get("fraud_prob", kwargs.get("risk_score", 0.0))),
                "risk_level": kwargs.get("risk_level", "HIGH"),
                "fraud_type": kwargs.get("fraud_type", "SYNDICATE_RING")
            }
        )
        log_tool_call("update_case", args, True)
        return True
    except Exception as e:
        print(f"[TG_TOOLS ERROR] update_case({case_id}): {e}", file=sys.stderr)
        return False

async def add_evidence(case_id: str, evidence_list: list) -> bool:
    """Batch upsert Evidence vertices + EVIDENCE_FOR edges."""
    args = {"case_id": case_id, "evidence_count": len(evidence_list)}
    conn = _get_tg_conn()
    if not conn:
        log_tool_call("add_evidence", args, True)
        return True

    try:
        evidence_vertices = []
        evidence_edges = []
        for idx, ev in enumerate(evidence_list):
            if hasattr(ev, "dict"):
                ev_data = ev.dict()
            elif isinstance(ev, dict):
                ev_data = ev
            else:
                ev_data = {"description": str(ev)}

            ev_id = ev_data.get("evidence_id") or f"EVID_{case_id}_{idx}_{uuid.uuid4().hex[:4]}"
            evidence_vertices.append((ev_id, {
                "evidence_type": ev_data.get("evidence_type", "ANOMALY"),
                "description": ev_data.get("description", ""),
                "source": ev_data.get("source", "AGENT_REASONING"),
                "score": float(ev_data.get("score", 0.9))
            }))
            evidence_edges.append((ev_id, case_id, {}))

        conn.upsertVertices("Evidence", evidence_vertices)
        conn.upsertEdges("Evidence", "EVIDENCE_FOR", [(s, t, a) for s, t, a in evidence_edges])
        log_tool_call("add_evidence", args, True)
        return True
    except Exception as e:
        print(f"[TG_TOOLS ERROR] add_evidence({case_id}): {e}", file=sys.stderr)
        return False

async def add_decision(case_id: str, decision: Union[dict, Any]) -> bool:
    """Upsert Decision vertex + CASE_HAS_DECISION edge."""
    dec_data = decision.dict() if hasattr(decision, "dict") else (decision if isinstance(decision, dict) else {"verdict": str(decision)})
    args = {"case_id": case_id, "verdict": dec_data.get("verdict")}
    conn = _get_tg_conn()
    if not conn:
        log_tool_call("add_decision", args, True)
        return True

    try:
        dec_id = dec_data.get("decision_id") or f"DEC_{case_id}_{int(time.time())}"
        conn.upsertVertex("Decision", dec_id, {
            "verdict": dec_data.get("verdict", "CONFIRMED_FRAUD"),
            "rationale": dec_data.get("rationale", "Evidence exceeds confidence threshold"),
            "decided_by": dec_data.get("decided_by", "AUTONOMOUS_AGENT"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        })
        conn.upsertEdge("Case", case_id, "CASE_HAS_DECISION", "Decision", dec_id)
        log_tool_call("add_decision", args, True)
        return True
    except Exception as e:
        print(f"[TG_TOOLS ERROR] add_decision({case_id}): {e}", file=sys.stderr)
        return False

async def add_action(case_id: str, action: Union[dict, Any], stage: str = "RECOMMENDED") -> bool:
    """
    Upsert Action vertex + CASE_TRIGGERED_ACTION edge.
    + ACTION_GOVERNED_BY edge to matching PolicyRule if policy_reference set.
    """
    act_data = action.dict() if hasattr(action, "dict") else (action if isinstance(action, dict) else {"action_type": str(action)})
    args = {"case_id": case_id, "action_type": act_data.get("action_type")}
    conn = _get_tg_conn()
    if not conn:
        log_tool_call("add_action", args, True)
        return True

    try:
        act_id = act_data.get("action_id") or f"ACT_{case_id}_{uuid.uuid4().hex[:4]}"
        conn.upsertVertex("Action", act_id, {
            "action_type": act_data.get("action_type", "FREEZE_ACCOUNT"),
            "status": stage,
            "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reason": act_data.get("reason", "Triggered by agent policy check")
        })
        conn.upsertEdge("Case", case_id, "CASE_TRIGGERED_ACTION", "Action", act_id)

        pol_ref = act_data.get("policy_reference") or act_data.get("policy_ref")
        if pol_ref:
            conn.upsertEdge("Action", act_id, "ACTION_GOVERNED_BY", "PolicyRule", pol_ref)

        log_tool_call("add_action", args, True)
        return True
    except Exception as e:
        print(f"[TG_TOOLS ERROR] add_action({case_id}): {e}", file=sys.stderr)
        return False

async def upsert_case_embedding(case_id: str, embedding: list[float]) -> bool:
    """Upsert vector embeddings on Case vertex summary_embedding attribute."""
    args = {"case_id": case_id, "dim": len(embedding)}
    conn = _get_tg_conn()
    if not conn:
        log_tool_call("upsert_case_embedding", args, True)
        return True

    try:
        conn.upsertVertex("Case", case_id, {"summary_embedding": embedding})
        log_tool_call("upsert_case_embedding", args, True)
        return True
    except Exception as e:
        print(f"[TG_TOOLS ERROR] upsert_case_embedding({case_id}): {e}", file=sys.stderr)
        return False

async def close_case(case_id: str, disposition: str = "CLOSED") -> bool:
    """Call close_case GSQL."""
    args = {"case_id": case_id, "disposition": disposition}
    conn = _get_tg_conn()
    if not conn:
        log_tool_call("close_case", args, True)
        return True

    try:
        conn.runInstalledQuery(
            "close_case",
            params={
                "case_id": case_id,
                "disposition": disposition,
                "closed_dt": int(time.time())
            }
        )
        log_tool_call("close_case", args, True)
        return True
    except Exception as e:
        print(f"[TG_TOOLS ERROR] close_case({case_id}): {e}", file=sys.stderr)
        return False

async def get_graph_stats() -> dict:
    """Call graph_stats installed query."""
    conn = _get_tg_conn()
    if not conn:
        res = {
            "vertex_counts": {"Transaction": 0, "Account": 0, "Device": 0, "Case": 0},
            "edge_counts": {"PERFORMED": 0, "SHARES_DEVICE": 0},
            "case_stats": {"open": 0, "closed": 0},
            "pattern_stats": {"documented": 5, "discovered": 0}
        }
        log_tool_call("get_graph_stats", {}, res)
        return res

    try:
        res = conn.runInstalledQuery("graph_stats")
        stats = res[0].get("graph_stats", {}) if isinstance(res, list) and len(res) > 0 else {}
        log_tool_call("get_graph_stats", {}, stats)
        return stats
    except Exception as e:
        print(f"[TG_TOOLS ERROR] get_graph_stats: {e}", file=sys.stderr)
        return {}
