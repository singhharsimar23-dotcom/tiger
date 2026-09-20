import os
import sys
import asyncio
from typing import Dict, Any, Callable

from agent.state import InvestigationState, CaseStatus
from agent.nodes import (
    trigger_node,
    investigate_node,
    gather_evidence_node,
    assess_uncertainty_node,
    should_gather_more,
    gather_more_evidence_node,
    action_node,
    explain_node,
    memory_node,
)

# Detect if official LangGraph package is installed
try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

class _GraphVisualizer:
    def print_ascii(self):
        ascii_art = """
        [START]
           |
           v
     [trigger_node]
           |
           v
    [investigate_node]
           |
           v
  [gather_evidence_node]
           |
           v
 [assess_uncertainty_node] <---------------+
           |                               |
    (should_gather_more)                   |
      /            \\                       |
  [proceed]    [gather_more]               |
    |               |                      |
    |               v                      |
    |     [gather_more_evidence_node] -----+
    v
[action_node]
    |
    v
[explain_node]
    |
    v
[memory_node]
    |
    v
  [END]
        """
        print(ascii_art)


class _FallbackCompiledGraph:
    def __init__(self, nodes: Dict[str, Callable]):
        self.nodes = nodes

    def get_graph(self):
        return _GraphVisualizer()

    async def ainvoke(self, state: InvestigationState) -> InvestigationState:
        curr = state
        curr = await self.nodes["trigger"](curr)
        curr = await self.nodes["investigate"](curr)
        curr = await self.nodes["gather_evidence"](curr)

        while True:
            curr = await self.nodes["assess_uncertainty"](curr)
            route = should_gather_more(curr)
            if route == "gather_more":
                curr = await self.nodes["gather_more_evidence"](curr)
            else:
                break

        curr = await self.nodes["action"](curr)
        curr = await self.nodes["explain"](curr)
        curr = await self.nodes["memory"](curr)
        return curr

def build_investigation_graph():
    if HAS_LANGGRAPH:
        builder = StateGraph(InvestigationState)
        builder.add_node("trigger", trigger_node)
        builder.add_node("investigate", investigate_node)
        builder.add_node("gather_evidence", gather_evidence_node)
        builder.add_node("assess_uncertainty", assess_uncertainty_node)
        builder.add_node("gather_more_evidence", gather_more_evidence_node)
        builder.add_node("action", action_node)
        builder.add_node("explain", explain_node)
        builder.add_node("memory", memory_node)

        builder.set_entry_point("trigger")
        builder.add_edge("trigger", "investigate")
        builder.add_edge("investigate", "gather_evidence")
        builder.add_edge("gather_evidence", "assess_uncertainty")

        builder.add_conditional_edges(
            "assess_uncertainty",
            should_gather_more,
            {
                "gather_more": "gather_more_evidence",
                "proceed": "action"
            }
        )
        builder.add_edge("gather_more_evidence", "assess_uncertainty")
        builder.add_edge("action", "explain")
        builder.add_edge("explain", "memory")
        builder.add_edge("memory", END)

        return builder.compile()
    else:
        # Fallback executor matching identical DAG semantics
        return _FallbackCompiledGraph({
            "trigger": trigger_node,
            "investigate": investigate_node,
            "gather_evidence": gather_evidence_node,
            "assess_uncertainty": assess_uncertainty_node,
            "gather_more_evidence": gather_more_evidence_node,
            "action": action_node,
            "explain": explain_node,
            "memory": memory_node
        })

# Exported compiled graph singleton
graph = build_investigation_graph()

async def run_investigation(trigger: dict) -> InvestigationState:
    """
    Main entry point for running autonomous graph investigations.
    Supports trigger dicts from case_pack.csv or API:
    {
      "case_id": "HHG-001",
      "trigger_type": "risk_score",
      "flagged_txn_id": "3514030",
      "card_id": "C12382-K1",
      "customer_id": "C12382",
      "risk_score": 0.61,
      "trigger_text": "..."
    }
    """
    flagged_txn = trigger.get("flagged_txn_id")
    if not flagged_txn:
        txn_list = trigger.get("trigger_txn_ids") or []
        flagged_txn = txn_list[0] if txn_list else "T3514030"
    if not str(flagged_txn).startswith("T"):
        flagged_txn = f"T{flagged_txn}"

    risk_val = trigger.get("risk_score")
    if risk_val is None or risk_val == "":
        risk_val = trigger.get("trigger_risk_score", 0.0)
    try:
        risk_float = float(risk_val)
    except Exception:
        risk_float = 0.0

    initial_state = InvestigationState(
        case_id=trigger.get("case_id", ""),
        trigger_type=trigger.get("trigger_type", "risk_score"),
        flagged_txn_id=flagged_txn,
        card_id=trigger.get("card_id", ""),
        customer_id=trigger.get("customer_id", ""),
        trigger_risk_score=risk_float,
        trigger_text=trigger.get("trigger_text") or trigger.get("notes", ""),
    )

    final_state = await graph.ainvoke(initial_state)
    return final_state
