# TigerGraph Agentic Fraud Investigation (HHGOA)

> **Autonomous AI Agent for Multi-Hop Financial Crime Investigation, Graph Reasoning, and Next-Best Action**  
> Built for the TigerGraph Hackathon 2026.

---

## What is This?

Traditional fraud detection relies on isolated rule engines and tabular machine learning models. When fraud syndicates operate across multi-card rings, shared hardware fingerprints, and distributed micro-transfers, single-transaction scoring fails. Analysts are left manually piecing together evidence across siloed logs, checking compliance policies, and drafting Suspicious Activity Reports (SARs).

This project implements an **autonomous fraud investigation agent** powered by **TigerGraph** and **Google Gemini**:
1. **Ingests fraud alerts** across card accounts, devices, and transaction paths.
2. **Executes multi-hop graph traversals** in TigerGraph to expose connected cards, shared devices, and velocity spikes.
3. **Decides Next-Best Actions (NBA)** dynamically (card freezes, merchant velocity limits, customer callbacks, or immediate clearance).
4. **Protects innocent customers** by differentiating legitimate behavior (e.g. business travel, authorized device changes) from syndicated crime.
5. **Generates regulatory compliance dossiers**, including FFIEC/FinCEN-compliant SAR narratives and full audit trails.

---

## Key Features

- **Interactive Analyst Cockpit**: Real-time web dashboard (FastAPI + Tailwind + Cytoscape.js) visualizing transaction subgraphs, card networks, investigation logs, and downloadable compliance bundles.
- **Official HHGOA 20-Case Benchmark Suite**: Evaluated against the official 20 benchmark scenarios (`HHG-001` through `HHG-020`), covering card-not-present rings, device collusion farms, mule chains, and false-positive shield cases.
- **Dynamic Decisioning (Next-Best Actions)**: Multi-tiered action policy routing (`AUTO_FREEZE`, `BLOCK_CARD`, `NOTIFY_CUSTOMER`, `MONITOR`, `CLOSE_NO_FRAUD`).
- **Value of Information (VoI) Stopping Gate**: Uses an entropy-reduction stopping condition so the agent acquires evidence efficiently without infinite traversal loops.
- **Resilient Dual-Mode Operation**:
  - **Live TigerGraph Mode**: Connects directly to TigerGraph Cloud via REST++ / pyTigerGraph running custom parameterized GSQL queries.
  - **High-Fidelity Graph Simulation Mode**: Automatically engages if the TigerGraph Cloud instance is paused, ensuring uninterrupted demos and testing anytime.

---

## System Architecture

```text
                           [ Alert Ingestion ]
                                   │
                                   ▼
                       [ TigerGraph GSQL Engine ]
                       ├── get_txn_neighborhood
                       ├── get_shared_identifiers
                       └── get_money_flow
                                   │
                    Topology & Multi-Hop Subgraph
                                   │
                                   ▼
                  [ Autonomous Agent (LangGraph) ]
                   ├── Ingest & Triage
                   ├── Multi-Hop Evidence Gathering
                   ├── Value of Information (MDL) Stopping Gate
                   ├── False-Positive Shield (Legitimate Filter)
                   └── Next-Best Action (NBA) Policy Engine
                                   │
            ┌──────────────────────┴──────────────────────┐
            ▼                                             ▼
   [ Regulatory SAR Dossier ]                   [ Real-Time UI Cockpit ]
   - FinCEN Narrative                           - Interactive Cytoscape Graph
   - FFIEC Compliance Fields                    - Live Event Streaming (SSE)
   - Exportable Audit JSON Bundle               - 20-Case Benchmark Switcher
```

---

## Repository Structure

```text
tiger/
├── agent/            # LangGraph multi-step investigation pipeline & Gemini prompts
├── benchmark/        # Benchmark runners, answer linters, and verification scripts
├── cases/            # Official HHGOA benchmark cases (HHG-001.json .. HHG-020.json)
├── dashboard/        # FastAPI web cockpit, Jinja templates, CSS, and Cytoscape.js app
│   ├── static/js/    # Interactive graph renderer and event stream handler (app.js)
│   ├── templates/    # Cockpit UI, Benchmark Case Explorer, Analytics, Architecture
│   └── app.py        # REST API, SSE streaming, and file bundle endpoints
├── docs/             # Technical specifications and ground truth documentation
├── innovation/       # Stopping gates (MDL) and legitimate customer shield logic
├── output/           # Pydantic schema models and compliance dossier builders
├── outputs/          # Generated SAR records, action plans, and benchmark summaries
├── queries/          # Parameterized GSQL queries installed on TigerGraph
├── schema/           # TigerGraph schema DDL and data loader scripts
└── tools/            # TigerGraph pyTigerGraph client, GSQL wrappers, and simulation layer
```

---

## Quick Start

### 1. Environment Setup

Requirements:
- Python 3.10+
- Git

```bash
# Clone repository
git clone https://github.com/singhharsimar23-dotcom/tiger.git
cd tiger

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)

Copy `.env.example` or create a `.env` file in the root directory:

```ini
# TigerGraph Cloud Configuration
TG_HOST=https://your-instance.tgcloud.io
TG_GRAPHNAME=FraudGraph
TG_USERNAME=tigergraph
TG_PASSWORD=your_password
TG_SECRET=your_restpp_secret

# LLM Reasoning Engine
GEMINI_API_KEY=your_gemini_api_key
LLM_MODEL_FAST=gemini-2.5-flash
```

*(Note: If your TigerGraph Cloud instance is sleeping or paused, the system automatically falls back to the embedded benchmark graph simulation mode, so you can test immediately without waiting for a cluster reboot.)*

### 3. Launch the Web Cockpit

```bash
python -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser at **[http://localhost:8000](http://localhost:8000)**.

---

## Navigating the Dashboard

- **Interactive Case Selector**: Toggle quickly between benchmark scenarios (`HHG-014`, `HHG-007`, `HHG-005`, `HHG-001`) or choose any case from `HHG-001` through `HHG-020` via the dropdown.
- **Topological Graph Viewer**: Zoom and inspect transactions (green/red), cards, and device fingerprints connected by real GSQL relationships (`MADE`, `FROM_DEVICE`, `NEXT`, `SIBLING_CARD`).
- **Live Investigation Stream**: Click **"Run Investigation"** to watch the agent analyze the graph, evaluate policies, and determine the Next-Best Action in real time.
- **Compliance & Dossier Tabs**:
  - View raw structured output: `case_record.json`, `sar.json`, `action_before.json`, and `action_after.json`.
  - Download the complete regulatory audit package with one click via **"Download Case Bundle (.zip)"**.
- **Case Explorer (`/cases`)**: Dedicated tabular view comparing all 20 benchmark scenarios with risk scores, exposure, pattern typologies, and final dispositions.

---

## Running Benchmarks & Tests

To validate schema conformance and benchmark execution across all test cases:

```bash
# Run automated tests
pytest tests/

# Run benchmark validation
python benchmark/run_benchmark.py
```

---

## Tech Stack

- **Graph Storage & Querying**: TigerGraph 4.x, GSQL, pyTigerGraph
- **Agent Orchestration**: LangGraph, Python 3.10+
- **LLM Reasoning**: Google Gemini
- **Web UI & Visualization**: FastAPI, Jinja2, Tailwind CSS, Cytoscape.js
- **Validation & Compliance**: Pydantic v2, FinCEN/FFIEC SAR format specifications
