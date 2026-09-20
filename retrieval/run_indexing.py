import asyncio
from tools import tg_tools
from retrieval.embedder import Embedder
from retrieval.vector_indexer import index_closed_cases, index_patterns

async def main():
    print("=== HHGOA Fraud Agent: Vector Indexing Pipeline ===")
    embedder = Embedder()
    conn = tg_tools._get_tg_conn()

    print("\n--- 1. Indexing Closed Cases ---")
    await index_closed_cases(conn, embedder)

    print("\n--- 2. Indexing Pattern Templates ---")
    pattern_count = await index_patterns(conn, embedder)

    print("\n--- 3. Spot Check Indexing Verification ---")
    if conn:
        try:
            cases = conn.getVertices("Case", limit=5)
            indexed_cases = [c for c in cases if c.get("attributes", {}).get("summary_embedding")]
            print(f"Spot check: {len(indexed_cases)}/5 sampled cases have active vector embeddings.")
        except Exception as e:
            print(f"Spot check note: {e}")
    else:
        print("Completed indexing routine (standalone mock execution).")

    print("\n[SUCCESS] Vector indexing pipeline execution finished.")

if __name__ == "__main__":
    asyncio.run(main())
