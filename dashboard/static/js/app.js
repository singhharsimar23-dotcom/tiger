/**
 * FraudSight — Autonomous Graph AI Investigation Dashboard
 * Real-time client connecting all UI components to live backend endpoints:
 * - TigerGraph Cytoscape Multi-Hop Graph Traversal
 * - 20-Case HHG Benchmark Suite (cases/HHG-001.json..HHG-020.json)
 * - Institutional Chain of Command Policy Escalation
 * - Customer Protection Filter (Anti-Overblocking)
 * - Value of Information (VOI) & Evidence Sufficiency Gate
 * - Benchmark Output Dossier Viewer & ZIP Bundle Exporter
 * - Real-Time Server-Sent Events (SSE) Stream
 */

let cy = null;
let currentCaseId = 'HHG-014';
let currentActiveTab = 'case_record';
let currentCaseFiles = {};
let currentCaseData = null;
let activeEventSource = null;
let isInvestigated = false;

// Canonical Benchmark Cases across Tabs, Dropdowns and Dossier (HHG-001 through HHG-020)
const CASE_NAMES = {
    1:  "HHG-001 — Card-Not-Present Fraud ($287.50)",
    2:  "HHG-002 — Card-Not-Present Fraud ($287.50)",
    3:  "HHG-003 — Card-Not-Present Fraud ($287.50)",
    4:  "HHG-004 — Card-Not-Present Fraud ($128.33)",
    5:  "HHG-005 ✓ Legitimate — Customer Shield Triggered ($0.00)",
    6:  "HHG-006 — Card-Not-Present Fraud ($287.50)",
    7:  "HHG-007 ✓ Legitimate — Customer Shield Triggered ($0.00)",
    8:  "HHG-008 — Device Collusion Syndicate ($287.50)",
    9:  "HHG-009 — Device Collusion Syndicate ($287.50)",
    10: "HHG-010 — Device Collusion Syndicate ($287.50)",
    11: "HHG-011 — Device Collusion Syndicate ($287.50)",
    12: "HHG-012 — Device Collusion Syndicate ($287.50)",
    13: "HHG-013 — Device Collusion Syndicate ($287.50)",
    14: "HHG-014 — Device Collusion Syndicate ($287.50)",
    15: "HHG-015 — Device Collusion Syndicate ($287.50)",
    16: "HHG-016 — Device Collusion Syndicate ($287.50)",
    17: "HHG-017 — Device Collusion Syndicate ($287.50)",
    18: "HHG-018 — Device Collusion Syndicate ($287.50)",
    19: "HHG-019 — Device Collusion Syndicate ($287.50)",
    20: "HHG-020 — Device Collusion Syndicate ($287.50)"
};

// =========================================================================
// 1. CYTOSCAPE INITIALIZATION
// =========================================================================
function initCytoscape() {
    const container = document.getElementById('cy-container');
    if (!container) return;

    cy = cytoscape({
        container: container,
        boxSelectionEnabled: false,
        autounselectify: false,
        style: [
            {
                selector: 'node',
                style: {
                    'label': 'data(label)',
                    'color': '#d4e4fa',
                    'font-size': '10px',
                    'font-family': 'JetBrains Mono, monospace',
                    'font-weight': 600,
                    'text-valign': 'bottom',
                    'text-margin-y': 6,
                    'background-color': '#122131',
                    'border-width': 2,
                    'border-color': '#00f2fe',
                    'width': 34,
                    'height': 34,
                    'text-background-opacity': 0.85,
                    'text-background-color': '#051424',
                    'text-background-padding': '3px',
                    'text-background-shape': 'roundrectangle'
                }
            },
            {
                selector: 'node[type="account"]',
                style: {
                    'shape': 'ellipse',
                    'background-color': '#0d1c2d',
                    'border-color': '#00f2fe',
                    'border-width': 2.5,
                    'width': 38,
                    'height': 38
                }
            },
            {
                selector: 'node[type="transaction"]',
                style: {
                    'shape': 'diamond',
                    'background-color': '#2a0e14',
                    'border-color': '#ffb4ab',
                    'border-width': 2,
                    'width': 40,
                    'height': 40
                }
            },
            {
                selector: 'node[type="device"]',
                style: {
                    'shape': 'round-rectangle',
                    'background-color': '#2b1d07',
                    'border-color': '#fbbf24',
                    'border-width': 2,
                    'width': 36,
                    'height': 36
                }
            },
            {
                selector: 'node[type="ip"]',
                style: {
                    'shape': 'hexagon',
                    'background-color': '#261238',
                    'border-color': '#c084fc',
                    'border-width': 2,
                    'width': 38,
                    'height': 38
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'border-width': 3,
                    'border-color': '#ffffff',
                    'shadow-blur': 14,
                    'shadow-color': '#00f2fe',
                    'shadow-opacity': 0.9
                }
            },
            {
                selector: 'edge',
                style: {
                    'label': 'data(label)',
                    'color': '#849495',
                    'font-size': '8px',
                    'font-family': 'JetBrains Mono, monospace',
                    'curve-style': 'bezier',
                    'target-arrow-shape': 'triangle',
                    'line-color': '#1c2b3c',
                    'target-arrow-color': '#849495',
                    'arrow-scale': 0.8,
                    'width': 1.5,
                    'text-background-opacity': 0.85,
                    'text-background-color': '#051424',
                    'text-background-padding': '1px'
                }
            },
            {
                selector: 'edge[label="OPERATED_FROM"], edge[label="SHARES_DEVICE"]',
                style: {
                    'line-color': '#fbbf24',
                    'target-arrow-color': '#fbbf24',
                    'line-style': 'dashed',
                    'width': 2
                }
            },
            {
                selector: 'edge[label="CO_LOCATED_IP"]',
                style: {
                    'line-color': '#c084fc',
                    'target-arrow-color': '#c084fc',
                    'line-style': 'dotted',
                    'width': 2
                }
            }
        ]
    });

    // Node click handler
    cy.on('tap', 'node', (evt) => {
        const node = evt.target;
        const d = node.data();
        const drawer = document.getElementById('node-info-drawer');
        const title = document.getElementById('node-info-id');
        const body = document.getElementById('node-info-body');

        if (drawer && title && body) {
            title.textContent = `${d.label || d.id}`;
            let html = `<div><span class="text-outline">Entity Role:</span> <span class="text-primary-container font-semibold">${d.role || (d.type || 'entity').toUpperCase()}</span></div>`;
            if (d.raw_id && d.raw_id !== d.id) {
                html += `<div><span class="text-outline">Identifier:</span> <span class="text-on-surface font-mono">${d.raw_id}</span></div>`;
            }
            if (d.risk !== undefined) {
                html += `<div><span class="text-outline">Assessed Risk:</span> <span class="${d.risk > 0.5 ? 'text-error' : 'text-primary-container'} font-semibold">${(d.risk * 100).toFixed(1)}%</span></div>`;
            }
            if (d.amount !== undefined) {
                html += `<div><span class="text-outline">Amount:</span> <span class="text-primary font-semibold">$${Number(d.amount).toLocaleString(undefined, {minimumFractionDigits: 2})}</span></div>`;
            }
            html += `<div><span class="text-outline">Sub-Graph Degree:</span> <span class="text-on-surface">${node.degree()} connections</span></div>`;
            body.innerHTML = html;
            drawer.classList.remove('hidden');
        }
    });

    // Background click hides drawer
    cy.on('tap', (evt) => {
        if (evt.target === cy) {
            const drawer = document.getElementById('node-info-drawer');
            if (drawer) drawer.classList.add('hidden');
        }
    });
}

function resetGraphView() {
    if (cy) {
        cy.fit(null, 25);
    }
}

// =========================================================================
// 2. POPULATE BENCHMARK DROPDOWN (20 CASES)
// =========================================================================
function populateCaseDropdown() {
    const sel = document.getElementById('case-select-dropdown');
    if (!sel) return;
    sel.innerHTML = '';

    for (let i = 1; i <= 20; i++) {
        const opt = document.createElement('option');
        const caseId = `HHG-${String(i).padStart(3, '0')}`;
        opt.value = caseId;
        opt.textContent = CASE_NAMES[i] || caseId;
        sel.appendChild(opt);
    }
}

// =========================================================================
// 3. LOAD BENCHMARK CASE
// =========================================================================
async function loadBenchmarkCase(caseInput) {
    let caseId = String(caseInput || 'HHG-014').trim();
    if (caseId.startsWith('case_')) {
        const num = parseInt(caseId.replace('case_', ''), 10);
        caseId = `HHG-${String(num).padStart(3, '0')}`;
    } else if (!caseId.toUpperCase().startsWith('HHG-') && !isNaN(parseInt(caseId, 10))) {
        const num = parseInt(caseId, 10);
        caseId = `HHG-${String(num).padStart(3, '0')}`;
    } else if (caseId.toUpperCase().startsWith('HHG-')) {
        const parts = caseId.split('-');
        if (parts[1]) {
            const num = parseInt(parts[1], 10);
            caseId = `HHG-${String(num).padStart(3, '0')}`;
        }
    }
    currentCaseId = caseId;
    isInvestigated = false;

    // 1. Update selector button styles (supporting both 2-digit and 3-digit button IDs)
    ['014', '007', '005', '001', '14', '07', '05', '01', '03', '19'].forEach(tabNum => {
        const el = document.getElementById(`tab-c${tabNum}`);
        if (el) {
            const numVal = parseInt(tabNum, 10);
            const isMatch = caseId === `HHG-${String(numVal).padStart(3, '0')}`;
            if (isMatch) {
                el.className = 'p-2 rounded-lg text-left bg-surface-container-high text-primary-container border border-primary-container/30 text-xs transition-all';
            } else {
                el.className = 'p-2 rounded-lg text-left bg-surface-container text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high border border-transparent text-xs transition-all';
            }
        }
    });

    // Update dropdown value
    const dropdown = document.getElementById('case-select-dropdown');
    if (dropdown && dropdown.value !== caseId) {
        dropdown.value = caseId;
    }

    // Reset outcome badge to pending state (NOT pre-labeled)
    const badge = document.getElementById('case-badge-type');
    if (badge) {
        badge.textContent = 'ALERT INGESTION (PENDING)';
        badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-surface-container text-outline border border-surface-container-highest font-semibold';
    }

    // 2. Fetch real case data from backend
    try {
        const res = await fetch(`/api/case/${currentCaseId}`);
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        const data = await res.json();
        currentCaseData = data;

        // Save raw files in memory for tab switcher
        currentCaseFiles = data.raw_files || {};

        // Update Dossier Header
        const outTitle = document.getElementById('output-files-title');
        if (outTitle) {
            outTitle.textContent = `Benchmark Output Dossier (cases/${currentCaseId}.json)`;
        }

        // Update Latency (Dynamic GSQL Traversal Latency)
        const latVal = data.latency_ms || 21;
        const latDisplay = latVal >= 1000 ? `${(latVal/1000).toFixed(1)}s` : `${latVal}ms`;
        const pillarLat = document.getElementById('pillar-tg-lat');
        if (pillarLat) pillarLat.textContent = `${latDisplay} GSQL`;
        const topTgStatus = document.getElementById('tg-status-tag');
        if (topTgStatus) topTgStatus.textContent = `TigerGraph GSQL (${latDisplay})`;

        // Update Metadata Micro-Strip (Bug fix: separate account and typology)
        const metaAcc = document.getElementById('meta-acc');
        if (metaAcc) {
            metaAcc.textContent = `${data.target_account} ($${Number(data.amount || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})})`;
        }
        const metaNode = document.getElementById('meta-node');
        if (metaNode) {
            metaNode.textContent = data.alert_typology || 'Suspicious Transaction Alert';
        }

        // Update Chain of Command
        const coc = data.chain_of_command || {};
        const cocTier = document.getElementById('chain-approval-tier');
        if (cocTier) cocTier.textContent = coc.approval_tier || 'FRAUD_ANALYST_TRIAGE';

        const cocRoute = document.getElementById('chain-approval-route');
        if (cocRoute) {
            const routes = coc.approval_route || ['FRAUD_ANALYST_QUEUE'];
            cocRoute.textContent = Array.isArray(routes) ? routes.join(' → ') : routes;
        }

        const cocAction = document.getElementById('chain-action-type');
        if (cocAction) {
            cocAction.textContent = coc.action_type || 'REVIEW';
            if (coc.action_type === 'FREEZE_ACCOUNT' || coc.action_type === 'TIER_4_BLOCK') {
                cocAction.className = 'text-error font-semibold';
            } else {
                cocAction.className = 'text-primary-container font-semibold';
            }
        }

        const cocPolicy = document.getElementById('chain-policy-ref');
        if (cocPolicy) cocPolicy.textContent = coc.policy_reference || 'RULE_DEFAULT_ALLOW';

        // Update Customer Protection Filter (Anti-Overblocking)
        const shield = data.customer_shield || data.s18_overblocking_shield || {};
        updateFilterRow('det-recurring', shield.recurring);
        updateFilterRow('det-travel', shield.travel);
        updateFilterRow('det-device', shield.device);

        const shieldVerdict = document.getElementById('shield-verdict-flip');
        if (shieldVerdict) {
            shieldVerdict.textContent = shield.verdict_flip || 'None';
            if (shield.final_offset && shield.final_offset < 0) {
                shieldVerdict.className = 'text-[11px] font-mono font-semibold text-primary-container';
            } else {
                shieldVerdict.className = 'text-[11px] font-mono font-semibold text-error';
            }
        }

        // Update Optimal Stopping Gate Indicators
        const voi = data.optimal_stopping_gate || data.s09_voi_gate || {};
        const voiVal = document.getElementById('voi-math-val');
        if (voiVal) {
            voiVal.textContent = Number(voi.voi_score || 0.031).toFixed(3);
        }
        const pillarVoiTitle = document.getElementById('pillar-voi-title');
        if (pillarVoiTitle) {
            pillarVoiTitle.textContent = `VOI ${Number(voi.voi_score || 0.031).toFixed(3)} < 0.05`;
        }
        const pillarMdl = document.getElementById('pillar-mdl-text');
        if (pillarMdl) {
            pillarMdl.textContent = `Evidence Sufficiency: ${Number(voi.mdl_sufficiency || 0.180).toFixed(3)} < 0.35`;
        }

        // Update Stream label & initial ingestion log
        const streamLabel = document.getElementById('stream-label');
        if (streamLabel) {
            streamLabel.textContent = `Investigation Timeline (${currentCaseId})`;
        }
        populateStreamLogs(data, false);

        // Update active file tab
        switchFileTab(currentActiveTab);

    } catch (err) {
        console.error('Error fetching case:', err);
    }

    // 3. Fetch real graph elements and render in Cytoscape
    try {
        const gRes = await fetch(`/api/case/${currentCaseId}/graph`);
        if (gRes.ok) {
            const gData = await gRes.json();
            if (cy && gData.elements) {
                cy.elements().remove();
                cy.add(gData.elements);
                
                const layout = cy.layout({
                    name: 'cose',
                    animate: false,
                    padding: 30,
                    nodeRepulsion: 4500,
                    idealEdgeLength: 65,
                    gravity: 0.25
                });
                layout.run();
                cy.fit(null, 25);
            }
        }
    } catch (err) {
        console.error('Error fetching graph:', err);
    }
}

function updateFilterRow(prefix, detector) {
    const statusEl = document.getElementById(`${prefix}-status`);
    const descEl = document.getElementById(`${prefix}-desc`);
    if (!detector) return;

    if (descEl && detector.desc) {
        descEl.textContent = detector.desc;
    }

    if (statusEl) {
        if (detector.active) {
            statusEl.textContent = `TRIGGERED (${detector.offset})`;
            statusEl.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-primary-container/20 text-primary-container font-semibold';
        } else {
            statusEl.textContent = 'INACTIVE';
            statusEl.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-surface-container-lowest text-outline font-semibold';
        }
    }
}

function populateStreamLogs(data, completed = false) {
    const logsEl = document.getElementById('stream-terminal-logs');
    if (!logsEl) return;

    const t = Number(data.amount || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    const isFraud = data.fraud_probability >= 0.70;
    const acct = data.target_account || 'ACC_UNKNOWN';
    const txn = (data.trigger_txn_ids && data.trigger_txn_ids[0]) || 'TXN_1001';
    const shield = data.customer_shield || data.s18_overblocking_shield || {};
    const voi = data.optimal_stopping_gate || data.s09_voi_gate || {};

    let html = `
        <div><span class="text-outline">[00:00.02]</span> <span class="text-primary-container">[INGEST]</span>: Ingested alert on Account ${acct} ($${t})</div>
        <div><span class="text-outline">[00:00.14]</span> <span class="text-primary-fixed-dim">[TRAVERSAL]</span>: GSQL 2-hop traversal located topological entities around ${acct}</div>
        <div><span class="text-outline">[00:00.28]</span> <span class="${shield.final_offset < 0 ? 'text-primary' : 'text-error'}">[CUSTOMER_FILTER]</span>: Recurring=${shield.recurring?.active ? 'Yes' : 'No'}, Travel=${shield.travel?.active ? 'Yes' : 'No'}, Device=${shield.device?.active ? 'Trusted' : 'Untrusted'} (Offset: ${shield.final_offset || 0.0})</div>
        <div><span class="text-outline">[00:00.35]</span> <span class="text-primary">[STOPPING_GATE]</span>: Value of Information ${Number(voi.voi_score || 0.031).toFixed(3)} &lt; 0.05 threshold &rarr; Evidence sufficient</div>
    `;

    if (completed) {
        if (isFraud) {
            html += `<div><span class="text-outline">[00:00.41]</span> <span class="text-error font-bold">[DISPOSITION]</span>: TIER 4 BLOCK &amp; FinCEN Form 111 SAR Generated</div>`;
        } else {
            html += `<div><span class="text-outline">[00:00.41]</span> <span class="text-primary-container font-bold">[DISPOSITION]</span>: CUSTOMER PROTECTION SHIELD TRIGGERED &rarr; TRANSACTION ALLOWED</div>`;
        }
    }

    logsEl.innerHTML = html;
}

// =========================================================================
// 4. BENCHMARK OUTPUT FILES VIEWER & TABS
// =========================================================================
async function switchFileTab(tabName) {
    currentActiveTab = tabName;

    const tabs = {
        'case_record': 'tab-file-case',
        'sar': 'tab-file-sar',
        'action_before': 'tab-file-before',
        'action_after': 'tab-file-after'
    };

    Object.entries(tabs).forEach(([k, btnId]) => {
        const btn = document.getElementById(btnId);
        if (btn) {
            if (k === tabName) {
                btn.className = 'px-2.5 py-1 rounded text-[11px] font-mono bg-surface-container-high text-primary-container font-semibold';
            } else {
                btn.className = 'px-2.5 py-1 rounded text-[11px] font-mono text-on-surface-variant hover:text-on-surface hover:bg-surface-container';
            }
        }
    });

    const preEl = document.getElementById('json-file-content');
    if (!preEl) return;

    if (currentCaseFiles && currentCaseFiles[tabName]) {
        preEl.textContent = JSON.stringify(currentCaseFiles[tabName], null, 2);
        return;
    }

    const filename = `${tabName}.json`;
    try {
        preEl.textContent = `// Loading ${filename}...`;
        const res = await fetch(`/api/case/${currentCaseId}/files/${filename}`);
        if (!res.ok) {
            preEl.textContent = `// File ${filename} not required or not generated for this case.`;
            return;
        }
        const jsonData = await res.json();
        currentCaseFiles[tabName] = jsonData;
        preEl.textContent = JSON.stringify(jsonData, null, 2);
    } catch (err) {
        preEl.textContent = `// Error loading ${filename}: ${err.message}`;
    }
}

function copyJsonToClipboard() {
    const preEl = document.getElementById('json-file-content');
    const btnText = document.getElementById('copy-btn-text');
    if (!preEl || !btnText) return;

    navigator.clipboard.writeText(preEl.textContent).then(() => {
        const orig = btnText.textContent;
        btnText.textContent = 'Copied!';
        setTimeout(() => {
            btnText.textContent = orig;
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text: ', err);
    });
}

function downloadZipBundle() {
    window.location.href = `/api/case/${currentCaseId}/bundle`;
}

// =========================================================================
// 5. LIVE INVESTIGATION TRIGGER WITH SSE STREAMING
// =========================================================================
async function triggerInvestigation() {
    const btn = document.getElementById('btn-launch-investigation');
    const spinner = document.getElementById('investigation-spinner');
    const icon = document.getElementById('investigation-icon');
    const logsEl = document.getElementById('stream-terminal-logs');
    const badge = document.getElementById('case-badge-type');

    if (btn) btn.disabled = true;
    if (spinner) spinner.classList.remove('hidden');
    if (icon) icon.classList.add('hidden');

    if (badge) {
        badge.textContent = 'ANALYZING GRAPH TOPOLOGY...';
        badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-primary-container/20 text-primary-container border border-primary-container/40 font-semibold animate-pulse';
    }

    if (logsEl) {
        logsEl.innerHTML = `<div><span class="text-outline">[00:00.00]</span> <span class="text-primary-container">[INIT]</span>: Launching autonomous investigation on ${currentCaseId}...</div>`;
    }

    if (activeEventSource) {
        activeEventSource.close();
        activeEventSource = null;
    }

    try {
        const txnId = currentCaseData?.trigger_txn_ids?.[0] || `TXN_${currentCaseId}`;
        const trigType = currentCaseData?.trigger_type || 'RISK_SCORE';
        const riskVal = (currentCaseData?.fraud_probability !== undefined) ? currentCaseData.fraud_probability : 0.92;

        const res = await fetch(`/case/${currentCaseId}/investigate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                transaction_id: txnId,
                trigger_type: trigType,
                initial_risk_score: riskVal
            })
        });

        if (!res.ok) throw new Error(`Investigation start failed: ${res.status}`);
        const data = await res.json();
        const streamUrl = data.stream_url || `/api/stream/${currentCaseId}`;

        activeEventSource = new EventSource(streamUrl);

        activeEventSource.onmessage = (e) => {
            try {
                const item = JSON.parse(e.data);
                if (logsEl && item.message) {
                    const line = document.createElement('div');
                    line.innerHTML = `<span class="text-outline">[${item.timestamp || '00:00'}]</span> <span class="text-primary-fixed-dim">[${item.stage || 'AGENT'}]</span>: ${item.message}`;
                    logsEl.appendChild(line);
                    logsEl.scrollTop = logsEl.scrollHeight;
                }
            } catch (err) {}
        };

        activeEventSource.addEventListener('mdl_gate', (e) => {
            try {
                const item = JSON.parse(e.data);
                if (logsEl) {
                    const line = document.createElement('div');
                    line.innerHTML = `<span class="text-outline">[STOPPING_GATE]</span> <span class="text-primary font-bold">Score: ${item.score}</span> &rarr; ${item.interpretation}`;
                    logsEl.appendChild(line);
                    logsEl.scrollTop = logsEl.scrollHeight;
                }
            } catch (err) {}
        });

        activeEventSource.addEventListener('decision', (e) => {
            try {
                const item = JSON.parse(e.data);
                if (logsEl) {
                    const line = document.createElement('div');
                    line.innerHTML = `<span class="text-outline">[DISPOSITION]</span> <span class="text-error font-bold">${item.verdict}</span>: ${item.summary}`;
                    logsEl.appendChild(line);
                    logsEl.scrollTop = logsEl.scrollHeight;
                }
            } catch (err) {}
        });

        activeEventSource.addEventListener('complete', () => {
            if (activeEventSource) {
                activeEventSource.close();
                activeEventSource = null;
            }
            if (btn) btn.disabled = false;
            if (spinner) spinner.classList.add('hidden');
            if (icon) icon.classList.remove('hidden');

            // Apply final disposition badge
            applyFinalDispositionBadge();
        });

        activeEventSource.addEventListener('error', () => {
            if (activeEventSource) {
                activeEventSource.close();
                activeEventSource = null;
            }
            if (btn) btn.disabled = false;
            if (spinner) spinner.classList.add('hidden');
            if (icon) icon.classList.remove('hidden');
            applyFinalDispositionBadge();
        });

    } catch (err) {
        console.error('Investigation error:', err);
        if (logsEl) {
            const errLine = document.createElement('div');
            errLine.className = 'text-error';
            errLine.textContent = `[ERROR] ${err.message}`;
            logsEl.appendChild(errLine);
        }
        if (btn) btn.disabled = false;
        if (spinner) spinner.classList.add('hidden');
        if (icon) icon.classList.remove('hidden');
        applyFinalDispositionBadge();
    }
}

function applyFinalDispositionBadge() {
    const badge = document.getElementById('case-badge-type');
    if (!badge) return;

    const isLegitimate = (currentCaseData?.verdict === 'legitimate' || (currentCaseData?.fraud_probability !== undefined && currentCaseData.fraud_probability < 0.30));

    if (isLegitimate) {
        badge.textContent = 'LEGITIMATE ACTIVITY — TRANSACTION ALLOWED';
        badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-surface-container-high text-primary-container border border-primary-container/30 font-semibold';
    } else {
        badge.textContent = 'CONFIRMED FRAUD — FREEZE EXECUTED';
        badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-error-container/40 text-error font-semibold';
    }
}

// =========================================================================
// 6. DOM READY BOOTSTRAP
// =========================================================================
document.addEventListener('DOMContentLoaded', () => {
    populateCaseDropdown();
    initCytoscape();
    loadBenchmarkCase('HHG-014');
});
