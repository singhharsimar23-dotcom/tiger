import os
import sys
import time
from typing import List, Dict, Any, Optional

from agent.state import (
    InvestigationState,
    CaseStatus,
    RiskLevel,
    FraudType,
    ApprovalTier,
    ActionType,
    EvidenceType,
    Evidence,
    Decision,
    RecommendedAction,
)
from agent.prompts import (
    EVIDENCE_SYNTHESIS_PROMPT,
    RISK_ASSESSMENT_PROMPT,
    ACTION_SELECTION_PROMPT,
    CASE_SUMMARY_PROMPT,
)
from agent.llm import call_llm_json
from tools import tg_tools
from retrieval.embedder import Embedder
from retrieval.graphrag import GraphRAGRetriever

# Module level constants and singleton embedder
MAX_ITERATIONS = 3
embedder = Embedder()
retriever = GraphRAGRetriever(embedder)

# Minimum Description Length (MDL) Evidence Sufficiency Gate
from innovation.mdl_gate import (
    compute_sufficiency,
    interpret_sufficiency,
    EVIDENCE_COST,
    MDL_THRESHOLD,
)


def stub_seed(state: InvestigationState) -> InvestigationState:
    """Seeds default investigation fields if empty (Section 2.6)."""
    if not state.trigger_txn_ids:
        state.trigger_txn_ids = ["T_2987000"]
    if not state.trigger_account_id:
        state.trigger_account_id = "ACC_13926_0_315"
    if not state.case_id:
        state.case_id = f"CASE_{int(time.time())}"
    return state

def _log_node_action(state: InvestigationState, node_name: str, action_desc: str):
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    state.tool_calls.append(f"{timestamp}: {node_name}: {action_desc}")
    state.decision_log.append({"stage": node_name, "summary": action_desc})

# =========================================================================
# 9 LANGGRAPH NODES
# =========================================================================

async def trigger_node(state: InvestigationState) -> InvestigationState:
    """
    Node 1: Initializes investigation case and registers alert trigger in TigerGraph.
    """
    state = stub_seed(state)
    case_id = await tg_tools.create_or_get_case(
        trigger_txn_ids=state.trigger_txn_ids,
        trigger_type=state.trigger_type,
        account_id=state.trigger_account_id,
        risk_score=state.trigger_risk_score
    )
    state.case_id = case_id
    state.status = CaseStatus.INVESTIGATING
    _log_node_action(state, "trigger_node", f"Created investigation {case_id} for trigger {state.trigger_type}")
    return state

async def investigate_node(state: InvestigationState) -> InvestigationState:
    """
    Node 2: Traverses graph neighborhood, shared devices, and fund flow pathways.
    """
    all_accounts = set()
    all_devices = set()
    all_ips = set()

    for txn_id in state.trigger_txn_ids:
        hood = await tg_tools.get_txn_neighborhood(txn_id, depth=2)
        state.subgraph[txn_id] = hood
        for acc in hood.get("accounts", []):
            all_accounts.add(acc.get("v_id") or acc.get("account_id"))
        for dev in hood.get("devices", []):
            all_devices.add(dev.get("v_id") or dev.get("device_id"))
        for ip in hood.get("ip_clusters", []):
            all_ips.add(ip.get("v_id") or ip.get("ip_cluster_id"))

    if state.trigger_account_id:
        all_accounts.add(state.trigger_account_id)
        shared = await tg_tools.get_shared_identifiers(state.trigger_account_id)
        state.shared_identifiers = shared
        flow = await tg_tools.get_money_flow(state.trigger_account_id, depth=2)
        state.money_flow = flow

    state.accounts = [a for a in all_accounts if a]
    state.devices = [d for d in all_devices if d]
    state.ip_clusters = [i for i in all_ips if i]

    _log_node_action(
        state,
        "investigate_node",
        f"Discovered {len(state.accounts)} accounts, {len(state.devices)} devices, {len(state.ip_clusters)} IP clusters"
    )
    return state

async def gather_evidence_node(state: InvestigationState) -> InvestigationState:
    """
    Node 3: Evaluates typologies, performs GraphRAG hybrid retrieval, and synthesizes evidence.
    """
    # 1. Pattern Matching
    for txn_id in state.trigger_txn_ids:
        matches = await tg_tools.get_matching_patterns(txn_id)
        state.matched_patterns.extend(matches)

    # 2. GraphRAG Prior Case Hybrid Retrieval
    similar = await retriever.get_similar_prior_cases(
        case_id=state.case_id,
        query_accounts=state.accounts,
        query_text=f"Fraud syndicate shared devices {state.devices} accounts {state.accounts}",
        top_k=3
    )
    state.similar_cases = similar

    # 3. LLM Evidence Synthesis
    ctx = {
        "case_id": state.case_id,
        "trigger_type": state.trigger_type,
        "trigger_txns": ", ".join(state.trigger_txn_ids),
        "account_id": state.trigger_account_id or "N/A",
        "accounts": str(state.accounts[:10]),
        "devices": str(state.devices[:10]),
        "ip_clusters": str(state.ip_clusters[:5]),
        "shared_identifiers": str(state.shared_identifiers[:5]),
        "money_flow": str(state.money_flow.get("chains", [])[:5]),
        "matched_patterns": str(state.matched_patterns[:5]),
        "similar_cases": str(state.similar_cases[:3])
    }
    llm_res = await call_llm_json(EVIDENCE_SYNTHESIS_PROMPT, ctx)

    new_evidences = []
    for idx, ev in enumerate(llm_res.get("evidences", [])):
        ev_obj = Evidence(
            evidence_id=f"EVID_{state.case_id}_{len(state.evidence_list) + idx}",
            evidence_type=EvidenceType(ev.get("evidence_type", "GRAPH_NEIGHBORHOOD")),
            description=ev.get("description", "Graph anomaly"),
            score=float(ev.get("score", 0.8)),
            source="LLM_GRAPH_SYNTHESIS"
        )
        new_evidences.append(ev_obj)

    state.evidence_list.extend(new_evidences)
    await tg_tools.add_evidence(state.case_id, [e.dict() for e in new_evidences])

    _log_node_action(state, "gather_evidence_node", f"Synthesized {len(new_evidences)} new evidence items")
    return state

async def assess_uncertainty_node(state: InvestigationState) -> InvestigationState:
    """
    Node 4: Evaluates epistemic uncertainty and risk level via Minimum Description Length (MDL) gate.
    """
    state.iteration_count += 1
    ev_summary = "\n".join(f"- [{e.evidence_type}] {e.description} (Score: {e.score})" for e in state.evidence_list)
    
    ctx = {
        "case_id": state.case_id,
        "trigger_risk_score": state.trigger_risk_score,
        "iteration_count": state.iteration_count,
        "evidence_count": len(state.evidence_list),
        "evidence_summary": ev_summary,
        "matched_patterns": str(state.matched_patterns)
    }
    risk_res = await call_llm_json(RISK_ASSESSMENT_PROMPT, ctx)

    fraud_prob = float(risk_res.get("fraud_probability", 0.85))
    unc_score = float(risk_res.get("uncertainty_score", 0.2))

    # Compute current decision
    state.current_decision = Decision(
        decision_id=f"DEC_{state.case_id}_{state.iteration_count}",
        verdict="CONFIRMED_FRAUD" if fraud_prob >= 0.7 else "SUSPICIOUS",
        fraud_type=FraudType(risk_res.get("fraud_type", "DEVICE_RING")),
        risk_level=RiskLevel(risk_res.get("risk_level", "HIGH")),
        confidence=float(risk_res.get("confidence", 0.85)),
        fraud_probability=fraud_prob,
        rationale=risk_res.get("rationale", "Evidence exceeds confidence threshold"),
        decided_by="AUTONOMOUS_INVESTIGATION_AGENT",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    state.uncertainty_score = unc_score

    # Compute information-theoretic evidence sufficiency
    gathered_cost = sum(EVIDENCE_COST.get(e.evidence_type, 1.0) for e in state.evidence_list)
    state.evidence_sufficiency_score = compute_sufficiency(
        state.current_decision.fraud_probability, gathered_cost, state.iteration_count
    )
    mdl_interpretation = interpret_sufficiency(
        state.evidence_sufficiency_score, state.iteration_count
    )

    # Append MDL interpretation to decision log
    state.decision_log.append({
        "stage": "mdl_gate",
        "summary": mdl_interpretation["interpretation"],
        "details": mdl_interpretation
    })

    _log_node_action(
        state,
        "assess_uncertainty_node",
        f"Iteration {state.iteration_count}: MDL Score={state.evidence_sufficiency_score:.3f} -> {mdl_interpretation['recommended_action']}"
    )
    return state

def should_gather_more(state: InvestigationState) -> str:
    """
    Conditional Edge: Routes to gather_more_evidence if evidence sufficiency score >= MDL_THRESHOLD
    and iteration count < MAX_ITERATIONS.
    """
    if state.iteration_count < MAX_ITERATIONS and state.evidence_sufficiency_score >= MDL_THRESHOLD:
        return "gather_more"
    return "proceed"


async def gather_more_evidence_node(state: InvestigationState) -> InvestigationState:
    """
    Node 5: Deeper graph traversal expanding 3-hop connections across discovered entities.
    """
    from innovation.mdl_gate import compute_sufficiency, interpret_sufficiency

    # Deepen exploration on discovered accounts
    additional_txns = []
    for acc in state.accounts[:3]:
        money_flow = await tg_tools.get_money_flow(acc, depth=3)
        for chain in money_flow.get("chains", []):
            if chain.get("is_ring"):
                ev_obj = Evidence(
                    evidence_id=f"EVID_RING_{state.case_id}_{len(state.evidence_list)}",
                    evidence_type=EvidenceType.GRAPH_NEIGHBORHOOD,
                    description=f"Circular money flow detected involving account {acc}",
                    score=0.95,
                    source="DEEP_GRAPH_EXPANSION"
                )
                state.evidence_list.append(ev_obj)

    _log_node_action(state, "gather_more_evidence_node", f"Deepened graph search to 3 hops (Iter {state.iteration_count})")
    return state

async def action_node(state: InvestigationState) -> InvestigationState:
    """
    Node 6: Maps case risks to institutional compliance policy rules and prescribes remediation actions.
    """
    risk_score = state.decision.confidence if state.decision else 0.8
    txn_amt = 5000.0
    rules = await tg_tools.get_policy_rules(txn_amt=txn_amt, risk_score=risk_score)
    state.matched_policies = rules

    ctx = {
        "case_id": state.case_id,
        "risk_level": state.decision.risk_level.value if state.decision else "HIGH",
        "fraud_type": state.decision.fraud_type.value if state.decision else "DEVICE_RING",
        "confidence": risk_score,
        "policy_rules": str(rules)
    }
    action_res = await call_llm_json(ACTION_SELECTION_PROMPT, ctx)

    rec_actions = []
    for idx, act in enumerate(action_res.get("recommended_actions", [])):
        action_obj = RecommendedAction(
            action_id=f"ACT_{state.case_id}_{idx}",
            action_type=ActionType(act.get("action_type", "FLAG_FOR_REVIEW")),
            approval_tier=ApprovalTier(act.get("approval_tier", "ANALYST_TIER_1")),
            reason=act.get("reason", "Institutional risk threshold reached"),
            policy_reference=act.get("policy_reference", "RULE_BLOCK_ACC_002")
        )
        rec_actions.append(action_obj)
        await tg_tools.add_action(state.case_id, action_obj.dict(), stage="RECOMMENDED")

    state.recommended_actions = rec_actions
    if state.decision:
        await tg_tools.add_decision(state.case_id, state.decision.dict())

    _log_node_action(state, "action_node", f"Selected {len(rec_actions)} policy actions")
    return state

async def explain_node(state: InvestigationState) -> InvestigationState:
    """
    Node 7: Compiles comprehensive compliance dossier narrative and audit summary.
    """
    ev_summary = "\n".join(f"- {e.evidence_type}: {e.description}" for e in state.evidence_list)
    act_summary = "\n".join(f"- {a.action_type} (Tier: {a.approval_tier}): {a.reason}" for a in state.recommended_actions)
    case_summary_text = "\n".join(f"- {c.get('case_id')}: {c.get('summary_excerpt')}" for c in state.similar_cases)

    ctx = {
        "case_id": state.case_id,
        "account_id": state.trigger_account_id or "N/A",
        "verdict": state.decision.verdict if state.decision else "CONFIRMED_FRAUD",
        "fraud_type": state.decision.fraud_type.value if state.decision else "DEVICE_RING",
        "risk_level": state.decision.risk_level.value if state.decision else "HIGH",
        "confidence": state.decision.confidence if state.decision else 0.9,
        "evidence_summary": ev_summary,
        "actions_summary": act_summary,
        "similar_cases_summary": case_summary_text
    }
    summary_res = await call_llm_json(CASE_SUMMARY_PROMPT, ctx)
    state.case_summary = summary_res.get("case_summary", "Investigation concluded.")

    await tg_tools.update_case(
        state.case_id,
        status="RESOLVED",
        fraud_prob=state.decision.confidence if state.decision else 0.9,
        risk_level=state.decision.risk_level.value if state.decision else "HIGH",
        fraud_type=state.decision.fraud_type.value if state.decision else "DEVICE_RING"
    )

    _log_node_action(state, "explain_node", "Generated audit-ready compliance dossier")
    return state

async def memory_node(state: InvestigationState) -> InvestigationState:
    """
    Node 8: Indexes resolved case summary into vector storage for future GraphRAG precedent retrieval.
    """
    if state.case_summary and state.decision:
        emb = embedder.embed_case(
            state.case_summary,
            state.decision.fraud_type.value,
            state.decision.risk_level.value
        )
        await tg_tools.upsert_case_embedding(state.case_id, emb)

    await tg_tools.close_case(state.case_id, disposition="CONFIRMED_FRAUD")
    state.status = CaseStatus.CLOSED

    _log_node_action(state, "memory_node", f"Archived case {state.case_id} into vector memory and closed")
    return state
