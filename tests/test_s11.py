"""
Unit tests for S11: Structured Output Generation.
Validates generation of:
- case_record.json
- sar.json
- action_before.json
- action_after.json
Verifies schema compliance, approval routing, and file integrity.
"""

import json
import time
from pathlib import Path
import pytest

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
from output.formatter import OutputFormatter


@pytest.fixture
def mock_investigation_state() -> InvestigationState:
    """Creates a rich, realistic InvestigationState for testing export formats."""
    return InvestigationState(
        case_id="CASE_2026_099",
        status=CaseStatus.RESOLVED,
        trigger_type="HIGH_RISK_RULE",
        trigger_txn_ids=["T_2987000", "T_2987001"],
        trigger_account_id="ACC_13926_0_315",
        trigger_risk_score=0.91,
        accounts=["ACC_13926_0_315", "ACC_4461_375_184", "ACC_1804_161_269"],
        devices=["DEV_WINDOWS_CHROME_89"],
        ip_clusters=["IP_49182301"],
        matched_patterns=[
            {"pattern_id": "PAT_001_DEVICE_RING", "name": "Device Sharing Ring", "confidence": 1.0}
        ],
        matched_policies=[
            {"v_id": "RULE_SAR_001", "name": "Mandatory SAR Filing", "action_type": "FILE_SAR"}
        ],
        similar_cases=[
            {"case_id": "CASE_2026_001", "score": 0.95, "summary_excerpt": "Device syndicate"}
        ],
        evidence_list=[
            Evidence(
                evidence_id="EVID_001",
                evidence_type=EvidenceType.SHARED_DEVICE,
                description="3 distinct accounts transacting via single physical device",
                score=0.95,
                source="GRAPH_EXPANSION"
            ),
            Evidence(
                evidence_id="EVID_002",
                evidence_type=EvidenceType.PATTERN_MATCH,
                description="Coordinated transaction timing within 120s window",
                score=0.88,
                source="TEMPORAL_ANALYSIS"
            )
        ],
        uncertainty_score=0.10,
        evidence_sufficiency_score=0.05,
        iteration_count=2,
        started_at=time.time() - 3.2,
        decision=Decision(
            decision_id="DEC_2026_099",
            verdict="CONFIRMED_FRAUD",
            fraud_type=FraudType.DEVICE_RING,
            risk_level=RiskLevel.HIGH,
            confidence=0.95,
            fraud_probability=0.95,
            rationale="Definitive hardware device sharing across non-familial accounts with rapid velocity.",
            decided_by="AUTONOMOUS_INVESTIGATION_AGENT",
            timestamp="2026-09-20T12:00:00Z"
        ),
        recommended_actions=[
            RecommendedAction(
                action_id="ACT_01",
                action_type=ActionType.FREEZE_ACCOUNT,
                approval_tier=ApprovalTier.SUPERVISOR,
                reason="Coordinated syndicate risk requires immediate fund containment.",
                policy_reference="RULE_FREEZE_001",
                executed=False
            ),
            RecommendedAction(
                action_id="ACT_02",
                action_type=ActionType.FILE_SAR,
                approval_tier=ApprovalTier.LEGAL_COMPLIANCE,
                reason="Regulatory AML threshold exceeded.",
                policy_reference="RULE_SAR_001",
                executed=True
            )
        ],
        action_before_additional_evidence=RecommendedAction(
            action_id="ACT_01",
            action_type=ActionType.FLAG_FOR_REVIEW,
            approval_tier=ApprovalTier.ANALYST_TIER_1,
            reason="Preliminary alert screening.",
            policy_reference="RULE_MONITOR_001"
        ),
        action_after_additional_evidence=RecommendedAction(
            action_id="ACT_02",
            action_type=ActionType.FREEZE_ACCOUNT,
            approval_tier=ApprovalTier.SUPERVISOR,
            reason="Post-expansion evidence confirms syndicated fraud.",
            policy_reference="RULE_FREEZE_001"
        ),
        case_summary="Multi-account synthetic identity syndicate operating across shared device fingerprints.",
        sar_narrative="On September 20, 2026, investigative telemetry confirmed coordinated fraud across accounts ACC_13926_0_315 and ACC_4461_375_184.",
        sar_required=True,
        decision_log=[
            {"stage": "mdl_gate", "summary": "Evidence sufficiency threshold met"}
        ],
        tool_calls=["get_txn_neighborhood", "get_shared_identifiers", "get_policy_rules"]
    )


def test_output_formatter_creates_four_files(mock_investigation_state: InvestigationState, tmp_path: Path):
    """
    Assert:
    - 4 files created in outputs/cases/case_99/
    - case_record.json is valid JSON with required keys
    - action_before.json has 'stage' = 'BEFORE_ADDITIONAL_EVIDENCE'
    - sar.json has 'sar_required' key
    """
    formatter = OutputFormatter(output_dir=str(tmp_path))
    case_dir = formatter.format_and_save(mock_investigation_state, case_number=99)

    assert case_dir.exists(), "Case directory should be created"
    assert case_dir.name == "case_99"

    # 1. Verify 4 files exist
    expected_files = ["case_record.json", "sar.json", "action_before.json", "action_after.json"]
    for fname in expected_files:
        fpath = case_dir / fname
        assert fpath.is_file(), f"File {fname} was not created"

    # 2. Verify case_record.json structure
    with open(case_dir / "case_record.json", "r", encoding="utf-8") as f:
        case_rec = json.load(f)

    assert case_rec["case_id"] == "CASE_2026_099"
    assert case_rec["case_number"] == 99
    assert "investigation_duration_seconds" in case_rec
    assert case_rec["investigation_duration_seconds"] > 0
    assert case_rec["status"] == "RESOLVED"
    assert case_rec["evidence_count"] == 2
    assert "decision" in case_rec
    assert case_rec["decision"]["verdict"] == "CONFIRMED_FRAUD"
    assert "mdl_sufficiency_score" in case_rec
    assert "decision_log" in case_rec

    # 3. Verify action_before.json
    with open(case_dir / "action_before.json", "r", encoding="utf-8") as f:
        act_before = json.load(f)

    assert act_before["stage"] == "BEFORE_ADDITIONAL_EVIDENCE"
    assert "action_type" in act_before
    assert "approval_route" in act_before
    assert isinstance(act_before["approval_route"], list)

    # 4. Verify action_after.json
    with open(case_dir / "action_after.json", "r", encoding="utf-8") as f:
        act_after = json.load(f)

    assert act_after["stage"] == "AFTER_ADDITIONAL_EVIDENCE"
    assert act_after["approval_tier"] == "SUPERVISOR"
    assert "SUPERVISOR_REVIEW" in act_after["approval_route"]

    # 5. Verify sar.json
    with open(case_dir / "sar.json", "r", encoding="utf-8") as f:
        sar = json.load(f)

    assert "sar_required" in sar
    assert sar["sar_required"] is True
    assert sar["filing_tier"] == "TIER_1_EXPEDITED"
    assert "sar_narrative" in sar
    assert "On September 20, 2026" in sar["sar_narrative"]
    assert sar["compliance_officer_signoff"] == "AUTONOMOUS_FRAUD_INVESTIGATION_AGENT"


def test_action_after_fallback_when_zero_iterations(tmp_path: Path):
    """
    Constraint: If additional evidence was NOT gathered (iterations <= 1):
    action_after = action_before (same content, different stage label).
    """
    state = InvestigationState(
        case_id="CASE_ZERO_ITER",
        iteration_count=0,
        recommended_actions=[
            RecommendedAction(
                action_id="ACT_INIT",
                action_type=ActionType.FLAG_FOR_REVIEW,
                approval_tier=ApprovalTier.ANALYST_TIER_1,
                reason="Initial screening."
            )
        ]
    )
    formatter = OutputFormatter(output_dir=str(tmp_path))
    case_dir = formatter.format_and_save(state, case_number=1)

    with open(case_dir / "action_before.json", "r", encoding="utf-8") as f:
        act_before = json.load(f)
    with open(case_dir / "action_after.json", "r", encoding="utf-8") as f:
        act_after = json.load(f)

    assert act_before["stage"] == "BEFORE_ADDITIONAL_EVIDENCE"
    assert act_after["stage"] == "AFTER_ADDITIONAL_EVIDENCE"
    assert act_before["action_type"] == act_after["action_type"]
    assert act_before["approval_tier"] == act_after["approval_tier"]
    assert act_before["reason"] == act_after["reason"]
