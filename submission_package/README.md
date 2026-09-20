# FraudSight: Autonomous Graph-Augmented Fraud Investigation Agent

[![TigerGraph HHGOA](https://img.shields.io/badge/TigerGraph-HHGOA%20Hackathon%202026-orange.svg)](https://devpost.com)
[![LangGraph](https://img.shields.io/badge/Agent-LangGraph%20%2F%20DAG-blue.svg)](https://langchain-ai.github.io/langgraph/)
[![Google Gemini](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-green.svg)](https://ai.google.dev/)
[![Compliance](https://img.shields.io/badge/Audit--Ready-FFIEC%20%2F%20FinCEN%20SAR-red.svg)](outputs/cases/)

---

## 1. Overview

**FraudSight** is an autonomous, graph-augmented AI fraud investigation agent designed to uncover syndicated financial crime rings, coordinate multi-hop evidence gathering, and generate audit-ready regulatory dossiers. Traditional tabular machine learning models evaluate transactions in isolation, consistently missing distributed crime syndicates that disperse volume across synthetic identities, shared devices, and proxy IP clusters. 

By natively integrating **TigerGraph**'s massive graph database with an **8-node LangGraph state machine** and **Google Gemini 2.5**, FraudSight conducts autonomous topological traversals across 860,000+ transactions and materializes derived collusion edges (`SHARES_DEVICE`, `SHARES_EMAIL_DOMAIN`). The agent synthesizes forensic evidence, evaluates policy rules across institutional approval tiers, and stops evidence acquisition using an information-theoretic **Minimum Description Length (MDL) Sufficiency Gate**, producing four canonical compliance artifacts including FFIEC-compliant Suspicious Activity Reports (SARs).

---

## 2. System Architecture

The core of FraudSight is an 8-node cyclic directed acyclic graph (DAG) implemented with LangGraph and TigerGraph MCP query tools:

```text
                            [START]
                               │
                               ▼
                        [trigger_node]
            (Ingests alert, parses transaction ID & initial risk)
                               │
                               ▼
                       [investigate_node]
             (Traverses 1-hop & 2-hop topological subgraphs)
                               │
                               ▼
                     [gather_evidence_node]
           (Extracts shared hardware, velocity, and mule links)
                               │
                               ▼
           ┌────────► [assess_uncertainty_node] ◄──────────────┐
           │                   │                               │
           │            (should_gather_more)                   │
           │              /            \                       │
           │          [proceed]    [gather_more]               │
           │            │               │                      │
           │            │               ▼                      │
           │            │    [gather_more_evidence_node] ──────┘
           │            │    (Expands 3-hop money flow & proxies)
           │            ▼
           │       [action_node]
           │  (Applies institutional policy rules & freezing tiers)
           │            │
           │            ▼
           │       [explain_node]
           │  (Compiles FFIEC SAR narratives & audit dossiers)
           │            │
           │            ▼
           │       [memory_node]
           │  (Indexes case vector embeddings into GraphRAG)
           │            │
           │            ▼
           └───────── [END]
```

---

## 3. Quick Start

### Prerequisites
- Python 3.10+
- TigerGraph Cloud instance (or local Docker container on `14240`)
- Google Gemini API Key

### Installation

```bash
# 1. Clone repository
git clone https://github.com/singhharsimar23-dotcom/tiger.git
cd tiger

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
```

### Environment Configuration (`.env`)
```ini
TG_HOST=https://your-instance.tgcloud.io
TG_GRAPHNAME=FraudGraph
TG_USERNAME=tigergraph
TG_PASSWORD=your_password
TG_SECRET=your_restpp_secret
GEMINI_API_KEY=your_gemini_api_key
LLM_MODEL_FAST=gemini-2.5-flash
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Run Benchmark Investigation Suite
Execute autonomous investigations across the 20 benchmark fraud cases:

```bash
# Run 20-case benchmark pipeline
python benchmark/run_benchmark.py

# Validate generated compliance dossiers
python benchmark/validate_outputs.py
```

### Launch Real-Time UI Command Center
```bash
# Start FastAPI web dashboard with live SSE streaming
uvicorn dashboard.app:app --port 8000 --reload
```
Open [http://localhost:8000](http://localhost:8000) to view active cases, network topologies in Cytoscape.js, and real-time reasoning streams.

---

## 4. Project Structure

```text
tiger/
├── agent/            # LangGraph 8-node investigation state machine & Gemini prompts
├── benchmark/        # 20 benchmark fraud test cases and output validation scripts
├── checkpoints/      # State recovery checkpoints for embeddings and graph pipelines
├── dashboard/        # FastAPI analyst command center with SSE, Tailwind & Cytoscape.js
├── data/             # IEEE-CIS transaction, identity, and historical case datasets
├── docs/             # Technical architecture blueprints, benchmark blogs, and guides
├── innovation/       # Minimum Description Length (MDL) gate & unsupervised pattern discovery
├── output/           # Canonical schema models, JSON serializers, and compliance builders
├── outputs/cases/    # 4 required JSON output files per case (case_record, SAR, actions)
├── queries/          # 8 parameterized GSQL graph analytical queries and installer
├── retrieval/        # Sentence-transformers embedder, vector indexer, and GraphRAG
├── schema/           # GSQL schema DDL, batch ingestion pipelines, and derived edges
├── tests/            # Pytest test suites validating all roadmap milestones
└── tools/            # TigerGraph REST++ async tools, MCP adapter, and circuit breakers
```

---

## 5. Key Innovations

- **Information-Theoretic MDL Sufficiency Gate:**  
  Solves the multi-hop "over-investigation" trap. Unlike naive LLM agents that query indefinitely or stop on arbitrary iteration limits, FraudSight balances binary entropy reduction against traversal query costs using Minimum Description Length theory:
  $$\text{Sufficiency} = \frac{H(p)}{\log_2(2)} \cdot \left(1 + \frac{\text{Cost}}{10}\right)^{-1} \cdot e^{-0.1 \times \text{iterations}}$$
  When the score drops below 0.35, the agent terminates evidence acquisition with mathematical confidence and escalates to decisioning.

- **Unsupervised Pattern Discovery:**  
  Discovers emerging, undocumented fraud typologies by combining Louvain graph community detection with 21-dimensional DBSCAN behavioral clustering over confirmed fraud subgraphs. Detects micro-structuring loops and synchronized dormancy reactivation before rules can be authored.

- **Hybrid GraphRAG Memory Retrieval:**  
  Combines topological structural proximity ($0.4 \times \text{Graph Distance}$) with semantic cosine similarity ($0.6 \times \text{Sentence Transformers}$) over historical closed cases and documented policy templates, ensuring precedent-grounded reasoning.

---

## 6. Dataset Specification

The system is trained and benchmarked on the industry-standard **IEEE-CIS Fraud Detection** dataset (via `HHGOA_IEEE`):
- `train_transaction.csv`: 590,540 financial transactions featuring amounts, card identities, product codes, address coordinates, and time deltas.
- `train_identity.csv`: 144,233 device fingerprints, browser strings, and network attributes.
- **20 Curated Benchmark Scenarios:** Covering rapid velocity smurfing, synthetic identity rings, device collusion farms, account takeovers, and cross-border proxy tunnels.

---

## 7. Technology Stack

| Layer | Technologies | Purpose |
| :--- | :--- | :--- |
| **Graph Database** | TigerGraph Cloud 4.x / pyTigerGraph | Native graph storage, GSQL queries, sub-second BFS traversal |
| **Agent Orchestration** | LangGraph / StateGraph | 8-node cyclic state machine coordinating multi-hop investigations |
| **LLM Reasoning** | Google Gemini 2.5 Flash | Context synthesis, risk assessment, and regulatory narrative drafting |
| **Vector Search** | Sentence-Transformers (`all-MiniLM-L6-v2`) | 384-dimensional dense semantic embeddings for GraphRAG memory |
| **Data & ML** | NumPy, Scikit-Learn (DBSCAN, Louvain) | Behavioral clustering and unsupervised pattern discovery |
| **Web Dashboard** | FastAPI, Jinja2, Tailwind CSS, Cytoscape.js | High-density analyst command center with SSE streaming |
| **Validation** | Pydantic v2, Pytest | Typed schemas, output validation, and regression suites |

---

## 8. Hackathon Details

Developed for the **TigerGraph HHGOA Hackathon 2026** (AI Agent & Graph Track).  
- **Repository:** [https://github.com/singhharsimar23-dotcom/tiger](https://github.com/singhharsimar23-dotcom/tiger)
- **Official Challenge:** [TigerGraph Hackathon Portal](https://www.tigergraph.com)
- **Compliance Output:** 100% test coverage across all 20 benchmark test cases producing FFIEC/FinCEN SAR standards.
