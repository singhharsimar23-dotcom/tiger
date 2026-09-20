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
    
    Trigger dict format:
    {
      "trigger_type": "RISK_SCORE",
      "trigger_txn_ids": ["T_XXXX"],
      "trigger_account_id": "ACC_XXXX",
      "trigger_risk_score": 0.87
    }
    """
    initial_state = InvestigationState(
        trigger_type=trigger.get("trigger_type", "RISK_SCORE"),
        trigger_txn_ids=trigger.get("trigger_txn_ids", []),
        trigger_account_id=trigger.get("trigger_account_id"),
        trigger_risk_score=float(trigger.get("trigger_risk_score", 0.85))
    )

    final_state = await graph.ainvoke(initial_state)
    return final_state
