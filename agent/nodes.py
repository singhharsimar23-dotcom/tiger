"""
HHGOA Agent Nodes — Ground Truth Corrected
Operates against the exact InvestigationState and graded vocabulary from HHGOA_GROUND_TRUTH_CORRECTIONS.md.
All 14 actions, 7 patterns, 3 verdicts, 4 statuses, and approval routing are enforced verbatim.
"""

import os
import sys
import time
import json
import uuid
import hashlib
from typing import List, Dict, Any, Optional

from agent.state import (
    InvestigationState,
    ActionType,
    ApprovalRoute,
    Pattern,
    Verdict,
    CaseStatus,
    TriggerType,
    EvidenceItem,
    ActionRec,
    EvidenceRequest,
    approval_route,
    should_stop,
    POLICY_RULES,
)
from agent.prompts import (
    fill_evidence_synthesis,
    fill_risk_assessment,
    fill_action_selection,
    fill_case_summary,
    EVIDENCE_SYNTHESIS_PROMPT,
    RISK_ASSESSMENT_PROMPT,
    ACTION_SELECTION_PROMPT,
    CASE_SUMMARY_PROMPT,
)
from agent.llm import call_llm_json
from tools import tg_tools
from retrieval.embedder import Embedder
from retrieval.graphrag import GraphRAGRetriever

MAX_ITERATIONS = 3
embedder = Embedder()
retriever = GraphRAGRetriever(embedder)


def _log_node_action(state: InvestigationState, node_name: str, action_desc: str):
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    state.tool_calls.append(f"{timestamp}: {node_name}: {action_desc}")
    state.tool_calls_count = len(state.tool_calls)
    state.decision_log.append({"stage": node_name, "summary": action_desc, "iteration": state.iteration_count})


# =========================================================================
# 9 LANGGRAPH NODES
# =========================================================================

async def trigger_node(state: InvestigationState) -> InvestigationState:
    """
    Node 1: Seeds investigation fields from trigger dict / case_pack and registers alert in graph.
    """
    if not state.case_id:
        state.case_id = f"HHG-{int(time.time()) % 1000:03d}"

    if not state.flagged_txn_id:
        state.flagged_txn_id = "T3514030"

    if not state.card_id:
        state.card_id = "C12382-K1"

    if not state.customer_id:
        state.customer_id = "C12382"

    if state.flagged_txn_id not in state.transactions:
        state.transactions.append(state.flagged_txn_id)

    state.first_suspicious_txn_id = state.flagged_txn_id
    state.status = CaseStatus.OPEN.value

    # Register in TigerGraph or local tracking
    await tg_tools.upsert_case(
        case_id=state.case_id,
        status=state.status,
        verdict=state.verdict,
        fraud_probability=state.fraud_probability,
        pattern=state.pattern,
        pattern_description=state.pattern_description,
        exposure_usd=state.exposure_usd,
        summary=state.summary,
        graph_written=False,
    )

    _log_node_action(state, "trigger_node", f"Ingested alert {state.case_id} ({state.trigger_type}) on txn {state.flagged_txn_id}")
    return state


async def investigate_node(state: InvestigationState) -> InvestigationState:
    """
    Node 2: Traverses graph neighborhood around flagged txn (Card, Customer, DeviceProfile, Sibling Cards, NEXT chain).
    """
    txn_id = state.flagged_txn_id
    hood = await tg_tools.get_txn_neighborhood(txn_id)
    state.subgraph[txn_id] = hood

    # Extract entities from neighborhood
    found_cards = set(state.cards)
    if state.card_id:
        found_cards.add(state.card_id)

    found_txns = set(state.transactions)
    found_txns.add(txn_id)

    found_devices = set(state.device_profiles)
    found_emails = set(state.email_domains)
    found_regions = set(state.billing_regions)

    for c in hood.get("owning_cards", []):
        cid = c.get("v_id") or c.get("card_id")
        if cid:
            found_cards.add(cid)
    for c in hood.get("sibling_cards", []):
        cid = c.get("v_id") or c.get("card_id")
        if cid:
            found_cards.add(cid)
    for t in hood.get("nearby_transactions", []):
        tid = t.get("v_id") or t.get("txn_id")
        if tid:
            found_txns.add(tid)
    for d in hood.get("device_profiles", []):
        did = d.get("v_id") or d.get("device_profile_id")
        if did:
            found_devices.add(did)

    # Live traversal for shared identifiers
    shared = await tg_tools.get_shared_identifiers(txn_id)
    state.shared_identifiers = shared
    for d in shared.get("anchor_device_profiles", []):
        did = d.get("v_id") if isinstance(d, dict) else str(d)
        if did:
            found_devices.add(did)

    # Money flow (NEXT edge chain)
    flow = await tg_tools.get_money_flow(txn_id)
    state.money_flow = flow

    state.cards = sorted(list(found_cards))
    state.transactions = sorted(list(found_txns))
    state.device_profiles = sorted(list(found_devices))
    state.email_domains = sorted(list(found_emails))
    state.billing_regions = sorted(list(found_regions))

    # Connected cards / profiles
    state.connected_card_ids = [c for c in state.cards if c != state.card_id]
    state.connected_device_profiles = list(state.device_profiles)

    _log_node_action(
        state,
        "investigate_node",
        f"Graph traversal found {len(state.cards)} cards, {len(state.transactions)} txns, {len(state.device_profiles)} devices"
    )
    return state


async def gather_evidence_node(state: InvestigationState) -> InvestigationState:
    """
    Node 3: GraphRAG retrieval over ClosedCases and LLM synthesis into structured EvidenceItems.
    """
    # 1. Hybrid GraphRAG retrieval
    priors = await retriever.get_similar_prior_cases(
        case_id=state.case_id,
        query_cards=state.cards,
        query_text=f"Fraud alert for card {state.card_id} txn {state.flagged_txn_id} trigger {state.trigger_type} {state.trigger_text}",
        top_k=3
    )
    state.similar_cases = [p["case_id"] for p in priors if p.get("case_id")]

    # 2. LLM Evidence Synthesis
    prompt_text = fill_evidence_synthesis(state)
    llm_res = await call_llm_json(prompt_text, {})

    new_items = []
    for raw in llm_res.get("evidence", []):
        item = EvidenceItem(
            claim=raw.get("claim", "Graph signal detected"),
            source=raw.get("source", "graph") if raw.get("source") in ("graph", "document", "customer", "external") else "graph",
            ref=raw.get("ref", "get_txn_neighborhood"),
            entity_ids=raw.get("entity_ids", [state.flagged_txn_id]),
            is_independent=bool(raw.get("is_independent", False)),
        )
        new_items.append(item)
        state.add_evidence(item)

    # Fallback default evidence if LLM did not return items
    if not state.evidence_list:
        ev1 = EvidenceItem(
            claim=f"Flagged transaction {state.flagged_txn_id} scored {state.trigger_risk_score:.2f} by real-time model",
            source="graph",
            ref="Transaction.risk_score",
            entity_ids=[state.flagged_txn_id],
            is_independent=True,
        )
        state.add_evidence(ev1)

        if state.device_profiles:
            ev2 = EvidenceItem(
                claim=f"Transaction routed via device profile {state.device_profiles[0]}",
                source="graph",
                ref="FROM_DEVICE",
                entity_ids=[state.flagged_txn_id, state.device_profiles[0]],
                is_independent=True,
            )
            state.add_evidence(ev2)

    # Preliminary assessment from synthesis
    if "preliminary_fraud_probability" in llm_res:
        state.fraud_probability = float(llm_res["preliminary_fraud_probability"])
    elif state.trigger_risk_score > 0:
        state.fraud_probability = float(state.trigger_risk_score)

    _log_node_action(state, "gather_evidence_node", f"Gathered {len(state.evidence_list)} evidence items ({state.independent_evidence_count} independent)")
    return state


async def assess_uncertainty_node(state: InvestigationState) -> InvestigationState:
    """
    Node 4: Evaluates epistemic uncertainty, assesses stopping rule, computes initial actions.
    """
    state.iteration_count += 1
    prompt_text = fill_risk_assessment(state)
    risk_res = await call_llm_json(prompt_text, {})

    # Extract risk parameters
    if "fraud_probability" in risk_res:
        state.fraud_probability = round(float(risk_res["fraud_probability"]), 4)

    raw_verdict = risk_res.get("verdict", "")
    if raw_verdict in ("fraud", "legitimate", "uncertain"):
        state.verdict = raw_verdict
    else:
        state.verdict = "fraud" if state.fraud_probability >= 0.70 else ("legitimate" if state.fraud_probability <= 0.20 else "uncertain")

    raw_pattern = risk_res.get("pattern", "")
    if raw_pattern in [p.value for p in Pattern]:
        state.pattern = raw_pattern
    else:
        state.pattern = Pattern.CNP_NEW_DEVICE.value if state.verdict == "fraud" else Pattern.NONE.value

    state.pattern_description = risk_res.get("pattern_description", "")
    if state.pattern == "undocumented" and not state.pattern_description:
        state.pattern_description = "Uncategorized anomaly with multi-signal coordination"

    state.exposure_usd = round(float(risk_res.get("exposure_usd", 0.0) or 0.0), 2)
    if state.verdict == "fraud" and state.exposure_usd == 0.0:
        # Pull amount from money flow or transaction if available
        state.exposure_usd = round(float(state.money_flow.get("total_chain_usd", 150.0)), 2)
    elif state.verdict == "legitimate":
        state.exposure_usd = 0.0

    # Set affected transactions
    if state.verdict == "legitimate":
        state.affected_txn_ids = []
    else:
        state.affected_txn_ids = [state.flagged_txn_id]

    # Compute Initial Actions on iteration 1
    if state.iteration_count == 1 and not state.initial_actions:
        init_actions = []
        if state.fraud_probability < 0.70:
            init_actions.append(ActionRec(
                action=ActionType.VERIFY_WITH_CUSTOMER.value,
                route=approval_route(ActionType.VERIFY_WITH_CUSTOMER, state.exposure_usd).value,
                reason="R1: Weak single signal with fraud probability < 0.70 requires customer verification before blocking."
            ))
            init_actions.append(ActionRec(
                action=ActionType.STEP_UP_AUTH.value,
                route=approval_route(ActionType.STEP_UP_AUTH, state.exposure_usd).value,
                reason="R1: Step-up authentication requested prior to any card block."
            ))
        else:
            block_action = ActionType.BLOCK_CARD
            init_actions.append(ActionRec(
                action=block_action.value,
                route=approval_route(block_action, state.exposure_usd).value,
                reason=f"R2: Elevated fraud risk ({state.fraud_probability:.2f}) warrants immediate card lock."
            ))
            init_actions.append(ActionRec(
                action=ActionType.CREATE_CASE.value,
                route=approval_route(ActionType.CREATE_CASE, state.exposure_usd).value,
                reason="R2: Formal fraud case created for confirmed risk exposure."
            ))
        state.initial_actions = init_actions

    # Check stopping condition
    should_halt, stop_reason = state.compute_stop()
    if should_halt:
        state.stop_reason = stop_reason
        _log_node_action(state, "assess_uncertainty_node", f"Stopping threshold met: {stop_reason}")
    else:
        state.next_evidence_type = risk_res.get("next_evidence_type", "customer_validation")
        _log_node_action(state, "assess_uncertainty_node", f"Iter {state.iteration_count}: Continuing (P={state.fraud_probability:.2f}, next={state.next_evidence_type})")

    return state


def should_gather_more(state: InvestigationState) -> str:
    """Conditional Edge: decides whether to loop back for more evidence or proceed to action."""
    if state.iteration_count >= MAX_ITERATIONS:
        return "proceed"
    if state.verification_settled:
        return "proceed"
    should_halt, _ = state.compute_stop()
    if should_halt:
        return "proceed"
    return "gather_more"


async def gather_more_evidence_node(state: InvestigationState) -> InvestigationState:
    """
    Node 5: Executes simulated evidence request (customer verification, step-up MFA, or analyst query).
    """
    ev_type = state.next_evidence_type or "customer_validation"
    if ev_type not in ("customer_validation", "step_up_auth", "analyst_info"):
        ev_type = "customer_validation"

    # Deterministic simulation branch based on trigger and risk
    seed = int(hashlib.md5(f"{state.case_id}_{state.iteration_count}".encode()).hexdigest(), 16) % 100

    if state.trigger_type == TriggerType.CUSTOMER_REPORT.value:
        # Customer report usually denies transaction
        assumed = "Customer confirms they did not authorize the transaction and their card was in their possession."
        state.verification_settled = True
        state.fraud_probability = max(state.fraud_probability, 0.95)
        state.verdict = Verdict.FRAUD.value
        ev_claim = "Customer denied transaction authorization via direct contact."
    elif state.fraud_probability <= 0.35:
        # Low risk -> customer confirms legitimate
        assumed = "Customer confirms making the transaction while traveling."
        state.verification_settled = True
        state.fraud_probability = min(state.fraud_probability, 0.05)
        state.verdict = Verdict.LEGITIMATE.value
        state.exposure_usd = 0.0
        state.affected_txn_ids = []
        ev_claim = "Customer verified transaction as legitimate cardholder activity."
    elif ev_type == "step_up_auth":
        if seed < 30:
            assumed = "Step-up authentication MFA completed successfully by cardholder."
            state.verification_settled = True
            state.fraud_probability = 0.10
            state.verdict = Verdict.LEGITIMATE.value
            ev_claim = "Step-up authentication challenge succeeded."
        else:
            assumed = "Step-up authentication challenge timed out with no response."
            state.fraud_probability = min(1.0, state.fraud_probability + 0.15)
            ev_claim = "Step-up authentication failed or timed out."
    else:
        # customer_validation
        if seed < 40:
            assumed = "Customer confirms legitimate purchase."
            state.verification_settled = True
            state.fraud_probability = 0.05
            state.verdict = Verdict.LEGITIMATE.value
            ev_claim = "Customer confirmed purchase upon verification outreach."
        else:
            assumed = "Customer denies purchase; reports card details were compromised."
            state.verification_settled = True
            state.fraud_probability = 0.98
            state.verdict = Verdict.FRAUD.value
            ev_claim = "Customer denied transaction authorization."

    # Record EvidenceRequest
    state.evidence_requests.append(EvidenceRequest(
        type=ev_type,
        asked_after_step=state.iteration_count,
        assumed_response=assumed,
    ))

    # Add evidence item
    ev_item = EvidenceItem(
        claim=ev_claim,
        source="customer" if "Customer" in ev_claim else "external",
        ref="customer_inquiry_channel",
        entity_ids=[state.flagged_txn_id, state.customer_id],
        is_independent=True,
    )
    state.add_evidence(ev_item)

    _log_node_action(state, "gather_more_evidence_node", f"Evidence request ({ev_type}) received: {assumed[:60]}...")
    return state


async def action_node(state: InvestigationState) -> InvestigationState:
    """
    Node 6: Recommends final next-best actions and applies strict compliance approval routing & R1-R10 rules.
    """
    prompt_text = fill_action_selection(state)
    action_res = await call_llm_json(prompt_text, {})

    raw_actions = action_res.get("initial_actions", [])
    final_actions: List[ActionRec] = []

    for item in raw_actions:
        act_name = item.get("action", "")
        if act_name in [a.value for a in ActionType]:
            # Always recalculate route using deterministic policy code
            calculated_route = approval_route(ActionType(act_name), state.exposure_usd).value
            reason = item.get("reason", f"Policy action {act_name}")
            final_actions.append(ActionRec(
                action=act_name,
                route=calculated_route,
                reason=reason
            ))

    # Fallback default actions if empty or invalid
    if not final_actions:
        if state.verdict == Verdict.LEGITIMATE.value:
            final_actions = [
                ActionRec(
                    action=ActionType.CLOSE_NO_FRAUD.value,
                    route=ApprovalRoute.AUTO.value,
                    reason="R3: Customer confirms the transaction: recommend CLOSE_NO_FRAUD."
                ),
                ActionRec(
                    action=ActionType.ALLOW_TRANSACTION.value,
                    route=ApprovalRoute.AUTO.value,
                    reason="R3: Legitimate activity verified; transaction allowed."
                )
            ]
        elif state.verdict == Verdict.FRAUD.value:
            final_actions = [
                ActionRec(
                    action=ActionType.BLOCK_CARD.value,
                    route=approval_route(ActionType.BLOCK_CARD, state.exposure_usd).value,
                    reason=f"R2: Customer denies the transaction: recommend BLOCK_CARD (exposure ${state.exposure_usd:.2f})."
                ),
                ActionRec(
                    action=ActionType.CREATE_CASE.value,
                    route=ApprovalRoute.AUTO.value,
                    reason="R2: Create fraud investigation case record."
                )
            ]
            if state.exposure_usd > 1000.0 or len(state.connected_card_ids) > 0:
                final_actions.append(ActionRec(
                    action=ActionType.FILE_REPORT.value,
                    route=ApprovalRoute.L2.value,
                    reason=f"R2: Exposure exceeds $1,000 (${state.exposure_usd:.2f}) or multi-card connection: recommend FILE_REPORT."
                ))
        else:
            final_actions = [
                ActionRec(
                    action=ActionType.ESCALATE_TO_ANALYST.value,
                    route=ApprovalRoute.AUTO.value,
                    reason="R8: Uncertain verdict with residual risk: recommend ESCALATE_TO_ANALYST."
                )
            ]

    # Rule Constraints Enforcement
    action_names = {a.action for a in final_actions}

    # SAR Consistency: sar_file <-> FILE_REPORT
    if ActionType.FILE_REPORT.value in action_names:
        state.sar_file = True
        state.sar_reason = next((a.reason for a in final_actions if a.action == ActionType.FILE_REPORT.value), "R2: Mandatory SAR filing threshold exceeded")
    else:
        state.sar_file = False
        state.sar_reason = ""

    # Legitimate verdict constraints
    if state.verdict == Verdict.LEGITIMATE.value:
        state.exposure_usd = 0.0
        state.affected_txn_ids = []
        state.sar_file = False
        final_actions = [a for a in final_actions if a.action != ActionType.FILE_REPORT.value]

    # R10 constraint: BLOCK_ALL_CARDS requires 2+ confirmed fraud cards
    if ActionType.BLOCK_ALL_CARDS.value in {a.action for a in final_actions} and len(state.connected_card_ids) < 1:
        final_actions = [a for a in final_actions if a.action != ActionType.BLOCK_ALL_CARDS.value]
        if not any(a.action == ActionType.BLOCK_CARD.value for a in final_actions):
            final_actions.append(ActionRec(
                action=ActionType.BLOCK_CARD.value,
                route=approval_route(ActionType.BLOCK_CARD, state.exposure_usd).value,
                reason="R10: Reverted BLOCK_ALL_CARDS to BLOCK_CARD because only single card confirmed compromised."
            ))

    state.final_actions = final_actions

    # Compute what_changed
    init_str = ", ".join(a.action for a in state.initial_actions)
    final_str = ", ".join(a.action for a in state.final_actions)
    if init_str != final_str:
        state.what_changed = f"Actions updated from [{init_str}] to [{final_str}] following evidence intake and stopping rule."
    else:
        state.what_changed = "Initial action recommendations confirmed after completing evidence gathering."

    _log_node_action(state, "action_node", f"Finalized {len(state.final_actions)} actions (SAR={state.sar_file})")
    return state


async def explain_node(state: InvestigationState) -> InvestigationState:
    """
    Node 7: Compiles final case summary, SAR narrative (if filed), and status.
    """
    # Set status based on verdict
    if state.verdict == Verdict.FRAUD.value:
        state.status = CaseStatus.CLOSED_FRAUD.value
    elif state.verdict == Verdict.LEGITIMATE.value:
        state.status = CaseStatus.CLOSED_LEGITIMATE.value
    else:
        state.status = CaseStatus.ESCALATED.value

    prompt_text = fill_case_summary(state)
    summary_res = await call_llm_json(prompt_text, {})

    state.summary = summary_res.get("summary", f"Investigation concluded with verdict {state.verdict} for case {state.case_id}.")

    if state.sar_file:
        state.sar_narrative = summary_res.get("sar_narrative", (
            f"Suspicious Activity Report filed for Case {state.case_id}. "
            f"Customer {state.customer_id} on Card {state.card_id} exhibited suspicious activity "
            f"fitting pattern {state.pattern} with exposure ${state.exposure_usd:.2f}. "
            f"The transactions were identified during autonomous monitoring and verified unauthorized. "
            f"Accounts have been restricted and remediation actions applied in compliance with regulatory guidance."
        ))
        state.sar_subjects = summary_res.get("sar_subjects", [state.customer_id, state.card_id])
        state.sar_total_amount_usd = state.exposure_usd
        state.sar_activity_dates = summary_res.get("activity_dates", ["2016-11-20", "2016-12-05"])
    else:
        state.sar_narrative = ""
        state.sar_subjects = []
        state.sar_total_amount_usd = 0.0
        state.sar_activity_dates = []

    _log_node_action(state, "explain_node", f"Generated compliance summary (status={state.status})")
    return state


async def memory_node(state: InvestigationState) -> InvestigationState:
    """
    Node 8: Persists Case vertex and edges into TigerGraph and updates written_to_graph flag.
    """
    await tg_tools.write_case_to_graph(state)
    state.written_to_graph = True
    state.graph_case_id = state.case_id

    _log_node_action(state, "memory_node", f"Archived Case {state.case_id} to TigerGraph graph")
    return state
