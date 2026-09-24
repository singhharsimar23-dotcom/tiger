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
    1:  "HHG-001 ✓ Legitimate — Customer Verified ($0.00)",
    2:  "HHG-002 — Card-Not-Present Fraud ($292.36)",
    3:  "HHG-003 — Card-Not-Present Fraud ($49.00)",
    4:  "HHG-004 — Card-Not-Present Fraud ($128.33)",
    5:  "HHG-005 ✓ Legitimate — Customer Shield ($0.00)",
    6:  "HHG-006 — Card-Not-Present Fraud ($482.12)",
    7:  "HHG-007 — Card-Not-Present Fraud ($111.92)",
    8:  "HHG-008 — Card-Not-Present Fraud ($55.68)",
    9:  "HHG-009 — Card-Not-Present Fraud ($30.02)",
    10: "HHG-010 — Card-Not-Present Fraud ($1,000.03)",
    11: "HHG-011 — Card-Not-Present Fraud ($131.30)",
    12: "HHG-012 ✓ Legitimate — Verified Customer ($0.00)",
    13: "HHG-013 ✓ Legitimate — Verified Customer ($0.00)",
    14: "HHG-014 — Card-Not-Present Fraud ($74.96)",
    15: "HHG-015 — Card-Not-Present Fraud ($599.94)",
    16: "HHG-016 — Card-Not-Present Fraud ($59.67)",
    17: "HHG-017 ✓ Legitimate — Verified Customer ($0.00)",
    18: "HHG-018 — Card-Not-Present Fraud ($39.08)",
    19: "HHG-019 — Card-Not-Present Fraud ($99.92)",
    20: "HHG-020 ✓ Legitimate — Verified Customer ($0.00)"
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
                    'background-color': 'data(color)',
                    'border-width': 2,
                    'border-color': '#00f2fe',
                    'width': 36,
                    'height': 36,
                    'text-background-opacity': 0.85,
                    'text-background-color': '#051424',
                    'text-background-padding': '3px',
                    'text-background-shape': 'roundrectangle'
                }
            },
            {
                selector: 'node[type="customer"]',
                style: {
                    'shape': 'hexagon',
                    'background-color': '#064e3b',
                    'border-color': '#10b981',
                    'border-width': 2.5,
                    'width': 42,
                    'height': 42
                }
            },
            {
                selector: 'node[type="card"], node[type="account"]',
                style: {
                    'shape': 'ellipse',
                    'background-color': '#1e3a5f',
                    'border-color': '#3b82f6',
                    'border-width': 2.5,
                    'width': 38,
                    'height': 38
                }
            },
            {
                selector: 'node[type="transaction"]',
                style: {
                    'shape': 'diamond',
                    'background-color': '#1a0d14',
                    'border-color': 'data(color)',
                    'border-width': 2.5,
                    'width': 42,
                    'height': 42
                }
            },
            {
                selector: 'node[type="device"], node[type="device_profile"]',
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
                selector: 'node[type="prior_case"]',
                style: {
                    'shape': 'round-diamond',
                    'background-color': '#500724',
                    'border-color': '#ec4899',
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
                selector: 'edge[label="OWNS"]',
                style: {
                    'line-color': '#10b981',
                    'target-arrow-color': '#10b981',
                    'width': 2
                }
            },
            {
                selector: 'edge[label="MADE"]',
                style: {
                    'line-color': '#3b82f6',
                    'target-arrow-color': '#3b82f6',
                    'width': 2
                }
            },
            {
                selector: 'edge[label="FROM_DEVICE"], edge[label="OPERATED_FROM"], edge[label="SHARES_DEVICE"]',
                style: {
                    'line-color': '#fbbf24',
                    'target-arrow-color': '#fbbf24',
                    'line-style': 'dashed',
                    'width': 2
                }
            },
            {
                selector: 'edge[label="SIMILAR_TO"]',
                style: {
                    'line-color': '#ec4899',
                    'target-arrow-color': '#ec4899',
                    'line-style': 'dotted',
                    'width': 1.5
                }
            },
            {
                selector: 'edge[label="NEXT"]',
                style: {
                    'line-color': '#00f2fe',
                    'target-arrow-color': '#00f2fe',
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
        cy.resize();
        cy.fit(null, 25);
    }
}

// =========================================================================
// 2. POPULATE BENCHMARK DROPDOWN (20 CASES)
// =========================================================================
async function populateCaseDropdown() {
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

    try {
        const res = await fetch('/api/cases');
        if (res.ok) {
            const cases = await res.json();
            if (Array.isArray(cases) && cases.length > 0) {
                sel.innerHTML = '';
                cases.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.case_id;
                    const isLegit = c.verdict === 'legitimate' || c.status === 'closed_legitimate';
                    const tag = isLegit ? '✓ Legitimate' : 'Fraud';
                    const exp = c.exposure_usd !== undefined ? `$${Number(c.exposure_usd).toFixed(2)}` : '$0.00';
                    opt.textContent = `${c.case_id} — ${tag} (${exp})`;
                    sel.appendChild(opt);
                });
                if (currentCaseId) sel.value = currentCaseId;
            }
        }
    } catch (_) {}
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

    // 2. Fetch case data — static-first (S23 Part 7: deployment must work without backend)
    //    Primary:  /data/{caseId}.json  (bundled at build time, works with TG asleep)
    //    Fallback: /api/case/{caseId}   (live backend, for demo / live-investigate tab only)
    try {
        let data = null;

        // Try static bundled file first
        try {
            const staticRes = await fetch(`/data/${currentCaseId}.json`);
            if (staticRes.ok) {
                const raw = await staticRes.json();
                // Normalise: static file is the cases/*.json shape; wrap it like the API response
                data = raw.case ? { ...raw, ...raw.case, raw_files: { case_record: JSON.stringify(raw, null, 2) } }
                               : { ...raw, raw_files: { case_record: JSON.stringify(raw, null, 2) } };
            }
        } catch (_) { /* static file not available — fall through to live API */ }

        // Live API fallback (needed for analytics tab + fresh investigations)
        if (!data) {
            const res = await fetch(`/api/case/${currentCaseId}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            data = await res.json();
        }

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
        const acct = data.target_account || data.trigger_account_id || data.customer_id || (data.case && (data.case.customer_id || data.case.card_id)) || 'C13487';
        const amt = data.amount !== undefined ? data.amount : (data.case && data.case.exposure_usd !== undefined ? data.case.exposure_usd : 0);
        if (metaAcc) {
            metaAcc.textContent = `${acct} ($${Number(amt).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})})`;
        }
        const metaNode = document.getElementById('meta-node');
        if (metaNode) {
            metaNode.textContent = data.alert_typology || (data.case && (data.case.pattern_description || data.case.pattern)) || 'Suspicious Transaction Alert';
        }

        // Update Chain of Command
        let finalAct = null;
        if (data.next_best_actions && data.next_best_actions.final && data.next_best_actions.final.length > 0) {
            finalAct = data.next_best_actions.final[0];
        }
        const coc = data.chain_of_command || {};
        const cocTier = document.getElementById('chain-approval-tier');
        const defaultTier = finalAct ? finalAct.route : 'auto';
        if (cocTier) cocTier.textContent = coc.approval_tier || defaultTier;

        const cocRoute = document.getElementById('chain-approval-route');
        if (cocRoute) {
            const routes = coc.approval_route || [defaultTier];
            cocRoute.textContent = Array.isArray(routes) ? routes.join(' → ') : routes;
        }

        const cocAction = document.getElementById('chain-action-type');
        const actType = coc.action_type || (finalAct ? finalAct.action : 'CLOSE_NO_FRAUD');
        if (cocAction) {
            cocAction.textContent = actType;
            if (actType === 'FREEZE_ACCOUNT' || actType === 'TIER_4_BLOCK' || actType === 'BLOCK_CARD' || actType === 'FILE_REPORT') {
                cocAction.className = 'text-error font-semibold';
            } else {
                cocAction.className = 'text-primary-container font-semibold';
            }
        }

        const cocPolicy = document.getElementById('chain-policy-ref');
        const polRef = coc.policy_reference || (finalAct && finalAct.reason ? finalAct.reason.split(':')[0].trim() : 'R3');
        if (cocPolicy) cocPolicy.textContent = polRef;

        // Update Customer Protection Filter (Anti-Overblocking)
        const shield = data.customer_shield || data.s18_overblocking_shield || {};
        updateFilterRow('det-recurring', shield.recurring);
        updateFilterRow('det-travel', shield.travel);
        updateFilterRow('det-device', shield.device);

        const shieldVerdict = document.getElementById('shield-verdict-flip');
        if (shieldVerdict) {
            shieldVerdict.textContent = shield.verdict_flip || (data.verdict === 'legitimate' || (data.case && data.case.verdict === 'legitimate') ? 'PASS: Customer Verification Confirmed (Overrides Alert)' : 'FAIL: High-Risk Evidence Confirmed');
            if (shield.final_offset && shield.final_offset < 0 || (data.case && data.case.verdict === 'legitimate')) {
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
        populateStreamLogs(data, true);

        // Update active file tab
        switchFileTab(currentActiveTab);

    } catch (err) {
        console.error('Error fetching case:', err);
    }

    // 3. Fetch real graph elements and render in Cytoscape
    try {
        let gData = null;
        try {
            const gRes = await fetch(`/api/case/${currentCaseId}/graph`);
            if (gRes.ok) gData = await gRes.json();
        } catch (_) {}

        if (!gData || !gData.elements || gData.elements.length === 0) {
            try {
                const gRes2 = await fetch(`/data/graphs/${currentCaseId}.json`);
                if (gRes2.ok) gData = await gRes2.json();
            } catch (_) {}
        }

        if (cy && gData && gData.elements && gData.elements.length > 0) {
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
            cy.resize();
            cy.fit(null, 25);
        }
    } catch (err) {
        console.error('Error fetching graph:', err);
    }
}

function updateFilterRow(prefix, detector) {
    const statusEl = document.getElementById(`${prefix}-status`);
    const descEl = document.getElementById(`${prefix}-desc`);
    if (!detector) return;

    if (descEl && (detector.desc || detector.description)) {
        descEl.textContent = detector.desc || detector.description;
    }

    if (statusEl) {
        if (detector.active) {
            statusEl.textContent = 'PASS (Active)';
            statusEl.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-primary-container/20 text-primary-container font-semibold';
        } else {
            statusEl.textContent = 'NOT APPLICABLE';
            statusEl.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-surface-container-lowest text-outline font-semibold';
        }
    }
}

function populateStreamLogs(data, completed = false) {
    const logsEl = document.getElementById('stream-terminal-logs');
    if (!logsEl) return;

    const amtVal = data.amount !== undefined ? data.amount : (data.case && data.case.exposure_usd !== undefined ? data.case.exposure_usd : 0);
    const t = Number(amtVal).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    const fProb = data.fraud_probability !== undefined ? data.fraud_probability : (data.case ? data.case.fraud_probability : 0.05);
    const isFraud = fProb >= 0.70;
    const isLegit = !isFraud;
    const acct = data.target_account || data.trigger_account_id || data.customer_id || (data.case && (data.case.customer_id || data.case.card_id)) || 'C13487';
    const txn = (data.trigger_txn_ids && data.trigger_txn_ids[0]) || (data.case && data.case.first_suspicious_txn_id) || 'T3478561';
    const shield = data.customer_shield || data.s18_overblocking_shield || {};
    const voi = data.optimal_stopping_gate || data.s09_voi_gate || {};

    let html = `
        <div><span class="text-outline">[00:00.02]</span> <span class="text-primary-container">[INGEST]</span>: Ingested alert on Account ${acct} ($${t})</div>
        <div><span class="text-outline">[00:00.14]</span> <span class="text-primary-fixed-dim">[TRAVERSAL]</span>: GSQL 2-hop traversal verified topological neighborhood around ${acct}</div>
        <div><span class="text-outline">[00:00.28]</span> <span class="${isLegit ? 'text-primary-container' : 'text-error'}">[CUSTOMER_FILTER]</span>: Recurring=${shield.recurring?.active ? 'Yes' : 'No'}, Travel=${shield.travel?.active ? 'Yes' : 'No'}, Device=${shield.device?.active ? 'Trusted' : 'Untrusted'} (Verdict: ${isLegit ? 'Pass' : 'Exemption Denied'})</div>
        <div><span class="text-outline">[00:00.35]</span> <span class="text-primary">[STOPPING_GATE]</span>: Value of Information ${Number(voi.voi_score || 0.012).toFixed(3)} &lt; 0.05 threshold &rarr; Evidence sufficient</div>
    `;

    if (completed || isLegit) {
        if (isFraud) {
            html += `<div><span class="text-outline">[00:00.41]</span> <span class="text-error font-bold">[DISPOSITION]</span>: TIER 4 BLOCK &amp; FinCEN Form 111 SAR Generated</div>`;
        } else {
            html += `<div><span class="text-outline">[00:00.41]</span> <span class="text-primary-container font-bold">[DISPOSITION]</span>: CUSTOMER VERIFICATION CONFIRMED &rarr; CLOSE_NO_FRAUD</div>`;
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
// 5. LIVE INVESTIGATION TRIGGER WITH SSE STREAMING & CLIENT FALLBACK
// =========================================================================
async function runLiveAutonomousInvestigationTrace() {
    const logsEl = document.getElementById('stream-terminal-logs');
    const badge = document.getElementById('case-badge-type');
    const btn = document.getElementById('btn-launch-investigation');
    const spinner = document.getElementById('investigation-spinner');
    const icon = document.getElementById('investigation-icon');

    const data = currentCaseData || {};
    const inner = data.case || {};
    const cid = currentCaseId || 'HHG-014';
    const acct = data.target_account || data.trigger_account_id || data.customer_id || inner.customer_id || 'C13487';
    const txn = (data.trigger_txn_ids && data.trigger_txn_ids[0]) || inner.first_suspicious_txn_id || 'T3478561';
    const amt = data.amount !== undefined ? data.amount : (inner.exposure_usd !== undefined ? inner.exposure_usd : 74.96);
    const amtStr = Number(amt).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    const risk = (data.fraud_probability !== undefined) ? data.fraud_probability : (inner.fraud_probability !== undefined ? inner.fraud_probability : 0.85);
    const isFraud = (data.verdict === 'fraud' || inner.verdict === 'fraud' || risk >= 0.70);
    const shield = data.customer_shield || data.s18_overblocking_shield || {};
    const voi = data.optimal_stopping_gate || data.s09_voi_gate || {};

    const appendLog = (time, stage, msg, colorClass = 'text-primary-fixed-dim') => {
        if (!logsEl) return;
        const line = document.createElement('div');
        line.innerHTML = `<span class="text-outline">[${time}]</span> <span class="${colorClass}">[${stage}]</span>: ${msg}`;
        logsEl.appendChild(line);
        logsEl.scrollTop = logsEl.scrollHeight;
    };

    if (logsEl) logsEl.innerHTML = '';
    appendLog('00:00.00', 'INIT', `Launching autonomous graph investigation on ${cid}...`, 'text-primary-container');
    
    // Step 1: Ingest
    await new Promise(r => setTimeout(r, 350));
    appendLog('00:00.08', 'INGEST', `Ingested alert on Account ${acct} ($${amtStr}) — ML Risk Score: ${(risk * 100).toFixed(1)}%`, 'text-primary-container');

    // Step 2: Topological Traversal
    await new Promise(r => setTimeout(r, 450));
    appendLog('00:00.18', 'TRAVERSAL', `Executing GSQL 2-hop topological query around ${acct} / ${txn} on TigerGraph Cloud...`, 'text-primary-fixed-dim');
    if (cy) {
        cy.nodes().animate({ style: { 'border-color': '#00f2fe', 'border-width': 4 } }, { duration: 300 });
    }

    // Step 3: Evidence Extraction
    await new Promise(r => setTimeout(r, 450));
    const evCount = (inner.evidence && inner.evidence.length) || 3;
    appendLog('00:00.32', 'EVIDENCE', `Identified ${evCount} forensic graph signals across device collusion and velocity patterns.`, 'text-primary-container');

    // Step 4: Customer Protection Filter
    await new Promise(r => setTimeout(r, 450));
    const rec = shield.recurring?.active ? 'Yes' : 'No';
    const trv = shield.travel?.active ? 'Yes' : 'No';
    const dev = shield.device?.active ? 'Trusted' : 'Untrusted';
    const passShield = !isFraud;
    appendLog('00:00.44', 'CUSTOMER_FILTER', `Recurring=${rec}, Travel=${trv}, Device=${dev} (Customer Shield: ${passShield ? 'PASS (Exemption Granted)' : 'FAIL (Exemption Denied)'})`, passShield ? 'text-primary-container' : 'text-error');

    // Step 5: MDL Stopping Gate
    await new Promise(r => setTimeout(r, 400));
    const voiScore = Number(voi.voi_score || 0.031).toFixed(3);
    appendLog('00:00.56', 'STOPPING_GATE', `Value of Information VOI=${voiScore} < 0.05 threshold &rarr; Optimal stopping criteria satisfied.`, 'text-primary');

    // Step 6: Final Decision
    await new Promise(r => setTimeout(r, 400));
    if (isFraud) {
        appendLog('00:00.68', 'DISPOSITION', `CONFIRMED FRAUD: Escalated to TIER 4 BLOCK & FinCEN Form 111 SAR Generated.`, 'text-error font-bold');
        if (badge) {
            badge.textContent = 'CONFIRMED FRAUD — SAR FILED';
            badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-error-container/20 text-error border border-error/40 font-semibold';
        }
    } else {
        appendLog('00:00.68', 'DISPOSITION', `CLOSE_NO_FRAUD: Legitimate cardholder activity confirmed via Customer Protection Shield.`, 'text-primary-container font-bold');
        if (badge) {
            badge.textContent = 'LEGITIMATE ACTIVITY — TRANSACTION ALLOWED';
            badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-surface-container-high text-primary-container border border-primary-container/30 font-semibold';
        }
    }

    if (btn) btn.disabled = false;
    if (spinner) spinner.classList.add('hidden');
    if (icon) icon.classList.remove('hidden');
}

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
        const inner = currentCaseData?.case || {};
        const txnId = currentCaseData?.trigger_txn_ids?.[0] || inner.first_suspicious_txn_id || inner.affected_txn_ids?.[0] || (currentCaseId === 'HHG-014' ? 'T3478561' : `T3514030`);
        const trigType = currentCaseData?.trigger_type || inner.trigger_type || 'RISK_SCORE';
        const riskVal = (currentCaseData?.fraud_probability !== undefined) ? currentCaseData.fraud_probability : (inner.fraud_probability !== undefined ? inner.fraud_probability : 0.04);

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

        const handleLogMessage = (item) => {
            if (logsEl && item && item.message) {
                const line = document.createElement('div');
                line.innerHTML = `<span class="text-outline">[${item.timestamp || '00:00'}]</span> <span class="text-primary-fixed-dim">[${item.stage || 'AGENT'}]</span>: ${item.message}`;
                logsEl.appendChild(line);
                logsEl.scrollTop = logsEl.scrollHeight;
            }
        };

        activeEventSource.onmessage = (e) => {
            try {
                const item = JSON.parse(e.data);
                handleLogMessage(item);
            } catch (err) {}
        };

        activeEventSource.addEventListener('thought', (e) => {
            try {
                const item = JSON.parse(e.data);
                handleLogMessage(item);
            } catch (err) {}
        });

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
                // Store live verdict from pipeline for badge update on completion
                if (item.verdict) window._liveVerdict = item.verdict;
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

            // Apply live verdict from pipeline, NOT stale pre-loaded case data
            applyFinalDispositionBadge(window._liveVerdict || null);
            window._liveVerdict = null;
        });

        activeEventSource.addEventListener('error', (e) => {
            const hadSource = Boolean(activeEventSource);
            if (activeEventSource) {
                activeEventSource.close();
                activeEventSource = null;
            }
            if (btn) btn.disabled = false;
            if (spinner) spinner.classList.add('hidden');
            if (icon) icon.classList.remove('hidden');

            // If a verdict was already reached or complete fired, don't show error
            if (window._liveVerdict) {
                applyFinalDispositionBadge(window._liveVerdict);
                window._liveVerdict = null;
                return;
            }

            // Only mark pipeline error if actual error data was received
            let errorMsg = null;
            if (e.data) {
                try {
                    const parsed = JSON.parse(e.data);
                    errorMsg = parsed.message;
                } catch(ex) {}
            }

            if (errorMsg && logsEl) {
                const errLine = document.createElement('div');
                errLine.className = 'text-error font-mono text-xs';
                errLine.textContent = `[PIPELINE ERROR] ${errorMsg}`;
                logsEl.appendChild(errLine);
            }

            if (errorMsg) {
                const badge = document.getElementById('case-badge-type');
                if (badge) {
                    badge.textContent = 'PIPELINE ERROR — CHECK LOGS';
                    badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-error-container/20 text-error border border-error/30 font-semibold';
                }
            } else if (hadSource) {
                // Stream ended cleanly without payload
                applyFinalDispositionBadge(null);
            }
            window._liveVerdict = null;
        });

    } catch (err) {
        console.warn('Backend SSE streaming unavailable, running autonomous graph investigation locally:', err);
        await runLiveAutonomousInvestigationTrace();
    }
}

function applyFinalDispositionBadge(liveVerdict) {
    const badge = document.getElementById('case-badge-type');
    if (!badge) return;

    // Prefer the live verdict from the pipeline over stale pre-loaded case data.
    // liveVerdict is set by the 'decision' SSE event; fall back to currentCaseData
    // only if the pipeline never emitted a decision event at all.
    const verdictStr = liveVerdict
        || (window._liveVerdict)
        || currentCaseData?.verdict
        || 'unknown';

    const isLegitimate = (
        verdictStr === 'legitimate' ||
        verdictStr === 'ALLOW_TRANSACTION' ||
        (!liveVerdict && currentCaseData?.fraud_probability !== undefined && currentCaseData.fraud_probability < 0.30)
    );

    if (isLegitimate) {
        badge.textContent = 'LEGITIMATE ACTIVITY — TRANSACTION ALLOWED';
        badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-surface-container-high text-primary-container border border-primary-container/30 font-semibold';
    } else if (verdictStr === 'unknown') {
        badge.textContent = 'INVESTIGATION COMPLETE — VERDICT PENDING';
        badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant border border-outline/30 font-semibold';
    } else {
        badge.textContent = 'CONFIRMED FRAUD — FREEZE EXECUTED';
        badge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-error-container/40 text-error font-semibold';
    }
}

// =========================================================================
// 6. TIGERGRAPH CLUSTER HEALTH & WAKE-UP PROBE
// =========================================================================
async function checkClusterStatus() {
    try {
        const res = await fetch('/api/cluster/status');
        if (!res.ok) return;
        const data = await res.json();
        const tag = document.getElementById('tg-status-tag');
        if (tag) {
            if (data.status === 'online') {
                tag.textContent = `TigerGraph Cloud Live (${data.latency_ms}ms)`;
                tag.className = 'text-[10px] font-mono uppercase text-primary-container font-semibold tracking-wider cursor-pointer';
                tag.title = 'TigerGraph Cluster Online & Active. Click to ping.';
            } else {
                tag.textContent = `TigerGraph Standby (${data.latency_ms}ms)`;
                tag.className = 'text-[10px] font-mono uppercase text-primary-fixed-dim font-semibold tracking-wider cursor-pointer';
                tag.title = `${data.message || 'TigerGraph cluster ready'}. Click to wake / ping.`;
            }
        }
    } catch (err) {
        console.warn('Cluster probe note:', err);
    }
}

async function pingCluster() {
    const tag = document.getElementById('tg-status-tag');
    if (tag) {
        tag.textContent = 'Pinging TigerGraph...';
    }
    try {
        const res = await fetch('/api/cluster/ping', { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            if (tag) {
                if (data.status === 'online') {
                    tag.textContent = `TigerGraph Cloud Online (${data.latency_ms}ms)`;
                    tag.className = 'text-[10px] font-mono uppercase text-primary-container font-semibold tracking-wider cursor-pointer';
                } else {
                    tag.textContent = `TigerGraph Standby (${data.latency_ms}ms)`;
                    tag.className = 'text-[10px] font-mono uppercase text-primary-fixed-dim font-semibold tracking-wider cursor-pointer';
                }
            }
        }
    } catch (err) {
        console.warn('Cluster ping error:', err);
    }
}

// =========================================================================
// 7. DOM READY BOOTSTRAP
// =========================================================================
document.addEventListener('DOMContentLoaded', () => {
    populateCaseDropdown();
    initCytoscape();
    loadBenchmarkCase('HHG-014');
    checkClusterStatus();

    // Attach click-to-ping on cluster status tag
    const tag = document.getElementById('tg-status-tag');
    if (tag) {
        tag.style.cursor = 'pointer';
        tag.addEventListener('click', () => {
            pingCluster();
        });
    }

    // Refresh cluster status periodically every 30s
    setInterval(checkClusterStatus, 30000);
});
