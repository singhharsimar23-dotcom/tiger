"""
Pydantic output schema definitions for benchmark case investigation exports.
Specifies compliant formats for:
- case_record.json: Comprehensive investigation ledger & graph evidence
- sar.json: FinCEN-compliant Suspicious Activity Report dossier
- action_before.json / action_after.json: Policy remediation decisions
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class CaseRecordOutput(BaseModel):
    """Schema model for case_record.json compliance archive."""
    case_id: str = Field(description="Unique case identification string")
    case_number: int = Field(description="Sequential benchmark case index (1-20)")
    timestamp: str = Field(description="ISO 8601 creation timestamp")
    investigation_duration_seconds: float = Field(description="Total agent deliberation runtime in seconds")
    status: str = Field(description="Final case lifecycle status (RESOLVED, CLOSED)")
    trigger_type: str = Field(description="Initial alert ingestion trigger mechanism")
    trigger_txn_ids: List[str] = Field(default_factory=list, description="List of alerting transaction IDs")
    trigger_account_id: Optional[str] = Field(default=None, description="Primary implicated bank account ID")
    trigger_risk_score: float = Field(description="Upstream model anomaly score (0.0 - 1.0)")
    
    # Discovered Graph Topology
    accounts_discovered: List[str] = Field(default_factory=list, description="Unique account nodes discovered in k-hop graph")
    devices_discovered: List[str] = Field(default_factory=list, description="Hardware device nodes shared across accounts")
    ip_clusters_discovered: List[str] = Field(default_factory=list, description="Network subnet clusters mapped to transactions")
    
    # Intelligence Corroboration
    matched_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="Detected fraud typology pattern templates")
    matched_policies: List[Dict[str, Any]] = Field(default_factory=list, description="Institutional governance rules triggered")
    similar_prior_cases: List[Dict[str, Any]] = Field(default_factory=list, description="Precedent cases retrieved via GraphRAG")
    
    # Deliberation & Minimum Description Length
    evidence_list: List[Dict[str, Any]] = Field(default_factory=list, description="Synthesized evidence units with confidence weights")
    evidence_count: int = Field(description="Total count of verified evidence items")
    uncertainty_score: float = Field(description="Epistemic uncertainty score derived from Shannon entropy")
    mdl_sufficiency_score: float = Field(description="Minimum Description Length net information gain score")
    iteration_count: int = Field(description="Number of investigative feedback loops executed")
    
    # Verdict & Remediations
    decision: Optional[Dict[str, Any]] = Field(default=None, description="Formal verdict, fraud typology, and final risk score")
    recommended_actions: List[Dict[str, Any]] = Field(default_factory=list, description="Selected compliance actions")
    case_summary: Optional[str] = Field(default=None, description="Human-readable legal and compliance investigative narrative")
    decision_log: List[Dict[str, Any]] = Field(default_factory=list, description="Chronological audit trace of agent deliberations")
    tool_calls_executed: List[str] = Field(default_factory=list, description="Names of TigerGraph and retrieval tools invoked")

    model_config = {
        "json_schema_extra": {
            "example": {
                "case_id": "CASE_2026_099",
                "case_number": 99,
                "timestamp": "2026-09-20T12:00:00Z",
                "investigation_duration_seconds": 2.45,
                "status": "CLOSED",
                "trigger_type": "HIGH_RISK_ALERT",
                "trigger_txn_ids": ["T_2987000"],
                "trigger_account_id": "ACC_13926_0_315",
                "trigger_risk_score": 0.89,
                "accounts_discovered": ["ACC_13926_0_315", "ACC_4461_375_184"],
                "devices_discovered": ["DEV_WINDOWS_CHROME_89"],
                "ip_clusters_discovered": ["IP_49182301"],
                "matched_patterns": [{"pattern_id": "PAT_001_DEVICE_RING", "name": "Device Sharing Ring"}],
                "matched_policies": [{"rule_id": "RULE_SAR_001", "name": "Mandatory SAR"}],
                "similar_prior_cases": [{"case_id": "CASE_2026_001", "score": 0.94}],
                "evidence_list": [{"evidence_id": "EVID_01", "evidence_type": "SHARED_DEVICE", "score": 0.92}],
                "evidence_count": 1,
                "uncertainty_score": 0.12,
                "mdl_sufficiency_score": 0.08,
                "iteration_count": 1,
                "decision": {
                    "verdict": "CONFIRMED_FRAUD",
                    "fraud_type": "DEVICE_RING",
                    "risk_level": "HIGH",
                    "confidence": 0.94,
                    "rationale": "Direct collusion confirmed across shared hardware fingerprints."
                },
                "recommended_actions": [
                    {"action_id": "ACT_01", "action_type": "FREEZE_ACCOUNT", "approval_tier": "SUPERVISOR"}
                ],
                "case_summary": "Comprehensive multi-account device collusion syndicate detected.",
                "decision_log": [{"stage": "mdl_gate", "summary": "Sufficiency met"}],
                "tool_calls_executed": ["get_txn_neighborhood", "get_shared_identifiers"]
            }
        }
    }


class SAROutput(BaseModel):
    """Schema model for sar.json regulatory suspicious activity filing dossier."""
    case_id: str = Field(description="Unique case identifier")
    sar_required: bool = Field(description="Whether activity meets regulatory threshold for FinCEN filing")
    filing_tier: str = Field(description="Urgency tier (TIER_1_EXPEDITED, STANDARD_30_DAY, NONE)")
    suspect_information: Dict[str, Any] = Field(description="Aggregated suspect accounts, hardware tokens, and network identifiers")
    suspicious_activity_summary: str = Field(description="Executive synopsis of financial crime typology")
    transaction_ids: List[str] = Field(default_factory=list, description="All implicated transaction IDs")
    total_suspicious_amount: float = Field(description="Cumulative transaction volume in USD under scrutiny")
    primary_fraud_type: str = Field(description="Classified fraud typology categorization")
    risk_score: float = Field(description="Quantitative assessment of fraud probability (0.0 - 1.0)")
    sar_narrative: str = Field(description="Comprehensive regulatory narrative complying with Bank Secrecy Act standards")
    filing_deadline: str = Field(description="Mandatory regulatory completion timestamp (30 days from alert)")
    compliance_officer_signoff: str = Field(description="Designation of certifying automated compliance engine")
    created_at: str = Field(description="ISO 8601 export timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "case_id": "CASE_2026_099",
                "sar_required": True,
                "filing_tier": "TIER_1_EXPEDITED",
                "suspect_information": {
                    "primary_account": "ACC_13926_0_315",
                    "collusive_accounts": ["ACC_4461_375_184"],
                    "devices": ["DEV_WINDOWS_CHROME_89"],
                    "ip_clusters": ["IP_49182301"]
                },
                "suspicious_activity_summary": "Coordinated multi-card device collusion ring executing structured micro-transactions.",
                "transaction_ids": ["T_2987000", "T_2987001"],
                "total_suspicious_amount": 14500.0,
                "primary_fraud_type": "DEVICE_RING",
                "risk_score": 0.94,
                "sar_narrative": "Between January 15 and January 18, Subject account ACC_13926_0_315 engaged in coordinated rapid funds transfers...",
                "filing_deadline": "2026-02-17T00:00:00Z",
                "compliance_officer_signoff": "AUTONOMOUS_FRAUD_INVESTIGATION_AGENT",
                "created_at": "2026-09-20T12:00:00Z"
            }
        }
    }


class ActionOutput(BaseModel):
    """Schema model for action_before.json and action_after.json."""
    case_id: str = Field(description="Unique case identifier")
    stage: str = Field(description="Deliberation stage: BEFORE_ADDITIONAL_EVIDENCE or AFTER_ADDITIONAL_EVIDENCE")
    action_type: str = Field(description="Remediation category (FREEZE_ACCOUNT, DECLINE_TRANSACTION, STEP_UP_MFA, etc.)")
    approval_tier: str = Field(description="Hierarchy of human authorization required (SUPERVISOR, ANALYST_TIER_1, LEGAL, AUTO)")
    approval_route: List[str] = Field(default_factory=list, description="Sequential authorization queues for compliance routing")
    reason: str = Field(description="Factual justification based on synthesized graph evidence")
    policy_reference: Optional[str] = Field(default=None, description="Mapped institutional compliance rule ID")
    executed: bool = Field(description="Execution readiness indicator")
    confidence: float = Field(description="Action confidence score based on case risk certainty")
    timestamp: str = Field(description="ISO 8601 decision timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "case_id": "CASE_2026_099",
                "stage": "BEFORE_ADDITIONAL_EVIDENCE",
                "action_type": "FREEZE_ACCOUNT",
                "approval_tier": "SUPERVISOR",
                "approval_route": ["FRAUD_ANALYST_QUEUE", "SUPERVISOR_REVIEW"],
                "reason": "Exceeded high-velocity syndicate threshold across 3 shared accounts.",
                "policy_reference": "RULE_FREEZE_001",
                "executed": False,
                "confidence": 0.92,
                "timestamp": "2026-09-20T12:00:00Z"
            }
        }
    }
