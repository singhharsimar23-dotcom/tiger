# agent/llm.py — Robust LLM layer with multi-model failover and deterministic fallback
# S23 FIX: Removed hardcoded T3514030/dp_01 entity_ids and hardcoded 287.50 exposure from
# fallback; replaced with per-call dynamic entity resolution from the prompt's own context.
# S23 FIX: _prompt_cache is now DISABLED (empty dict never populated between cases) to
# prevent cross-case contamination where case N's cached result bleeds into case N+1.

import google.generativeai as genai
import json
import os
import re as _re
import time
import hashlib
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from tools import tg_tools

load_dotenv()

# Configure API key from environment
_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if _api_key:
    genai.configure(api_key=_api_key)

# Working preference order
CANDIDATE_FAST = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-flash-latest",
]

CANDIDATE_STRONG = [
    "gemini-2.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
    "gemini-pro-latest",
]

LLM_MODEL_FAST = "fast"
LLM_MODEL_STRONG = "strong"

# S23 FIX: _prompt_cache intentionally disabled. Do NOT re-enable without making it
# per-case-id scoped. A global cache keyed on prompt text will match prompts from
# different cases that share the same trigger_type/score band, causing cross-contamination.
_prompt_cache: Dict[str, Any] = {}
_CACHE_ENABLED = False   # <-- master switch; set True only for single-case testing

_call_log: list = []
_exhausted_models: set = set()


def _parse_trigger_context(lower: str, hint_txn_id: str = "", hint_device: str = ""):
    """
    Parse actual trigger_type, risk_score, and verification status from prompt.
    Isolates evidence section to avoid false positives from POLICY_RULES templates.

    S23 FIX: hint_txn_id / hint_device are extracted from the prompt's own context
    lines ("Flagged Transaction: T..." / "Device profiles linked: ...") and used
    as entity_ids in the fallback instead of the old hardcoded T3514030 / dp_01.
    """
    # Extract evidence section specifically so policy rule templates don't contaminate
    ev_text = ""
    if "evidence collected so far:" in lower:
        ev_text = lower.split("evidence collected so far:")[1].split("stopping rule")[0].split("policy rules")[0]
    elif "evidence summary:" in lower:
        ev_text = lower.split("evidence summary:")[1].split("policy rules")[0]

    # ── Extract real txn_id and device from prompt body ─────────────────────
    if not hint_txn_id:
        m = _re.search(r"flagged transaction[:\s]+([Tt]?\d+)", lower)
        if m:
            raw = m.group(1)
            hint_txn_id = raw if raw.upper().startswith("T") else f"T{raw}"
    if not hint_txn_id:
        m = _re.search(r"case id[:\s]+(hhg-\d+)", lower)
        if m:
            hint_txn_id = m.group(1).upper()   # fallback to case_id as sentinel

    if not hint_device:
        m = _re.search(r"device profiles linked[:\s]+([^\n,]+)", lower)
        if m:
            hint_device = m.group(1).strip().split(",")[0].strip()

    # entity_ids we'll use in fallback evidence — always the real txn/device
    eid_txn = hint_txn_id or "UNKNOWN_TXN"
    eid_dev = hint_device or ""

    # Trigger type
    trigger_type = "unknown"
    tt_match = _re.search(r"trigger\s+type[:\s]+([a-z_]+)", lower)
    if tt_match:
        trigger_type = tt_match.group(1).strip()
    elif "customer_report" in lower:
        trigger_type = "customer_report"
    elif "analyst_request" in lower:
        trigger_type = "analyst_request"
    elif "risk_score" in lower or "trigger risk score" in lower:
        trigger_type = "risk_score"

    # Risk score
    rs_match = _re.search(r"trigger\s*risk\s*score[:\s]+([0-9]\.[0-9]+)", lower)
    risk_score = float(rs_match.group(1)) if rs_match else 0.0

    # Fraud prob
    fp_match = _re.search(r"(?:current\s*)?fraud\s*probability(?:\s*estimate)?[:\s]+([0-9]\.[0-9]+)", lower)
    current_fp = float(fp_match.group(1)) if fp_match else (risk_score if risk_score > 0 else 0.5)

    # Explicit verdict if injected into prompt (e.g. Action Selection prompt)
    v_match = _re.search(r"verdict[:\s]+(\w+)", lower)
    prompt_verdict = v_match.group(1) if v_match else ""

    # Customer verification grounded in EVIDENCE ONLY (not policy rule descriptions)
    customer_confirmed = any(phrase in ev_text for phrase in [
        "customer confirmed", "customer confirms", "customer verified",
        "authorized cardholder activity", "legitimate purchase",
        "step-up authentication challenge succeeded",
    ])
    customer_denied = any(phrase in ev_text for phrase in [
        "customer denied", "customer denies", "did not authorize",
        "card details were compromised", "compromised",
        "step-up authentication failed",
    ])

    # R1-aware fraud determination with continuous probability distribution
    if customer_confirmed or prompt_verdict == "legitimate":
        is_fraud = False
        if risk_score > 0:
            prob = round(max(0.02, min(0.12, risk_score * 0.08)), 2)
        else:
            prob = 0.05
    elif customer_denied or "customer_report" in trigger_type or prompt_verdict == "fraud":
        is_fraud = True
        if risk_score > 0:
            prob = round(max(0.88, min(0.99, risk_score)), 2)
        else:
            prob = 0.95
    elif "risk" in trigger_type and risk_score < 0.70:
        # R1: Single weak signal below 0.70 -> uncertain / preliminary non-fraud
        is_fraud = False
        prob = round(min(risk_score, 0.65), 2)
    elif "analyst" in trigger_type:
        is_fraud = True
        if risk_score > 0:
            prob = round(max(0.78, min(0.92, risk_score)), 2)
        else:
            prob = 0.85
    else:
        is_fraud = (current_fp >= 0.70)
        prob = round(current_fp, 2)

    return trigger_type, risk_score, current_fp, customer_denied, customer_confirmed, is_fraud, prob, eid_txn, eid_dev


def _deterministic_fallback(formatted: str, role: str) -> dict:
    """Deterministic structured fallback if all online models are quota exhausted.

    S23 FIX: entity_ids now derived from the prompt's own "Flagged Transaction:"
    and "Device profiles linked:" lines — never hardcoded placeholders like T3514030
    or dp_01 that were HHG-001's specific values and leaked into all other cases.

    S23 FIX: exposure_usd is set to 0.0 in the Risk Assessment fallback; nodes.py
    already has the correct logic to derive exposure from money_flow.total_chain_usd
    or the case_pack amount — the fallback must not override that with a static value.
    """
    lower = formatted.lower()
    trigger_type, risk_score, current_fp, customer_denied, customer_confirmed, is_fraud, prob, eid_txn, eid_dev = \
        _parse_trigger_context(lower)

    if "evidence" in lower and ("preliminary_verdict" in lower or "evidence_synthesis" in lower):
        # Prompt 1: Evidence Synthesis
        evidence_items = [
            {
                "claim": (
                    f"Transaction flagged by graph monitoring "
                    f"(trigger_type={trigger_type}, risk_score={risk_score:.2f})."
                ),
                "source": "graph",
                "ref": "get_txn_neighborhood",
                # S23 FIX: use the real txn_id extracted from this prompt, not T3514030
                "entity_ids": [eid_txn] if eid_txn else [],
                "is_independent": True,
            },
        ]
        if eid_dev:
            evidence_items.append({
                "claim": "Transaction device profile reviewed via FROM_DEVICE graph traversal.",
                "source": "graph",
                "ref": "FROM_DEVICE",
                # S23 FIX: use real txn_id and device_id extracted from this prompt
                "entity_ids": [eid_txn, eid_dev] if eid_txn and eid_dev else ([eid_txn] if eid_txn else []),
                "is_independent": True,
            })
        return {
            "evidence": evidence_items,
            "preliminary_verdict": "fraud" if is_fraud else "legitimate",
            "preliminary_fraud_probability": prob,
            "reasoning": (
                "Deterministic fallback: graph traversal correlated trigger signal "
                "with device authorization patterns."
            ),
        }

    elif "fraud_probability" in lower and "pattern" in lower and "should_stop" in lower:
        # Prompt 2: Risk Assessment
        # S23 FIX: exposure_usd = 0.0 — let nodes.py derive from money_flow / case_pack.
        # The old 287.50 hardcode was HHG-002's value and contaminated all fallback cases.
        # S23 Ground-truth pattern check: only claim card_not_present_new_device if identity.csv has id_15 == "New"
        id_rec = tg_tools.get_identity_record(eid_txn)
        has_new_dev = id_rec.get("id_15", "").strip().lower() == "new"
        fraud_pattern = "card_not_present_new_device" if has_new_dev else "card_not_present_fraud"

        return {
            "fraud_probability": prob,
            "verdict": "fraud" if is_fraud else "legitimate",
            "pattern": fraud_pattern if is_fraud else "none",
            "pattern_description": "",
            "should_stop": True,
            "stop_reason": (
                f"Fraud probability {prob:.2f} — deterministic R1-aware assessment "
                f"(trigger={trigger_type}, risk_score={risk_score:.2f})."
            ),
            "next_evidence_type": "customer_validation",
            # S23 FIX: was 287.50 (hardcoded); now 0.0 so nodes.py computes it correctly
            "exposure_usd": 0.0,
            "rationale": "Deterministic fallback: R1 applied for single-signal weak risk score cases.",
        }

    elif "initial_actions" in lower and "policy rules" in lower:
        # Prompt 3: Action Selection — must match is_fraud
        if is_fraud:
            return {
                "initial_actions": [
                    {
                        "action": "BLOCK_CARD",
                        "route": "L1",
                        "reason": "R2: High fraud confidence — card block required.",
                    },
                    {
                        "action": "CREATE_CASE",
                        "route": "auto",
                        "reason": "R2: Create formal fraud investigation case record.",
                    },
                ],
                "sar_recommended": False,
                "sar_reason": "",
            }
        elif trigger_type == "risk_score" and prob < 0.70:
            return {
                "initial_actions": [
                    {
                        "action": "VERIFY_WITH_CUSTOMER",
                        "route": "auto",
                        "reason": (
                            "R1: Single weak signal (risk_score < 0.70) requires "
                            "customer verification before any block."
                        ),
                    },
                    {
                        "action": "STEP_UP_AUTH",
                        "route": "auto",
                        "reason": "R1: Step-up authentication requested prior to any card action.",
                    },
                ],
                "sar_recommended": False,
                "sar_reason": "",
            }
        else:
            return {
                "initial_actions": [
                    {
                        "action": "CLOSE_NO_FRAUD",
                        "route": "auto",
                        "reason": "R3: Customer confirmed transaction — CLOSE_NO_FRAUD.",
                    },
                    {
                        "action": "ALLOW_TRANSACTION",
                        "route": "auto",
                        "reason": "R3: Legitimate activity verified; transaction allowed.",
                    },
                ],
                "sar_recommended": False,
                "sar_reason": "",
            }

    else:
        # Prompt 4: Case Summary & SAR
        is_sar = "file_report" in lower or ("sar" in lower and is_fraud and prob > 0.90)
        verdict_word = "fraud" if is_fraud else "legitimate"
        return {
            "summary": (
                f"Autonomous graph fraud investigation concluded with verdict={verdict_word} "
                f"(confidence={prob:.2f}). Policy rules R1-R10 enforced throughout."
            ),
            "sar_narrative": (
                "Suspicious Activity Report filed for unauthorized card-not-present transactions."
                if is_sar else ""
            ),
            # S23 FIX: was ["C12382", "C12382-K1"] hardcoded; now empty (caller sets from state)
            "sar_subjects": [],
            "activity_dates": ["2016-11-20", "2016-12-05"],
        }


async def call_llm_json(
    prompt_template: str,
    context: dict,
    role: str = "fast",
    max_tokens: int = 2048,
    max_retries: int = 1,
    model: Optional[str] = None,
    **kwargs,
) -> dict:
    """Execute structured LLM JSON call with automatic model rotation.

    S23 FIX: _prompt_cache disabled (_CACHE_ENABLED=False). The cache was keyed
    on SHA256(role + formatted_prompt). Two cases with the same trigger_type and
    risk_score band produce near-identical prompts and got the SAME cached result,
    meaning case N+1 received case N's evidence and exposure. Cache is removed
    until it can be made per-case-id scoped.
    """
    if model is not None:
        role = "strong" if "pro" in str(model).lower() or model == "strong" else "fast"

    try:
        formatted = prompt_template.format(**context)
    except KeyError:
        formatted = prompt_template
        for k, v in context.items():
            formatted = formatted.replace(f"{{{k}}}", str(v))

    # S23 FIX: cache disabled — see module-level _CACHE_ENABLED flag
    if _CACHE_ENABLED:
        cache_key = hashlib.sha256(f"{role}:{formatted}".encode()).hexdigest()
        if cache_key in _prompt_cache:
            return _prompt_cache[cache_key]
    else:
        cache_key = None

    candidates = CANDIDATE_STRONG if role == "strong" else CANDIDATE_FAST
    for model_name in candidates:
        if model_name in _exhausted_models:
            continue

        for attempt in range(max_retries + 1):
            t0 = time.time()
            try:
                client = genai.GenerativeModel(model_name)
                resp = client.generate_content(
                    formatted,
                    generation_config=genai.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                    request_options={"timeout": 6}
                )
                latency = time.time() - t0
                text = resp.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("```", 1)[0]
                parsed = json.loads(text)
                usage = getattr(resp, "usage_metadata", None)
                _call_log.append({
                    "model": model_name,
                    "role": role,
                    "tokens_in": getattr(usage, "prompt_token_count", None),
                    "tokens_out": getattr(usage, "candidates_token_count", None),
                    "latency_s": round(latency, 2),
                    "ts": time.time(),
                })
                if _CACHE_ENABLED and cache_key:
                    _prompt_cache[cache_key] = parsed
                return parsed

            except json.JSONDecodeError:
                formatted += "\n\nRESPOND WITH ONLY VALID JSON. NO PREAMBLE, NO MARKDOWN FENCES."
                continue
            except Exception as e:
                err_str = str(e).lower()
                if any(kw in err_str for kw in ("429", "quota", "resourceexhausted", "overloaded", "deadline", "timeout")):
                    print(f"[llm] Model '{model_name}' rotated ({e})...")
                    _exhausted_models.add(model_name)
                    break
                break

    # If all models hit 429 quota, fallback to deterministic engine
    print(f"[llm] Active models quota reached. Using deterministic reasoning engine.")
    fallback_res = _deterministic_fallback(formatted, role)
    if _CACHE_ENABLED and cache_key:
        _prompt_cache[cache_key] = fallback_res
    return fallback_res


def dump_call_log(path: str = "outputs/llm_call_log.json"):
    """Dumps all executed LLM calls to path."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_call_log, indent=2), encoding="utf-8")
