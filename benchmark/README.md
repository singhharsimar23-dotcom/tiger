# HHGOA Fraud Investigation Benchmark Cases (20 Cases)

This directory contains the 20 standardized benchmark cases for evaluating autonomous multi-hop fraud investigation, MDL evidence sufficiency scoring, and automated compliance reporting.

## Case File Schema

Each case file in `benchmark/cases/case_{NN}.json` contains:
```json
{
  "case_number": 1,
  "case_id": "CASE_BENCHMARK_01",
  "trigger_type": "RISK_SCORE | CUSTOMER_REPORT | ANALYST_REFERRAL | VELOCITY_SPIKE | GEO_ANOMALY | SHARED_DEVICE_ALERT",
  "trigger_txn_ids": ["TXN_3882914"],
  "trigger_account_id": "ACC_88219",
  "trigger_risk_score": 0.94,
  "notes": "Context narrative explaining triggering signals..."
}
```

## Supported Trigger Types:
- `RISK_SCORE`: Automated ML anomaly tripped threshold (>0.85).
- `CUSTOMER_REPORT`: Customer dispute or unauthorized activity report.
- `ANALYST_REFERRAL`: Tier-1 investigator escalation.
- `VELOCITY_SPIKE`: Burst of transactions within short time window.
- `GEO_ANOMALY`: Impossible travel or proxy/VPN discrepancy.
- `SHARED_DEVICE_ALERT`: New device linked to multiple accounts or previous fraud.
