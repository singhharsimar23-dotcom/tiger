import json
from pathlib import Path

cases_dir = Path(__file__).resolve().parent / "cases"
cases_dir.mkdir(parents=True, exist_ok=True)

cases_data = [
    {
        "case_number": 1,
        "case_id": "CASE_BENCHMARK_01",
        "trigger_type": "RISK_SCORE",
        "trigger_txn_ids": ["TXN_3882914"],
        "trigger_account_id": "ACC_88219",
        "trigger_risk_score": 0.94,
        "notes": "Automated ML scoring tripped high-risk threshold (0.94). Suspected device collusion syndicate."
    },
    {
        "case_number": 2,
        "case_id": "CASE_BENCHMARK_02",
        "trigger_type": "VELOCITY_SPIKE",
        "trigger_txn_ids": ["TXN_2910482"],
        "trigger_account_id": "ACC_19402",
        "trigger_risk_score": 0.88,
        "notes": "Rapid smurfing velocity loop detected. 5 transactions in under 90 seconds."
    },
    {
        "case_number": 3,
        "case_id": "CASE_BENCHMARK_03",
        "trigger_type": "CUSTOMER_REPORT",
        "trigger_txn_ids": ["TXN_4401823"],
        "trigger_account_id": "ACC_55019",
        "trigger_risk_score": 0.82,
        "notes": "Customer reported unauthorized debit card transaction from unknown merchant."
    },
    {
        "case_number": 4,
        "case_id": "CASE_BENCHMARK_04",
        "trigger_type": "ANALYST_REFERRAL",
        "trigger_txn_ids": ["TXN_5129401"],
        "trigger_account_id": "ACC_33912",
        "trigger_risk_score": 0.96,
        "notes": "Tier-1 analyst flagged sudden $12,500 withdrawal following dormant account reactivation."
    },
    {
        "case_number": 5,
        "case_id": "CASE_BENCHMARK_05",
        "trigger_type": "RISK_SCORE",
        "trigger_txn_ids": ["TXN_6819203"],
        "trigger_account_id": "ACC_77201",
        "trigger_risk_score": 0.91,
        "notes": "Bust-out risk model triggered. Line of credit maxed out within 48 hours of credit limit increase."
    },
    {
        "case_number": 6,
        "case_id": "CASE_BENCHMARK_06",
        "trigger_type": "GEO_ANOMALY",
        "trigger_txn_ids": ["TXN_7391024"],
        "trigger_account_id": "ACC_44819",
        "trigger_risk_score": 0.89,
        "notes": "Impossible travel detected. Card swiped in Chicago 18 minutes after transaction in Frankfurt."
    },
    {
        "case_number": 7,
        "case_id": "CASE_BENCHMARK_07",
        "trigger_type": "SHARED_DEVICE_ALERT",
        "trigger_txn_ids": ["TXN_8192048"],
        "trigger_account_id": "ACC_99210",
        "trigger_risk_score": 0.95,
        "notes": "Device fingerprint DEV_88192 previously associated with confirmed ATO ring."
    },
    {
        "case_number": 8,
        "case_id": "CASE_BENCHMARK_08",
        "trigger_type": "CUSTOMER_REPORT",
        "trigger_txn_ids": ["TXN_9018273"],
        "trigger_account_id": "ACC_12049",
        "trigger_risk_score": 0.86,
        "notes": "Report of unauthorized wire transfer routed to offshore digital bank entity."
    },
    {
        "case_number": 9,
        "case_id": "CASE_BENCHMARK_09",
        "trigger_type": "RISK_SCORE",
        "trigger_txn_ids": ["TXN_1092837"],
        "trigger_account_id": "ACC_66391",
        "trigger_risk_score": 0.93,
        "notes": "Card cycling structuring anomaly detected. Repeated micro-charges testing CVV validity."
    },
    {
        "case_number": 10,
        "case_id": "CASE_BENCHMARK_10",
        "trigger_type": "ANALYST_REFERRAL",
        "trigger_txn_ids": ["TXN_2093847"],
        "trigger_account_id": "ACC_88192",
        "trigger_risk_score": 0.90,
        "notes": "Circular money flow detected between 3 accounts with shared residential address."
    },
    {
        "case_number": 11,
        "case_id": "CASE_BENCHMARK_11",
        "trigger_type": "RISK_SCORE",
        "trigger_txn_ids": ["TXN_3192840"],
        "trigger_account_id": "ACC_22384",
        "trigger_risk_score": 0.87,
        "notes": "High-value Card-Not-Present transaction from unverified web proxy."
    },
    {
        "case_number": 12,
        "case_id": "CASE_BENCHMARK_12",
        "trigger_type": "VELOCITY_SPIKE",
        "trigger_txn_ids": ["TXN_4192849"],
        "trigger_account_id": "ACC_77491",
        "trigger_risk_score": 0.84,
        "notes": "Sudden spike of 8 peer-to-peer transfers just under mandatory reporting threshold."
    },
    {
        "case_number": 13,
        "case_id": "CASE_BENCHMARK_13",
        "trigger_type": "CUSTOMER_REPORT",
        "trigger_txn_ids": ["TXN_5291048"],
        "trigger_account_id": "ACC_99302",
        "trigger_risk_score": 0.92,
        "notes": "Customer victim of SIM swap attack. Password and notification email reset prior to wire."
    },
    {
        "case_number": 14,
        "case_id": "CASE_BENCHMARK_14",
        "trigger_type": "ANALYST_REFERRAL",
        "trigger_txn_ids": ["TXN_6391029"],
        "trigger_account_id": "ACC_11492",
        "trigger_risk_score": 0.89,
        "notes": "Dormant account reactivation immediately followed by cryptocurrency exchange purchase."
    },
    {
        "case_number": 15,
        "case_id": "CASE_BENCHMARK_15",
        "trigger_type": "RISK_SCORE",
        "trigger_txn_ids": ["TXN_7491028"],
        "trigger_account_id": "ACC_33829",
        "trigger_risk_score": 0.95,
        "notes": "BIN attack pattern. High frequency sequential card numbers used at POS terminal."
    },
    {
        "case_number": 16,
        "case_id": "CASE_BENCHMARK_16",
        "trigger_type": "SHARED_DEVICE_ALERT",
        "trigger_txn_ids": ["TXN_8592019"],
        "trigger_account_id": "ACC_55920",
        "trigger_risk_score": 0.97,
        "notes": "Device emulator farm fingerprint detected with randomized MAC and screen dimensions."
    },
    {
        "case_number": 17,
        "case_id": "CASE_BENCHMARK_17",
        "trigger_type": "GEO_ANOMALY",
        "trigger_txn_ids": ["TXN_9692018"],
        "trigger_account_id": "ACC_44910",
        "trigger_risk_score": 0.85,
        "notes": "Known Tor exit node IP cluster utilized for e-commerce checkout."
    },
    {
        "case_number": 18,
        "case_id": "CASE_BENCHMARK_18",
        "trigger_type": "CUSTOMER_REPORT",
        "trigger_txn_ids": ["TXN_1792019"],
        "trigger_account_id": "ACC_66928",
        "trigger_risk_score": 0.65,
        "notes": "Customer dispute for subscription recurring charge (low initial suspicion)."
    },
    {
        "case_number": 19,
        "case_id": "CASE_BENCHMARK_19",
        "trigger_type": "ANALYST_REFERRAL",
        "trigger_txn_ids": ["TXN_2893019"],
        "trigger_account_id": "ACC_77819",
        "trigger_risk_score": 0.91,
        "notes": "Merchant collusion shell company. Transactions all routed through single unregistered terminal."
    },
    {
        "case_number": 20,
        "case_id": "CASE_BENCHMARK_20",
        "trigger_type": "RISK_SCORE",
        "trigger_txn_ids": ["TXN_3994029"],
        "trigger_account_id": "ACC_88920",
        "trigger_risk_score": 0.98,
        "notes": "Multi-hop syndicate ring with money mule dispersion and structuring behavior."
    }
]

def generate_cases():
    for item in cases_data:
        num = item["case_number"]
        case_path = cases_dir / f"case_{num:02d}.json"
        with open(case_path, "w", encoding="utf-8") as f:
            json.dump(item, f, indent=2)
    print(f"Generated {len(cases_data)} benchmark case files in {cases_dir}")

if __name__ == "__main__":
    generate_cases()
