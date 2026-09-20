# HHGOA — GROUND TRUTH CORRECTIONS
> Read this FIRST, before HHGOA_MASTER_BUILD.md. Anywhere the two conflict, THIS FILE WINS.
> The master doc's LangGraph flow, MCP wiring, GraphRAG retrieval, and entropy-based
> stopping logic are still valid architecture. Everything below replaces guessed
> vocabulary with the real dataset's exact contract.

---

## 0. STILL NEEDED FROM YOU

`case_pack.csv` is done — all 20 rows written to `case_pack.csv` in this same output,
sourced verbatim from the README, no guessing.

Still required before S03 (data loading) can run for real:
- `transactions.csv` (708 MB, 590,742 rows) — column layout is now fully known (Section 3),
  don't need to see the file to write the loader, but need it to actually load.
  **Place at:** `data/transactions.csv`
- `identity.csv` (144,432 rows, online txns only) — same, columns known.
  **Place at:** `data/identity.csv`
- `closed_cases_history.csv` (5,565 rows) — this is the case memory corpus.
  **Place at:** `data/closed_cases_history.csv`

Upload these three (or point the loader at the Drive files once you've downloaded them
locally) before running S03/S12 for real.

---

## 1. GRAPH SCHEMA — REPLACES Master Doc Section 5

### Required base (from the brief — do not rename these)

```gsql
CREATE VERTEX Customer (
  PRIMARY_ID customer_id STRING          -- e.g. "C12382"
)

CREATE VERTEX Card (
  PRIMARY_ID card_id STRING,             -- e.g. "C12382-K1"
  card1 INT, card2 FLOAT, card3 FLOAT,
  card4 STRING,                          -- network: visa/mastercard/amex/discover
  card5 FLOAT,
  card6 STRING                           -- credit / debit
)

CREATE VERTEX Transaction (
  PRIMARY_ID txn_id STRING,              -- e.g. "T3514030" (prefix the raw TransactionID)
  transaction_dt INT,                    -- TransactionDT, seconds from dataset start
  ts DATETIME,                           -- real timestamp, added column
  transaction_amt FLOAT,
  product_cd STRING,                     -- W, C, H, R, S
  channel STRING,                        -- in_person | online (added column)
  risk_score FLOAT,                      -- bank model output, 0-1. INPUT NOT ANSWER.
  addr1 FLOAT, addr2 FLOAT,
  dist1 FLOAT, dist2 FLOAT,
  p_emaildomain STRING, r_emaildomain STRING,
  c_features_json STRING,                -- C1-C14, counts
  d_features_json STRING,                -- D1-D15, time deltas in days
  m_features_json STRING,                -- M1-M9, match flags
  v_features_json STRING                 -- V1-V339, Vesta engineered, unnamed
)

CREATE VERTEX DeviceProfile (
  PRIMARY_ID device_profile_id STRING,   -- hash of (DeviceInfo + id_30 OS + id_31 browser + id_33 screen)
  device_type STRING,                    -- mobile | desktop
  device_info STRING,
  os STRING, browser STRING, screen STRING,
  proxy_flag STRING,                     -- id_23: transparent/anonymous/hidden/none
  device_match STRING,                   -- id_15: New | Found
  id_features_json STRING                -- id_01-id_11 encoded ratings
)

CREATE VERTEX EmailDomain (
  PRIMARY_ID domain STRING
)

CREATE VERTEX BillingRegion (
  PRIMARY_ID region_code STRING          -- addr1 value; store addr2 (country) as attribute
  , country_code FLOAT
)

CREATE VERTEX ClosedCase (
  PRIMARY_ID case_id STRING,             -- e.g. "CC-0141"
  customer_id STRING, card_id STRING,
  opened_at DATETIME, closed_at DATETIME,
  outcome STRING,                        -- confirmed_fraud | cleared
  pattern STRING,                        -- one of the 7 pattern values, or "none"
  first_fraud_txn_id STRING,
  txn_ids_json STRING,                   -- pipe-separated in source -> JSON array here
  n_txns INT,
  exposure_usd FLOAT,
  connected_card_ids_json STRING,
  actions_taken STRING,
  report_filed BOOL,
  analyst_notes STRING,
  notes_embedding LIST<FLOAT>            -- for vector retrieval, embed analyst_notes + pattern
) WITH VECTOR="notes_embedding(dim=384)"
```

### Required edges (from the brief)

```gsql
CREATE DIRECTED EDGE OWNS (From Customer, To Card)
CREATE DIRECTED EDGE MADE (From Card, To Transaction)
CREATE DIRECTED EDGE FROM_DEVICE (From Transaction, To DeviceProfile)   -- online only
CREATE DIRECTED EDGE PURCHASER_EMAIL (From Transaction, To EmailDomain)
CREATE DIRECTED EDGE BILLED_IN (From Transaction, To BillingRegion)
CREATE DIRECTED EDGE NEXT (From Transaction, To Transaction)           -- ordered by ts, same card
CREATE DIRECTED EDGE CC_INVOLVES (From ClosedCase, To Transaction)
CREATE DIRECTED EDGE CC_ON_CARD (From ClosedCase, To Card)
CREATE DIRECTED EDGE CC_CONNECTED_TO (From ClosedCase, To Card)
```

### Your own additions (allowed — brief says "start here, then change it")

```gsql
CREATE VERTEX Case (                     -- the agent's OWN case, not ClosedCase
  PRIMARY_ID case_id STRING,             -- MUST equal the case_pack case_id: "HHG-001" etc.
  status STRING,                         -- open | closed_fraud | closed_legitimate | escalated
  verdict STRING,                        -- fraud | legitimate | uncertain
  fraud_probability FLOAT,
  pattern STRING,
  pattern_description STRING,
  exposure_usd FLOAT,
  summary STRING,
  graph_written BOOL,
  summary_embedding LIST<FLOAT>
) WITH VECTOR="summary_embedding(dim=384)"

CREATE VERTEX PolicyRule (
  PRIMARY_ID rule_id STRING,             -- "R1".."R10"
  rule_text STRING,
  rule_embedding LIST<FLOAT>
) WITH VECTOR="rule_embedding(dim=384)"

CREATE DIRECTED EDGE CASE_INVOLVES (From Case, To Transaction)
CREATE DIRECTED EDGE CASE_ON_CARD (From Case, To Card)
CREATE DIRECTED EDGE CASE_CONNECTED_TO (From Case, To Card)
CREATE UNDIRECTED EDGE CASE_SIMILAR_TO (From Case, To ClosedCase, similarity_score FLOAT)
```

### Retired from the original doc — do NOT build these

Account, IPCluster, Evidence-as-vertex, Decision-as-vertex, Action-as-vertex,
SHARES_DEVICE / SHARES_EMAIL_DOMAIN / SHARES_ADDRESS (precomputed pairwise edges).

**Why they're gone:** device/region/email sharing is a *query*, not a precomputed edge.
`Card → MADE → Transaction → FROM_DEVICE → DeviceProfile` — if that DeviceProfile has
other incoming `FROM_DEVICE` edges from transactions on *other* cards, that's your
shared-device signal, found live with one traversal.

---

## 2. THE REAL POLICY ENGINE — REPLACES Master Doc Sections 2.4, 2.5

### Actions (exact strings — used verbatim in output JSON)

```python
ACTIONS = [
    "ALLOW_TRANSACTION", "DECLINE_TRANSACTION", "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS", "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH", "BLOCK_CARD", "BLOCK_ALL_CARDS", "GENERATE_REPORT",
    "CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST", "CLOSE_NO_FRAUD",
]
```

### Approval routing (exact strings)

```python
APPROVAL_AUTO = {
    "ALLOW_TRANSACTION", "MONITOR_CARD", "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH",
    "GENERATE_REPORT", "CREATE_CASE", "ESCALATE_TO_ANALYST", "CLOSE_NO_FRAUD",
}
# DECLINE_TRANSACTION -> always L1
# BLOCK_CARD -> L1 if exposure_usd <= 2500 else L2
# BLOCK_ALL_CARDS -> always L2
# FILE_REPORT -> always L2
```

### Rules R1-R10

- **R1**: Verify before you block on a weak signal. Single signal + fraud_probability < 0.70 → VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block.
- **R2**: Customer denies → BLOCK_CARD + CREATE_CASE. Add FILE_REPORT if exposure > $1,000 or shared device/card fraud.
- **R3**: Customer confirms → CLOSE_NO_FRAUD.
- **R4**: No reply 24h → MONITOR_CARD + DECLINE_TRANSACTION pending. Escalate if exposure > $500.
- **R5**: Card testing (3+ small online auths in 1h then larger purchase) → DECLINE_TRANSACTION + STEP_UP_AUTH. If >$100 cleared → BLOCK_CARD.
- **R6**: Shared origin (same device/billing/email across cards) → CREATE_CASE + FILE_REPORT + MONITOR_CONNECTED_CARDS.
- **R7**: Disputed but legitimate (recurring pattern) → CREATE_CASE + VERIFY_WITH_CUSTOMER + WARN_CUSTOMER. No block.
- **R8**: Uncertain + exposure > $500 or conflicting evidence → ESCALATE_TO_ANALYST.
- **R9**: Undocumented coordinated abuse → CREATE_CASE + FILE_REPORT + ESCALATE_TO_ANALYST. Describe pattern; don't force into known category.
- **R10**: Never BLOCK_ALL_CARDS unless 2+ cards show confirmed fraud or credentials confirmed compromised.

### Stopping rule

```python
def should_stop(fraud_probability, independent_evidence_count,
                verification_settled, iteration_count):
    if verification_settled:
        return True, "A verification response settled the question."
    if (fraud_probability >= 0.85 or fraud_probability <= 0.15) and independent_evidence_count >= 2:
        return True, f"Fraud probability {fraud_probability:.2f} with {independent_evidence_count} independent evidence pieces meets the confidence threshold."
    if iteration_count >= 3:
        return True, "Further steps are unlikely to change the decision after 3 evidence-gathering rounds."
    return False, ""
```

MDL/entropy (`innovation/mdl_gate.py`) picks the **next best question**; the 0.85/0.15
threshold with dual independent evidence decides **when to stop asking**.

---

## 3. REAL COLUMN LAYOUTS

**transactions.csv** — 393 original Vesta columns + 4 added:
`TransactionID, TransactionDT, TransactionAmt, ProductCD, card1-card6, addr1, addr2,
dist1, dist2, P_emaildomain, R_emaildomain, C1-C14, D1-D15, M1-M9, V1-V339,
customer_id, ts, channel, risk_score`

**identity.csv** — 41 original columns, online txns only, joins on TransactionID:
`TransactionID, id_01-id_11 (numeric ratings), id_12-id_38 (categorical — readable ones:
id_15 device New/Found, id_23 proxy transparent/anonymous/hidden, id_30 OS, id_31
browser, id_33 screen, id_34 match status), DeviceType, DeviceInfo`

**closed_cases_history.csv**:
`case_id, customer_id, card_id, opened_at, closed_at, outcome, pattern,
first_fraud_txn_id, txn_ids (pipe-separated), n_txns, exposure_usd,
connected_card_ids, actions_taken, report_filed, analyst_notes`

**IDs are disguised** — do NOT touch the public Kaggle IEEE-CIS file for anything.

---

## 4. REAL OUTPUT FORMAT

**One JSON file per case.** Filename `<case_id>.json` in `cases/` folder.
Old 4-file-per-case OutputFormatter (S11) is scrapped.

```python
class Evidence(BaseModel):
    claim: str
    source: Literal["graph", "document", "customer", "external"]
    ref: str
    entity_ids: list[str]

class EvidenceRequest(BaseModel):
    type: Literal["customer_validation", "step_up_auth", "analyst_info"]
    asked_after_step: int
    assumed_response: str

class ActionRec(BaseModel):
    action: str       # one of the 14 ACTIONS, exact string
    route: Literal["auto", "L1", "L2"]
    reason: str       # MUST cite rule number e.g. "R2: customer denied..."

class NextBestActions(BaseModel):
    initial: list[ActionRec]
    final: list[ActionRec]
    what_changed: str

class Case(BaseModel):
    status: Literal["open", "closed_fraud", "closed_legitimate", "escalated"]
    verdict: Literal["fraud", "legitimate", "uncertain"]
    fraud_probability: float
    pattern: Literal["card_testing", "card_not_present_fraud",
                      "card_not_present_new_device", "out_of_region_use",
                      "account_takeover", "undocumented", "none"]
    pattern_description: str
    affected_txn_ids: list[str]
    first_suspicious_txn_id: str
    connected_card_ids: list[str]
    connected_device_profiles: list[str]
    exposure_usd: float
    evidence: list[Evidence]
    similar_prior_cases: list[str]
    summary: str
    written_to_graph: bool
    graph_case_id: str

class SAR(BaseModel):
    file: bool
    reason: str
    narrative: str
    subjects: list[str]
    total_amount_usd: float
    activity_dates: list[str]

class CaseAnswer(BaseModel):
    case_id: str
    case: Case
    evidence_requests: list[EvidenceRequest]
    next_best_actions: NextBestActions
    sar: SAR
    stop_reason: str
    tool_calls: int
    tokens: int
    latency_s: float
```

**Hard validation assertions (run before submission):**
- `case_id` matches filename and a real row in `case_pack.csv`
- Every ID in `affected_txn_ids`, `connected_card_ids`, `similar_prior_cases` actually exists in loaded dataset
- `sar.file == True` ↔ `FILE_REPORT` in `next_best_actions.final`
- `verdict == "legitimate"` → `affected_txn_ids == []`, `exposure_usd == 0`, `sar.file == False`
- `pattern == "undocumented"` → `pattern_description != ""`

---

## 5. LangGraph STATE — DELTA

```python
class ActionType(str, Enum):
    ALLOW_TRANSACTION = "ALLOW_TRANSACTION"
    DECLINE_TRANSACTION = "DECLINE_TRANSACTION"
    MONITOR_CARD = "MONITOR_CARD"
    MONITOR_CONNECTED_CARDS = "MONITOR_CONNECTED_CARDS"
    WARN_CUSTOMER = "WARN_CUSTOMER"
    VERIFY_WITH_CUSTOMER = "VERIFY_WITH_CUSTOMER"
    STEP_UP_AUTH = "STEP_UP_AUTH"
    BLOCK_CARD = "BLOCK_CARD"
    BLOCK_ALL_CARDS = "BLOCK_ALL_CARDS"
    GENERATE_REPORT = "GENERATE_REPORT"
    CREATE_CASE = "CREATE_CASE"
    FILE_REPORT = "FILE_REPORT"
    ESCALATE_TO_ANALYST = "ESCALATE_TO_ANALYST"
    CLOSE_NO_FRAUD = "CLOSE_NO_FRAUD"

class ApprovalRoute(str, Enum):
    AUTO = "auto"; L1 = "L1"; L2 = "L2"

class Pattern(str, Enum):
    CARD_TESTING = "card_testing"
    CNP_FRAUD = "card_not_present_fraud"
    CNP_NEW_DEVICE = "card_not_present_new_device"
    OUT_OF_REGION = "out_of_region_use"
    ACCOUNT_TAKEOVER = "account_takeover"
    UNDOCUMENTED = "undocumented"
    NONE = "none"
```

Trigger dict for `run_investigation()`:
```python
{
  "case_id": "HHG-001",
  "trigger_type": "risk_score",           # risk_score | customer_report | analyst_request
  "flagged_txn_id": "T3514030",
  "card_id": "C12382-K1",
  "customer_id": "C12382",
  "risk_score": 0.61,
  "trigger_text": "...",
}
```

---

## 6. CODING AGENT STOP NOTICE

```
STOP. Before continuing any HHGOA session work, read
HHGOA_GROUND_TRUTH_CORRECTIONS.md in full. It overrides HHGOA_MASTER_BUILD.md
wherever the two conflict — schema (Section 5), action/approval vocabulary
(Sections 2.4-2.5), output file format (Section 10), and case IDs throughout.

If you already built S02 (schema), S05 (queries), S08 (state/prompts), or S11
(output formatter) against the OLD vocabulary, redo those four sessions against
this corrected doc before proceeding to S12 (benchmark run). Everything else
(S01 scaffold, S06 MCP wiring, S07 GraphRAG, S09 MDL/entropy math, S13 dashboard
shell) is still structurally valid — only the vocabulary inside them needs updating.

Do not invent any ID, action name, or approval tier not listed in this document.
Every action string, route string, and pattern string is graded verbatim.
```

*This file is the source of truth. HHGOA_MASTER_BUILD.md is architecture reference
only — never pull vocabulary, schema, or output shape from it once this file exists.*
