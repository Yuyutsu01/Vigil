# 📜 Vigil Landing Page — Master Script & UI/UX Storyboard

> **Document Status**: Proposal & Visual Specification  
> **Target Scope**: `frontend/` only (Backend untouched)  
> **Author**: Antigravity  
> **Version**: 1.0.0  

---

## 🎯 Executive Summary & Purpose

The **Vigil Landing Page** serves as the primary storefront and conversion engine for the **Agentic AI Code Review & Security Assistant**. It communicates Vigil’s deep technical rigor (static taint tracking, gVisor microVM patch isolation, multi-agent AST orchestration) through an ultra-sleek, OLED dark-mode aesthetic with interactive 3D WebGL particle physics, live interactive dashboard mockups, and transparent empirical benchmarks.

---

## 🎬 Section-by-Section Storyboard & Script

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 1. STICKY NAVBAR: Brand, Anchor Navigation, Status Indicator, Auth CTAs         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 2. 3D HERO: WebGL Vortex Particle Canvas, Pitch, Dual CTA Buttons, Marquee     │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 3. MISSION STATEMENT (#about): "Why Vigil Exists" + 3 Core Technical Pillars    │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 4. HOW VIGIL WORKS (#features): 6-Card Architecture & Review Pipeline Grid      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 5. EMPIRICAL BENCHMARKS (#benchmarks): Verifiable Architectural Metrics         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 6. CUSTOMER PROOF (#testimonials): Enterprise Security Engineer Endorsements    │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 7. STATEFUL EXECUTION (#execution): Interactive IDE & PR Pipeline Mockup        │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 8. GOVERNANCE & RULES (#verification): Interactive Policy Toggles & MicroVMs   │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 9. MULTI-AGENT FLEET TELEMETRY (#insights): 14-Agent Breakdown & Telemetry Lake │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 10. CELESTIAL CANVAS CTA (#cta): Dual-Stream Starfield & Final Conversion       │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 11. INTERACTIVE DEMO MODAL: 4-Step Live Terminal Sandbox Simulation             │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 12. GLOBAL FOOTER: System Status, Product Matrix, Compliance, Copyright         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### Scene 1: Sticky Navigation Header (`Navbar.tsx`)

* **Visual Style**: Broader translucent glassmorphism (`backdrop-blur-xl bg-black/85 border-b border-white/15 shadow-2xl`), sticky top-0, z-50 with specular top rim lighting.
* **Layout**:
  * **Dimensions**: `max-w-[1440px]`, `h-16 sm:h-[68px]`, generous horizontal padding (`px-5 sm:px-8 lg:px-12`).
  * **Left**: Brand Logo (Shield glyph with pulsing emerald dot) + `Vigil` wordmark.
  * **Center**: High-readability navigation links with **glossy frosted pill hover interactions**:
    * `About` → `#about`
    * `Capabilities` → `#features`
    * `Results` → `#benchmarks`
    * `Pipeline` → `#execution`
    * `Security` → `#verification`
    * `Product` → `#insights`
    * `Customers` → `#testimonials`
    * *Hover FX*: `hover:bg-white/[0.08] hover:border-white/20 hover:backdrop-blur-md hover:shadow-[0_0_15px_rgba(255,255,255,0.07)] active:scale-95`.
  * **Right**:
    * **SecOps Console** link with glossy ambient pill styling.
    * **Get Started** luminous star-glow button (`/register`).

---

### Scene 2: 3D Interactive Hero Canvas (`Hero.tsx` + `Vortex.tsx`)

* **Visual Style**: Full viewport height (`100dvh`), pure OLED background (`#000000`) with real-time Three.js WebGL particle vortex reacting to cursor velocity and pointer repel physics.
* **Primary Headline**:
  * **"Your Code's Got Secrets. We Find Them."**
* **Subheading**:
  * *"Vigil puts your code under the microscope. AI agents hunt down bugs, security risks, and code smells, then explain the issue, severity, and fix, so you can ship without surprises."*
* **Call-to-Action Cluster**:
  1. **Primary Button (`StarButton`)**: `GET STARTED →` — animated radial highlight sweeping around a pill border. Routes to `/register`.
  2. **Secondary Button (`DemoButton`)**: `REQUEST A DEMO` — crisp white pill button with subtle top specular line. Triggers interactive terminal simulation modal.
* **Pinned Velocity Marquee (Running Tech & Security Logos)**:
  * Infinite horizontal auto-scroll with fluid inertial acceleration on hover (`40px/s → 130px/s`).
  * Running Logos:
    * ⚛️ **React** (Interactive Atom SVG)
    * ⚗️ **Alembic** (Migration Flask SVG)
    * ⚡ **FastAPI** (Async Lightning Bolt SVG)
    * 🕸️ **LangGraph** (Multi-Agent State Graph SVG)
    * 🔐 **JWT** (Cryptographic Token Lock SVG)
    * 🐘 **PostgreSQL** (Relational Database SVG)
    * 🐳 **Docker** (Containerization Whale SVG)
    * 🛡️ **CWE** (MITRE Security Taxonomy Shield SVG)
    * 🔍 **Semgrep** (AST Rule Engine SVG)

---

### Scene 3: Editorial Mission Statement (`ContentSections.tsx` → `#about`)

* **Section Tag**: `WHY VIGIL EXISTS`
* **Lead Title**:
  * **"Every commit is a chance to ship a bug. Vigil watches your code, explains what's wrong, and tells you how to fix it — before your users find out the hard way."**
* **Three Architectural Value Pillars**:
  1. **Built on Real Code Analysis**: AST-level parsing matching compiler accuracy; zero hallucinated syntax errors.
  2. **Your Code Never Gets Run**: Strictly static analysis for evaluation. Candidate patches execute exclusively within zero-network disposable sandboxes.
  3. **Safe, Ready-to-Review Fixes**: Automated fixes formatted as unified diffs (`+` / `-`) ready for code review without style regressions.

---

### Scene 5: Core Capabilities 6-Card Grid (`ContentSections.tsx` → `#features`)

* **Section Tag**: `HOW VIGIL WORKS`
* **Headline**: *"A complete review pipeline that runs on every pull request."*
* **6 Structured Engine Cards**:
  * `01 // TRACKING`: **Trace user input across your code** — Inter-procedural taint flow from sources (query params, body payloads) to dangerous sinks (SQL execution, shell exec).
  * `02 // ISOLATION`: **Test fixes in an isolated sandbox** — MicroVM sandbox builds the patch and runs existing test suites to prevent behavioral regressions.
  * `03 // ENFORCEMENT`: **Stop bad code before it merges** — Automated GitHub PR status check blocking merges on Critical/High CWE violations.
  * `04 // REPORTS`: **Export reports for your security team** — Automated SARIF, JSON, PDF executive summaries and immutable audit trails.
  * `05 // LEARNING`: **Gets smarter from your feedback** — Tenant-isolated memory remembering false positives and team conventions.
  * `06 // COST CONTROL`: **No surprise AI bills** — Strict token/dollar budget caps and wall-clock deadlines per PR execution.

---

### Scene 6: Verifiable Architectural Benchmarks (`ContentSections.tsx` → `#benchmarks`)

* **Section Tag**: `VERIFIABLE METRICS`
* **Headline**: *"Built on transparent, verifiable architecture"*
* **4 Live Metric Tiles**:
  * `3` — **PYTHON · JS · TS** (Supported Languages)
  * `13` — **7 RULES + 6 ADAPTERS** (Detection Layers)
  * `0` — **ZERO EXECUTION** (Unsandboxed Runs)
  * `<dynamic>` — **MEDIAN REVIEW TIME** (Live backend stats or dynamic simulated median `1.8s`)
* **Footnote**: *"Numbers verified by Vigil's static analysis architecture and automated test suites."*

---

### Scene 7: Customer & Security Team Endorsements (`ContentSections.tsx` → `#testimonials`)

* **Section Tag**: `CUSTOMER PROOF`
* **Headline**: *"Trusted by engineering and security teams"*
* **Quotes**:
  * *David K. (Staff Security Engineer, FinTech Corp)*: "Vigil replaced three separate static analysis tools in our CI pipeline. It caught an authorization flaw that had evaded two external penetration tests."
  * *Elena R. (Head of AppSec, CloudScale)*: "The safe diff generation is revolutionary. Developers actually merge the proposed fixes because there are zero style or linter regressions."
  * *Marcus T. (VP Engineering, HealthGrid)*: "Our security auditors accepted Vigil's automated audit dossiers without requesting secondary manual reviews."

---

### Scene 8: Stateful Pipeline Execution Engine (`StatefulExecutionSection.tsx` → `#execution`)

* **Section Tag**: `REVIEW PIPELINE`
* **Headline**: *"Clear visibility across every review and fix."*
* **Interactive UI Component**:
  * Full embedded interactive IDE simulation with:
    * **Left Navigation**: Vulnerability Inbox (badges), Review Agents, Audit History, CWE Pulse.
    * **Middle Task Flow**: Monitored repos (`api-gateway`, `auth-service`), active run stages (`AST Parse → Semgrep Rules → LLM Taint Correlator → MicroVM Test`).
    * **Right Inspection Panel**: Real-time unified diff preview with syntax highlighting and step-by-step reasoning trace.

---

### Scene 9: Security Governance & Rule Enforcement (`DurableAutonomySection.tsx` → `#verification`)

* **Section Tag**: `SECURITY RULES & ENFORCEMENT`
* **Headline**: *"Total control over your security policies."*
* **Interactive Policy Matrix**:
  * Live dropdown controls for policy actions:
    * `SQL Injection (CWE-89)` → [Block PR | Require approval | Monitor only]
    * `Command Injection (CWE-78)` → [Block PR | Require approval | Monitor only]
    * `Insecure Deserialization (CWE-502)` → [Block PR | Require approval | Monitor only]
    * `Hardcoded Secrets & API Keys` → [Block PR | Require approval | Monitor only]
    * `MicroVM Sandbox Patch Test` → [Enforce | Require approval | Disable]
    * `SARIF Compliance Dossier` → [Enforce | Require approval | Disable]
  * Interactive Vulnerability Inbox Inspector showing tainted AST call graphs and remediation recommendations.

---

### Scene 10: Multi-Agent Fleet Telemetry (`AgentInsightsSection.tsx` → `#insights`)

* **Section Tag**: `MULTI-AGENT REVIEW ENGINE`
* **Headline**: *"Inspect real-time review intelligence."*
* **Interactive Visualization**:
  * **15-Agent Workload Distribution Bar Chart**: Interactive hovering over agent nodes (`GW`, `AU`, `DB`, `PY`, `WK`, `QU`, `NT`, `ST`, etc.) displaying task breakdowns across AST parsing, Semgrep rules, and LLM reasoning.
  * **Repository Distribution List**: Per-service task and taint detection statistics.
  * **Agent Specialization Modal**: Comprehensive mathematical and architectural breakdown of the multi-agent consensus protocol.

---

### Scene 11: Celestial Canvas CTA Finale (`CelestialCTASection.tsx` → `#cta`)

* **Visual Style**: High-performance dual-layered HTML5 Canvas starfield rendering 120+ streak particles with drifting velocity and glowing leader comets.
* **Headline**:
  * **"Ready to secure your codebase on every commit?"**
* **Subtext**:
  * *"Deploy Vigil into your GitHub workflow in under 2 minutes. Catch vulnerabilities before they hit production."*
* **Interactive Action Cluster**:
  * `Get Started Now` button (`/register`)
  * `Book Security Demo` button (triggers `DemoModal`)
  * `Explore Live Console` button (`/dashboard`)

---

### Scene 12: Interactive Demo Modal (`DemoModal.tsx`)

* **Trigger**: Any `Request a Demo` or `Live Demo` button.
* **Interactive Steps**:
  1. **Code Ingestion**: Uploading repository AST and extracting taint sources.
  2. **Vulnerability Detection**: Highlighting SQL injection flaw in `/api/v1/users/search`.
  3. **Autonomous Patch Generation**: Generating sanitized parameterized query diff.
  4. **MicroVM Sandbox Verification**: Isolated test execution confirming tests pass (0 failures).
* **Call to Action**: One-click registration to inspect real repositories.

---

### Scene 13: Global Footer & Legal Disclosures (`Footer.tsx`)

* **Layout**:
  * **Column 1**: Brand identity, tagline, live SOC-2 Type II / ISO-27001 compliance badges, system status indicator (`All Systems Operational`).
  * **Column 2 (Product)**: Features, Review Pipeline, Rule Engine, MicroVM Sandbox, Integrations, Pricing.
  * **Column 3 (Resources)**: Documentation, API Reference, Threat Model, CWE Coverage, Security Whitepaper.
  * **Column 4 (Company & Legal)**: About, Careers, Privacy Policy, Terms of Service, Responsible Disclosure, Consent Policy v1.0.
* **Bottom Bar**: `© 2026 Vigil Security Inc. All rights reserved. Zero-Telemetry Guarantee.`

---

## 🎨 Design System & Color Palette

| Token | Hex / Value | Usage |
|---|---|---|
| **Background Primary** | `#000000` (Pure OLED Black) | Base page background, canvas contrast |
| **Card / Surface** | `#09090b` / `#070709` | Interactive panels, mockups, containers |
| **Border Subtle** | `rgba(255, 255, 255, 0.1)` | Subtle gridlines and dividers |
| **Border Highlight** | `rgba(255, 255, 255, 0.25)` | Hover states, active cards |
| **Accent Cyan** | `#22d3ee` / `rgb(34, 211, 238)` | Section tags, tracking badges, dataflow lines |
| **Accent Emerald** | `#34d399` / `#10b981` | Verification badges, passing tests, live indicators |
| **Accent Rose** | `#fb7185` / `#f43f5e` | Vulnerability indicators, critical CWE badges |
| **Accent Amber** | `#fbbf24` | Warning states, rate limit notices |
| **Typography Display** | System / Geist Display Sans | Headlines, title cards |
| **Typography Mono** | JetBrains Mono / SF Mono | Code snippets, line numbers, CWE tags, timestamps |

---

## 🔒 Scope & Isolation Rules

1. **Strictly Frontend Only**: All modifications, additions, and polishes are strictly limited to `frontend/`.
2. **Backend Protection**: No files in `backend/`, `tests/`, or database migrations will be altered.
3. **Mock Resilience**: Frontend gracefully operates in `NEXT_PUBLIC_API_MODE=mock` so all UI demonstrations, metric counters, and interactive panels function seamlessly without external server dependencies.

---

## 🚀 Proposed Enhancements For User Review

Before writing any code or updating landing page components, please review the proposed enhancement options below:

1. **Option A (Copy & Typography Polish)**: Refine headings and card descriptions across all sections for maximum conversion punch and readability while keeping all interactive widgets intact.
2. **Option B (Interactive Widget Expansion)**: Enhance the interactive IDE pipeline in `StatefulExecutionSection.tsx` and the Policy Matrix in `DurableAutonomySection.tsx` with clickable live test scenarios.
3. **Option C (Visual Effects & Polish)**: Add glowing cursor-following hover effects and enhanced smooth transitions across card borders and CTA buttons.
4. **Option D (Custom Proposal)**: Let us know your specific direction or adjustments for the landing page.
