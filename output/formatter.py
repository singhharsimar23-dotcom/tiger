"""
output/formatter.py — Ground Truth Corrected Output Formatter (Section 4)

Writes ONE file per case: cases/{case_id}.json
Old 4-file-per-case format (case_record.json / sar.json / action_before.json /
action_after.json) is retired.

Validates internal consistency before writing.
"""

import json
import time
from pathlib import Path
from typing import Optional

from agent.state import InvestigationState, approval_route, ActionType
from output.schema_models import (
    CaseAnswer, Case, SAR, NextBestActions, ActionRec,
    Evidence, EvidenceRequest,
)


class OutputFormatter:
    """
    Serialises InvestigationState → CaseAnswer → cases/{case_id}.json.

    Usage:
        formatter = OutputFormatter()
        path = formatter.format_and_save(state)
    """

    def __init__(self, output_dir: str = "cases"):
        self.output_dir = Path(output_dir)

    def format_and_save(self, state: InvestigationState) -> Path:
        """Build CaseAnswer, validate, write single JSON file. Returns file path."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        answer = self._build_case_answer(state)
        self._validate(answer)

        out_path = self.output_dir / f"{answer.case_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(answer.model_dump(), f, indent=2, default=str)

        return out_path

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _build_case_answer(self, state: InvestigationState) -> CaseAnswer:
        latency = round(max(0.01, time.time() - (state.started_at or time.time())), 3)

        # Evidence list
        evidence_out = [
            Evidence(
                claim=e.claim,
                source=e.source if e.source in ("graph", "document", "customer", "external") else "graph",
                ref=e.ref,
                entity_ids=e.entity_ids,
            )
            for e in state.evidence_list
        ]

        # Evidence requests
        ev_requests_out = [
            EvidenceRequest(
                type=er.type if er.type in ("customer_validation", "step_up_auth", "analyst_info") else "customer_validation",
                asked_after_step=er.asked_after_step,
                assumed_response=er.assumed_response,
            )
            for er in state.evidence_requests
        ]

        # Actions — ensure route is computed from the approval_route() function
        def _to_action_rec(ar) -> ActionRec:
            if isinstance(ar, ActionRec):
                return ar
            if isinstance(ar, dict):
                return ActionRec(**ar)
            # From state.ActionRec dataclass
            action_str = ar.action if isinstance(ar.action, str) else ar.action.value
            return ActionRec(action=action_str, route=ar.route, reason=ar.reason)

        initial_out = [_to_action_rec(a) for a in state.initial_actions]
        final_out   = [_to_action_rec(a) for a in state.final_actions] if state.final_actions else initial_out

        nba = NextBestActions(
            initial=initial_out,
            final=final_out,
            what_changed=state.what_changed or "nothing",
        )

        # Case
        case_out = Case(
            status=state.status,
            verdict=state.verdict,
            fraud_probability=round(float(state.fraud_probability), 4),
            pattern=state.pattern,
            pattern_description=state.pattern_description or "",
            affected_txn_ids=state.affected_txn_ids,
            first_suspicious_txn_id=state.first_suspicious_txn_id or "",
            connected_card_ids=state.connected_card_ids,
            connected_device_profiles=state.connected_device_profiles,
            exposure_usd=round(float(state.exposure_usd), 2),
            evidence=evidence_out,
            similar_prior_cases=state.similar_cases,
            summary=state.summary or "",
            written_to_graph=state.written_to_graph,
            graph_case_id=state.graph_case_id or "",
        )

        # SAR
        sar_out = SAR(
            file=state.sar_file,
            reason=state.sar_reason or "",
            narrative=state.sar_narrative or "",
            subjects=state.sar_subjects,
            total_amount_usd=round(float(state.sar_total_amount_usd), 2),
            activity_dates=state.sar_activity_dates,
        )

        return CaseAnswer(
            case_id=state.case_id,
            case=case_out,
            evidence_requests=ev_requests_out,
            next_best_actions=nba,
            sar=sar_out,
            stop_reason=state.stop_reason or "",
            tool_calls=len(state.tool_calls),
            tokens=state.tokens_used,
            latency_s=latency,
        )

    # ------------------------------------------------------------------
    # Internal validation (mirrors output/validator.py full checks)
    # ------------------------------------------------------------------

    def _validate(self, answer: CaseAnswer) -> None:
        """Raise ValueError on internal consistency violations before writing."""
        c = answer.case

        # sar.file must agree with FILE_REPORT in final actions
        final_action_names = {a.action for a in answer.next_best_actions.final}
        if answer.sar.file and "FILE_REPORT" not in final_action_names:
            raise ValueError(
                f"[{answer.case_id}] sar.file=True but FILE_REPORT not in next_best_actions.final"
            )
        if not answer.sar.file and "FILE_REPORT" in final_action_names:
            raise ValueError(
                f"[{answer.case_id}] FILE_REPORT in final actions but sar.file=False"
            )

        # legitimate verdict constraints
        if c.verdict == "legitimate":
            if c.affected_txn_ids:
                raise ValueError(
                    f"[{answer.case_id}] verdict=legitimate but affected_txn_ids is non-empty"
                )
            if c.exposure_usd != 0.0:
                raise ValueError(
                    f"[{answer.case_id}] verdict=legitimate but exposure_usd={c.exposure_usd}"
                )
            if answer.sar.file:
                raise ValueError(
                    f"[{answer.case_id}] verdict=legitimate but sar.file=True"
                )

        # undocumented pattern requires description
        if c.pattern == "undocumented" and not c.pattern_description:
            raise ValueError(
                f"[{answer.case_id}] pattern=undocumented but pattern_description is empty"
            )

        # All action strings must be valid
        valid_actions = {at.value for at in ActionType}
        for ar in answer.next_best_actions.final:
            if ar.action not in valid_actions:
                raise ValueError(
                    f"[{answer.case_id}] Unknown action '{ar.action}'. Must be one of {sorted(valid_actions)}"
                )
