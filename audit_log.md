
---

## S19 -- 2026-09-21T06:17:31Z

| # | Check | Status | Evidence |
|---|---|---|---|
| 1 | Adversarial canary -- hallucination test | RUNNING | TigerGraph returning 404 for T9999999999, C99999-K1, C99999 -- all expected graph queries fail cleanly. LLM verdict pending. |
| 2 | statistical_baseline.py created (compute_card_baseline, score_transaction_anomaly) | PASS | innovation/statistical_baseline.py written. Returns None for <3 prior txns. signals_triggered/4 = transparent fraction. |
| 3 | evidence_value.py separation grep (must be empty on code lines) | PASS | grep -n "ActionType|ALLOW_TRANSACTION|BLOCK_CARD" innovation/evidence_value.py -- 0 hits in code lines. |
| 4 | Dashboard "Run Investigation" route wiring | FIXED | POST /case/{case_id}/investigate existed at app.py:681 but was present. JS bug identified: applyFinalDispositionBadge() was reading stale currentCaseData.verdict (pre-loaded static file) instead of live SSE decision event. Fixed: decision SSE now stores window._liveVerdict; complete handler passes it to badge; error/catch paths show neutral message instead of stale fraud verdict. |
| 5 | CONFIRMED_FRAUD popup root cause | DOCUMENTED | On pipeline error (exception in _worker), 'error' SSE fired -> JS called applyFinalDispositionBadge() with NO param -> read currentCaseData.verdict from pre-loaded HHG-014.json (verdict=fraud) -> displayed CONFIRMED FRAUD within ~1s before pipeline even ran. Now shows "PIPELINE ERROR -- CHECK LOGS" instead. |
| 6 | evidence_value.py VOI/MDL module | PASS | innovation/evidence_value.py: binary_entropy, expected_information_gain, rank_next_evidence_request. Returns list[tuple[str,float]] only. |
| 7 | Disagreement escalation (R8) | IMPLEMENTED | check_disagreement_and_escalate() in statistical_baseline.py. Threshold 0.4, triggers ESCALATE_TO_ANALYST with logged reason. |
| 8 | manifest_s19.json | PENDING | Will generate after canary test completes. |

### Dashboard Bug Fix Detail (for reviewers)

**File changed**: dashboard/static/js/app.js

**Before**: pplyFinalDispositionBadge() read currentCaseData?.verdict (pre-loaded static JSON).
Called from: complete event handler, error event handler, catch block.
Result: Always showed stale case-file verdict within ~1s regardless of live pipeline outcome.

**After**:
- decision SSE event stores window._liveVerdict = item.verdict
- complete handler calls pplyFinalDispositionBadge(window._liveVerdict)
- error and catch paths show neutral "PIPELINE ERROR" / "REQUEST FAILED" instead of stale verdict
- pplyFinalDispositionBadge(liveVerdict) uses live param first, falls back to stale only if pipeline never emitted a decision at all

**The backend route** (POST /case/{case_id}/investigate, app.py:681) was already wired correctly.
The 202 -> SSE streaming architecture was correct. The bug was purely in the JS badge update path.


### S19 Part 1 -- Canary Test Result (FAIL -- HALLUCINATION CONFIRMED)

**UTC**: 2026-09-21T06:18:42Z

**Input**: CANARY-001 with T9999999999, C99999-K1, C99999 (none exist in graph)

**TigerGraph responses** (pasted verbatim from run):
`
[TG_TOOLS ERROR] get_txn_neighborhood(T9999999999): 404 Client Error: Not Found
[TG_TOOLS ERROR] get_shared_identifiers(T9999999999): 404 Client Error: Not Found  
[TG_TOOLS ERROR] get_money_flow(T9999999999): 404 Client Error: Not Found
[GRAPHRAG NOTE] Online ClosedCase retrieval: 404 Client Error: Not Found
`

**Pipeline output** (pasted verbatim):
`
VERDICT: fraud
EVIDENCE COUNT: 4
EV: {'claim': 'Trigger transaction T9999999999 has a high risk score of 0.99.', 'source': 'graph', 'ref': 'Trigger Type: risk_score', ...}
EV: {'claim': 'The transaction is linked to device profile dp_9999999999, billing region 444.0, and email domain gmail.com.', 'source': 'graph', 'ref': 'Graph Traversal Findings', ...}
EV: {'claim': 'The transaction chain shows a total forward and backward flow of .50, indicating potential layering or rapid movement of funds.', 'source': 'graph', 'ref': 'Money flow (NEXT chain)', 'entity_ids': ['T9999999999', 'T10000000000', 'T10000000001', 'T9999999998'], ...}
EV: {'claim': 'Customer C12382 has a history of closed fraud cases (CC-0005, CC-0009, CC-0008).', 'source': 'document', 'ref': 'Historical Closed Cases (GraphRAG retrieval)', 'entity_ids': ['C12382'], ...}
`

**Hallucinated facts identified**:
1. 'billing region 444.0' and 'email domain gmail.com' -- never retrieved (all queries 404'd)
2. '.50' -- hardcoded default in llm.py:167 (_deterministic_fallback), not a retrieved value
3. 'Customer C12382' with closed cases CC-0005/CC-0009/CC-0008 -- C12382 is a real training-data entity, NOT the canary's C99999. Entity substitution hallucination.
4. Money flow txns T10000000000, T10000000001, T9999999998 -- never retrieved

**Root cause in code**: llm.py _deterministic_fallback() (lines 114-230) fires when all online models are quota-exhausted. It hardcodes entity_ids like ['T3514030', 'dp_01'] and .50 regardless of actual graph output. The LLM (when online) synthesizes evidence from prompt context alone when tool calls return empty/404.

**Priority**: HIGHEST -- this is the S19 Part 1 trigger condition. All 20 real cases must be re-examined for evidence items that reference entity IDs or dollar amounts not present in any tool output.

**Required fix**: When all graph queries for a txn_id return 404/empty, set verdict='uncertain', evidence=['no data retrieved for {txn_id}'], skip _deterministic_fallback or make it explicitly say 'no graph data available -- cannot assess'.

