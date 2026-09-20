---
name: Sentinel Graph Intelligence
colors:
  surface: '#051424'
  surface-dim: '#051424'
  surface-bright: '#2c3a4c'
  surface-container-lowest: '#010f1f'
  surface-container-low: '#0d1c2d'
  surface-container: '#122131'
  surface-container-high: '#1c2b3c'
  surface-container-highest: '#273647'
  on-surface: '#d4e4fa'
  on-surface-variant: '#b9cacb'
  inverse-surface: '#d4e4fa'
  inverse-on-surface: '#233143'
  outline: '#849495'
  outline-variant: '#3a494b'
  surface-tint: '#00dce6'
  primary: '#e0fdff'
  on-primary: '#00373a'
  primary-container: '#00f2fe'
  on-primary-container: '#006a70'
  inverse-primary: '#00696f'
  secondary: '#c0c1ff'
  on-secondary: '#1000a9'
  secondary-container: '#3131c0'
  on-secondary-container: '#b0b2ff'
  tertiary: '#fff5f4'
  on-tertiary: '#67001b'
  tertiary-container: '#ffcfd1'
  on-tertiary-container: '#be0d3c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ff6ff'
  primary-fixed-dim: '#00dce6'
  on-primary-fixed: '#002022'
  on-primary-fixed-variant: '#004f53'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#ffdadb'
  tertiary-fixed-dim: '#ffb2b7'
  on-tertiary-fixed: '#40000d'
  on-tertiary-fixed-variant: '#92002a'
  background: '#051424'
  on-background: '#d4e4fa'
  surface-variant: '#273647'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  mono-data-lg:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: -0.01em
  mono-data-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
  mono-label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.04em
  mono-micro:
    fontFamily: JetBrains Mono
    fontSize: 9px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.06em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.75rem
  gutter-desktop: 1rem
  margin: 0.75rem
  margin-desktop: 1.25rem
  space-xs: 0.25rem
  space-sm: 0.375rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

The design system projects mission-critical authority, rigorous compliance clarity, and ultra-high-density analytical power. Tailored for Tier-1 financial crime investigators, forensic blockchain auditors, and institutional SecOps intelligence units, the visual tone balances forensic precision with instantaneous cognitive triage.

The aesthetic fuses **Precision Technical Minimalism** with **Subtle Structural Glassmorphism**:
- **Controlled Visual Density:** Information-packed layouts engineered for dual-monitor SOC configurations, removing decorative latency while preserving scannability.
- **Forensic Legibility:** Micro-borders, fine hairline separators, and optical data anchors that prevent analytical fatigue during extended investigative workflows.
- **Deterministic Encodings:** Absolute, non-negotiable color semantic mappings for entity taxonomy, risk triage, and regulatory SAR/FinCEN audit trails.
- **Tactical Utility:** Zero decorative noise, zero oversized radius treatments, and intentional negative space calibrated strictly around relational data nodes and evidentiary trees.

## Colors

The system employs a cold-spectrum, slate-obsidian foundation calibrated to reduce ocular strain during deep log audits, overlaid with high-luminance functional accents.

### Palette Architecture
- **Canvas & Surface System:**
  - `Surface Void` (`#070a0f`): Base application viewport and graph canvas backing.
  - `Surface Tier 1` (`#0b0f17`): Structural docking panels, sidebar navigation, dossier headers.
  - `Surface Tier 2` (`#111827`): Active inspectors, analytical cards, node property sheets.
  - `Surface Elevated / Popover` (`#1e293b`): Contextual menus, tooltip dossiers, floating controls.
  - `Border Hairline` (`#1e293b` / `rgba(148, 163, 184, 0.12)`): Monolithic 1px boundary rules.

### Entity & Graph Topology Taxonomies
- **Entities & Ledgers:** Cyan Primary (`#00f2fe`) to Indigo Accent (`#6366f1`). Identifies core ledger accounts, wallets, and counterparties.
- **Hardware & Fingerprints:** Amber Alert (`#f59e0b`). Identifies IMEI, hardware MACs, and session tokens.
- **Network & Perimeter:** Emerald Telemetry (`#10b981`). Identifies autonomous systems (ASNs), egress proxies, IPs, and DNS records.
- **Syndicates & Malicious Nexus:** Rose/Crimson Threat (`#f43f5e`). Applied exclusively to sanctioned actors, mule rings, and illicit clusters.

### Regulatory Risk & Audit Spectrum
- **Nominal / Cleared:** `#10b981` (Emerald-500)
- **Review / Suspicious:** `#f59e0b` (Amber-500)
- **Critical / SAR Immediate:** `#f43f5e` (Rose-500)
- **Audit Accent / Anchor:** `#38bdf8` (Sky-400)

## Typography

The typographic hierarchy separates semantic synthesis from telemetry extraction. 

- **Primary Interface Face (Inter):** Deployed for cognitive framing, workflow navigation, incident synopses, and structural form labels. Configured with tight negative tracking at scale to enforce an institutional, engineered posture.
- **Telemetry & Monospace Face (JetBrains Mono):** Dedicated to transaction hashes, cryptographic addresses, IP routes, timestamps (ISO-8601 UTC), audit log entries, and risk weights. The monospaced numerals preserve tabular alignment across high-frequency audit columns.
- **Rule of Upper-Case Micro Labels:** All system status indicators, badge counters, and SAR field taxonomies rely on `mono-micro` or `mono-label-sm` rendered in uppercase with deliberate positive letter-spacing (`0.04em`–`0.06em`) to guarantee immediate legibility at low point sizes.

## Layout & Spacing

The layout model is anchored by a high-density, multi-pane workbench layout optimized for relational graph exploration, live ledger streaming, and side-by-side compliance dossiers.

### Layout Framework
- **Workbench Topology:** Tri-panel split architecture (Collapsible Tactical Navigation [64px–240px] | Interactive Canvas / Timeline Core [Fluid, min 640px] | Contextual Dossier Inspector [360px–480px]).
- **Vertical Rhythm:** 4px atomic baseline grid. Internal card paddings default to `space-md` (12px) to maximize data density per visual field without clutter.
- **Breakpoints:**
  - `Desktop Forensic (≥1680px)`: Full 3-pane workbench active simultaneously with visible node telemetry.
  - `Desktop Standard (1280px–1679px)`: 3-pane active with contextual inspector collapsible to persistent rail.
  - `Mobile / Tablet Review (<1024px)`: Reflows to single-stream triage queue; graph canvas switches to linearized transaction timeline with bottom-sheet metadata drawers.

## Elevation & Depth

This design system rejects deep drop-shadows and generic blur dispersion, using instead razor-sharp structural layers and hairline luminances.

### Depth Hierarchy
1. **Level 0 (Investigation Canvas):** Solid `#070a0f`. Zero elevation, zero shadows. Features an optional SVG dot-matrix grid at 24px intervals with `#1e293b` color at 40% opacity.
2. **Level 1 (Docked Inspection Panels):** `#0b0f17` with hairline right or left border of `1px solid rgba(148, 163, 184, 0.1)`. No drop shadow.
3. **Level 2 (Analytical Cards & Dossier Units):** `#111827` surface with subtle background backdrop blur (`backdrop-filter: blur(8px)`) when overlaid on graph canvases. Inset hairline border: `1px solid rgba(255, 255, 255, 0.05)`.
4. **Level 3 (Modal Overlays & Quick-Inspect Flyouts):** `#1e293b` surface. Outset shadow: `0 8px 24px -4px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(148, 163, 184, 0.18)`.
5. **Node Hover & Selection Highlights:** Graph nodes project no diffuse shadow; instead, they render a crisp concentric SVG stroke halo (`2px ring` at `rgba(0, 242, 254, 0.4)`) with an outer hairline boundary.

## Shapes

The design system standardizes on a precise, clinical micro-radius geometry (`roundedness: 1`). Large, organic radii degrade spatial density and conflict with tabular financial and forensic data.

- **Base Radius (`0.25rem` / `4px`):** Used on all standard buttons, inputs, badge tags, tab navigators, and inline code blocks.
- **Card & Surface Radius (`rounded-lg: 0.5rem` / `8px`):** Applied to modal wrappers, audit dossier sections, and floating utility toolbars.
- **Strict Sharp Rules (`0px`):** Node visual anchors, graph viewport dividing rules, pinned workbench panels, and tabular row cells adhere to hard 0px corners to ensure visual continuity across continuous data grids.

## Components

### Buttons & Interactive Triggers
- **Primary Operational:** High-luminance Cyan (`#00f2fe`) background with obsidian text (`#070a0f`), font-weight 600. Active states trigger a 1px inset boundary (`rgba(0, 0, 0, 0.2)`).
- **Destructive / Flag Syndicate:** Crimson (`#f43f5e`) base with white text. Used exclusively for escalation, node termination, and high-risk freezing actions.
- **Secondary / Ghost Terminal:** Dark slate (`#111827`) fill, hairline border (`#1e293b`), text `#94a3b8`. Hover transitions text to `#f8fafc` and border to `#00f2fe`.

### Entity Badges & Status Indicators
- **Form Factor:** Pill or micro-box formats using `mono-micro` styling, with an absolute height of 20px, horizontal padding of 6px, and 1px borders.
- **Semantic Mappings:**
  - *Ledger Account:* Background `rgba(0, 242, 254, 0.08)`, Border `rgba(0, 242, 254, 0.3)`, Text `#00f2fe`.
  - *Flagged Ring:* Background `rgba(244, 63, 94, 0.12)`, Border `rgba(244, 63, 94, 0.4)`, Text `#f43f5e`.
  - *Network Route:* Background `rgba(16, 185, 129, 0.08)`, Border `rgba(16, 185, 129, 0.3)`, Text `#10b981`.

### Stopping Condition Gauges (VOI / MDL Thresholds)
- **Structure:** Value of Information (VOI) and Minimum Description Length (MDL) convergence meters are displayed as compact horizontal segment bars (height 4px) paired with real-time numeric readouts in `mono-data-md`.
- **States:** Active exploration renders in `#38bdf8`. Threshold convergence / stopping state locked triggers solid Emerald (`#10b981`) with a static, non-pulsing terminal badge (`"MDL OPTIMAL"`).

### Audit-Ready FFIEC SAR Dossier Tabs
- **Tab Rails:** Continuous 32px tab strip with `0.25rem` radius corners, styled with a `#070a0f` track. Active tab displays `#111827` surface with a 2px top accent line in `#00f2fe`.
- **Compliance Panels:** Fixed schema metadata views containing structured fields (e.g., Narrative Summary, Suspect Information, Suspicious Activity Classification). Field keys are rendered in `mono-label-sm` (`#94a3b8`), and values are rendered in `body-md` (`#f8fafc`) with an instant "Copy for FinCEN Filing" macro button adjacent to each section.

### Form Inputs & Terminal Filter Bars
- **Filter Inputs:** Monospaced inputs with an integrated search token parser. Background `#0b0f17`, border `1px solid #1e293b`, font `mono-data-md`. Focus state uses `1px solid #00f2fe` without glowing drop-shadow halos.
- **Checkboxes & Segment Radios:** Rigid 14px boxes with a 2px radius. Active state shows an obsidian checkmark over a solid `#00f2fe` ground.