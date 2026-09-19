'use client';

import React, { useState } from 'react';
import {
  Bot,
  CheckCircle2,
  Clock,
  Cpu,
  Boxes,
  ShieldCheck,
  Terminal,
  Activity,
} from 'lucide-react';

// 8 LLM Agents
const LLM_AGENTS = [
  { id: 'A3', name: 'A3: Security Specialist', role: 'Vulnerability Detection', model: 'Claude 3.5 Sonnet', latency: '420ms', findings: 142, status: 'Active' },
  { id: 'A4', name: 'A4: Quality & Maintainability', role: 'Static Anti-patterns', model: 'GPT-4o', latency: '380ms', findings: 89, status: 'Active' },
  { id: 'A6', name: 'A6: Patch Synthesizer', role: 'Unified Diff Generation', model: 'Claude 3.5 Sonnet', latency: '890ms', findings: 45, status: 'Active' },
  { id: 'A9', name: 'A9: PR Review Commenter', role: 'Contextual In-line Diffs', model: 'Claude 3.5 Haiku', latency: '310ms', findings: 64, status: 'Active' },
  { id: 'A10', name: 'A10: Specialist Risk Scorer', role: 'CWE Impact Evaluation', model: 'GPT-4o Mini', latency: '240ms', findings: 120, status: 'Active' },
  { id: 'A12', name: 'A12: Dataflow Investigator', role: 'Source-to-Sink Taint', model: 'Claude 3.5 Sonnet', latency: '650ms', findings: 38, status: 'Active' },
  { id: 'A13', name: 'A13: Test Generator', role: 'Reproduction Harnesses', model: 'GPT-4o', latency: '780ms', findings: 28, status: 'Active' },
  { id: 'A14', name: 'A14: Executive Summary', role: 'C-Suite Threat Dossiers', model: 'Claude 3.5 Haiku', latency: '290ms', findings: 18, status: 'Active' },
];

// 5 Deterministic Stages
const DETERMINISTIC_STAGES = [
  { id: 'A1', name: 'A1: AST Ingestion & Intake', role: 'Tree-sitter Parsing', engine: 'Native AST (Rust)', latency: '12ms', status: 'Healthy', note: 'Zero-execution memory parse' },
  { id: 'A2', name: 'A2: Static Tool Adapter Engine', role: 'Multi-Linter Orchestration', engine: 'Sub-Process Host', latency: '45ms', status: 'Healthy', note: 'Runs 6 static adapters: Bandit, Semgrep, Ruff, Trivy, Gitleaks, Pylint' },
  { id: 'A5', name: 'A5: Triage & Deduplication', role: 'Fingerprint Clustering', engine: 'Deterministic Hash', latency: '8ms', status: 'Healthy', note: 'Suppresses false positives & duplicate reports' },
  { id: 'A8', name: 'A8: Report & Dossier Compiler', role: 'SARIF & Attestation', engine: 'Cryptographic Engine', latency: '18ms', status: 'Healthy', note: 'SHA-256 digital signing for audit trails' },
  { id: 'A11', name: 'A11: Dependency Risk Evaluator', role: 'SCA & SBOM Analysis', engine: 'NVD / OSV Local Mirror', latency: '22ms', status: 'Healthy', note: 'Transitive CVE correlation' },
];

// 1 Sandbox Executor
const SANDBOX_EXECUTOR = {
  id: 'A7',
  name: 'A7: Validation Engine',
  role: 'Patch Reproduction & Safety Proofs',
  runtime: 'gVisor MicroVM (Isolated ephemerality)',
  egress: 'Zero Network Egress (Blocked)',
  latency: '1.2s avg reproduction',
  status: 'Ready',
  description:
    'Autonomous patch candidates undergo isolated reproduction runs inside ephemeral microVMs to verify exploit remediation and guarantee backward compatibility without regressions.',
};

export const AgentsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'all' | 'llm' | 'deterministic' | 'sandbox'>('all');

  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Bot className="w-5 h-5 text-white/80" />
            <span>14-Agent DAG Fleet Telemetry</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            <strong>Architecture Formula:</strong> 8 LLM agents + 5 deterministic stages + 1 sandbox executor = 14.
            Six static tool adapters run as sub-processes inside A2, not as separate agents.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-xs font-mono text-emerald-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>14 / 14 Fleet Nodes Active</span>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-white/10 pb-3 text-xs font-mono">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
            activeTab === 'all'
              ? 'bg-white text-black font-semibold'
              : 'text-white/60 hover:text-white hover:bg-white/5'
          }`}
        >
          All 14 Nodes
        </button>
        <button
          onClick={() => setActiveTab('llm')}
          className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
            activeTab === 'llm'
              ? 'bg-emerald-500 text-black font-semibold'
              : 'text-white/60 hover:text-white hover:bg-white/5'
          }`}
        >
          8 LLM Agents
        </button>
        <button
          onClick={() => setActiveTab('deterministic')}
          className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
            activeTab === 'deterministic'
              ? 'bg-cyan-500 text-black font-semibold'
              : 'text-white/60 hover:text-white hover:bg-white/5'
          }`}
        >
          5 Deterministic Stages
        </button>
        <button
          onClick={() => setActiveTab('sandbox')}
          className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
            activeTab === 'sandbox'
              ? 'bg-amber-500 text-black font-semibold'
              : 'text-white/60 hover:text-white hover:bg-white/5'
          }`}
        >
          1 Sandbox Executor
        </button>
      </div>

      {/* 8 LLM AGENTS SECTION */}
      {(activeTab === 'all' || activeTab === 'llm') && (
        <div className="flex flex-col gap-3">
          <div className="text-xs font-mono text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5" />
            <span>Tier 1: 8 LLM Reasoning Agents</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5">
            {LLM_AGENTS.map((agent) => (
              <div
                key={agent.id}
                className="p-4 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col justify-between gap-3 hover:border-white/20 transition-all"
              >
                <div>
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-emerald-400 font-semibold">{agent.id}</span>
                    <span className="text-emerald-400/80">{agent.status}</span>
                  </div>
                  <h3 className="text-xs font-bold text-white mt-1.5">{agent.name}</h3>
                  <p className="text-[11px] text-white/50 mt-0.5">{agent.role}</p>
                </div>
                <div className="pt-2.5 border-t border-white/10 text-[10.5px] font-mono text-white/60 flex justify-between">
                  <span>{agent.model}</span>
                  <span className="text-white">{agent.latency}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5 DETERMINISTIC STAGES SECTION */}
      {(activeTab === 'all' || activeTab === 'deterministic') && (
        <div className="flex flex-col gap-3 pt-2">
          <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
            <Boxes className="w-3.5 h-3.5" />
            <span>Tier 2: 5 Deterministic Stages (with 6 sub-process static adapters in A2)</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {DETERMINISTIC_STAGES.map((stage) => (
              <div
                key={stage.id}
                className="p-4 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col justify-between gap-3 hover:border-white/20 transition-all"
              >
                <div>
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-cyan-400 font-semibold">{stage.id}</span>
                    <span className="text-cyan-400/80">{stage.status}</span>
                  </div>
                  <h3 className="text-xs font-bold text-white mt-1.5">{stage.name}</h3>
                  <p className="text-[11px] text-white/50 mt-0.5">{stage.role}</p>
                  <p className="text-[10.5px] text-white/40 mt-2 font-mono bg-black/40 p-1.5 rounded border border-white/5">
                    {stage.note}
                  </p>
                </div>
                <div className="pt-2.5 border-t border-white/10 text-[10.5px] font-mono text-white/60 flex justify-between">
                  <span>Engine: {stage.engine}</span>
                  <span className="text-white">{stage.latency}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 1 SANDBOX EXECUTOR SECTION */}
      {(activeTab === 'all' || activeTab === 'sandbox') && (
        <div className="flex flex-col gap-3 pt-2">
          <div className="text-xs font-mono text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Tier 3: 1 Sandbox Executor</span>
          </div>
          <div className="p-5 rounded-2xl border border-amber-500/20 bg-amber-500/[0.03] flex flex-col gap-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <span className="text-amber-400 font-mono font-bold text-xs">
                  {SANDBOX_EXECUTOR.id}
                </span>
                <h3 className="text-sm font-bold text-white mt-0.5">
                  {SANDBOX_EXECUTOR.name} — {SANDBOX_EXECUTOR.role}
                </h3>
              </div>
              <span className="px-2.5 py-1 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-300 text-xs font-mono w-fit">
                {SANDBOX_EXECUTOR.runtime}
              </span>
            </div>
            <p className="text-xs text-white/70 leading-relaxed max-w-3xl">
              {SANDBOX_EXECUTOR.description}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 font-mono text-xs text-white/60">
              <div className="p-2.5 rounded-lg bg-black border border-white/10">
                <span className="text-white/40 block text-[10px]">NETWORK ISOLATION</span>
                <span className="text-emerald-400 font-semibold">{SANDBOX_EXECUTOR.egress}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-black border border-white/10">
                <span className="text-white/40 block text-[10px]">BENCHMARK LATENCY</span>
                <span className="text-white font-semibold">{SANDBOX_EXECUTOR.latency}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-black border border-white/10">
                <span className="text-white/40 block text-[10px]">VERDICT INTEGRITY</span>
                <span className="text-white font-semibold">100% Deterministic</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
