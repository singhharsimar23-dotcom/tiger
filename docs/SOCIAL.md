# Social Media Announcements

---

## LinkedIn Post (Max 300 words)

Most fraud detection systems fail for one simple reason: they evaluate transactions in flat rows and tabular columns. But organized fraud syndicates don't operate in silos—they operate in graphs. 🕸️💳

For the **TigerGraph HHGOA Hackathon**, I built **FraudSight**—an autonomous, graph-augmented AI fraud investigation agent powered by @TigerGraphDB, LangGraph, and Google Gemini 2.5.

Here was the most surprising insight from building it: **Giving an AI agent graph traversal tools creates an "over-investigation trap."** Left unchecked, LLM agents keep querying hop after hop, searching for certainty that doesn't exist, spiking latency and database costs.

To solve this, I designed an **Information-Theoretic Minimum Description Length (MDL) Sufficiency Gate**. 

Using Shannon entropy and compression theory, the agent calculates the marginal information gain of each graph query against traversal costs. When entropy reduction levels off, the agent mathematically knows it's time to stop investigating and trigger institutional policy actions—from Tier-1 analyst triage to supervisor-level account freezing.

Key highlights:
- 🚀 **Scale:** 860,000+ IEEE-CIS transactions and 1,248 derived `SHARES_DEVICE` collusion edges in TigerGraph.
- ⚡ **8-Node LangGraph Flow:** Multi-hop BFS, GSQL analytical queries, and hybrid GraphRAG.
- 📋 **Audit-Ready Dossiers:** Automatically generates FinCEN-compliant Suspicious Activity Reports (SARs) across 20 benchmark test scenarios.
- 🔍 **Unsupervised Discovery:** DBSCAN + Louvain clustering to detect emerging, undocumented smurfing typologies before rules are written.

Check out the full open-source codebase, architecture diagrams, and interactive dashboard here:  
👉 https://github.com/singhharsimar23-dotcom/tiger

Huge thanks to @TigerGraphDB for hosting this challenge! 

#TigerGraph #FraudDetection #GraphDatabase #AI #LangGraph #MachineLearning #Fintech #Cybersecurity

---

## X / Twitter Post (280 chars max)

Built an agentic fraud investigator for @TigerGraphDB hackathon.
Key insight: used MDL theory to tell the agent WHEN to stop gathering evidence.
Graph traversal > ML for fraud rings.
590K txns, 8-node LangGraph DAG.
https://github.com/singhharsimar23-dotcom/tiger #TigerGraph #AI
