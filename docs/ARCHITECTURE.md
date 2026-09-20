# FraudSight: Technical Architecture & System Blueprint

This document provides a comprehensive technical reference of the **FraudSight** system architecture for the TigerGraph HHGOA Hackathon evaluation panel.

---

## 1. Graph Schema Topology (`FraudGraph`)

TigerGraph's native graph database hosts the core entity and relationship data model. The schema is optimized for sub-second BFS multi-hop traversals and dynamic relationship materialization.

### 1.1 Vertex & Edge ASCII Schema Diagram

```text
    ┌──────────────┐                                ┌──────────────┐
    │    Device    │                                │  IPCluster   │
    │ (device_id)  │                                │(ip_cluster_id│
    └──────▲───────┘                                └──────▲───────┘
           │                                               │
     USED_DEVICE                                    FROM_IP_CLUSTER
           │                                               │
    ┌──────┴───────────────────────────────────────────────┴───────┐
    │                         Transaction                          │
    │            (txn_id, amount, is_fraud, risk_score)            │
    └──────────────────────────────▲───────────────────────────────┘
                                   │
                               PERFORMED
                                   │
    ┌──────────────────────────────┴───────────────────────────────┐
    │                           Account                            │
    │         (account_id, p_emaildomain, addr1, risk_score)       │
    └──────┬───────────────────────┬───────────────────────┬───────┘
           │                       │                       │
     SHARES_DEVICE       SHARES_EMAIL_DOMAIN         SHARES_ADDRESS
    (Undirected Ring)      (Domain Sharing)         (Mule Location)
           │                       │                       │
           ▼                       ▼                       ▼
    [Colluding Accts]      [Linked Accounts]       [Syndicate Hub]

========================================================================
             INVESTIGATION, POLICY & GOVERNANCE SUBGRAPH
========================================================================

    ┌──────────────────────────────────────────────────────────────┐
    │                             Case                             │
    │          (case_id, status, disposition, risk_score)          │
    └───┬──────────────────────────┬──────────────────────────┬────┘
        │                          │                          │
   EVIDENCE_FOR            CASE_TRIGGERED_ACTION      CASE_HAS_DECISION
        │                          │                          │
        ▼                          ▼                          ▼
 ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
 │   Evidence   │           │    Action    │           │   Decision   │
 │ (score, type)│           │ (action_type)│           │ (verdict,    │
 └──────────────┘           └──────┬───────┘           │  confidence) │
                                   │                   └──────────────┘
                           ACTION_GOVERNED_BY
                                   │
                                   ▼
                            ┌──────────────┐
                            │  PolicyRule  │
                            │(risk, tier,  │
                            │ requires_sar)│
                            └──────────────┘
```

### 1.2 Schema Entities Summary
- **Financial Entities:** `Account` (1,692 nodes), `Transaction` (860,141 nodes), `Device` (999 nodes), `IPCluster` (999 nodes).
- **Derived Collusion Edges:** `SHARES_DEVICE` (1,248 materialized edges), `SHARES_EMAIL_DOMAIN` (892 edges), `SHARES_ADDRESS` (450 edges).
- **Governance & Audit Entities:** `Case` (20 benchmark cases), `Evidence`, `Decision`, `Action`, `PolicyRule` (5 institutional tiers), `PatternTemplate` (7 documented + discovered patterns).

---

## 2. LangGraph 8-Node Agent State Machine

Investigations execute on a cyclic directed acyclic graph (DAG) compiled with LangGraph.

### 2.1 Node Flow Architecture Diagram

```text
                            [START]
                               │
                               ▼
                        [trigger_node]
               - Ingests alert trigger dictionary
               - Validates transaction ID & baseline risk
                               │
                               ▼
                       [investigate_node]
               - Invokes TigerGraph REST++ / MCP tools
               - Traverses 1-hop & 2-hop topological BFS
                               │
                               ▼
                     [gather_evidence_node]
               - Evaluates shared device hardware fingerprints
               - Computes velocity bursts & money mule links
               - Appends typed Evidence items to state
                               │
                               ▼
           ┌────────► [assess_uncertainty_node] ◄──────────────┐
           │   - Calculates Shannon entropy H(p)               │
           │   - Evaluates MDL Sufficiency Metric              │
           │   - Assesses uncertainty score                    │
           │                   │                               │
           │            (should_gather_more)                   │
           │              /            \                       │
           │   [MDL < 0.35 or iter>=3]  [MDL >= 0.35]          │
           │         /                      \                  │
           │     [proceed]              [gather_more]          │
           │        │                         │                │
           │        │                         ▼                │
           │        │            [gather_more_evidence_node] ──┘
           │        │            - Deep 3-hop money flow BFS
           │        │            - Proxy & IP cluster expansion
           │        ▼
           │   [action_node]
           │   - Matches institutional PolicyRules
           │   - Escalates: ANALYST_TIER_1 -> SUPERVISOR
           │   - Triggers freezing & SAR referral flags
           │        │
           │        ▼
           │   [explain_node]
           │   - Prompts Gemini 2.5 Flash for forensic narrative
           │   - Compiles FFIEC-compliant SAR JSON dossier
           │   - Generates case_record.json audit trail
           │        │
           │        ▼
           │   [memory_node]
           │   - Generates 384-d normalized vector embeddings
           │   - Stores resolved case memory in GraphRAG
           │        │
           │        ▼
           └───── [END]
```

---

## 3. Information-Theoretic Minimum Description Length (MDL) Gate

### 3.1 The Problem
In graph-augmented agentic systems, LLMs exhibit a propensity to enter indefinite search loops—repeatedly querying adjacent hops to achieve zero uncertainty. In enterprise fraud operations, every graph traversal introduces network latency and compute costs, while adding diminishing marginal diagnostic value.

### 3.2 The Mathematical Formulation
FraudSight formulates stopping criteria using **Minimum Description Length (MDL)** principles. The sufficiency score $S(p, C, k)$ is computed as:

$$H(p) = -p \log_2(p) - (1-p) \log_2(1-p)$$

$$S(p, C, k) = \left( \frac{H(p)}{\log_2(2)} \right) \cdot \left( 1 + \frac{C}{10} \right)^{-1} \cdot e^{-0.1 \cdot k}$$

Where:
- $p \in [0, 1]$: Current estimated fraud probability.
- $H(p) \in [0, 1]$: Binary Shannon entropy (normalized by $\log_2(2) = 1.0$).
- $C$: Cumulative cost of gathered evidence (normalized query and traversal weight).
- $k$: Iteration counter (penalizing repetitive loops).

### 3.3 Concrete Numerical Example

| Stage | Fraud Prob ($p$) | Entropy $H(p)$ | Cumulative Cost ($C$) | Iteration ($k$) | MDL Sufficiency Score | Decision Gate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Initial Alert** | 0.880 | 0.529 | 1.00 | 1 | **0.435** | `GATHER_MORE` |
| **After 2-Hop BFS** | 0.940 | 0.327 | 3.50 | 2 | **0.198** | `PROCEED` (Stop & Act) |
| **Ambiguous Case** | 0.550 | 0.993 | 2.00 | 1 | **0.751** | `GATHER_MORE` |
| **After 3-Hop Loop**| 0.890 | 0.500 | 6.50 | 3 | **0.224** | `PROCEED` (Stop & Act) |

**Threshold Rule:**
- If $S(p, C, k) < 0.35$ or $k \ge 3$: **STOP**. The evidence is compressed and sufficient. Transition to `action_node`.
- If $S(p, C, k) \ge 0.35$: **CONTINUE**. Information uncertainty remains high. Transition to `gather_more_evidence_node`.

---

## 4. Unsupervised Pattern Discovery Pipeline

Beyond matching documented static rules, FraudSight implements an autonomous discovery pipeline to detect novel fraud topologies.

```text
[Confirmed Fraud Cases] ──> [Extract 21-D Feature Vector] ──> [StandardScaler Normalization]
                                                                        │
                                                                        ▼
[LLM Semantic Labeling] <── [Compute Discriminating Feats] <── [DBSCAN Clustering (eps=1.5)]
          │
          ▼
[Register PatternTemplate in TigerGraph]
```

### 4.1 21-Dimensional Behavioral Vector
Each fraud case is mapped into a continuous feature space:
1. `mean_txn_amt`, `std_txn_amt`, `max_txn_amt` (Amounts)
2. `mean_c1` through `mean_c14` (IEEE-CIS velocity and count features)
3. `min_d1`, `mean_d1` (Timedelta indicators)
4. `device_type_encoded` (Hardware categorical encoding)
5. `mean_risk_score` (Aggregated model risk)

### 4.2 Discovered Typology Example
- **Cluster 1:** Identified a burst of 5+ micro-transactions under $200 occurring within 600 seconds sharing a single mobile hardware fingerprint. Automatically registered as:
  - **Title:** `High-Velocity Micro-Structuring Smurf Cluster`
  - **Confidence:** 94%
  - **Graph Heuristic:** `SHARES_DEVICE count >= 3 across distinct cardholders`.

---

## 5. Hybrid GraphRAG Memory Retrieval

To ground LLM investigations in institutional precedent, FraudSight implements a hybrid retrieval engine combining **Graph Topological Proximity** with **Dense Semantic Vector Similarity**.

```text
             Query: Target Case Alert Context
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
[TigerGraph Graph BFS]           [Sentence-Transformers]
Traverse k-hop to historical     Embed query into 384-d dense
resolved cases sharing devices   vector (all-MiniLM-L6-v2)
         │                                 │
         ▼                                 ▼
  Structural Score                  Cosine Similarity
   S_struct in [0, 1]                S_semantic in [0, 1]
         │                                 │
         └────────────────┬────────────────┘
                          ▼
           Hybrid Score = 0.4 * S_struct + 0.6 * S_semantic
                          │
                          ▼
             Ranked Precedent Retrieval
```

### 5.1 Retrieval Weighting
- **Topological Proximity ($w=0.4$):** Evaluates path length and common neighbor overlap in TigerGraph. Cases sharing direct device or email edges receive maximum structural affinity.
- **Semantic Similarity ($w=0.6$):** Cosine distance over 384-dimensional dense embeddings of historical investigation summaries and pattern descriptions.

---

## 6. Regulatory Output Dossier Specifications

Every completed investigation generates four standardized artifacts in `outputs/cases/case_XX/`:

1. **`case_record.json`:**
   - Complete investigation metadata, timestamp, and disposition.
   - Comprehensive evidence item array with sources and weights.
   - Full decision transition log with rationale and timestamps.
   - Information-theoretic metrics ($MDL$ score, uncertainty score).

2. **`sar.json`:**
   - Suspicious Activity Report formatted strictly to FFIEC / FinCEN specifications.
   - Regulatory checkboxes: `suspicious_activity_types`, `violation_codes`.
   - Comprehensive 4-paragraph formal narrative suitable for regulatory submission.

3. **`action_before.json` & `action_after.json`:**
   - Pre-investigation baseline policy action (e.g., `FLAG_FOR_REVIEW`, `ANALYST_TIER_1`).
   - Post-investigation escalated posture (e.g., `FREEZE_ACCOUNT`, `SUPERVISOR`).
   - Clear audit delta demonstrating the value added by graph intelligence.
