import os
import pytest
from agent.state import (
    RiskLevel,
    CaseStatus,
    FraudType,
    ApprovalTier,
    ActionType,
    EvidenceType,
    Evidence,
    Decision,
    RecommendedAction,
    InvestigationState,
)
from agent import prompts
from agent.llm import call_llm_json

def test_enums_defined():
    """Verify all investigation state enums have required values."""
    assert RiskLevel.LOW.value == "LOW"
    assert RiskLevel.CRITICAL.value == "CRITICAL"

    assert CaseStatus.OPEN.value == "OPEN"
    assert CaseStatus.CLOSED.value == "CLOSED"

    assert FraudType.DEVICE_RING.value == "DEVICE_RING"
    assert FraudType.ACCOUNT_TAKEOVER.value == "ACCOUNT_TAKEOVER"

    assert ApprovalTier.AUTOMATED_SYSTEM.value == "AUTOMATED_SYSTEM"
    assert ApprovalTier.SENIOR_COMPLIANCE_OFFICER.value == "SENIOR_COMPLIANCE_OFFICER"

    assert ActionType.DECLINE_TRANSACTION.value == "DECLINE_TRANSACTION"
    assert ActionType.FILE_SAR.value == "FILE_SAR"

    assert EvidenceType.SHARED_DEVICE.value == "SHARED_DEVICE"
    assert EvidenceType.PATTERN_MATCH.value == "PATTERN_MATCH"

def test_prompts_defined_and_formatted():
    """Verify all 4 core prompts exist and contain format placeholders."""
    all_prompts = [
        prompts.EVIDENCE_SYNTHESIS_PROMPT,
        prompts.RISK_ASSESSMENT_PROMPT,
        prompts.ACTION_SELECTION_PROMPT,
        prompts.CASE_SUMMARY_PROMPT,
    ]
    for p in all_prompts:
        assert isinstance(p, str)
        assert len(p.strip()) > 50
        assert "{case_id}" in p

@pytest.mark.asyncio
async def test_call_llm_json_structure():
    """Verify call_llm_json returns a valid dictionary."""
    test_template = "Return a JSON object for case {case_id} with status: active."
    res = await call_llm_json(test_template, {"case_id": "CASE_TEST_001"})
    assert isinstance(res, dict)
    assert len(res) > 0

def test_investigation_state_defaults():
    """Verify initial defaults on InvestigationState."""
    state = InvestigationState(
        trigger_type="RISK_SCORE",
        trigger_txn_ids=["T_100"],
        trigger_risk_score=0.88
    )
    assert state.status == CaseStatus.OPEN
    assert state.uncertainty_score == 1.0
    assert state.iteration_count == 0
    assert isinstance(state.evidence_list, list)
    assert isinstance(state.tool_calls, list)
    assert isinstance(state.decision_log, list)
