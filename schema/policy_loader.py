"""
schema/policy_loader.py — Loads R1-R10 PolicyRule vertices into TigerGraph.
Rule text is verbatim from HHGOA_GROUND_TRUTH_CORRECTIONS.md Section 2.
Every string is graded — do not paraphrase.
"""

from agent.state import POLICY_RULES


def load_policy_rules(conn) -> int:
    """
    Upsert all 10 PolicyRule vertices. rule_embedding is left empty (dim=384
    placeholder) — populated at runtime by the retrieval layer when it embeds
    the rule text for GraphRAG lookups.

    Returns the number of rules written.
    """
    rule_vertices = [
        (rule_id, {
            "rule_text":      rule_text,
            "rule_embedding": [],   # filled by retrieval/embed_policies.py at runtime
        })
        for rule_id, rule_text in POLICY_RULES.items()
    ]
    conn.upsertVertices("PolicyRule", rule_vertices)
    print(f"[DONE] load_policy_rules: {len(rule_vertices)} PolicyRule vertices written.")
    return len(rule_vertices)


if __name__ == "__main__":
    # Standalone run: python -m schema.policy_loader
    import sys
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()

    try:
        import pyTigerGraph as tg
    except ImportError:
        print("[ERROR] pyTigerGraph required. Run: pip install pyTigerGraph")
        sys.exit(1)

    conn = tg.TigerGraphConnection(
        host=os.getenv("TG_HOST", "http://127.0.0.1:14240"),
        graphname=os.getenv("TG_GRAPHNAME", "FraudGraph"),
        username=os.getenv("TG_USERNAME", "tigergraph"),
        password=os.getenv("TG_PASSWORD", "tigergraph"),
        secret=os.getenv("TG_SECRET") or None,
        apiToken=os.getenv("TG_TOKEN") or None,
    )
    conn.ping()
    n = load_policy_rules(conn)
    print(f"Policy rules loaded: {n}")
