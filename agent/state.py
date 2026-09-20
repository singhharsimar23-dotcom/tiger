import time
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class CaseStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CLOSED = "CLOSED"
    RESOLVED = "RESOLVED"
    FLAGGED = "FLAGGED"

class FraudType(str, Enum):
    DEVICE_RING = "DEVICE_RING"
    ACCOUNT_TAKEOVER = "ACCOUNT_TAKEOVER"
    SYNTHETIC_IDENTITY = "SYNTHETIC_IDENTITY"
    BUST_OUT = "BUST_OUT"
    SMURFING = "SMURFING"
    UNCONFIRMED_ANOMALY = "UNCONFIRMED_ANOMALY"

class ApprovalTier(str, Enum):
    AUTOMATED_SYSTEM = "AUTOMATED_SYSTEM"
    AUTO = "AUTOMATED_SYSTEM"
    ANALYST_TIER_1 = "ANALYST_TIER_1"
    ANALYST = "ANALYST_TIER_1"
    FRAUD_OPS_LEAD = "FRAUD_OPS_LEAD"
    SUPERVISOR = "SUPERVISOR"
    SENIOR_COMPLIANCE_OFFICER = "SENIOR_COMPLIANCE_OFFICER"
    LEGAL = "LEGAL_COMPLIANCE"
    LEGAL_COMPLIANCE = "LEGAL_COMPLIANCE"

class ActionType(str, Enum):
    DECLINE_TRANSACTION = "DECLINE_TRANSACTION"
    FREEZE_ACCOUNT = "FREEZE_ACCOUNT"
    STEP_UP_MFA = "STEP_UP_MFA"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    FILE_SAR = "FILE_SAR"

class EvidenceType(str, Enum):
    GRAPH_NEIGHBORHOOD = "GRAPH_NEIGHBORHOOD"
    SHARED_DEVICE = "SHARED_DEVICE"
    SHARED_DOMAIN = "SHARED_DOMAIN"
    SHARED_ADDRESS = "SHARED_ADDRESS"
    PATTERN_MATCH = "PATTERN_MATCH"
    POLICY_TRIGGER = "POLICY_TRIGGER"
    PRIOR_CASE_SIMILARITY = "PRIOR_CASE_SIMILARITY"

class Evidence(BaseModel):
    evidence_id: str = ""
    evidence_type: EvidenceType = EvidenceType.GRAPH_NEIGHBORHOOD
    description: str = ""
    source: str = "AGENT"
    score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Decision(BaseModel):
    decision_id: str = ""
    verdict: str = "CONFIRMED_FRAUD"
    fraud_type: FraudType = FraudType.UNCONFIRMED_ANOMALY
    risk_level: RiskLevel = RiskLevel.MEDIUM
    confidence: float = 0.5
    fraud_probability: float = 0.5
    rationale: str = ""
    decided_by: str = "AUTONOMOUS_AGENT"
    timestamp: str = ""

class RecommendedAction(BaseModel):
    action_id: str = ""
    action_type: ActionType = ActionType.FLAG_FOR_REVIEW
    approval_tier: ApprovalTier = ApprovalTier.ANALYST_TIER_1
    reason: str = ""
    policy_reference: Optional[str] = None
    executed: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class InvestigationState(BaseModel):
    case_id: str = ""
    status: CaseStatus = CaseStatus.OPEN
    trigger_type: str = "RISK_SCORE"
    trigger_txn_ids: List[str] = Field(default_factory=list)
    trigger_account_id: Optional[str] = None
    trigger_risk_score: float = 0.0

    # Graph Entities & Subgraphs
    accounts: List[str] = Field(default_factory=list)
    transactions: List[str] = Field(default_factory=list)
    devices: List[str] = Field(default_factory=list)
    ip_clusters: List[str] = Field(default_factory=list)
    subgraph: Dict[str, Any] = Field(default_factory=dict)
    shared_identifiers: List[Dict[str, Any]] = Field(default_factory=list)
    money_flow: Dict[str, Any] = Field(default_factory=dict)

    # Typology & Policy Intelligence
    matched_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    matched_policies: List[Dict[str, Any]] = Field(default_factory=list)
    similar_cases: List[Dict[str, Any]] = Field(default_factory=list)

    # Evidence & Deliberation
    evidence_list: List[Evidence] = Field(default_factory=list)
    uncertainty_score: float = 1.0
    evidence_sufficiency_score: float = 1.0
    iteration_count: int = 0
    started_at: float = Field(default_factory=time.time)

    # Verdict & Compliance Output
    decision: Optional[Decision] = None
    recommended_actions: List[RecommendedAction] = Field(default_factory=list)
    action_before_additional_evidence: Optional[Any] = None
    action_after_additional_evidence: Optional[Any] = None
    case_summary: Optional[str] = None
    sar_narrative: Optional[str] = None
    sar_required: bool = False

    # Telemetry & Audit Trails
    decision_log: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[str] = Field(default_factory=list)

    @property
    def current_decision(self) -> Optional[Decision]:
        return self.decision

    @current_decision.setter
    def current_decision(self, val: Optional[Decision]) -> None:
        self.decision = val

