import pytest
import asyncio
from tools import tg_tools

@pytest.mark.asyncio
async def test_get_policy_rules():
    """Verify get_policy_rules returns matched policies."""
    rules = await tg_tools.get_policy_rules(txn_amt=5000.0, risk_score=0.75)
    assert isinstance(rules, list), "Expected list of rules"
    assert len(rules) >= 1, "Expected at least 1 policy rule returned for risk_score=0.75"

@pytest.mark.asyncio
async def test_case_lifecycle():
    """Verify case creation, status update, and closure lifecycle."""
    # 1. Create case with dummy transaction ID
    case_id = await tg_tools.create_or_get_case(
        trigger_txn_ids=["T_XXXX"],
        trigger_type="ANALYST_REQUEST",
        risk_score=0.5
    )
    assert isinstance(case_id, str)
    assert len(case_id) > 0, "Expected non-empty case_id"

    # 2. Update case
    update_ok = await tg_tools.update_case(
        case_id,
        status="INVESTIGATING",
        fraud_prob=0.82,
        risk_level="HIGH"
    )
    assert update_ok is True

    # 3. Add Evidence
    ev_ok = await tg_tools.add_evidence(
        case_id,
        [{"evidence_type": "DEVICE_COLLUSION", "description": "Shared device anomaly", "score": 0.88}]
    )
    assert ev_ok is True

    # 4. Close case
    close_ok = await tg_tools.close_case(case_id, disposition="CONFIRMED_FRAUD")
    assert close_ok is True

@pytest.mark.asyncio
async def test_tool_call_logging():
    """Verify tool calls are registered in tool history."""
    history = tg_tools.get_tool_call_history()
    assert isinstance(history, list)
    assert len(history) > 0, "Expected tool calls to be recorded in history"
