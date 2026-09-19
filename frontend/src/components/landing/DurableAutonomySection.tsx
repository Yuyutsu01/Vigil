'use client';

import React, { useState } from 'react';
import {
  ChevronDown,
  Check,
  SlidersHorizontal,
  ArrowUpDown,
  CheckCircle2,
  Sparkles,
  Bot,
  Zap,
} from 'lucide-react';

interface DurableAutonomySectionProps {
  onGetStarted?: () => void;
  onRequestDemo?: () => void;
}

export const DurableAutonomySection: React.FC<DurableAutonomySectionProps> = () => {
  const [activeDropdownRow, setActiveDropdownRow] = useState<string | null>(null);
  const [policyValues, setPolicyValues] = useState<Record<string, string>>({
    sqli: 'Block PR',
    cmdi: 'Block PR',
    deserialization: 'Block PR',
    secrets: 'Block PR',
    microvm: 'Enforce',
    sarif: 'Enforce',
  });
  const [selectedInboxItem, setSelectedInboxItem] = useState<number | null>(1);

  const policyRules = [
    {
      id: 'sqli',
      title: 'SQL Injection (CWE-89)',
      desc: 'Tainted input flowing to database execution',
      options: ['Block PR', 'Require approval', 'Monitor only'],
    },
    {
      id: 'cmdi',
      title: 'Command Injection (CWE-78)',
      desc: 'child_process & system exec vulnerabilities',
      options: ['Block PR', 'Require approval', 'Monitor only'],
    },
    {
      id: 'deserialization',
      title: 'Insecure Deserialization (CWE-502)',
      desc: 'Untrusted pickle or yaml loads',
      options: ['Block PR', 'Require approval', 'Monitor only'],
    },
    {
      id: 'secrets',
      title: 'Hardcoded Secrets & API Keys',
      desc: 'Shannon entropy and token regex checks',
      options: ['Block PR', 'Require approval', 'Monitor only'],
    },
    {
      id: 'microvm',
      title: 'MicroVM Sandbox Patch Test',
      desc: 'Isolated regression verification before PR merge',
      options: ['Enforce', 'Require approval', 'Disable'],
    },
    {
      id: 'sarif',
      title: 'SARIF Compliance Dossier',
      desc: 'Export signed cryptographic security artifact',
      options: ['Enforce', 'Require approval', 'Disable'],
    },
  ];

  return (
    <section id="verification" className="relative z-20 w-full bg-black text-white pt-20 pb-32 px-4 sm:px-6 md:px-10 lg:px-12 border-t border-white/10">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-6">
          <div className="max-w-2xl">
            <div className="text-[11px] font-mono tracking-[0.2em] text-white/40 uppercase mb-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-white" />
              <span>Autonomous Enforcement</span>
            </div>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-[1.15]">
              Guaranteed policy gates before merge.
            </h2>
          </div>
          <p className="text-sm text-white/50 max-w-md">
            Enforce zero-regression policies, verify patches inside microVM sandboxes, and export cryptographic SARIF artifacts.
          </p>
        </div>

        {/* Outer 4-Module Bento Container */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 sm:gap-10">
          {/* CARD 1: Multi-Agent Triage Pipeline */}
          <div className="flex flex-col">
            <div className="relative rounded-2xl border border-white/15 bg-[#0a0a0d] p-5 sm:p-6 shadow-[0_0_50px_rgba(0,0,0,0.7)] overflow-hidden flex flex-col justify-between min-h-[380px]">
              <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/35 to-transparent" />

              <div className="flex items-center justify-between text-[11px] font-mono select-none mb-6">
                <div className="flex items-center gap-2 text-white/75 font-semibold tracking-wider uppercase">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
                  <span>TRIAGE MESH • LIVE</span>
                </div>
                <div className="text-white/40">
                  <span>3 agents • 0 false positives</span>
                </div>
              </div>

              <div className="relative my-auto py-3">
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-2 relative">
                  <div className="w-full sm:w-[26%] rounded-xl border border-white/10 bg-white/[0.03] p-3 text-center flex flex-col items-center justify-center min-h-[76px]">
                    <span className="text-[9.5px] uppercase tracking-wider text-white/40 font-mono">TRIGGER</span>
                    <span className="text-[13px] font-semibold text-white mt-0.5">PR #482 Open</span>
                    <span className="text-[10px] text-white/40 font-mono mt-0.5">GitHub Action</span>
                  </div>

                  <div className="hidden sm:flex items-center text-white/30 text-[10px] select-none">
                    &gt;
                  </div>

                  <div className="w-full sm:w-[30%] rounded-xl border border-white/10 bg-white/[0.03] p-3 text-center flex flex-col items-center justify-center min-h-[76px]">
                    <span className="text-[9.5px] uppercase tracking-wider text-white/40 font-mono">AST TAINT GRAPH</span>
                    <span className="text-[13px] font-semibold text-white mt-0.5">Taint Loaded</span>
                    <span className="text-[10px] text-white/40 font-mono mt-0.5">Python & TS AST</span>
                  </div>

                  <div className="hidden sm:flex items-center text-white/30 text-[10px] select-none">
                    &gt;
                  </div>

                  <div className="w-full sm:w-[32%] rounded-xl border border-white/60 bg-black p-3 text-center flex flex-col items-center justify-center min-h-[82px] shadow-[0_0_20px_rgba(255,255,255,0.08)]">
                    <span className="text-[9.5px] uppercase tracking-wider text-white/60 font-mono font-semibold">REASONER</span>
                    <span className="text-[13.5px] font-bold text-white mt-0.5">Triaging Risk</span>
                    <div className="flex items-center gap-1 my-1">
                      <span className="w-1 h-1 rounded-full bg-white/70 animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-1 h-1 rounded-full bg-white/70 animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-1 h-1 rounded-full bg-white/70 animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span className="text-[9.5px] text-white/50 font-mono">evidence verified</span>
                  </div>

                  <div className="w-full sm:w-[30%] flex flex-col gap-2 pt-2 sm:pt-0">
                    <div className="flex items-center justify-between px-3 py-1.5 rounded-lg border border-white/10 bg-white/[0.02] text-[11.5px]">
                      <span className="text-white/80">Security agent</span>
                      <span className="w-2 h-2 rounded-full bg-rose-400 shadow-[0_0_6px_#f43f5e]" />
                    </div>
                    <div className="flex items-center justify-between px-3 py-1.5 rounded-lg border border-white/10 bg-white/[0.02] text-[11.5px]">
                      <span className="text-white/80">Quality agent</span>
                      <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
                    </div>
                    <div className="flex items-center justify-between px-3 py-1.5 rounded-lg border border-white/10 bg-white/[0.02] text-[11.5px]">
                      <span className="text-white/80">Patch generator</span>
                      <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_6px_#22d3ee]" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-white/10 text-[11px] font-mono text-white/50 flex items-center gap-2">
                <span className="text-white/40">&gt;</span>
                <span className="truncate">AST taint proven: CWE-89 raw query in line 46 repaired with parameterized SQL</span>
              </div>

              <div className="mt-4 pt-3 border-t border-white/10 grid grid-cols-4 gap-2 text-left">
                <div>
                  <div className="text-[9.5px] uppercase tracking-wider text-white/40 font-mono">PRs AUDITED</div>
                  <div className="text-[14px] sm:text-[15px] font-bold text-white mt-0.5">1,487</div>
                </div>
                <div>
                  <div className="text-[9.5px] uppercase tracking-wider text-white/40 font-mono">PRECISION</div>
                  <div className="text-[14px] sm:text-[15px] font-bold text-white mt-0.5">99.9%</div>
                </div>
                <div>
                  <div className="text-[9.5px] uppercase tracking-wider text-white/40 font-mono">PATCH TIME</div>
                  <div className="text-[14px] sm:text-[15px] font-bold text-white mt-0.5">342ms</div>
                </div>
                <div className="text-right">
                  <div className="text-[9.5px] uppercase tracking-wider text-white/40 font-mono">ISOLATION</div>
                  <div className="text-[12px] sm:text-[13px] font-medium text-emerald-400 mt-1">gVisor VM</div>
                </div>
              </div>
            </div>

            <div className="mt-5">
              <h3 className="text-white text-xl sm:text-2xl font-semibold tracking-tight">
                Multi-Agent Triage Pipeline
              </h3>
              <p className="text-white/60 text-[14px] sm:text-[15px] leading-relaxed mt-2 font-normal">
                Coordinate specialized security and code review agents with shared AST context, exploit validation, and automated patch synthesis.
              </p>
            </div>
          </div>

          {/* CARD 2: CI/CD & Pipeline Triggers */}
          <div className="flex flex-col">
            <div className="relative rounded-2xl border border-white/15 bg-[#0a0a0d] p-5 sm:p-6 shadow-[0_0_50px_rgba(0,0,0,0.7)] overflow-hidden flex flex-col justify-between min-h-[380px]">
              <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/35 to-transparent" />

              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <span className="text-white font-bold text-[16px] tracking-tight">Review Pipeline</span>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-white/40">NEXT 7 DAYS</span>
                </div>
                <div className="px-2.5 py-1 rounded-full border border-white/20 bg-white/5 text-[10.5px] font-mono text-white/70">
                  12 QUEUED
                </div>
              </div>

              <div className="grid grid-cols-7 text-[10.5px] font-mono text-white/40 text-center uppercase tracking-wider pb-2 border-b border-white/10">
                <span>MON</span>
                <span>TUE</span>
                <span>WED</span>
                <span>THU</span>
                <span>FRI</span>
                <span>SAT</span>
                <span>SUN</span>
              </div>

              <div className="flex flex-col gap-5 py-4">
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-[11.5px]">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">PR Security Gate</span>
                      <span className="text-[10px] font-mono text-white/40">WEBHOOK • REAL-TIME</span>
                    </div>
                    <span className="text-[9.5px] font-mono text-white/80 tracking-wider">ACTIVE</span>
                  </div>
                  <div className="h-1.5 w-full bg-white/[0.08] rounded-full overflow-hidden relative">
                    <div className="absolute top-0 bottom-0 left-0 w-[58%] rounded-full bg-white" />
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-[11.5px]">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">Commit AST Taint Trace</span>
                      <span className="text-[10px] font-mono text-white/40">PUSH EVENT</span>
                    </div>
                    <span className="text-[9.5px] font-mono text-white/80 tracking-wider">ACTIVE</span>
                  </div>
                  <div className="h-1.5 w-full bg-white/[0.08] rounded-full overflow-hidden relative">
                    <div className="absolute top-0 bottom-0 left-[22%] w-[42%] rounded-full bg-white/70" />
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-[11.5px]">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">Nightly CWE Sweep</span>
                      <span className="text-[10px] font-mono text-white/40">CRON • 02:00</span>
                    </div>
                    <span className="text-[9.5px] font-mono text-white/50 tracking-wider">SCHEDULED</span>
                  </div>
                  <div className="h-1.5 w-full bg-white/[0.08] rounded-full overflow-hidden relative">
                    <div className="absolute top-0 bottom-0 left-[48%] w-[38%] rounded-full bg-white/40" />
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-white/45 select-none">
                <span>GitHub • GitLab • Bitbucket</span>
                <span>&lt;450ms AST evaluation</span>
              </div>
            </div>

            <div className="mt-5">
              <h3 className="text-white text-xl sm:text-2xl font-semibold tracking-tight">
                CI/CD & Pipeline Triggers
              </h3>
              <p className="text-white/60 text-[14px] sm:text-[15px] leading-relaxed mt-2 font-normal">
                Trigger autonomous code reviews on GitHub/GitLab pull requests, commit pushes, or scheduled repository sweeps.
              </p>
            </div>
          </div>

          {/* CARD 3: Automated Security Policies */}
          <div className="flex flex-col">
            <div className="relative rounded-2xl border border-white/15 bg-[#0a0a0d] p-5 sm:p-6 shadow-[0_0_50px_rgba(0,0,0,0.7)] overflow-visible min-h-[380px] flex flex-col justify-between">
              <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/35 to-transparent pointer-events-none" />

              <div className="flex flex-col gap-1.5 relative">
                {policyRules.map((rule, idx) => {
                  const isLast = idx === policyRules.length - 1;
                  const isOpen = activeDropdownRow === rule.id;
                  const currentValue = policyValues[rule.id] || 'Block PR';

                  return (
                    <div
                      key={rule.id}
                      className={`relative flex items-center justify-between py-2 px-1 ${
                        !isLast ? 'border-b border-white/[0.06]' : ''
                      }`}
                    >
                      <div className="pr-3">
                        <div className="text-[13px] font-medium text-white">{rule.title}</div>
                        <div className="text-[11px] text-white/45">{rule.desc}</div>
                      </div>

                      <div className="relative shrink-0">
                        <button
                          onClick={() => setActiveDropdownRow(isOpen ? null : rule.id)}
                          className={`flex items-center gap-1.5 px-3 py-1 rounded-md border text-[12px] font-mono transition-all cursor-pointer select-none ${
                            isOpen
                              ? 'border-white/40 bg-white/10 text-white'
                              : 'border-white/15 bg-white/[0.04] hover:bg-white/[0.08] hover:border-white/30 text-white'
                          }`}
                        >
                          <Check className="w-3 h-3 text-white/80" strokeWidth={2.5} />
                          <span>{currentValue}</span>
                          <ChevronDown
                            className={`w-3 h-3 text-white/40 transition-transform duration-200 ${
                              isOpen ? 'rotate-180 text-white' : ''
                            }`}
                          />
                        </button>

                        {isOpen && (
                          <div className="absolute right-0 top-10 z-30 w-48 rounded-xl border border-white/20 bg-[#121217] p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.95)]">
                            <div className="px-2.5 py-1 text-[10px] font-mono text-white/40 uppercase tracking-wider border-b border-white/10 mb-1">
                              Policy Action
                            </div>
                            {rule.options.map((opt) => {
                              const isSelected = currentValue === opt;
                              return (
                                <button
                                  key={opt}
                                  onClick={() => {
                                    setPolicyValues((prev) => ({ ...prev, [rule.id]: opt }));
                                    setActiveDropdownRow(null);
                                  }}
                                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left text-[12px] transition-colors cursor-pointer ${
                                    isSelected
                                      ? 'bg-white/10 text-white font-medium'
                                      : 'text-white/60 hover:text-white hover:bg-white/5'
                                  }`}
                                >
                                  <span>{opt}</span>
                                  {isSelected && (
                                    <Check className="w-3.5 h-3.5 text-white shrink-0" strokeWidth={2.5} />
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="mt-5">
              <h3 className="text-white text-xl sm:text-2xl font-semibold tracking-tight">
                Automated Security Policies
              </h3>
              <p className="text-white/60 text-[14px] sm:text-[15px] leading-relaxed mt-2 font-normal">
                Define deterministic gating rules and compliance barriers that automatically halt insecure pull requests before deployment.
              </p>
            </div>
          </div>

          {/* CARD 4: Security Findings Inbox */}
          <div className="flex flex-col">
            <div className="relative rounded-2xl border border-white/15 bg-[#0a0a0d] p-5 sm:p-6 shadow-[0_0_50px_rgba(0,0,0,0.7)] overflow-hidden flex flex-col justify-between min-h-[380px]">
              <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/35 to-transparent" />

              <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <span className="text-white font-bold text-[16px] tracking-tight">Findings Inbox</span>
                  <span className="text-white/40 text-xs">•</span>
                </div>
                <div className="flex items-center gap-3 text-white/45">
                  <SlidersHorizontal className="w-3.5 h-3.5 hover:text-white cursor-pointer transition-colors" />
                  <ArrowUpDown className="w-3.5 h-3.5 hover:text-white cursor-pointer transition-colors" />
                </div>
              </div>

              <div className="flex flex-col gap-2.5">
                <div
                  onClick={() => setSelectedInboxItem(1)}
                  className={`flex items-start justify-between p-2.5 rounded-xl border transition-all cursor-pointer ${
                    selectedInboxItem === 1
                      ? 'border-white/30 bg-white/[0.08]'
                      : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05]'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="relative w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0 mt-0.5">
                      <Sparkles className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                      <div className="text-[13px] font-medium text-white">CWE-89 Patch verified</div>
                      <div className="text-[11.5px] text-white/50 mt-0.5">api-gateway: Parameterized query patch tested in gVisor</div>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-white/40 shrink-0 mt-0.5">8m</span>
                </div>

                <div
                  onClick={() => setSelectedInboxItem(2)}
                  className={`flex items-start justify-between p-2.5 rounded-xl border transition-all cursor-pointer ${
                    selectedInboxItem === 2
                      ? 'border-white/30 bg-white/[0.08]'
                      : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05]'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="relative w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="w-4 h-4 text-amber-400" />
                    </div>
                    <div>
                      <div className="text-[13px] font-medium text-white">CWE-502 Deserialization blocked</div>
                      <div className="text-[11.5px] text-white/50 mt-0.5">auth-service: Untrusted pickle stream halted in PR #479</div>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-white/40 shrink-0 mt-0.5">1h</span>
                </div>

                <div
                  onClick={() => setSelectedInboxItem(3)}
                  className={`flex items-start justify-between p-2.5 rounded-xl border transition-all cursor-pointer ${
                    selectedInboxItem === 3
                      ? 'border-white/30 bg-white/[0.08]'
                      : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05]'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="relative w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center shrink-0 mt-0.5">
                      <Zap className="w-4 h-4 text-cyan-400" />
                    </div>
                    <div>
                      <div className="text-[13px] font-medium text-white">MicroVM Regression Gate Passed</div>
                      <div className="text-[11.5px] text-white/50 mt-0.5">worker-node: Child process command args sanitized</div>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-white/40 shrink-0 mt-0.5">4h</span>
                </div>

                <div
                  onClick={() => setSelectedInboxItem(4)}
                  className={`flex items-start justify-between p-2.5 rounded-xl border transition-all cursor-pointer ${
                    selectedInboxItem === 4
                      ? 'border-white/30 bg-white/[0.08]'
                      : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05]'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="relative w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/30 flex items-center justify-center shrink-0 mt-0.5">
                      <CheckCircle2 className="w-4 h-4 text-purple-400" />
                    </div>
                    <div>
                      <div className="text-[13px] font-medium text-white">Full AST Sweep Complete</div>
                      <div className="text-[11.5px] text-white/50 mt-0.5">All 28 microservice repositories clean • SARIF ledger generated</div>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-white/40 shrink-0 mt-0.5">1d</span>
                </div>
              </div>
            </div>

            <div className="mt-5">
              <h3 className="text-white text-xl sm:text-2xl font-semibold tracking-tight">
                Security Findings Inbox
              </h3>
              <p className="text-white/60 text-[14px] sm:text-[15px] leading-relaxed mt-2 font-normal">
                Triage verified vulnerabilities, review sandbox-tested patch candidates, and merge automated git diffs with a single click.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
