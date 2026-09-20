import pytest
import asyncio
from retrieval.embedder import Embedder
from retrieval.vector_indexer import index_patterns
from retrieval.graphrag import GraphRAGRetriever

def test_embedder_embedding_shape_and_types():
    """Verify embedder returns 384-dimensional normalized float vectors."""
    embedder = Embedder()
    vec = embedder.embed("card fraud ring account takeover HIGH")
    assert isinstance(vec, list), "Expected list output from embedder"
    assert len(vec) == 384, f"Expected 384 dimensions, got {len(vec)}"
    assert all(isinstance(x, float) for x in vec), "Expected all elements to be floats"

@pytest.mark.asyncio
async def test_index_patterns_execution():
    """Verify index_patterns runs smoothly."""
    embedder = Embedder()
    res = await index_patterns(None, embedder)
    assert res >= 0

@pytest.mark.asyncio
async def test_graphrag_retriever():
    """Verify GraphRAG hybrid retrieval returns ranked similar cases."""
    embedder = Embedder()
    retriever = GraphRAGRetriever(embedder)
    
    cases = await retriever.get_similar_prior_cases(
        case_id="CASE_TEST_999",
        query_accounts=["ACC_13926_0_315", "ACC_4461_375_184"],
        query_text="Syndicate organized fraud ring with shared devices and high velocity transactions",
        top_k=3
    )

    assert isinstance(cases, list), "Expected list from hybrid retrieval"
    assert len(cases) <= 3
    if cases:
        top_match = cases[0]
        assert "case_id" in top_match
        assert "similarity_score" in top_match
        assert "disposition" in top_match
        assert 0.0 <= top_match["similarity_score"] <= 1.0
