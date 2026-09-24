"""
LLM Prompt Templates for HHGOA Fraud Investigation Agent.
Ground Truth Corrected (Section 5 / HHGOA_GROUND_TRUTH_CORRECTIONS.md).

ALL action strings, verdict strings, pattern strings, route strings are
graded verbatim — do NOT paraphrase or rename them in the JSON response.

Importing POLICY_RULES from agent.state ensures the prompt always has the
current verbatim rule text, not a paraphrase.
"""

from agent.state import POLICY_RULES


# ---------------------------------------------------------------------------
# Helper — format the policy table for insertion into prompts
# ---------------------------------------------------------------------------

def _format_policy_table() -> str:
    lines = []
    for rule_id, rule_text in POLICY_RULES.items():
        lines.append(f"  {rule_id}: {rule_text}")
    return "\n".join(lines)


_POLICY_TABLE = _format_policy_table()

_ACTIONS_LIST = (
    "ALLOW_TRANSACTION, DECLINE_TRANSACTION, MONITOR_CARD, MONITOR_CONNECTED_CARDS, "
    "WARN_CUSTOMER, VERIFY_WITH_CUSTOMER, STEP_UP_AUTH, BLOCK_CARD, BLOCK_ALL_CARDS, "
    "GENERATE_REPORT, CREATE_CASE, FILE_REPORT, ESCALATE_TO_ANALYST, CLOSE_NO_FRAUD"
)


# ---------------------------------------------------------------------------
# Prompt 1 — Evidence Synthesis
# ---------------------------------------------------------------------------

EVIDENCE_SYNTHESIS_PROMPT = """You are a senior financial crime graph analyst conducting a fraud investigation.

Case ID: {case_id}
Trigger Type: {trigger_type}
Flagged Transaction: {flagged_txn_id}
Card ID: {card_id}
Customer ID: {customer_id}
Trigger Risk Score: {trigger_risk_score}
Trigger Text: {trigger_text}

Graph Entities Discovered:
  Cards on customer:         {cards}
  Transactions in scope:     {transactions}
  Device profiles linked:    {device_profiles}
  Email domains:             {email_domains}
  Billing regions:           {billing_regions}

Graph Traversal Findings:
  Shared identifiers (live traversal): {shared_identifiers}
  Money flow (NEXT chain):             {money_flow}

Historical Closed Cases (GraphRAG retrieval):
  {similar_cases}

POLICY RULES (cite by number in evidence claims):
{policy_rules}

Your task:
Synthesise all graph connections into structured evidence items.
For each item, identify whether it is INDEPENDENT of other items (i.e. comes from
a different data source or traversal path) — mark is_independent=true only when
the evidence cannot be explained by the same underlying cause as another item.

Respond ONLY in valid JSON:
{{
  "evidence": [
    {{
      "claim": "Specific, factual assertion grounded in the graph data",
      "source": "graph" | "document" | "customer" | "external",
      "ref": "name of the query or data source used",
      "entity_ids": ["T3514030", "C12382-K1"],
      "is_independent": true | false
    }}
  ],
  "preliminary_verdict": "fraud" | "legitimate" | "uncertain",
  "preliminary_fraud_probability": 0.0,
  "reasoning": "2-4 sentence summary of findings"
}}
"""

# ---------------------------------------------------------------------------
# Prompt 2 — Risk Assessment & Stopping Decision
# ---------------------------------------------------------------------------

RISK_ASSESSMENT_PROMPT = """You are a compliance risk officer deciding whether the investigation has enough evidence to conclude.

Case ID: {case_id}
Trigger Type: {trigger_type}
Iteration: {iteration_count}
Trigger Risk Score: {trigger_risk_score}
Current Fraud Probability Estimate: {current_fraud_probability}
Independent Evidence Count: {independent_evidence_count}
Verification Settled: {verification_settled}

Evidence collected so far:
{evidence_summary}

Stopping rule (apply exactly):
  - If verification_settled=true → stop.
  - If (fraud_probability >= 0.85 OR fraud_probability <= 0.15) AND independent_evidence_count >= 2 → stop.
  - If iteration_count >= 3 → stop.
  Otherwise → gather more evidence.

POLICY RULES:
{policy_rules}

KNOWN PATTERNS:
  card_testing, card_not_present_fraud, card_not_present_new_device,
  out_of_region_use, account_takeover, undocumented, none

Respond ONLY in valid JSON:
{{
  "fraud_probability": 0.0,
  "verdict": "fraud" | "legitimate" | "uncertain",
  "pattern": "card_testing" | "card_not_present_fraud" | "card_not_present_new_device" | "out_of_region_use" | "account_takeover" | "undocumented" | "none",
  "pattern_description": "Required if pattern=undocumented, else empty string",
  "should_stop": true | false,
  "stop_reason": "Exact reason from the stopping rule, or empty string",
  "next_evidence_type": "What to gather next if not stopping — e.g. 'customer_validation', 'device_traversal', 'similar_case_lookup'",
  "exposure_usd": 0.0,
  "rationale": "2-4 sentence explanation"
}}
"""

# ---------------------------------------------------------------------------
# Prompt 3 — Action Selection
# ---------------------------------------------------------------------------

ACTION_SELECTION_PROMPT = """You are an automated regulatory enforcement engine selecting remediation actions.

Case ID: {case_id}
Verdict: {verdict}
Fraud Probability: {fraud_probability}
Pattern: {pattern}
Exposure USD: {exposure_usd}
Evidence:
{evidence_summary}

EXACT POLICY RULES — cite by number (e.g. "R2: ...") in every reason field:
{policy_rules}

ALLOWED ACTIONS (use exact strings only — these are graded verbatim):
  {actions_list}

APPROVAL ROUTING (apply exactly):
  - DECLINE_TRANSACTION → always "L1"
  - BLOCK_CARD          → "L1" if exposure_usd <= 2500, else "L2"
  - BLOCK_ALL_CARDS     → always "L2"
  - FILE_REPORT         → always "L2"
  - All others          → "auto"

CRITICAL CONSTRAINTS:
  - Never recommend BLOCK_ALL_CARDS unless 2+ of the customer's cards show confirmed fraud (R10).
  - If fraud_probability < 0.70 and evidence is single-signal, recommend VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block (R1).
  - If sar.file=True is implied, FILE_REPORT MUST be in the actions list.
  - Every reason string MUST cite the rule number e.g. "R5: card-testing confirmed..."

Respond ONLY in valid JSON:
{{
  "initial_actions": [
    {{
      "action": "EXACT_ACTION_STRING",
      "route": "auto" | "L1" | "L2",
      "reason": "R<N>: specific reason citing evidence"
    }}
  ],
  "sar_recommended": true | false,
  "sar_reason": "Rule citation or empty string"
}}
"""

# ---------------------------------------------------------------------------
# Prompt 4 — Final Case Summary & SAR Narrative
# ---------------------------------------------------------------------------

CASE_SUMMARY_PROMPT = """You are an expert fraud compliance auditor writing the final investigation record.

Case ID: {case_id}
Card ID: {card_id}
Customer ID: {customer_id}
Final Verdict: {verdict}
Fraud Probability: {fraud_probability}
Pattern: {pattern}
Pattern Description: {pattern_description}
Exposure USD: {exposure_usd}
Status: {status}

Evidence:
{evidence_summary}

Final Actions:
{actions_summary}

Similar Prior Cases: {similar_cases}

POLICY RULES:
{policy_rules}

Tasks:
1. Write a 2-6 sentence case summary (factual, professional, audit-ready).
2. If SAR filing is required (FILE_REPORT in actions), write a 6-12 sentence BSA-compliant SAR narrative.
   Otherwise set sar_narrative to empty string.

Respond ONLY in valid JSON:
{{
  "summary": "2-6 sentence factual narrative of the investigation outcome",
  "sar_narrative": "6-12 sentence BSA narrative or empty string",
  "sar_subjects": ["entity IDs if SAR filed, else empty list"],
  "activity_dates": ["YYYY-MM-DD first", "YYYY-MM-DD last"] 
}}
"""


# ---------------------------------------------------------------------------
# Template-filling helpers
# ---------------------------------------------------------------------------

def fill_evidence_synthesis(state) -> str:
    return EVIDENCE_SYNTHESIS_PROMPT.format(
        case_id=state.case_id,
        trigger_type=state.trigger_type,
        flagged_txn_id=state.flagged_txn_id,
        card_id=state.card_id,
        customer_id=state.customer_id,
        trigger_risk_score=state.trigger_risk_score,
        trigger_text=state.trigger_text or "",
        cards=", ".join(state.cards) or "none",
        transactions=", ".join(state.transactions[:20]) or "none",
        device_profiles=", ".join(state.device_profiles) or "none",
        email_domains=", ".join(state.email_domains) or "none",
        billing_regions=", ".join(state.billing_regions) or "none",
        shared_identifiers=str(state.shared_identifiers or []),
        money_flow=str(state.money_flow or {}),
        similar_cases=", ".join(state.similar_cases) or "none",
        policy_rules=_POLICY_TABLE,
    )


def fill_risk_assessment(state) -> str:
    ev_summary = "\n".join(
        f"  - [{e.source}] {e.claim} (ref: {e.ref})"
        for e in state.evidence_list
    ) or "  (no evidence yet)"
    return RISK_ASSESSMENT_PROMPT.format(
        case_id=state.case_id,
        trigger_type=state.trigger_type,
        iteration_count=state.iteration_count,
        trigger_risk_score=state.trigger_risk_score,
        current_fraud_probability=state.fraud_probability,
        independent_evidence_count=state.independent_evidence_count,
        verification_settled=state.verification_settled,
        evidence_summary=ev_summary,
        policy_rules=_POLICY_TABLE,
    )


def fill_action_selection(state) -> str:
    ev_summary = "\n".join(
        f"  - [{e.source}] {e.claim}"
        for e in state.evidence_list
    ) or "  (no evidence)"
    return ACTION_SELECTION_PROMPT.format(
        case_id=state.case_id,
        verdict=state.verdict,
        fraud_probability=state.fraud_probability,
        pattern=state.pattern,
        exposure_usd=state.exposure_usd,
        evidence_summary=ev_summary,
        policy_rules=_POLICY_TABLE,
        actions_list=_ACTIONS_LIST,
    )


def fill_case_summary(state) -> str:
    ev_summary = "\n".join(
        f"  - [{e.source}] {e.claim} (ref: {e.ref})"
        for e in state.evidence_list
    ) or "  (no evidence)"
    final_actions_summary = "\n".join(
        f"  - {a.action} [{a.route}]: {a.reason}"
        for a in state.final_actions
    ) or "  (no actions)"
    return CASE_SUMMARY_PROMPT.format(
        case_id=state.case_id,
        card_id=state.card_id,
        customer_id=state.customer_id,
        verdict=state.verdict,
        fraud_probability=state.fraud_probability,
        pattern=state.pattern,
        pattern_description=state.pattern_description or "",
        exposure_usd=state.exposure_usd,
        status=state.status,
        evidence_summary=ev_summary,
        actions_summary=final_actions_summary,
        similar_cases=", ".join(state.similar_cases) or "none",
        policy_rules=_POLICY_TABLE,
    )
