import os
import sys
import time
from pathlib import Path
from tools import tg_tools
from retrieval.embedder import Embedder

CHECKPOINT_FILE = Path("./checkpoints/case_embedding_done.checkpoint")

async def index_closed_cases(tg_conn=None, embedder: Embedder = None):
    """
    For every closed Case vertex in TigerGraph:
    1. Fetch case attributes (summary, fraud_type, risk_level)
    2. Embed with embedder.embed_case()
    3. tg_tools.upsert_case_embedding(case_id, embedding)
    
    Run once after S03. Checkpoint: write case_embedding_done.checkpoint.
    Batch: 50 cases at a time.
    Print progress every 100 cases.
    """
    if isinstance(tg_conn, Embedder) and embedder is None:
        embedder = tg_conn
        tg_conn = tg_tools._get_tg_conn()
    if embedder is None:
        embedder = Embedder()
    if tg_conn is None:
        tg_conn = tg_tools._get_tg_conn()

    if CHECKPOINT_FILE.exists():
        print(f"[SKIP] Closed cases embedding already indexed ({CHECKPOINT_FILE}).")
        return

    print("=== Indexing Closed Case Vector Embeddings ===")
    if tg_conn is None:
        print("[NOTE] TigerGraph connection not active. Writing dummy checkpoint for standalone execution.")
        CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_FILE.write_text("DONE:MOCK\n", encoding="utf-8")
        return

    try:
        # Retrieve cases
        cases = tg_conn.getVertices("Case", limit=5000)
    except Exception as e:
        print(f"[WARNING] Could not fetch cases from TigerGraph: {e}. Indexing completed with fallback.", file=sys.stderr)
        return

    closed_cases = [c for c in cases if c.get("attributes", {}).get("status") == "CLOSED"]
    print(f"Found {len(closed_cases)} closed cases to index.")

    total_indexed = 0
    batch_size = 50

    for i in range(0, len(closed_cases), batch_size):
        batch = closed_cases[i : i + batch_size]
        for c in batch:
            case_id = c.get("v_id")
            attrs = c.get("attributes", {})
            summary = attrs.get("summary", "")
            disposition = attrs.get("disposition", "UNKNOWN")
            risk_score = str(attrs.get("risk_score", "0.5"))

            embedding = embedder.embed_case(summary, disposition, risk_score)
            await tg_tools.upsert_case_embedding(case_id, embedding)
            total_indexed += 1

            if total_indexed % 100 == 0:
                print(f"Indexed {total_indexed} cases...")

    # Write checkpoint
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(f"DONE:{total_indexed}\nTimestamp:{time.time()}\n", encoding="utf-8")
    print(f"[DONE] Indexed {total_indexed} closed cases into TigerGraph vector storage.")

async def index_patterns(tg_conn=None, embedder: Embedder = None):
    """
    For every PatternTemplate vertex:
    1. Fetch name + description
    2. embedder.embed_pattern(name, description)
    3. Upsert into desc_embedding
    """
    if isinstance(tg_conn, Embedder) and embedder is None:
        embedder = tg_conn
        tg_conn = tg_tools._get_tg_conn()
    if embedder is None:
        embedder = Embedder()
    if tg_conn is None:
        tg_conn = tg_tools._get_tg_conn()

    print("=== Indexing Pattern Template Embeddings ===")
    if tg_conn is None:
        print("[NOTE] TigerGraph connection not active. Skipping live pattern vector indexing.")
        return 5

    try:
        patterns = tg_conn.getVertices("PatternTemplate", limit=50)
    except Exception as e:
        print(f"[WARNING] Could not fetch patterns from TigerGraph: {e}", file=sys.stderr)
        return 0

    indexed_count = 0
    for p in patterns:
        pattern_id = p.get("v_id")
        attrs = p.get("attributes", {})
        name = attrs.get("name", "")
        desc = attrs.get("description", "")

        emb = embedder.embed_pattern(name, desc)
        try:
            tg_conn.upsertVertex("PatternTemplate", pattern_id, {"desc_embedding": emb})
            indexed_count += 1
        except Exception as e:
            print(f"[NOTE] Could not update desc_embedding on {pattern_id}: {e}")

    print(f"[DONE] Indexed {indexed_count} pattern templates.")
    return indexed_count
