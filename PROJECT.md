# HHGOA Fraud Investigation Agent — Master Project Specification

## 1. Executive Summary & Objective
The **HHGOA Fraud Investigation Agent** is an autonomous, graph-augmented AI system designed to investigate financial fraud, identify syndicated crime rings, and generate comprehensive, audit-ready compliance dossiers. Built for the HHGOA hackathon, the system leverages TigerGraph's high-performance native graph database, Model Context Protocol (MCP) integrations, LangGraph agent workflows, and Google Gemini LLMs to detect complex multi-hop fraud patterns that evade traditional flat machine learning pipelines.

---

## 2. Architecture & System Components
The system consists of several layered subsystems:

1. **TigerGraph Core (`FraudGraph`)**:
   - Stores transactions, accounts, devices, IP clusters, cases, and rules.
   - Materializes derived relationship edges (`SHARES_DEVICE`, `SHARES_EMAIL_DOMAIN`, `SHARES_ADDRESS`) to uncover collusion networks and money mules.
   - Hosts high-performance GSQL graph algorithms (PageRank, Louvain community detection, connected components, shortest path).

2. **Graph Retrieval & MCP Layer (`tools/`, `retrieval/`)**:
   - `tigergraph-mcp` adapter exposing GSQL queries and topological traversals as callable agent tools.
   - Vector retrieval over narrative transaction memos, merchant codes, and historical case summaries.

3. **LangGraph Agent Workflow (`agent/`)**:
   - Multi-stage investigation graph: Alert Ingestion → Subgraph Expansion → Ring Detection → Behavioral Profiling → Dossier Compilation.
   - Dynamic tool selection for querying 1-hop, 2-hop, and k-hop transaction networks.

4. **Web Dashboard & Real-Time Visualization (`dashboard/`)**:
   - FastAPI server with Server-Sent Events (SSE) for streaming reasoning steps.
   - Interactive graph visualizer for fraud rings and transaction flows.

5. **Benchmark & Evaluation (`benchmark/`)**:
   - Precision, recall, and detection latency benchmarks against synthetic and real-world fraud scenarios.

---

## 3. Dataset Specification & Storage
The dataset is structured based on the IEEE-CIS Fraud Detection benchmark with hackathon extensions:
- `train_transaction.csv`: Transaction features, card details, amounts, email domains, address codes, V-features, and fraud labels.
- `train_identity.csv`: Device information, browser, and network identifiers.
- Closed investigation cases: Historical resolved cases for memory retrieval.
- Fraud policy documents: Governance guidelines, thresholds, and SAR triggers.
- Fraud pattern documents: Documented fraud typologies (e.g. bust-out, smurfing, ring collusion).

---

## 4. Environment Variables & Configuration
The project is configured via environment variables specified in `.env` (refer to `.env.example`):

### TigerGraph Connection
- `TG_HOST`: Base URL of the TigerGraph instance (e.g., `http://127.0.0.1:14240` or Savanna Cloud URL).
- `TG_GRAPHNAME`: Name of the target graph (default: `FraudGraph`).
- `TG_USERNAME`: Username for TigerGraph authentication (default: `tigergraph`).
- `TG_PASSWORD`: Password for TigerGraph authentication (default: `tigergraph`).
- `TG_SECRET`: REST++ authentication secret for token generation.
- `TG_TOKEN`: Active REST++ token (optional; auto-generated if secret is present).

### Dataset & Local Storage
- `DATASET_PATH`: Path to the directory containing dataset CSVs (default: `./data`).

### LLM / AI Configuration
- `GEMINI_API_KEY`: API key for Google Gemini model access.

### Embeddings & Vector Search
- `EMBEDDING_MODEL`: Hugging Face Sentence Transformers model name (default: `all-MiniLM-L6-v2`).

### Web Server & Environment
- `HOST`: Server bind address (default: `0.0.0.0`).
- `PORT`: Web server listen port (default: `8000`).
- `ENVIRONMENT`: Runtime environment (`development`, `staging`, `production`).

---

## 5. Schema Definition

### 5.1 Vertex Types

```gsql
-- Core Financial Entities
CREATE VERTEX Account (
    PRIMARY_ID account_id STRING,
    p_emaildomain STRING,
    addr1 FLOAT,
    addr2 FLOAT,
    card1 INT,
    card2 FLOAT,
    risk_score FLOAT
) WITH STATS="OUTDEGREE_BY_EDGETYPE";

CREATE VERTEX Transaction (
    PRIMARY_ID txn_id STRING,
    is_fraud INT,
    txn_dt INT,
    amount FLOAT,
    product_cd STRING,
    card1 INT,
    card2 FLOAT,
    card3 FLOAT,
    card4 STRING,
    card5 FLOAT,
    card6 STRING,
    addr1 FLOAT,
    addr2 FLOAT,
    dist1 FLOAT,
    dist2 FLOAT,
    p_emaildomain STRING,
    r_emaildomain STRING,
    risk_score FLOAT,
    v_features_json STRING,
    m_features_json STRING
) WITH STATS="OUTDEGREE_BY_EDGETYPE";

CREATE VERTEX Device (
    PRIMARY_ID device_id STRING,
    device_info STRING,
    device_type STRING,
    browser STRING
) WITH STATS="OUTDEGREE_BY_EDGETYPE";

CREATE VERTEX IPCluster (
    PRIMARY_ID ip_cluster_id STRING,
    ip_hash STRING
) WITH STATS="OUTDEGREE_BY_EDGETYPE";

-- Investigation & Compliance Entities
-- Requires TigerGraph 4.2+ for vector/TigerVector support
CREATE VERTEX Case (
    PRIMARY_ID case_id STRING,
    status STRING,
    disposition STRING,
    risk_score FLOAT,
    created_at STRING,
    summary STRING
) WITH STATS="OUTDEGREE_BY_EDGETYPE";

CREATE VERTEX Evidence (
    PRIMARY_ID evidence_id STRING,
    evidence_type STRING,
    description STRING,
    source STRING,
    score FLOAT
) WITH STATS="OUTDEGREE_BY_EDGETYPE";

-- Requires TigerGraph 4.2+ for vector/TigerVector support
CREATE VERTEX PatternTemplate (
    PRIMARY_ID pattern_id STRING,
    name STRING,
    description STRING,
    is_documented BOOL,
    confidence FLOAT,
    match_criteria_json STRING
) WITH STATS="OUTDEGREE_BY_EDGETYPE";

CREATE VERTEX PolicyRule (
    PRIMARY_ID rule_id STRING,
    name STRING,
    category STRING,
    trigger_condition STRING,
    action_type STRING,
    approval_tier STRING,
    risk_threshold FLOAT,
    amount_threshold FLOAT,
    regulatory_ref STRING,
    requires_sar BOOL
) WITH STATS="OUTDEGREE_BY_EDGETYPE";

CREATE VERTEX Action (
    PRIMARY_ID action_id STRING,
    action_type STRING,
    status STRING,
    executed_at STRING,
    reason STRING
) WITH STATS="OUTDEGREE_BY_EDGETYPE";

CREATE VERTEX Decision (
    PRIMARY_ID decision_id STRING,
    verdict STRING,
    rationale STRING,
    decided_by STRING,
    timestamp STRING
) WITH STATS="OUTDEGREE_BY_EDGETYPE";
```

### 5.2 Edge Types

```gsql
-- Transaction & Device Edges
CREATE DIRECTED EDGE PERFORMED (FROM Account, TO Transaction, txn_dt INT) WITH REVERSE_EDGE="REVERSE_PERFORMED";
CREATE DIRECTED EDGE USED_DEVICE (FROM Transaction, TO Device) WITH REVERSE_EDGE="REVERSE_USED_DEVICE";
CREATE DIRECTED EDGE FROM_IP_CLUSTER (FROM Transaction, TO IPCluster) WITH REVERSE_EDGE="REVERSE_FROM_IP_CLUSTER";

-- Derived Collusion & Ring Edges
CREATE UNDIRECTED EDGE SHARES_DEVICE (FROM Account, TO Account, device_id STRING, shared_count INT);
CREATE UNDIRECTED EDGE SHARES_EMAIL_DOMAIN (FROM Account, TO Account, domain STRING, shared_count INT);
CREATE UNDIRECTED EDGE SHARES_ADDRESS (FROM Account, TO Account, addr_key STRING, shared_count INT);

-- Case Management & Evidence Edges
CREATE DIRECTED EDGE CASE_TARGETS_TXN (FROM Case, TO Transaction) WITH REVERSE_EDGE="REVERSE_CASE_TARGETS_TXN";
CREATE DIRECTED EDGE CASE_TARGETS_ACCOUNT (FROM Case, TO Account) WITH REVERSE_EDGE="REVERSE_CASE_TARGETS_ACCOUNT";
CREATE DIRECTED EDGE EVIDENCE_FOR (FROM Evidence, TO Case) WITH REVERSE_EDGE="REVERSE_EVIDENCE_FOR";

-- Pattern & Typology Edges
CREATE DIRECTED EDGE CASE_MATCHES_PATTERN (FROM Case, TO PatternTemplate, similarity FLOAT) WITH REVERSE_EDGE="REVERSE_CASE_MATCHES_PATTERN";
CREATE DIRECTED EDGE TXN_MATCHES_PATTERN (FROM Transaction, TO PatternTemplate, score FLOAT) WITH REVERSE_EDGE="REVERSE_TXN_MATCHES_PATTERN";

-- Policy & Governance Edges
CREATE DIRECTED EDGE CASE_TRIGGERED_ACTION (FROM Case, TO Action) WITH REVERSE_EDGE="REVERSE_CASE_TRIGGERED_ACTION";
CREATE DIRECTED EDGE ACTION_GOVERNED_BY (FROM Action, TO PolicyRule) WITH REVERSE_EDGE="REVERSE_ACTION_GOVERNED_BY";
CREATE DIRECTED EDGE CASE_HAS_DECISION (FROM Case, TO Decision) WITH REVERSE_EDGE="REVERSE_CASE_HAS_DECISION";

-- Case Similarity Edge
CREATE UNDIRECTED EDGE CASE_SIMILAR_TO (FROM Case, TO Case, similarity FLOAT);
```

---

## 6. GSQL Analytical Query Library
The analytical backbone consists of 8 parameterized GSQL queries supporting agent investigations:

1. `get_txn_neighborhood(VERTEX<Transaction> txn_id, INT depth)`:
   Multi-hop BFS exploring accounts, devices, and network clusters connected to a transaction.
2. `get_shared_identifiers(VERTEX<Account> account_id)`:
   Identifies accounts linked via derived device, email domain, and address sharing edges, computing transaction volumes and risk indicators.
3. `get_money_flow(VERTEX<Account> account_id, INT depth)`:
   Traces fund flow pathways and detects syndication loops / rings.
4. `get_policy_rules(FLOAT txn_amt, FLOAT risk_score)`:
   Matches applicable compliance rules and triggers (SAR filing, freezing, monitoring).
5. `case_crud.gsql`:
   - `create_or_get_case(trigger_type, txn_ids_json, account_id, trigger_risk_score)`
   - `update_case_status(case_id, status, fraud_prob, risk_level, fraud_type)`
   - `close_case(case_id, disposition, closed_dt)`
   - `get_open_cases()`
6. `graph_stats()`:
   Topological summary of vertices, edges, case distributions, and pattern templates.

---

## 7. Development Roadmap & Sessions
- **S01**: Repository Scaffold & Environment Baseline
- **S02**: TigerGraph Schema Design & GSQL Initialization
- **S03**: Data Pipeline & Ingestion
- **S04**: Derived Graph Edges Materialization
- **S05**: Graph Queries & Subgraph Traversal Tools
- **S06**: MCP Server Integration
- **S07**: Vector Search & Context Retrieval
- **S08**: LangGraph Investigation Flow Design
- **S09**: Agent Reasoning & Multi-hop Expansion
- **S10**: Dossier Generation & Compliance Reporting
- **S11**: Real-Time Streaming FastAPI Backend
- **S12**: Web UI & Interactive Graph Visualization
- **S13**: Innovation Features (Explainable Risk Scoring & Ring Isolation)
- **S14**: Benchmarks, Latency & Precision Validation
- **S15**: Final Polish, Packaging & Hackathon Demonstration

