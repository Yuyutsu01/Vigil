'use client';

import React, { useState } from 'react';
import {
  Search,
  ExternalLink,
  ChevronDown,
  Inbox,
  Bot,
  History,
  Activity,
  LayoutGrid,
  Calendar,
  MoreHorizontal,
  Sparkles,
  BarChart3,
  ShieldCheck,
  Cpu,
  Boxes,
  FileCode,
  CheckCircle2,
  Target,
  Settings,
} from 'lucide-react';

interface AgentInsightsSectionProps {
  onGetStarted?: () => void;
  onRequestDemo?: () => void;
}

export const AgentInsightsSection: React.FC<AgentInsightsSectionProps> = () => {
  const [hoveredProject, setHoveredProject] = useState<string | null>(null);
  const [hoveredBarIndex, setHoveredBarIndex] = useState<number | null>(null);
  const [showAgentBreakdown, setShowAgentBreakdown] = useState(false);

  const assigneeData = [
    { initial: 'GW', color: 'bg-rose-500/80', yellow: 34, purple: 88, white: 44, total: 166 },
    { initial: 'AU', color: 'bg-cyan-500/80', yellow: 30, purple: 78, white: 38, total: 146 },
    { initial: 'DB', color: 'bg-amber-500/80', yellow: 28, purple: 70, white: 35, total: 133 },
    { initial: 'PY', color: 'bg-purple-500/80', yellow: 26, purple: 66, white: 34, total: 126 },
    { initial: 'WK', color: 'bg-indigo-500/80', yellow: 25, purple: 62, white: 33, total: 120 },
    { initial: 'QU', color: 'bg-emerald-500/80', yellow: 22, purple: 58, white: 30, total: 110 },
    { initial: 'NT', color: 'bg-orange-500/80', yellow: 19, purple: 50, white: 27, total: 96 },
    { initial: 'ST', color: 'bg-blue-500/80', yellow: 17, purple: 44, white: 23, total: 84 },
    { initial: 'ML', color: 'bg-pink-500/80', yellow: 15, purple: 38, white: 20, total: 73 },
    { initial: 'EV', color: 'bg-teal-500/80', yellow: 14, purple: 35, white: 18, total: 67 },
    { initial: 'TX', color: 'bg-yellow-500/80', yellow: 13, purple: 30, white: 16, total: 59 },
    { initial: 'LG', color: 'bg-violet-500/80', yellow: 11, purple: 26, white: 14, total: 51 },
    { initial: 'CF', color: 'bg-green-500/80', yellow: 10, purple: 22, white: 12, total: 44 },
    { initial: 'AP', color: 'bg-sky-500/80', yellow: 8, purple: 18, white: 10, total: 36 },
    { initial: 'IN', color: 'bg-blue-600/80', yellow: 7, purple: 14, white: 8, total: 29 },
  ];

  const projectRows = [
    { name: 'api-gateway', icon: 'zap', tasks: 239, ast: 81, semgrep: 76, llm: 82 },
    { name: 'auth-service', icon: 'mail', tasks: 181, ast: 25, semgrep: 151, llm: 5 },
    { name: 'billing-engine', icon: 'heart', tasks: 95, ast: 22, semgrep: 44, llm: 29 },
    { name: 'worker-node', icon: 'message', tasks: 88, ast: 0, semgrep: 12, llm: 76 },
    { name: 'order-processor', icon: 'search', tasks: 72, ast: 59, semgrep: 13, llm: 0 },
    { name: 'payment-router', icon: 'receipt', tasks: 51, ast: 0, semgrep: 51, llm: 0 },
    { name: 'customer-portal', icon: 'database', tasks: 50, ast: 3, semgrep: 0, llm: 47 },
    { name: 'notification-svc', icon: 'send', tasks: 45, ast: 18, semgrep: 21, llm: 6 },
    { name: 'data-ingestion', icon: 'bar', tasks: 43, ast: 12, semgrep: 24, llm: 7 },
    { name: 'identity-broker', icon: 'grid', tasks: 38, ast: 14, semgrep: 8, llm: 16 },
  ];

  return (
    <section id="insights" className="relative z-20 w-full bg-black text-white pt-24 pb-32 px-4 sm:px-6 md:px-10 lg:px-12 border-t border-white/10">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-6">
          <div className="max-w-2xl">
            <div className="text-xs md:text-sm font-mono tracking-[0.15em] text-white/50 uppercase mb-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              <span>MULTI-AGENT REVIEW ENGINE</span>
            </div>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-[1.15]">
              Inspect real-time review intelligence.
            </h2>
          </div>
          <div className="max-w-md">
            <p className="text-sm md:text-base text-white/70 leading-relaxed mb-3">
              <strong className="text-white font-medium">Coordinated AI Agents:</strong> Specialized agents work together on every step — analyzing code, identifying security risks, writing safer code, and testing fixes safely.
            </p>
            <button
              type="button"
              onClick={() => setShowAgentBreakdown((v) => !v)}
              className="text-xs sm:text-sm font-mono text-white/60 hover:text-white/70 underline underline-offset-4 cursor-pointer"
            >
              {showAgentBreakdown ? '▲ Hide full agent breakdown' : '▼ View full agent structure'}
            </button>
          </div>
        </div>

        {/* Expandable 14-Agent DAG Architecture Breakdown */}
        {showAgentBreakdown && (
          <div className="mb-10 p-6 rounded-2xl border border-white/15 bg-[#09090b] grid grid-cols-1 md:grid-cols-3 gap-6 text-xs animate-in fade-in slide-in-from-top-2 duration-300">
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02]">
              <div className="font-mono text-white/60 font-semibold mb-2 flex items-center gap-2">
                <Cpu className="w-4 h-4" /> 8 LLM Agents
              </div>
              <ul className="space-y-1.5 text-zinc-300">
                <li><span className="text-white font-mono">A3:</span> Security Reasoning</li>
                <li><span className="text-white font-mono">A4:</span> Quality & Maintainability</li>
                <li><span className="text-white font-mono">A6:</span> Patch Synthesis</li>
                <li><span className="text-white font-mono">A9:</span> PR Review Commenter</li>
                <li><span className="text-white font-mono">A10:</span> Specialist Risk Scoring</li>
                <li><span className="text-white font-mono">A12:</span> Dataflow Investigation</li>
                <li><span className="text-white font-mono">A13:</span> Test Case Generation</li>
                <li><span className="text-white font-mono">A14:</span> Executive Summary</li>
              </ul>
            </div>
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02]">
              <div className="font-mono text-white/60 font-semibold mb-2 flex items-center gap-2">
                <Boxes className="w-4 h-4" /> 5 Deterministic Stages
              </div>
              <ul className="space-y-1.5 text-zinc-300">
                <li><span className="text-white font-mono">A1:</span> Intake & AST Ingestion</li>
                <li>
                  <span className="text-white font-mono">A2:</span> Static Analysis
                  <span className="block text-[11px] text-zinc-500 mt-0.5">Runs 6 static tool adapters (Bandit, Semgrep, Ruff, etc.) as sub-processes</span>
                </li>
                <li><span className="text-white font-mono">A5:</span> Triage & Deduplication</li>
                <li><span className="text-white font-mono">A8:</span> Audit & Dossier Report</li>
                <li><span className="text-white font-mono">A11:</span> Dependency Risk Evaluator</li>
              </ul>
            </div>
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02]">
              <div className="font-mono text-amber-400 font-semibold mb-2 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4" /> 1 Sandbox Executor
              </div>
              <ul className="space-y-1.5 text-zinc-300">
                <li><span className="text-white font-mono">A7:</span> Patch Validation Engine</li>
                <li className="text-zinc-400 text-[11px] pt-1">
                  Runs candidate patches inside gVisor microVMs with zero egress to verify bug reproduction and eliminate regressions.
                </li>
              </ul>
            </div>
          </div>
        )}


        <div className="relative rounded-2xl border border-white/15 bg-[#09090b] shadow-[0_0_60px_rgba(0,0,0,0.8)] overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/40 to-transparent" />
          <div className="flex flex-col md:flex-row min-h-[640px]">
            {/* Left Sidebar */}
            <div className="w-full md:w-56 lg:w-60 border-b md:border-b-0 md:border-r border-white/10 bg-[#070709] p-4 flex flex-col justify-between select-none">
              <div className="flex flex-col gap-5">
                <div className="flex items-center justify-between pb-2 border-b border-white/10">
                  <div className="flex items-center gap-2 text-white font-medium text-[13px] hover:text-white/90 cursor-pointer">
                    <img
                      src="/images/vigil-logo.png"
                      alt="Vigil"
                      className="w-4 h-auto shrink-0 drop-shadow-[0_0_8px_rgba(255,255,255,0.2)]"
                    />
                    <span>Vigil Security</span>
                    <ChevronDown className="w-3.5 h-3.5 text-white/50" />
                  </div>
                  <div className="flex items-center gap-2 text-white/40">
                    <Search className="w-3.5 h-3.5 hover:text-white/80 cursor-pointer transition-colors" />
                    <ExternalLink className="w-3.5 h-3.5 hover:text-white/80 cursor-pointer transition-colors" />
                  </div>
                </div>

                <div className="flex flex-col gap-0.5 text-[12.5px] text-white/70">
                  <button className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-white/10 text-white font-medium border border-white/10 text-left shadow-sm">
                    <div className="flex items-center gap-2.5">
                      <LayoutGrid className="w-3.5 h-3.5 text-white" />
                      <span>Overview</span>
                    </div>
                  </button>
                  <button className="flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <div className="flex items-center gap-2.5">
                      <FileCode className="w-3.5 h-3.5 text-white/50" />
                      <span>All Reviews</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 rounded bg-white/10 text-white/70">12</span>
                  </button>
                  <button className="flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <div className="flex items-center gap-2.5">
                      <ExternalLink className="w-3.5 h-3.5 text-white/50" />
                      <span>GitHub PRs</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 rounded bg-white/10 text-white/70">CI</span>
                  </button>
                  <button className="flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <div className="flex items-center gap-2.5">
                      <Activity className="w-3.5 h-3.5 text-white/50" />
                      <span>Autonomous Patches</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 rounded bg-white/10 text-white/70">3</span>
                  </button>
                  <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <Target className="w-3.5 h-3.5 text-white/50" />
                    <span>Benchmark Bench</span>
                  </button>
                  <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <Bot className="w-3.5 h-3.5 text-white/50" />
                    <span>Agent Fleet</span>
                  </button>
                  <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <Settings className="w-3.5 h-3.5 text-white/50" />
                    <span>Settings</span>
                  </button>
                </div>


              </div>

              <div className="pt-4 border-t border-white/10 flex items-center justify-between text-[11px] text-white/40">
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-pulse" />
                  <span>Scanner Online</span>
                </div>
                <span className="font-mono text-[10px] text-white/60">99.9%</span>
              </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 p-5 sm:p-6 lg:p-7 bg-[#09090b] flex flex-col gap-6 overflow-x-auto">
              <div className="flex items-center gap-2 text-white">
                <span className="text-[15px] sm:text-[16px] font-semibold tracking-tight">Security pulse</span>
                <span className="text-amber-400 text-xs">★</span>
              </div>

              {/* Top 4 KPI Metrics Row */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col justify-between">
                  <div className="text-[12px] text-white/50 font-normal">Vulnerabilities patched</div>
                  <div className="text-2xl sm:text-3xl font-normal text-white mt-2 tracking-tight">
                    3,389
                  </div>
                </div>
                <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col justify-between">
                  <div className="text-[12px] text-white/50 font-normal">Pull requests audited</div>
                  <div className="text-2xl sm:text-3xl font-normal text-white mt-2 tracking-tight">
                    1,128
                  </div>
                </div>
                <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col justify-between">
                  <div className="text-[12px] text-white/50 font-normal">Sandbox testbeds passed</div>
                  <div className="text-2xl sm:text-3xl font-normal text-white mt-2 tracking-tight">
                    729
                  </div>
                </div>
                <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <div className="text-[12px] text-white/50 font-normal">False-positive rate</div>
                    <div className="flex items-center gap-1.5 text-[11px] text-white/60 font-mono">
                      <span className="w-1.5 h-1.5 rounded-full bg-white/30 animate-pulse" />
                      <span>AST-Proven</span>
                    </div>
                  </div>
                  <div className="mt-2">
                    <div className="flex items-baseline gap-1">
                      <span className="text-xl sm:text-2xl font-semibold text-white tracking-tight">&lt; 0.1%</span>
                      <span className="text-xs text-white/60/80 font-mono">/ 0 fp SLA</span>
                    </div>
                    <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden mt-2">
                      <div className="h-full rounded-full bg-white/30" style={{ width: '99.9%' }} />
                    </div>
                    <div className="text-[10.5px] text-white/40 mt-1 font-mono">
                      Deterministic AST taint path validation
                    </div>
                  </div>
                </div>
              </div>

              {/* Lower Section */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 pt-1">
                {/* Column 1: Stacked Bar Chart */}
                <div className="lg:col-span-5 p-4 sm:p-5 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col justify-between min-h-[360px]">
                  <div className="text-[13px] font-medium text-white/90 mb-4">
                    Security audits per microservice
                  </div>

                  <div className="relative flex items-end h-[240px] pt-4 pb-8 pl-8 pr-2">
                    <div className="absolute left-0 top-4 bottom-8 w-7 flex flex-col justify-between text-[10px] font-mono text-white/40 text-right select-none pr-1">
                      <span>180</span>
                      <span>160</span>
                      <span>140</span>
                      <span>120</span>
                      <span>100</span>
                      <span>80</span>
                      <span>60</span>
                      <span>40</span>
                      <span>20</span>
                      <span>0</span>
                    </div>

                    <div className="absolute left-8 right-2 top-4 bottom-8 flex flex-col justify-between pointer-events-none">
                      <div className="border-b border-white/[0.05] w-full" />
                      <div className="border-b border-white/[0.05] w-full" />
                      <div className="border-b border-white/[0.05] w-full" />
                      <div className="border-b border-white/[0.05] w-full" />
                      <div className="border-b border-white/[0.05] w-full" />
                      <div className="border-b border-white/[0.05] w-full" />
                      <div className="border-b border-white/[0.05] w-full" />
                      <div className="border-b border-white/[0.05] w-full" />
                      <div className="border-b border-white/[0.05] w-full" />
                      <div className="border-b border-white/[0.1] w-full" />
                    </div>

                    <div className="relative z-10 w-full h-full flex items-end justify-between gap-1 sm:gap-1.5">
                      {assigneeData.map((item, idx) => {
                        const maxVal = 180;
                        const heightPct = (item.total / maxVal) * 100;
                        const isHovered = hoveredBarIndex === idx;
                        return (
                          <div
                            key={item.initial}
                            className="flex-1 flex flex-col items-center h-full justify-end group cursor-pointer relative"
                            onMouseEnter={() => setHoveredBarIndex(idx)}
                            onMouseLeave={() => setHoveredBarIndex(null)}
                          >
                            {isHovered && (
                              <div className="absolute -top-12 z-30 px-2 py-1 bg-black/90 border border-white/20 rounded text-[10px] font-mono text-white whitespace-nowrap shadow-lg">
                                {item.initial}: {item.total} audited
                              </div>
                            )}
                            <div
                              className="w-full max-w-[14px] flex flex-col justify-end rounded-t-sm overflow-hidden transition-all duration-200"
                              style={{ height: `${heightPct}%` }}
                            >
                              <div
                                style={{ height: `${(item.white / item.total) * 100}%` }}
                                className="w-full bg-white transition-opacity group-hover:opacity-95"
                              />
                              <div
                                style={{ height: `${(item.purple / item.total) * 100}%` }}
                                className="w-full bg-[#5b5bd6] transition-opacity group-hover:opacity-95"
                              />
                              <div
                                style={{ height: `${(item.yellow / item.total) * 100}%` }}
                                className="w-full bg-[#eab308] transition-opacity group-hover:opacity-95"
                              />
                            </div>
                            <div className="absolute -bottom-7 flex items-center justify-center">
                              <span
                                className={`w-3.5 h-3.5 sm:w-4 sm:h-4 rounded-full ${item.color} flex items-center justify-center text-[7px] sm:text-[8px] font-bold text-black select-none`}
                              >
                                {item.initial}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Column 2: Repositories audited */}
                <div className="lg:col-span-7 p-4 sm:p-5 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col justify-between overflow-x-auto">
                  <div>
                    <div className="text-[13px] font-medium text-white/90 mb-3">
                      Repositories under continuous audit
                    </div>

                    <div className="grid grid-cols-12 text-[11px] font-mono text-white/45 pb-2 border-b border-white/10 select-none min-w-[420px]">
                      <span className="col-span-5">Repository</span>
                      <span className="col-span-2 text-right">Audits</span>
                      <span className="col-span-2 flex items-center justify-end gap-1 text-sky-400">
                        <Sparkles className="w-3 h-3 text-sky-400" />
                        <span>AST Taint</span>
                      </span>
                      <span className="col-span-2 flex items-center justify-end gap-1 text-white/80">
                        <span className="w-2.5 h-2.5 rounded-full border border-white/70 flex items-center justify-center text-[7px] font-mono">
                          S
                        </span>
                        <span>Semgrep</span>
                      </span>
                      <span className="col-span-1 flex items-center justify-end gap-1 text-amber-400">
                        <span>Reasoner</span>
                      </span>
                    </div>

                    <div className="flex flex-col divide-y divide-white/[0.04] text-[12px] min-w-[420px]">
                      {projectRows.map((row) => {
                        const isHovered = hoveredProject === row.name;
                        return (
                          <div
                            key={row.name}
                            onMouseEnter={() => setHoveredProject(row.name)}
                            onMouseLeave={() => setHoveredProject(null)}
                            className={`grid grid-cols-12 py-1.5 items-center transition-colors cursor-pointer rounded px-1 ${
                              isHovered ? 'bg-white/[0.04]' : 'hover:bg-white/[0.02]'
                            }`}
                          >
                            <div className="col-span-5 flex items-center gap-2 text-white/85 font-normal truncate">
                              <span className="w-1 h-1 rounded-full bg-white/30" />
                              <span className="truncate">{row.name}</span>
                            </div>
                            <span className="col-span-2 text-right font-mono text-white/90 font-medium">
                              {row.tasks}
                            </span>
                            <span
                              className={`col-span-2 text-right font-mono ${
                                row.ast > 0 ? 'text-white/80' : 'text-white/25'
                              }`}
                            >
                              {row.ast}
                            </span>
                            <span
                              className={`col-span-2 text-right font-mono ${
                                row.semgrep > 0 ? 'text-white/80' : 'text-white/25'
                              }`}
                            >
                              {row.semgrep}
                            </span>
                            <span
                              className={`col-span-1 text-right font-mono ${
                                row.llm > 0 ? 'text-white/80' : 'text-white/25'
                              }`}
                            >
                              {row.llm}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-white/40 select-none">
                    <span>10 repositories actively scanned</span>
                    <span className="text-white/60/90">Autonomous patch verification active</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
