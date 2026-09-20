"""
HHGOA Agent State — Ground Truth Corrected (Section 5)
Enums, stop logic, and approval routing are graded verbatim.
Do NOT rename any enum value or add new ones without updating the corrections doc.
"""

import time
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Corrected Enums (Section 5 — exact graded strings)
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    ALLOW_TRANSACTION      = "ALLOW_TRANSACTION"
    DECLINE_TRANSACTION    = "DECLINE_TRANSACTION"
    MONITOR_CARD           = "MONITOR_CARD"
    MONITOR_CONNECTED_CARDS = "MONITOR_CONNECTED_CARDS"
    WARN_CUSTOMER          = "WARN_CUSTOMER"
    VERIFY_WITH_CUSTOMER   = "VERIFY_WITH_CUSTOMER"
    STEP_UP_AUTH           = "STEP_UP_AUTH"
    BLOCK_CARD             = "BLOCK_CARD"
    BLOCK_ALL_CARDS        = "BLOCK_ALL_CARDS"
    GENERATE_REPORT        = "GENERATE_REPORT"
    CREATE_CASE            = "CREATE_CASE"
    FILE_REPORT            = "FILE_REPORT"
    ESCALATE_TO_ANALYST    = "ESCALATE_TO_ANALYST"
    CLOSE_NO_FRAUD         = "CLOSE_NO_FRAUD"


class ApprovalRoute(str, Enum):
    AUTO = "auto"
    L1   = "L1"
    L2   = "L2"


class Pattern(str, Enum):
    CARD_TESTING    = "card_testing"
    CNP_FRAUD       = "card_not_present_fraud"
    CNP_NEW_DEVICE  = "card_not_present_new_device"
    OUT_OF_REGION   = "out_of_region_use"
    ACCOUNT_TAKEOVER = "account_takeover"
    UNDOCUMENTED    = "undocumented"
    NONE            = "none"


class Verdict(str, Enum):
    FRAUD       = "fraud"
    LEGITIMATE  = "legitimate"
    UNCERTAIN   = "uncertain"


class CaseStatus(str, Enum):
    OPEN               = "open"
    CLOSED_FRAUD       = "closed_fraud"
    CLOSED_LEGITIMATE  = "closed_legitimate"
    ESCALATED          = "escalated"


class TriggerType(str, Enum):
    RISK_SCORE        = "risk_score"
    CUSTOMER_REPORT   = "customer_report"
    ANALYST_REQUEST   = "analyst_request"


# ---------------------------------------------------------------------------
# Policy helpers (Section 2 — exact logic, graded)
# ---------------------------------------------------------------------------

APPROVAL_AUTO = {
    ActionType.ALLOW_TRANSACTION,
    ActionType.MONITOR_CARD,
    ActionType.MONITOR_CONNECTED_CARDS,
    ActionType.WARN_CUSTOMER,
    ActionType.VERIFY_WITH_CUSTOMER,
    ActionType.STEP_UP_AUTH,
    ActionType.GENERATE_REPORT,
    ActionType.CREATE_CASE,
    ActionType.ESCALATE_TO_ANALYST,
    ActionType.CLOSE_NO_FRAUD,
}


def approval_route(action: ActionType, exposure_usd: float) -> ApprovalRoute:
    """Return the approval tier for an action. Section 2 — exact logic."""
    if action == ActionType.DECLINE_TRANSACTION:
        return ApprovalRoute.L1
    if action == ActionType.BLOCK_CARD:
        return ApprovalRoute.L1 if exposure_usd <= 2500 else ApprovalRoute.L2
    if action in (ActionType.BLOCK_ALL_CARDS, ActionType.FILE_REPORT):
        return ApprovalRoute.L2
    if action in APPROVAL_AUTO:
        return ApprovalRoute.AUTO
    raise ValueError(f"Unknown action: {action}")


def should_stop(
    fraud_probability: float,
    independent_evidence_count: int,
    verification_settled: bool,
    iteration_count: int,
) -> Tuple[bool, str]:
    """
    Section 2 — exact stopping rule.
    MDL/entropy in innovation/mdl_gate.py picks the next best question;
    this function decides when to stop asking.
    """
    if verification_settled:
        return True, "A verification response settled the question."
    if (fraud_probability >= 0.85 or fraud_probability <= 0.15) and independent_evidence_count >= 2:
        return True, (
            f"Fraud probability {fraud_probability:.2f} with "
            f"{independent_evidence_count} independent evidence pieces meets the confidence threshold."
        )
    if iteration_count >= 3:
        return True, "Further steps are unlikely to change the decision after 3 evidence-gathering rounds."
    return False, ""


# ---------------------------------------------------------------------------
# Policy rules lookup (Section 2 — exact text, graded verbatim)
# ---------------------------------------------------------------------------

POLICY_RULES: Dict[str, str] = {
    "R1": (
        "Verify before you block on a weak signal. If the case rests on a single signal "
        "(including a risk score alone) and assessed fraud probability is below 0.70, "
        "recommend VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block."
    ),
    "R2": (
        "Customer denies the transaction: recommend BLOCK_CARD and CREATE_CASE. "
        "Add FILE_REPORT if exposure exceeds $1,000 or the case connects to a shared "
        "device profile or another card's fraud."
    ),
    "R3": (
        "Customer confirms the transaction: recommend CLOSE_NO_FRAUD. Note the "
        "confirmation in the case file."
    ),
    "R4": (
        "No reply within 24 hours: recommend MONITOR_CARD and DECLINE_TRANSACTION for "
        "pending authorizations. Escalate if exposure exceeds $500."
    ),
    "R5": (
        "Card testing (3+ small online authorizations on one card within an hour, then "
        "a larger purchase): recommend DECLINE_TRANSACTION and STEP_UP_AUTH. If a "
        "purchase over $100 has already cleared, recommend BLOCK_CARD."
    ),
    "R6": (
        "Shared origin: when several cards show fraud from the same device profile, "
        "billing region, or recipient email in one window: name the shared element, "
        "recommend CREATE_CASE and FILE_REPORT, and MONITOR_CONNECTED_CARDS for every "
        "card that shares it."
    ),
    "R7": (
        "Disputed but legitimate (customer disputes a charge matching their own "
        "recurring pattern - same merchant, same amount, monthly): recommend "
        "CREATE_CASE, VERIFY_WITH_CUSTOMER, and WARN_CUSTOMER. Do not block."
    ),
    "R8": (
        "Escalate when uncertain and exposed: if verdict is uncertain and exposure "
        "exceeds $500, or evidence conflicts, recommend ESCALATE_TO_ANALYST."
    ),
    "R9": (
        "Undocumented patterns: when activity fits none of the known patterns but "
        "evidence shows coordinated or repeated abuse across customers, recommend "
        "CREATE_CASE, FILE_REPORT, and ESCALATE_TO_ANALYST. Describe the pattern in "
        "your own words. Do not force it into a known category."
    ),
    "R10": (
        "Never BLOCK_ALL_CARDS unless at least two of the customer's cards show "
        "confirmed fraud or the customer's credentials are confirmed compromised."
    ),
}


# ---------------------------------------------------------------------------
# Evidence & Action models (match output/schema_models.py shapes)
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    """An individual evidence item gathered during investigation."""
    claim: str = ""
    source: str = "graph"       # graph | document | customer | external
    ref: str = ""               # query name, doc section, or request id
    entity_ids: List[str] = Field(default_factory=list)
    # Internal scoring (not written to output JSON directly)
    score: float = 0.0
    is_independent: bool = False  # counts toward independent_evidence_count


class ActionRec(BaseModel):
    """A recommended action with its approval route and rule citation."""
    action: str = ""            # exact ActionType string
    route: str = "auto"         # auto | L1 | L2
    reason: str = ""            # MUST cite rule number e.g. "R2: customer denied..."


class EvidenceRequest(BaseModel):
    """A simulated evidence request (customer/analyst/step-up)."""
    type: str = "customer_validation"   # customer_validation | step_up_auth | analyst_info
    asked_after_step: int = 0
    assumed_response: str = ""


# ---------------------------------------------------------------------------
# Main Investigation State
# ---------------------------------------------------------------------------

class InvestigationState(BaseModel):
    """
    Complete mutable state for one investigation run through the LangGraph.
    Trigger dict shape (from case_pack.csv):
        {
          "case_id": "HHG-001",
          "trigger_type": "risk_score",        # risk_score | customer_report | analyst_request
          "flagged_txn_id": "T3514030",
          "card_id": "C12382-K1",
          "customer_id": "C12382",
          "risk_score": 0.61,                  # null for non-risk_score triggers
          "trigger_text": "...",               # useful for customer_report / analyst_request
        }
    """

    # --- Case identification ---
    case_id: str = ""
    trigger_type: str = TriggerType.RISK_SCORE.value
    flagged_txn_id: str = ""
    card_id: str = ""
    customer_id: str = ""
    trigger_risk_score: float = 0.0
    trigger_text: str = ""

    # --- Graph Entities discovered ---
    cards: List[str] = Field(default_factory=list)           # card_ids on same customer
    transactions: List[str] = Field(default_factory=list)    # txn_ids in scope
    device_profiles: List[str] = Field(default_factory=list) # DeviceProfile IDs
    email_domains: List[str] = Field(default_factory=list)   # EmailDomain IDs
    billing_regions: List[str] = Field(default_factory=list) # BillingRegion IDs
    subgraph: Dict[str, Any] = Field(default_factory=dict)
    shared_identifiers: List[Dict[str, Any]] = Field(default_factory=list)
    money_flow: Dict[str, Any] = Field(default_factory=dict)

    # --- Policy & retrieval ---
    matched_policies: List[Dict[str, Any]] = Field(default_factory=list)
    similar_cases: List[str] = Field(default_factory=list)  # ClosedCase IDs e.g. "CC-0141"

    # --- Evidence & deliberation ---
    evidence_list: List[EvidenceItem] = Field(default_factory=list)
    evidence_requests: List[EvidenceRequest] = Field(default_factory=list)
    independent_evidence_count: int = 0
    verification_settled: bool = False
    iteration_count: int = 0
    started_at: float = Field(default_factory=time.time)

    # --- Verdict ---
    verdict: str = Verdict.UNCERTAIN.value
    fraud_probability: float = 0.5
    pattern: str = Pattern.NONE.value
    pattern_description: str = ""     # required when pattern == "undocumented"
    status: str = CaseStatus.OPEN.value
    exposure_usd: float = 0.0
    affected_txn_ids: List[str] = Field(default_factory=list)
    first_suspicious_txn_id: str = ""
    connected_card_ids: List[str] = Field(default_factory=list)
    connected_device_profiles: List[str] = Field(default_factory=list)
    summary: str = ""
    written_to_graph: bool = False
    graph_case_id: str = ""

    # --- Actions ---
    initial_actions: List[ActionRec] = Field(default_factory=list)
    final_actions: List[ActionRec] = Field(default_factory=list)
    what_changed: str = "nothing"

    # --- SAR ---
    sar_file: bool = False
    sar_reason: str = ""
    sar_narrative: str = ""
    sar_subjects: List[str] = Field(default_factory=list)
    sar_total_amount_usd: float = 0.0
    sar_activity_dates: List[str] = Field(default_factory=list)

    # --- Telemetry ---
    stop_reason: str = ""
    tool_calls_count: int = 0
    tokens_used: int = 0
    decision_log: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[str] = Field(default_factory=list)  # names of tools invoked

    # --- MDL/entropy innovation layer ---
    mdl_sufficiency_score: float = 1.0   # from innovation/mdl_gate.py
    next_evidence_type: Optional[str] = None

    def compute_stop(self) -> Tuple[bool, str]:
        """Convenience wrapper around module-level should_stop()."""
        return should_stop(
            self.fraud_probability,
            self.independent_evidence_count,
            self.verification_settled,
            self.iteration_count,
        )

    def add_evidence(self, item: EvidenceItem) -> None:
        """Append evidence and update independent count if flagged."""
        self.evidence_list.append(item)
        if item.is_independent:
            self.independent_evidence_count += 1

    def log_step(self, stage: str, summary: str, **kwargs: Any) -> None:
        """Append a chronological audit log entry."""
        self.decision_log.append({
            "stage": stage,
            "summary": summary,
            "iteration": self.iteration_count,
            **kwargs,
        })
