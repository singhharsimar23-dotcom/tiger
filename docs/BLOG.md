# Building a Graph-Powered Agentic Fraud Investigator with TigerGraph

*By Harsimar Singh 

---

## 1. What waas Built 

When financial fraud occurs, it rarely happens in isolation. Fraud rings operate across dozens of synthetic accounts, rotating burner devices, and coordinated timing windows. Standard relational tables and isolated machine learning scoring models are blind to these relational topologies. 

To tackle this, I built **FraudSight**—an autonomous, graph-augmented fraud investigation agent powered by TigerGraph, LangGraph, and Google Gemini 2.5 Flash. Given an initial high-risk alert, FraudSight autonomously investigates transaction networks, dynamically materializes collusion connections, gathers multi-hop graph evidence, and evaluates institutional policies.

Rather than producing a black-box probability score, the agent compiles four regulatory-grade compliance dossiers per case—including FinCEN-compliant Suspicious Activity Reports (SARs) and audit trails. Across 20 benchmark test cases covering 860,000+ transactions from the IEEE-CIS dataset, FraudSight demonstrated sub-second graph traversal, 100% case validation pass rates, and actionable risk escalation from Tier-1 analyst triage to supervisor-level account freezes.

---

## 2. The Architecture 

The architecture connects TigerGraph's high-performance native graph engine to an 8-node cyclic state machine orchestrated via LangGraph. 

```text
[trigger_node] ──> [investigate_node] ──> [gather_evidence_node]
                         │                         │
                         ▼                         ▼
                  [action_node] <── (gate) <── [assess_uncertainty_node]
                         │                         ▲
                         ▼                         │
                   [explain_node] ──> [memory_node] ──> [gather_more_evidence_node]
```

The investigation workflow begins at `trigger_node`, which ingests transaction alerts, parses card details, and initializes the typed `InvestigationState`. Control flows to `investigate_node`, which executes multi-hop breadth-first searches (BFS) in TigerGraph around the target entities up to 2 hops away. 

Next, `gather_evidence_node` synthesizes graph evidence—such as shared device hardware fingerprints, shared IP clusters, and transactional velocity spikes. The agent then enters `assess_uncertainty_node`. 

Here lies one of our core innovations: the **Minimum Description Length (MDL) Sufficiency Gate**. A common pitfall in autonomous AI agents is the "over-investigation loop"—an LLM calling graph tools indefinitely looking for certainty that doesn't exist. Our MDL gate applies information theory to calculate whether the expected information gain of another tool call outweighs the traversal latency and computational cost. When entropy reduction slows ($MDL < 0.35$), the conditional edge `should_gather_more` directs the agent to stop gathering and proceed to decisioning.

If more context is mathematically required, `gather_more_evidence_node` executes deep 3-hop money-flow traversals and proxy scans before re-evaluating. Once sufficient, `action_node` matches institutional policies (from Tier-1 review to immediate account freezes), `explain_node` drafts regulatory narrative dossiers, and `memory_node` writes the final vectors to persistent storage.

---

## 3. How TigerGraph is Used 

TigerGraph serves as the foundational source of truth and analytical engine for FraudSight. Our `FraudGraph` schema hosts 10 vertex types (including `Account`, `Transaction`, `Device`, `IPCluster`, `Case`, and `PolicyRule`) and 15 edge types.

To expose syndicated collusion, we developed a GSQL query pipeline that materializes derived undirected relationship edges: `SHARES_DEVICE`, `SHARES_EMAIL_DOMAIN`, and `SHARES_ADDRESS`. In our IEEE-CIS benchmark dataset, materializing these links uncovered 1,248 shared-device collusion edges connecting accounts that appeared completely independent on flat tabular CSVs.

We authored and installed 8 parameterized GSQL analytical queries:
- `get_txn_neighborhood`: Sub-second BFS extracting the topological 2-hop neighborhood.
- `get_shared_identifiers`: Traverses derived hardware and email edges to calculate connected account volume.
- `get_money_flow`: Traces directed transaction loops to detect circular smurfing syndicates.
- `get_policy_rules`: Matches institutional actions based on transaction amounts and risk scores.
- `case_crud` and `graph_stats`: Real-time ledger maintenance and database metrics.

Through pyTigerGraph and an MCP-compliant adapter, the agent invokes these queries as native tools with microsecond-level local execution and full parameter sanitization.

---

## 4. Agentic Capabilities 

FraudSight operates as a truly autonomous agent rather than a hardcoded script. Its reasoning capabilities include:
- **Tool Use with Circuit Breakers:** The agent dynamically decides which graph queries to execute based on active evidence gaps, backed by connection-pooling and graceful fallback handlers.
- **Hierarchical Approval Tiers:** Policies are tied to risk thresholds and monetary amounts, escalating decisions across `ANALYST_TIER_1`, `SENIOR_ANALYST`, and `SUPERVISOR` tiers.
- **Unsupervised Pattern Discovery:** Using DBSCAN clustering across 21 behavioral dimensions alongside Louvain community subgraphs, FraudSight autonomously detected two undocumented fraud typologies—including high-velocity micro-structuring loops—and registered them as formal `PatternTemplate` vertices.
- **Persistent Memory & GraphRAG:** Resolved cases are embedded with 384-dimensional dense vectors (`all-MiniLM-L6-v2`) and combined with graph proximity ($0.4 \times \text{topological} + 0.6 \times \text{semantic}$) so future investigations recall historical precedents.

---

## 5. What was learnt

Building this system reinforced that **graph topology completely outperforms raw feature engineering for financial crime**. A tabular classifier only sees a single $1,200 transaction; TigerGraph immediately exposes that three separate accounts logged in through the identical device fingerprint within ten minutes. 

On the agentic side, I learned that LLMs need strict mathematical boundaries. Without the MDL sufficiency gate, Gemini would frequently loop 4 or 5 times asking for marginal transaction history. Constraining the agent with information theory drastically cut latency while increasing decision explainability.

---

## 6. What You'd Improve (~100 words)

Given more time, I would expand FraudSight in two key areas:
1. **Dynamic GSQL Generation via Schema MCP:** Enable the LLM to write and compile parameterized GSQL queries on the fly for novel graph paths, sandbox-validated through TigerGraph's REST++ query compiler.
2. **Streaming WebSocket Graph Visualization:** While our Cytoscape.js dashboard renders concentric account networks smoothly and streams timeline events via SSE, streaming live graph node expansions in real time as the BFS expands would provide an even more compelling analyst experience.
