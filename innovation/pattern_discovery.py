"""
Density-Based Unsupervised Pattern Discovery Engine.
Discovers novel, undocumented fraud typologies by clustering confirmed fraud cases
using DBSCAN on 21-dimensional behavioral feature vectors.
"""

import os
import sys
import json
import math
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN

from tools import tg_tools
from agent.llm import LLM_MODEL_FAST

# 21 feature dimensions as defined in PROJECT.md Section 9.2
FEATURE_NAMES: List[str] = [
    "mean_txn_amt", "std_txn_amt", "max_txn_amt",
    "mean_c1", "mean_c2", "mean_c3", "mean_c4", "mean_c5", "mean_c6", "mean_c7",
    "mean_c8", "mean_c9", "mean_c10", "mean_c11", "mean_c12", "mean_c13", "mean_c14",
    "min_d1", "mean_d1",
    "device_type_encoded",  # 0=desktop, 1=mobile, 2=other, -1=null
    "mean_risk_score"
]

PATTERN_DISCOVERY_PROMPT = """You are a Senior Financial Crime Investigator.
Analyze the following newly discovered fraud cluster statistics and discriminating features:
Cluster ID: {cluster_id}
Case Count: {case_count}
Discriminating Features: {discriminating_features}
Cluster Statistics: {cluster_summary}

Identify and describe the fraud typology, mechanism, and behavioral indicators.
Provide a concise title and a 2-3 sentence description explaining why this behavior represents organized fraud.
Output MUST be valid JSON with:
{{
  "name": "<Typology Title, max 50 characters>",
  "description": "<Concise 2-3 sentence description, max 250 characters>"
}}
"""


def build_feature_vector(txns: list, case_risk_score: float = 0.5) -> List[float]:
    """
    Builds a 21-dimensional feature vector for a case from its associated transactions:
    [mean_txn_amt, std_txn_amt, max_txn_amt,
     mean_c1..mean_c14,
     min_d1, mean_d1,
     device_type_encoded,  # 0=desktop, 1=mobile, 2=other, -1=null
     mean_risk_score]
    """
    if not txns:
        return [0.0] * 19 + [-1.0, float(case_risk_score)]

    amounts: List[float] = []
    c_vals: Dict[int, List[float]] = {i: [] for i in range(1, 15)}
    d1_vals: List[float] = []
    device_types: List[float] = []
    risk_scores: List[float] = []

    for t in txns:
        if not isinstance(t, dict):
            continue

        # 1. Transaction Amounts
        amt = float(t.get("amount", 0.0) or 0.0)
        amounts.append(amt)

        # 2. C-Features (c1 to c14)
        for i in range(1, 15):
            c_val = float(t.get(f"c{i}", 0.0) or 0.0)
            c_vals[i].append(c_val)

        # 3. D1 Timings
        d1 = float(t.get("d1", 0.0) or 0.0)
        d1_vals.append(d1)

        # 4. Device Type Encoding
        dev = t.get("device_type", t.get("device_info"))
        if dev is None:
            device_types.append(-1.0)
        elif isinstance(dev, (int, float)):
            device_types.append(float(dev))
        elif isinstance(dev, str):
            dev_lower = dev.lower()
            if any(k in dev_lower for k in ("desktop", "windows", "mac", "pc", "linux")):
                device_types.append(0.0)
            elif any(k in dev_lower for k in ("mobile", "ios", "android", "iphone", "ipad")):
                device_types.append(1.0)
            elif dev_lower.strip():
                device_types.append(2.0)
            else:
                device_types.append(-1.0)
        else:
            device_types.append(-1.0)

        # 5. Risk Scores
        risk = float(t.get("risk_score", case_risk_score) or case_risk_score)
        risk_scores.append(risk)

    if not amounts:
        amounts = [0.0]

    mean_amt = float(np.mean(amounts))
    std_amt = float(np.std(amounts)) if len(amounts) > 1 else 0.0
    max_amt = float(np.max(amounts))

    c_means = [float(np.mean(c_vals[i])) if c_vals[i] else 0.0 for i in range(1, 15)]
    min_d1 = float(np.min(d1_vals)) if d1_vals else 0.0
    mean_d1 = float(np.mean(d1_vals)) if d1_vals else 0.0

    # Device encoding: mode across transactions in case
    encoded_dev = float(max(set(device_types), key=device_types.count)) if device_types else -1.0
    mean_risk = float(np.mean(risk_scores)) if risk_scores else float(case_risk_score)

    feature_vector: List[float] = [
        mean_amt,
        std_amt,
        max_amt,
        *c_means,
        min_d1,
        mean_d1,
        encoded_dev,
        mean_risk
    ]

    return [float(x) for x in feature_vector]


def compute_discriminating_features(
    cluster_features: np.ndarray,
    all_features: np.ndarray,
    feature_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Identifies features where cluster mean deviates > 1.5 std from overall dataset mean.
    Constructs match_criteria dictionary for the candidate pattern.
    """
    if feature_names is None:
        feature_names = FEATURE_NAMES

    cluster_arr = np.asarray(cluster_features, dtype=float)
    all_arr = np.asarray(all_features, dtype=float)

    overall_means = np.mean(all_arr, axis=0)
    overall_stds = np.std(all_arr, axis=0)
    cluster_means = np.mean(cluster_arr, axis=0)
    cluster_stds = np.std(cluster_arr, axis=0)

    discriminating: Dict[str, Dict[str, float]] = {}
    conditions: List[Dict[str, Any]] = []

    for idx, fname in enumerate(feature_names):
        o_mean = float(overall_means[idx])
        o_std = float(overall_stds[idx])
        c_mean = float(cluster_means[idx])
        c_std = float(cluster_stds[idx])

        std_denom = o_std if o_std > 1e-6 else 1.0
        z_score = abs(c_mean - o_mean) / std_denom

        if z_score > 1.5:
            discriminating[fname] = {
                "cluster_mean": round(c_mean, 4),
                "cluster_std": round(c_std, 4),
                "overall_mean": round(o_mean, 4),
                "overall_std": round(o_std, 4),
                "z_score": round(z_score, 2),
            }
            if c_mean > o_mean:
                conditions.append({
                    "feature": fname,
                    "op": ">=",
                    "value": round(c_mean - c_std, 2)
                })
            else:
                conditions.append({
                    "feature": fname,
                    "op": "<=",
                    "value": round(c_mean + c_std, 2)
                })

    match_criteria = {
        "logic": "AND",
        "conditions": conditions
    }

    cluster_stats = {
        fname: {
            "mean": round(float(cluster_means[i]), 4),
            "std": round(float(cluster_stds[i]), 4)
        }
        for i, fname in enumerate(feature_names)
    }

    return {
        "discriminating_features": discriminating,
        "match_criteria": match_criteria,
        "cluster_stats": cluster_stats
    }


def _extract_feature_stat(cluster_stats: dict, feat_key: str) -> Optional[float]:
    """Helper to extract mean value for a feature from cluster statistics."""
    alias_map = {
        "amount": ["mean_txn_amt", "amount", "max_txn_amt"],
        "txn_amt": ["mean_txn_amt", "amount"],
        "mean_txn_amt": ["mean_txn_amt", "amount"],
        "shared_device_accounts": ["device_type_encoded", "shared_device_accounts"],
        "risk_score": ["mean_risk_score", "risk_score"],
        "mean_risk_score": ["mean_risk_score", "risk_score"],
        "d1": ["mean_d1", "min_d1", "d1"],
    }
    candidates = alias_map.get(feat_key, [feat_key])
    for cand in candidates:
        if cand in cluster_stats:
            val = cluster_stats[cand]
            if isinstance(val, dict) and "mean" in val:
                return float(val["mean"])
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


def is_cluster_covered_by_docs(cluster_stats: dict, documented_patterns: list) -> bool:
    """
    Checks if a discovered cluster is covered by existing documented patterns.
    Returns True if > 70% of match conditions match any documented pattern.
    """
    if not documented_patterns:
        return False

    for pat in documented_patterns:
        criteria = pat.get("match_criteria_json") or pat.get("match_criteria") or pat.get("conditions")
        if isinstance(criteria, str):
            try:
                criteria = json.loads(criteria)
            except Exception:
                criteria = {}

        conditions: List[Dict[str, Any]] = []
        if isinstance(criteria, dict):
            conditions = criteria.get("conditions", [])
        elif isinstance(criteria, list):
            conditions = criteria

        if not conditions:
            continue

        matches = 0
        evaluable_count = 0

        for cond in conditions:
            feat = cond.get("feature")
            op = cond.get("op", ">=")
            thresh = cond.get("value", cond.get("threshold"))

            if feat is None or thresh is None:
                continue

            stat_val = _extract_feature_stat(cluster_stats, feat)
            if stat_val is None:
                continue

            evaluable_count += 1
            if op in (">=", "gte") and stat_val >= thresh:
                matches += 1
            elif op in ("<=", "lte") and stat_val <= thresh:
                matches += 1
            elif op in (">", "gt") and stat_val > thresh:
                matches += 1
            elif op in ("<", "lt") and stat_val < thresh:
                matches += 1
            elif op in ("==", "eq") and math.isclose(stat_val, thresh, rel_tol=1e-2):
                matches += 1

        if evaluable_count > 0 and (matches / evaluable_count) > 0.70:
            return True

    return False


async def generate_pattern_description(
    cluster_label: int,
    case_count: int,
    discriminating: Dict[str, Any],
    cluster_stats: Dict[str, Any]
) -> Dict[str, str]:
    """
    Generates a concise pattern title and narrative description using FAST LLM.
    Enforces max 300 tokens and 0.3 temperature.
    """
    top_disc = list(discriminating.keys())[:4]
    disc_summary = ", ".join(f"{k} (z={discriminating[k].get('z_score', 1.5)})" for k in top_disc)
    stats_summary = ", ".join(f"{k}: mean={cluster_stats[k]['mean']}" for k in top_disc if k in cluster_stats)

    ctx = {
        "cluster_id": f"DISC_{cluster_label:03d}",
        "case_count": case_count,
        "discriminating_features": disc_summary or "Anomalous velocity and amount metrics",
        "cluster_summary": stats_summary or "Unusual distribution deviation"
    }

    # High-quality offline fallback
    fallback = {
        "name": f"Discovered Pattern {cluster_label:03d} (High-Entropy Cluster)",
        "description": f"Empirically discovered cluster of {case_count} cases exhibiting high deviation in {', '.join(top_disc[:2]) or 'transaction velocity'}."
    }

    try:
        from agent.llm import call_llm_json
        res = await asyncio.wait_for(
            call_llm_json(PATTERN_DISCOVERY_PROMPT, ctx, model=LLM_MODEL_FAST, max_tokens=300),
            timeout=4.0
        )
        name = res.get("name", fallback["name"])[:60]
        desc = res.get("description", fallback["description"])[:300]
        return {"name": name, "description": desc}
    except Exception as e:
        print(f"[PATTERN LLM NOTE] Fallback used for cluster {cluster_label}: {e}", file=sys.stderr)
        return fallback


async def run_pattern_discovery(
    embedder: Optional[Any] = None,
    cases_override: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Full Pattern Discovery Execution Workflow:
    1. Load all closed cases with CONFIRMED_FRAUD disposition from TigerGraph.
    2. Build 21-dimensional feature vectors per case.
    3. Normalize with StandardScaler.
    4. Cluster via DBSCAN(eps=0.5, min_samples=5).
    5. Check cluster coverage against documented patterns.
    6. For uncovered clusters, generate descriptions and create PatternTemplate vertices (is_documented=FALSE, confidence=0.5).
    """
    print("[START] Starting Unsupervised Pattern Discovery Engine...")
    conn = tg_tools._get_tg_conn()

    cases: List[Dict[str, Any]] = []
    if cases_override is not None:
        cases = cases_override
    elif conn:
        try:
            raw_cases = conn.getVertices("Case")
            for c in raw_cases:
                attrs = c.get("attributes", {})
                disp = str(attrs.get("disposition", "")).upper()
                if "CONFIRMED" in disp or "FRAUD" in disp:
                    cases.append({
                        "case_id": c.get("v_id"),
                        "risk_score": float(attrs.get("risk_score", 0.9)),
                        "disposition": disp,
                        "transactions": []
                    })
            print(f"[DISCOVERY] Retrieved {len(cases)} confirmed fraud cases from TigerGraph.")
        except Exception as e:
            print(f"[DISCOVERY WARNING] Failed querying Case vertices: {e}", file=sys.stderr)

    # Constraint Check: ≥ 50 confirmed fraud cases required
    if len(cases) < 50:
        print(
            f"[WARNING] Only {len(cases)} confirmed fraud cases found (< 50 required). "
            "Skipping DBSCAN pattern discovery to avoid spurious typologies."
        )
        return {
            "cases_count": len(cases),
            "clusters_found": 0,
            "covered_by_docs": 0,
            "new_candidates": 0,
            "discovered_patterns": []
        }

    # Retrieve transactions and build feature vectors
    feature_matrix: List[List[float]] = []
    valid_cases: List[Dict[str, Any]] = []

    for c in cases:
        txns = c.get("transactions", [])
        if not txns and conn:
            try:
                # Query transactions via edges or fallback
                txn_edges = conn.getEdges("Case", c["case_id"], "CASE_TARGETS_TXN")
                txn_ids = [e.get("to_id") for e in txn_edges if e.get("to_id")]
                for tid in txn_ids[:10]:
                    t_vert = conn.getVerticesById("Transaction", tid)
                    if t_vert:
                        txns.append(t_vert[0].get("attributes", {}))
            except Exception:
                pass

        vec = build_feature_vector(txns, case_risk_score=c.get("risk_score", 0.85))
        feature_matrix.append(vec)
        valid_cases.append(c)

    X = np.array(feature_matrix, dtype=float)

    # Standardize features
    scaler = StandardScaler()
    X_norm = scaler.fit_transform(X)

    # DBSCAN Clustering (eps=0.5, min_samples=5)
    dbscan = DBSCAN(eps=0.5, min_samples=5)
    labels = dbscan.fit_predict(X_norm)

    unique_labels = set(labels)
    clusters = [l for l in unique_labels if l != -1]
    noise_count = int(np.sum(labels == -1))

    print(f"[DBSCAN] Total cases: {len(X)} | Clusters found: {len(clusters)} | Noise points: {noise_count}")

    # Retrieve documented patterns
    documented_patterns: List[Dict[str, Any]] = []
    if conn:
        try:
            raw_pats = conn.getVertices("PatternTemplate")
            for p in raw_pats:
                attrs = p.get("attributes", {})
                if attrs.get("is_documented", True):
                    documented_patterns.append(attrs)
        except Exception as e:
            print(f"[NOTE] Could not fetch documented patterns from TG: {e}", file=sys.stderr)

    covered_count = 0
    new_candidates = 0
    discovered_list: List[Dict[str, Any]] = []

    for cluster_label in sorted(clusters):
        cluster_indices = np.where(labels == cluster_label)[0]
        cluster_X = X[cluster_indices]
        case_count = len(cluster_indices)

        # Compute cluster statistics and discriminating features
        disc_info = compute_discriminating_features(cluster_X, X, FEATURE_NAMES)
        cluster_stats = disc_info["cluster_stats"]
        discriminating = disc_info["discriminating_features"]
        match_criteria = disc_info["match_criteria"]

        # Check coverage
        if is_cluster_covered_by_docs(cluster_stats, documented_patterns):
            covered_count += 1
            print(f"  Cluster {cluster_label}: COVERED by existing documented patterns ({case_count} cases)")
            continue

        # Novel candidate typology discovered
        new_candidates += 1
        pattern_id = f"DISC_{cluster_label:03d}"
        print(f"  Cluster {cluster_label}: DISCOVERED NOVEL PATTERN ({case_count} cases) -> {pattern_id}")

        desc_data = await generate_pattern_description(
            cluster_label=cluster_label,
            case_count=case_count,
            discriminating=discriminating,
            cluster_stats=cluster_stats
        )

        pat_name = desc_data["name"]
        pat_desc = desc_data["description"]

        candidate_obj = {
            "pattern_id": pattern_id,
            "name": pat_name,
            "description": pat_desc,
            "is_documented": False,
            "confidence": 0.5,
            "match_criteria_json": json.dumps(match_criteria),
            "cluster_label": int(cluster_label),
            "case_count": int(case_count),
            "discriminating_features": discriminating
        }

        # Embed description if embedder is provided
        if embedder:
            try:
                emb = embedder.embed(pat_desc)
                candidate_obj["desc_embedding"] = emb
            except Exception as emb_err:
                print(f"[NOTE] Embedder failed on pattern: {emb_err}")

        # Upsert PatternTemplate vertex in TigerGraph (preserve is_documented=False)
        if conn:
            try:
                vert_data = {
                    "name": pat_name,
                    "description": pat_desc,
                    "is_documented": False,
                    "confidence": 0.5,
                    "match_criteria_json": json.dumps(match_criteria)
                }
                if "desc_embedding" in candidate_obj:
                    vert_data["desc_embedding"] = candidate_obj["desc_embedding"]

                conn.upsertVertex("PatternTemplate", pattern_id, vert_data)
                print(f"  [TG UPSERT] Created PatternTemplate vertex: {pattern_id}")
            except Exception as up_err:
                print(f"[TG UPSERT ERROR] Could not save pattern {pattern_id}: {up_err}", file=sys.stderr)

        discovered_list.append(candidate_obj)

    print(f"\n[DISCOVERY SUMMARY] Total clusters: {len(clusters)} | Covered: {covered_count} | New Candidates: {new_candidates}")
    return {
        "cases_count": len(cases),
        "clusters_found": len(clusters),
        "noise_points": noise_count,
        "covered_by_docs": covered_count,
        "new_candidates": new_candidates,
        "discovered_patterns": discovered_list
    }
