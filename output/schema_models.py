"""
output/schema_models.py — HHGOA Ground Truth Corrected Output Schema (Section 4)

ONE JSON file per case: cases/{case_id}.json
Shape is CaseAnswer. ALL Literal values are graded verbatim — do not alter strings.

Old schema (CaseRecordOutput / SAROutput / ActionOutput / 4-file-per-case) is retired.
"""

from typing import List, Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """A single evidence item supporting the investigation conclusion."""
    claim: str = Field(description="What the evidence asserts")
    source: Literal["graph", "document", "customer", "external"] = Field(
        description="Origin of the evidence"
    )
    ref: str = Field(description="Query name, doc section, or request id")
    entity_ids: List[str] = Field(
        default_factory=list,
        description="IDs of graph entities referenced (txn_ids, card_ids, device_profile_ids)"
    )


class EvidenceRequest(BaseModel):
    """A simulated external information request made during investigation."""
    type: Literal["customer_validation", "step_up_auth", "analyst_info"] = Field(
        description="Type of evidence request"
    )
    asked_after_step: int = Field(
        description="Investigation iteration number after which this was requested"
    )
    assumed_response: str = Field(
        description="Simulated response (real responses never provided — agent must simulate)"
    )


class ActionRec(BaseModel):
    """A single recommended action with its approval route and rule citation."""
    action: str = Field(
        description=(
            "One of the 14 exact action strings: ALLOW_TRANSACTION, DECLINE_TRANSACTION, "
            "MONITOR_CARD, MONITOR_CONNECTED_CARDS, WARN_CUSTOMER, VERIFY_WITH_CUSTOMER, "
            "STEP_UP_AUTH, BLOCK_CARD, BLOCK_ALL_CARDS, GENERATE_REPORT, CREATE_CASE, "
            "FILE_REPORT, ESCALATE_TO_ANALYST, CLOSE_NO_FRAUD"
        )
    )
    route: Literal["auto", "L1", "L2"] = Field(
        description="Approval tier: auto (no human), L1 (analyst), L2 (senior/compliance)"
    )
    reason: str = Field(
        description="Justification — MUST cite rule number, e.g. 'R2: customer denied the transaction...'"
    )


class NextBestActions(BaseModel):
    """Initial and final action recommendations, with change summary."""
    initial: List[ActionRec] = Field(
        default_factory=list,
        description="Actions recommended before any evidence requests"
    )
    final: List[ActionRec] = Field(
        default_factory=list,
        description="Actions after all evidence gathered. Equals initial if nothing changed."
    )
    what_changed: str = Field(
        default="nothing",
        description="'nothing' if final == initial, otherwise describe what shifted"
    )


class Case(BaseModel):
    """Core case verdict and findings."""
    status: Literal["open", "closed_fraud", "closed_legitimate", "escalated"] = Field(
        default="open"
    )
    verdict: Literal["fraud", "legitimate", "uncertain"] = Field(
        default="uncertain"
    )
    fraud_probability: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="Calibrated probability 0-1. Graded for calibration quality."
    )
    pattern: Literal[
        "card_testing",
        "card_not_present_fraud",
        "card_not_present_new_device",
        "out_of_region_use",
        "account_takeover",
        "undocumented",
        "none",
    ] = Field(default="none")
    pattern_description: str = Field(
        default="",
        description="Required text if pattern == 'undocumented', else empty string"
    )
    affected_txn_ids: List[str] = Field(
        default_factory=list,
        description="Empty if verdict == legitimate. IDs must exist in loaded dataset."
    )
    first_suspicious_txn_id: str = Field(
        default="",
        description="Empty string if no suspicious transaction identified"
    )
    connected_card_ids: List[str] = Field(
        default_factory=list,
        description="Other card IDs implicated. Must exist in loaded dataset."
    )
    connected_device_profiles: List[str] = Field(
        default_factory=list,
        description="DeviceProfile IDs shared with the flagged transaction"
    )
    exposure_usd: float = Field(
        default=0.0,
        description="Zero if verdict == legitimate"
    )
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="All evidence items collected during investigation"
    )
    similar_prior_cases: List[str] = Field(
        default_factory=list,
        description="ClosedCase IDs e.g. ['CC-0141']. Must exist in loaded dataset."
    )
    summary: str = Field(
        default="",
        description="2-6 sentence narrative of the investigation outcome"
    )
    written_to_graph: bool = Field(
        default=False,
        description="True if Case vertex was written to TigerGraph"
    )
    graph_case_id: str = Field(
        default="",
        description="TigerGraph Case vertex ID, or empty if not written"
    )


class SAR(BaseModel):
    """Suspicious Activity Report filing decision."""
    file: bool = Field(
        default=False,
        description="Must agree with FILE_REPORT appearing in next_best_actions.final"
    )
    reason: str = Field(
        default="",
        description="Rule citation justifying the SAR decision"
    )
    narrative: str = Field(
        default="",
        description="Empty if file==False. 6-12 sentences if file==True (BSA-compliant)."
    )
    subjects: List[str] = Field(
        default_factory=list,
        description="Empty list if file==False"
    )
    total_amount_usd: float = Field(
        default=0.0,
        description="Zero if file==False"
    )
    activity_dates: List[str] = Field(
        default_factory=list,
        description="Empty if file==False, else [first_date, last_date] as YYYY-MM-DD"
    )


class CaseAnswer(BaseModel):
    """
    Complete investigation output. Written to cases/{case_id}.json — one file per case.
    Every field is graded. Fabricated IDs score zero.
    """
    case_id: str = Field(
        description="Exact match to case_pack.csv case_id (e.g. 'HHG-001')"
    )
    case: Case = Field(default_factory=Case)
    evidence_requests: List[EvidenceRequest] = Field(
        default_factory=list,
        description="Empty list if no external evidence was requested"
    )
    next_best_actions: NextBestActions = Field(default_factory=NextBestActions)
    sar: SAR = Field(default_factory=SAR)
    stop_reason: str = Field(
        default="",
        description="From should_stop() — the literal reason string"
    )
    tool_calls: int = Field(
        default=0,
        description="Total number of TigerGraph/retrieval tool calls made"
    )
    tokens: int = Field(
        default=0,
        description="Total LLM tokens consumed during investigation"
    )
    latency_s: float = Field(
        default=0.0,
        description="Wall-clock seconds from trigger receipt to output write"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "case_id": "HHG-001",
                "case": {
                    "status": "closed_fraud",
                    "verdict": "fraud",
                    "fraud_probability": 0.91,
                    "pattern": "card_testing",
                    "pattern_description": "",
                    "affected_txn_ids": ["T3514030", "T3514031", "T3514032"],
                    "first_suspicious_txn_id": "T3514030",
                    "connected_card_ids": [],
                    "connected_device_profiles": ["dp_a1b2c3"],
                    "exposure_usd": 347.50,
                    "evidence": [
                        {
                            "claim": "Three small authorizations under $5 on card C12382-K1 within 42 minutes followed by a $312 purchase.",
                            "source": "graph",
                            "ref": "get_txn_neighborhood",
                            "entity_ids": ["T3514030", "T3514031", "T3514032", "T3514033"]
                        }
                    ],
                    "similar_prior_cases": ["CC-0141"],
                    "summary": "Card C12382-K1 shows a classic card-testing pattern: three sub-$5 online authorizations over 42 minutes followed by a $312.50 purchase. The device profile dp_a1b2c3 is flagged as New (id_15). Prior case CC-0141 matches the same pattern with the same device profile.",
                    "written_to_graph": True,
                    "graph_case_id": "HHG-001"
                },
                "evidence_requests": [
                    {
                        "type": "customer_validation",
                        "asked_after_step": 1,
                        "assumed_response": "Customer did not respond within simulated 24-hour window."
                    }
                ],
                "next_best_actions": {
                    "initial": [
                        {"action": "STEP_UP_AUTH", "route": "auto", "reason": "R1: single risk-score signal, fraud_probability 0.61 below 0.70 threshold."},
                        {"action": "VERIFY_WITH_CUSTOMER", "route": "auto", "reason": "R1: verify before blocking on weak initial signal."}
                    ],
                    "final": [
                        {"action": "BLOCK_CARD", "route": "L1", "reason": "R5: card-testing pattern confirmed, $312 purchase cleared, exposure $347.50 <= $2500."},
                        {"action": "DECLINE_TRANSACTION", "route": "L1", "reason": "R4: no customer reply within 24h, pending authorization declined."}
                    ],
                    "what_changed": "Customer did not respond; card-testing pattern confirmed by graph traversal — escalated from verify to block."
                },
                "sar": {
                    "file": False,
                    "reason": "R5 does not require FILE_REPORT; exposure $347.50 below $1,000 threshold in R2.",
                    "narrative": "",
                    "subjects": [],
                    "total_amount_usd": 0.0,
                    "activity_dates": []
                },
                "stop_reason": "Fraud probability 0.91 with 2 independent evidence pieces meets the confidence threshold.",
                "tool_calls": 4,
                "tokens": 1820,
                "latency_s": 3.14
            }
        }
    }
