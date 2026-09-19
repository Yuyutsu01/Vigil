'use client';

import React, { useState } from 'react';
import {
  Clock,
  RefreshCw,
  ShieldCheck,
  Inbox,
  Bot,
  History,
  Activity,
  LayoutGrid,
  Calendar,
  MoreHorizontal,
  Search,
  ExternalLink,
  ChevronDown,
} from 'lucide-react';

interface StatefulExecutionSectionProps {
  onGetStarted?: () => void;
  onRequestDemo?: () => void;
}

export const StatefulExecutionSection: React.FC<StatefulExecutionSectionProps> = () => {
  const [, setHoveredTask] = useState<string | null>(null);

  return (
    <section id="execution" className="relative z-20 w-full bg-black text-white pt-24 pb-32 px-4 sm:px-6 md:px-10 lg:px-12 border-t border-white/10">
      <div className="max-w-7xl mx-auto">
        {/* Top Header Grid */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-6">
          <div className="max-w-2xl">
            <div className="text-[11px] font-mono tracking-[0.2em] text-white/40 uppercase mb-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-white" />
              <span>Execution Pipeline</span>
            </div>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-[1.15]">
              Stateful verification across the entire change surface.
            </h2>
          </div>
          <p className="text-sm text-white/50 max-w-md">
            Every run traverses AST representations, correlates data flow sinks, and synthesizes unified diffs in memory.
          </p>
        </div>

        {/* The Stateful Runtime Interactive Dashboard Mockup */}
        <div className="relative rounded-2xl border border-white/15 bg-[#09090b] shadow-[0_0_60px_rgba(0,0,0,0.8)] overflow-hidden">
          {/* Top specular glow border */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/40 to-transparent" />

          <div className="flex flex-col md:flex-row min-h-[580px]">
            {/* Left Sidebar */}
            <div className="w-full md:w-56 lg:w-60 border-b md:border-b-0 md:border-r border-white/10 bg-[#070709] p-4 flex flex-col justify-between select-none">
              <div className="flex flex-col gap-5">
                {/* Brand Header */}
                <div className="flex items-center justify-between pb-2 border-b border-white/10">
                  <div className="flex items-center gap-2 text-white font-medium text-[13px] hover:text-white/90 cursor-pointer">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span>Vigil Security</span>
                    <ChevronDown className="w-3.5 h-3.5 text-white/50" />
                  </div>
                  <div className="flex items-center gap-2 text-white/40">
                    <Search className="w-3.5 h-3.5 hover:text-white/80 cursor-pointer transition-colors" />
                    <ExternalLink className="w-3.5 h-3.5 hover:text-white/80 cursor-pointer transition-colors" />
                  </div>
                </div>

                {/* Primary Nav List */}
                <div className="flex flex-col gap-0.5 text-[12.5px] text-white/70">
                  <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <Inbox className="w-3.5 h-3.5 text-rose-400" />
                    <span className="flex-1">Vulnerability Inbox</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30">3</span>
                  </button>
                  <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <Bot className="w-3.5 h-3.5 text-white/50" />
                    <span>Review Agents</span>
                  </button>
                  <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <History className="w-3.5 h-3.5 text-white/50" />
                    <span>Audit History</span>
                  </button>
                  <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                    <Activity className="w-3.5 h-3.5 text-white/50" />
                    <span>CWE Pulse</span>
                  </button>
                </div>

                {/* Workspace Group */}
                <div>
                  <div className="flex items-center justify-between text-[10.5px] uppercase tracking-wider text-white/40 font-mono px-2.5 mb-1.5">
                    <span>Engine Modules</span>
                    <ChevronDown className="w-3 h-3 text-white/30" />
                  </div>
                  <div className="flex flex-col gap-0.5 text-[12.5px] text-white/70">
                    <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors">
                      <LayoutGrid className="w-3.5 h-3.5 text-white/50" />
                      <span>AST Taint Rules</span>
                    </button>
                    <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg bg-white/10 text-white font-medium border border-white/10 text-left shadow-sm">
                      <Calendar className="w-3.5 h-3.5 text-white" />
                      <span>PR Pipelines</span>
                    </button>
                    <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5 hover:text-white text-left transition-colors text-white/50">
                      <MoreHorizontal className="w-3.5 h-3.5 text-white/40" />
                      <span>MicroVM Tests</span>
                    </button>
                  </div>
                </div>

                {/* Favorites Group */}
                <div>
                  <div className="flex items-center justify-between text-[10.5px] uppercase tracking-wider text-white/40 font-mono px-2.5 mb-1.5">
                    <span>Monitored Repos</span>
                    <ChevronDown className="w-3 h-3 text-white/30" />
                  </div>
                  <div className="flex flex-col gap-1 text-[12px] text-white/70">
                    <div className="flex items-center gap-2.5 px-2.5 py-1 rounded hover:bg-white/5 cursor-pointer">
                      <span className="w-2 h-2 rounded-full border border-rose-400 bg-rose-400/30 inline-block" />
                      <span className="truncate">api-gateway (CWE-89)</span>
                    </div>
                    <div className="flex items-center gap-2.5 px-2.5 py-1 rounded hover:bg-white/5 cursor-pointer">
                      <span className="w-2 h-2 rounded-full border border-amber-400 bg-amber-400/30 inline-block" />
                      <span className="truncate">auth-service (CWE-502)</span>
                    </div>
                    <div className="flex items-center gap-2.5 px-2.5 py-1 rounded hover:bg-white/5 cursor-pointer">
                      <span className="w-2 h-2 rounded-full border border-cyan-400 bg-cyan-400/30 inline-block" />
                      <span className="truncate">worker-node (CWE-78)</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Bottom sidebar status */}
              <div className="pt-4 border-t border-white/10 flex items-center justify-between text-[11px] text-white/40">
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>AST Daemon v2.4</span>
                </div>
                <span className="font-mono text-[10px] text-emerald-400/80">ARMED</span>
              </div>
            </div>

            {/* Main Interactive Gantt & Timeline Canvas */}
            <div className="flex-1 overflow-x-auto bg-[#09090b] flex flex-col relative">
              {/* Timeline Header Ruler */}
              <div className="border-b border-white/10 px-6 py-3 flex items-center min-w-[700px] text-[11px] font-mono text-white/50 select-none">
                <div className="w-[20%] font-semibold text-white/80">PIPELINE AUDIT</div>
                <div className="w-[18%] text-center">01 // AST PARSE</div>
                <div className="w-[18%] text-center">02 // STATIC RULES</div>
                <div className="w-[18%] text-center">03 // LLM REASONING</div>
                <div className="w-[14%] text-center">04 // TRIAGE</div>
                <div className="w-[12%] text-center font-semibold text-emerald-400">05 // VERIFIED</div>
              </div>

              {/* Grid Background Lines */}
              <div className="absolute inset-0 top-[41px] flex min-w-[700px] pointer-events-none z-0">
                <div className="w-[20%] border-r border-white/[0.03]" />
                <div className="w-[18%] border-r border-white/[0.03]" />
                <div className="w-[18%] border-r border-white/[0.03]" />
                <div className="w-[18%] border-r border-white/[0.03]" />
                <div className="w-[14%] border-r border-white/[0.03]" />
                <div className="w-[12%]" />
              </div>

              {/* Rows Container */}
              <div className="p-6 flex flex-col gap-6 relative z-10 min-w-[700px] text-xs">
                {/* ROW 1: PR #482 */}
                <div
                  className="flex flex-col gap-1.5 group cursor-pointer"
                  onMouseEnter={() => setHoveredTask('daily')}
                  onMouseLeave={() => setHoveredTask(null)}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-sm bg-rose-400 inline-block shadow-[0_0_6px_#f43f5e]" />
                    <span className="text-white font-medium text-[12.5px]">PR #482 — fastapi-order-gateway</span>
                    <span className="text-[11px] font-mono text-rose-400/80">CWE-89 SQLi Detected</span>
                  </div>
                  <div className="relative h-9 w-full">
                    <div className="absolute top-1 left-[14%] w-[72%] h-7 rounded-lg border border-white/15 bg-white/[0.04] flex items-center justify-between px-3 text-[10.5px] text-white/70 backdrop-blur-sm transition-all group-hover:border-white/30">
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-white/70" />
                        <span className="font-mono">AST Trace</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-400 shadow-[0_0_6px_#f43f5e]" />
                        <span className="font-mono">Taint Sink Found</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
                        <span className="font-mono">Diff Patch Verified</span>
                      </div>
                      <div className="absolute right-0 top-0 bottom-0 w-[24%] rounded-r-lg border-l border-dashed border-emerald-500/50 bg-emerald-500/10 flex items-center justify-center overflow-hidden">
                        <div
                          className="w-full h-full opacity-35"
                          style={{
                            backgroundImage:
                              'repeating-linear-gradient(45deg, rgba(52,211,153,0.3) 0, rgba(52,211,153,0.3) 2px, transparent 0, transparent 6px)',
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* ROW 2: PR #479 */}
                <div
                  className="flex flex-col gap-1.5 group cursor-pointer"
                  onMouseEnter={() => setHoveredTask('lead')}
                  onMouseLeave={() => setHoveredTask(null)}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-sm bg-amber-400 inline-block shadow-[0_0_6px_#fbbf24]" />
                    <span className="text-white font-medium text-[12.5px]">PR #479 — auth-service</span>
                    <span className="text-[11px] font-mono text-amber-400/80">CWE-502 Deserialization</span>
                  </div>
                  <div className="relative h-9 w-full">
                    <div className="absolute top-1 left-[2%] w-[84%] h-7 rounded-lg border border-white/15 bg-white/[0.04] flex items-center justify-between px-4 text-[10.5px] text-white/70 backdrop-blur-sm transition-all group-hover:border-white/30">
                      <div className="flex items-center gap-1.5 ml-8">
                        <span className="w-1.5 h-1.5 rounded-full bg-white/70" />
                        <span className="font-mono">Pickle Stream AST</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shadow-[0_0_5px_#fbbf24]" />
                        <span className="font-mono">RCE Exploit Proof</span>
                      </div>
                      <div className="flex items-center gap-1.5 mr-24">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        <span className="font-mono">JSON Migration Patch</span>
                      </div>
                      <div className="absolute right-0 top-0 bottom-0 w-[20%] rounded-r-lg border-l border-dashed border-sky-400/50 bg-sky-400/10 flex items-center justify-center overflow-hidden">
                        <div
                          className="w-full h-full opacity-35"
                          style={{
                            backgroundImage:
                              'repeating-linear-gradient(45deg, rgba(56,189,248,0.3) 0, rgba(56,189,248,0.3) 2px, transparent 0, transparent 6px)',
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* ROW 3: Commit 8f3d */}
                <div
                  className="flex flex-col gap-1.5 group cursor-pointer"
                  onMouseEnter={() => setHoveredTask('customer')}
                  onMouseLeave={() => setHoveredTask(null)}
                >
                  <div className="flex items-center gap-2 pl-[18%]">
                    <span className="w-1.5 h-1.5 rounded-sm bg-sky-400 inline-block shadow-[0_0_6px_#38bdf8]" />
                    <span className="text-white font-medium text-[12.5px]">Commit 8f3d — worker-node</span>
                    <span className="text-[11px] font-mono text-sky-400/80">CWE-78 Command Injection</span>
                  </div>
                  <div className="relative h-9 w-full">
                    <div className="absolute top-1 left-[18%] w-[76%] h-7 rounded-lg border border-white/15 bg-white/[0.04] flex items-center justify-between px-4 text-[10.5px] text-white/70 backdrop-blur-sm transition-all group-hover:border-white/30">
                      <div className="flex items-center gap-1.5 ml-8">
                        <span className="w-1.5 h-1.5 rounded-full bg-white/70" />
                        <span className="font-mono">child_process Exec</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-white/70" />
                        <span className="font-mono">Sanitized Array Args</span>
                      </div>
                      <div className="flex items-center gap-1.5 mr-20">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        <span className="font-mono">MicroVM Gate Passed</span>
                      </div>
                      <div className="absolute right-0 top-0 bottom-0 w-[18%] rounded-r-lg border-l border-dashed border-emerald-400/50 bg-emerald-400/10 flex items-center justify-center overflow-hidden">
                        <div
                          className="w-full h-full opacity-35"
                          style={{
                            backgroundImage:
                              'repeating-linear-gradient(45deg, rgba(52,211,153,0.35) 0, rgba(52,211,153,0.35) 2px, transparent 0, transparent 6px)',
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* ROW 4 & 5: OWASP Benchmark Suite -> SARIF */}
                <div className="relative flex flex-col gap-4">
                  <div
                    className="flex flex-col gap-1.5 group cursor-pointer"
                    onMouseEnter={() => setHoveredTask('research')}
                    onMouseLeave={() => setHoveredTask(null)}
                  >
                    <div className="flex items-center gap-2 pl-[14%]">
                      <span className="w-1.5 h-1.5 rounded-sm bg-purple-400 inline-block shadow-[0_0_6px_#c084fc]" />
                      <span className="text-white font-medium text-[12.5px]">OWASP Benchmark Suite v1.2</span>
                      <span className="text-[11px] font-mono text-purple-400/80">Evaluation Run</span>
                    </div>
                    <div className="relative h-9 w-full">
                      <div
                        id="source-pipeline"
                        className="absolute top-1 left-[14%] w-[52%] h-7 rounded-lg border border-white/15 bg-white/[0.04] flex items-center justify-between px-6 text-[10.5px] text-white/70 backdrop-blur-sm transition-all group-hover:border-white/30"
                      >
                        <div className="flex items-center gap-1.5 ml-14">
                          <span className="w-1.5 h-1.5 rounded-full bg-white/70" />
                          <span className="font-mono">2,740 Test Cases</span>
                        </div>
                        <div className="flex items-center gap-1.5 mr-16">
                          <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                          <span className="font-mono">F1 Score: 0.941</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <svg
                    className="absolute pointer-events-none z-20 overflow-visible"
                    style={{
                      left: '66%',
                      top: '32px',
                      width: '80px',
                      height: '68px',
                    }}
                  >
                    <path
                      d="M 0,4 C 28,4 32,56 46,56"
                      fill="none"
                      stroke="rgba(255, 255, 255, 0.45)"
                      strokeWidth="1.4"
                    />
                    <circle cx="46" cy="56" r="2.2" fill="#34d399" />
                  </svg>

                  <div
                    className="flex flex-col gap-1.5 group cursor-pointer pl-[48%]"
                    onMouseEnter={() => setHoveredTask('invoice')}
                    onMouseLeave={() => setHoveredTask(null)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-sm bg-emerald-400 inline-block shadow-[0_0_6px_#34d399]" />
                      <span className="text-white font-medium text-[12.5px]">SARIF Compliance Dossier</span>
                      <span className="text-[11px] font-mono text-emerald-400/80">SOC2 Type II Artifact</span>
                    </div>
                    <div className="relative h-9 w-full">
                      <div className="absolute top-1 left-0 w-[84%] h-7 rounded-lg border border-white/15 bg-white/[0.04] flex items-center justify-between px-6 text-[10.5px] text-white/70 backdrop-blur-sm transition-all group-hover:border-white/30">
                        <div className="flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-white/70" />
                          <span className="font-mono">SARIF v2.1.0 JSON</span>
                        </div>
                        <div className="flex items-center gap-1.5 mr-8">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          <span className="font-mono">Signed Ledger Hash</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* ROW 6: Secret Exfiltration */}
                <div
                  className="flex flex-col gap-1.5 group cursor-pointer"
                  onMouseEnter={() => setHoveredTask('memory')}
                  onMouseLeave={() => setHoveredTask(null)}
                >
                  <div className="flex items-center gap-2 pl-[7%]">
                    <span className="w-1.5 h-1.5 rounded-sm bg-sky-400 inline-block shadow-[0_0_6px_#38bdf8]" />
                    <span className="text-white font-medium text-[12.5px]">Secret Exfiltration Sweep</span>
                    <span className="text-[11px] font-mono text-white/40">Entropy Scanner</span>
                  </div>
                  <div className="relative h-9 w-full">
                    <div className="absolute top-1 left-[7%] w-[58%] h-7 rounded-lg border border-white/15 bg-white/[0.04] flex items-center justify-between px-6 text-[10.5px] text-white/70 backdrop-blur-sm transition-all group-hover:border-white/30">
                      <div className="flex items-center gap-1.5 ml-10">
                        <span className="w-1.5 h-1.5 rounded-full bg-white/70" />
                        <span className="font-mono">Shannons Entropy</span>
                      </div>
                      <div className="flex items-center gap-1.5 mr-6">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        <span className="font-mono">Zero Leaked API Keys</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 3 Core Feature Pillars */}
        <div className="mt-14 sm:mt-16 grid grid-cols-1 md:grid-cols-3 gap-8 sm:gap-10 pt-2">
          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-2 text-white font-medium text-[15px] sm:text-[16px]">
              <div className="w-5 h-5 rounded-full flex items-center justify-center text-white/90">
                <Clock className="w-4 h-4 text-white" />
              </div>
              <h3 className="font-semibold text-white tracking-tight">Audit on commit & PR.</h3>
            </div>
            <p className="text-white/60 text-[13.5px] sm:text-[14px] leading-relaxed font-normal">
              Continuous AST triggers on every pull request, push event, or scheduled security baseline sweep.
            </p>
          </div>

          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-2 text-white font-medium text-[15px] sm:text-[16px]">
              <div className="w-5 h-5 flex items-center justify-center text-white/90">
                <RefreshCw className="w-4 h-4 text-white" />
              </div>
              <h3 className="font-semibold text-white tracking-tight">Reason with AST context.</h3>
            </div>
            <p className="text-white/60 text-[13.5px] sm:text-[14px] leading-relaxed font-normal">
              Trace data-flow taints across functions, imported modules, and control-flow branches with zero context drift.
            </p>
          </div>

          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-2 text-white font-medium text-[15px] sm:text-[16px]">
              <div className="w-5 h-5 flex items-center justify-center text-white/90">
                <ShieldCheck className="w-4 h-4 text-white" />
              </div>
              <h3 className="font-semibold text-white tracking-tight">Verify in microVM sandboxes.</h3>
            </div>
            <p className="text-white/60 text-[13.5px] sm:text-[14px] leading-relaxed font-normal">
              Execute proof-of-concept tests and patch candidates in gVisor and Firecracker containers with zero regression risk.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};
