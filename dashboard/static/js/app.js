document.addEventListener('DOMContentLoaded', () => {
    let cy = null;
    let activeEventSource = null;
    let currentCaseData = null;

    // Benchmark sample cases
    const BENCHMARK_SAMPLES = [
        { txn_id: "TXN_3882914", amount: 4820.00, risk: 0.94, typology: "DEVICE_COLLUSION" },
        { txn_id: "TXN_2910482", amount: 950.00, risk: 0.88, typology: "VELOCITY_SPIKE" },
        { txn_id: "TXN_5129401", amount: 12500.00, risk: 0.97, typology: "HIGH_VALUE_ANOMALY" },
        { txn_id: "TXN_4401823", amount: 310.00, risk: 0.82, typology: "CREDENTIAL_STUFFING" }
    ];

    // Initialize Cytoscape
    function initCytoscape() {
        const container = document.getElementById('cy-container');
        cy = cytoscape({
            container: container,
            style: [
                {
                    selector: 'node',
                    style: {
                        'label': 'data(label)',
                        'color': '#f1f5f9',
                        'font-size': '10px',
                        'font-family': 'Inter, sans-serif',
                        'text-valign': 'bottom',
                        'text-margin-y': 5,
                        'background-color': '#00f2fe',
                        'border-width': 2,
                        'border-color': 'rgba(255, 255, 255, 0.4)',
                        'width': 36,
                        'height': 36
                    }
                },
                {
                    selector: 'node[type="transaction"]',
                    style: {
                        'background-color': '#ff2a5f',
                        'border-color': '#ff6b8b',
                        'width': 44,
                        'height': 44
                    }
                },
                {
                    selector: 'node[type="account"]',
                    style: {
                        'background-color': '#00f2fe',
                        'border-color': '#70f9ff'
                    }
                },
                {
                    selector: 'node[type="device"]',
                    style: {
                        'background-color': '#f59e0b',
                        'border-color': '#fbbf24'
                    }
                },
                {
                    selector: 'node[type="ip"]',
                    style: {
                        'background-color': '#9d4edd',
                        'border-color': '#c77dff'
                    }
                },
                {
                    selector: 'node[type="policy"]',
                    style: {
                        'background-color': '#10b981',
                        'border-color': '#34d399'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': 'rgba(255, 255, 255, 0.15)',
                        'target-arrow-color': 'rgba(255, 255, 255, 0.25)',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'label': 'data(label)',
                        'font-size': '8px',
                        'color': '#94a3b8'
                    }
                },
                {
                    selector: 'edge[label="SHARES_DEVICE"]',
                    style: {
                        'line-color': '#ff2a5f',
                        'line-style': 'dashed',
                        'width': 3
                    }
                }
            ],
            layout: {
                name: 'cose',
                animate: true,
                padding: 30
            }
        });
    }

    // Append thought / event to live stream
    function appendStreamItem(type, title, message) {
        const streamFeed = document.getElementById('stream-feed');
        const placeholder = streamFeed.querySelector('.feed-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        const item = document.createElement('div');
        item.className = `stream-item ${type}`;

        const timeStr = new Date().toLocaleTimeString();
        item.innerHTML = `
            <div class="item-meta">
                <span class="type-tag">${title}</span>
                <span class="item-time">${timeStr}</span>
            </div>
            <div class="item-content">${message}</div>
        `;

        streamFeed.appendChild(item);
        streamFeed.scrollTop = streamFeed.scrollHeight;
    }

    // Launch investigation
    async function startInvestigation(payload) {
        if (activeEventSource) {
            activeEventSource.close();
        }

        document.getElementById('stream-indicator').innerText = 'INVESTIGATING...';
        document.getElementById('decision-card').style.display = 'none';

        try {
            const resp = await fetch('/api/investigate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await resp.json();
            const caseId = data.case_id;

            appendStreamItem('thought', 'AGENT_INIT', `Investigation started for ${payload.transaction_id}. Session: ${caseId}`);

            // Connect SSE stream
            activeEventSource = new EventSource(`/api/stream/${caseId}`);

            activeEventSource.addEventListener('status', (e) => {
                const msg = JSON.parse(e.data);
                appendStreamItem('thought', msg.stage || 'STATUS', msg.message);
            });

            activeEventSource.addEventListener('thought', (e) => {
                const msg = JSON.parse(e.data);
                appendStreamItem('thought', 'REASONING', msg.message);
            });

            activeEventSource.addEventListener('mdl_gate', (e) => {
                const msg = JSON.parse(e.data);
                document.getElementById('mdl-score-val').innerText = Number(msg.score).toFixed(3);
                document.getElementById('mdl-action-badge').innerText = `RECOMMENDED: ${msg.action}`;
                document.getElementById('mdl-gauge-bar').style.width = `${Math.min(msg.score * 100, 100)}%`;
                document.getElementById('mdl-desc').innerText = msg.interpretation;
                appendStreamItem('mdl', 'MDL_GATE', `Evidence Sufficiency Score: ${msg.score}. Action: ${msg.action}`);
            });

            activeEventSource.addEventListener('graph_subgraph', (e) => {
                const graphData = JSON.parse(e.data);
                if (cy) {
                    cy.elements().remove();
                    graphData.nodes.forEach(n => {
                        cy.add({ group: 'nodes', data: { id: n.id, label: n.label, type: n.type } });
                    });
                    graphData.edges.forEach(ed => {
                        cy.add({ group: 'edges', data: { source: ed.source, target: ed.target, label: ed.label } });
                    });
                    cy.layout({ name: 'cose', animate: true }).run();
                }
            });

            activeEventSource.addEventListener('decision', (e) => {
                const msg = JSON.parse(e.data);
                currentCaseData = msg;
                document.getElementById('dossier-verdict').innerText = msg.verdict;
                document.getElementById('dossier-risk').innerText = `Risk Level: ${msg.risk_level}`;
                document.getElementById('dossier-summary').innerText = msg.summary;
                document.getElementById('decision-card').style.display = 'block';
                appendStreamItem('decision', 'DECISION_FINAL', `Disposition: ${msg.verdict} | SAR Required: ${msg.sar_required}`);
            });

            activeEventSource.addEventListener('complete', () => {
                document.getElementById('stream-indicator').innerText = 'COMPLETED';
                activeEventSource.close();
            });

            activeEventSource.addEventListener('error', (e) => {
                appendStreamItem('decision', 'ERROR', 'Stream disconnected or completed.');
                activeEventSource.close();
            });

        } catch (err) {
            appendStreamItem('decision', 'NETWORK_ERROR', err.message);
        }
    }

    // Modal Handlers
    document.getElementById('btn-view-sar').addEventListener('click', () => {
        const modal = document.getElementById('modal-overlay');
        document.getElementById('modal-title').innerText = 'Suspicious Activity Report (SAR.json) Preview';
        const dummySAR = {
            sar_id: `SAR_${Date.now()}`,
            case_id: currentCaseData ? currentCaseData.case_id : "CASE_DEMO",
            filing_institution: "HHGOA Autonomous Risk Defense",
            suspect_entity: {
                account_id: "ACC_MULE_1",
                risk_score: 0.94,
                collusion_type: "DEVICE_SHARING_RING"
            },
            narrative: currentCaseData ? currentCaseData.summary : "Confirmed multi-hop fraud syndicate.",
            generated_at: new Date().toISOString()
        };
        document.getElementById('modal-json-content').innerText = JSON.stringify(dummySAR, null, 2);
        modal.style.display = 'flex';
    });

    document.getElementById('btn-view-case').addEventListener('click', () => {
        const modal = document.getElementById('modal-overlay');
        document.getElementById('modal-title').innerText = 'Master Case Record (case_record.json) Preview';
        const dummyCase = {
            case_id: currentCaseData ? currentCaseData.case_id : "CASE_DEMO",
            verdict: currentCaseData ? currentCaseData.verdict : "CONFIRMED_FRAUD",
            risk_level: currentCaseData ? currentCaseData.risk_level : "CRITICAL",
            mdl_sufficiency: { score: 0.28, action: "ACT" },
            actions_executed: ["FREEZE_ACCOUNT", "DECLINE_PENDING_TXNS", "FILE_SAR"],
            timestamp: new Date().toISOString()
        };
        document.getElementById('modal-json-content').innerText = JSON.stringify(dummyCase, null, 2);
        modal.style.display = 'flex';
    });

    document.getElementById('btn-close-modal').addEventListener('click', () => {
        document.getElementById('modal-overlay').style.display = 'none';
    });

    // Random transaction picker
    document.getElementById('btn-random-txn').addEventListener('click', () => {
        const sample = BENCHMARK_SAMPLES[Math.floor(Math.random() * BENCHMARK_SAMPLES.length)];
        document.getElementById('input-txnid').value = sample.txn_id;
        document.getElementById('input-amount').value = sample.amount.toFixed(2);
        document.getElementById('input-risk').value = sample.risk;
        document.getElementById('input-trigger').value = sample.typology;
    });

    // Form submit
    document.getElementById('investigate-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const payload = {
            transaction_id: document.getElementById('input-txnid').value,
            amount: parseFloat(document.getElementById('input-amount').value),
            initial_risk_score: parseFloat(document.getElementById('input-risk').value),
            trigger_type: document.getElementById('input-trigger').value
        };
        startInvestigation(payload);
    });

    // Toolbar controls
    document.getElementById('btn-relayout').addEventListener('click', () => {
        if (cy) cy.layout({ name: 'cose', animate: true }).run();
    });

    document.getElementById('btn-fit-graph').addEventListener('click', () => {
        if (cy) cy.fit();
    });

    // Run benchmark trigger
    document.getElementById('btn-run-benchmark').addEventListener('click', () => {
        appendStreamItem('thought', 'BENCHMARK', 'Initiating 20-case benchmark evaluation suite...');
        startInvestigation({
            transaction_id: "BENCHMARK_SUITE_01",
            amount: 8400.0,
            initial_risk_score: 0.96,
            trigger_type: "DEVICE_COLLUSION"
        });
    });

    // Init
    initCytoscape();
    // Load initial sample graph
    fetch('/api/graph/sample')
        .then(r => r.json())
        .then(data => {
            if (cy && data.elements) {
                cy.add(data.elements);
                cy.layout({ name: 'cose', animate: false }).run();
            }
        })
        .catch(() => {});
});
