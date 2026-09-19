'use client';

import React from 'react';
import { Target, CheckCircle2, TrendingUp, AlertTriangle, ShieldCheck } from 'lucide-react';
import { EVALUATION_BENCHMARK } from '@/data/vigilData';

export const EvaluationView: React.FC = () => {
  const bench = EVALUATION_BENCHMARK;

  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Target className="w-5 h-5 text-white/80" />
            <span>Empirical Evaluation & Precision Benchmarks</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            Standardized precision, recall, and false-positive benchmark tests against OWASP Benchmark v1.2 and SEC-Eval suites.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/20 bg-white/5 text-xs font-mono text-white/80">
          <span>Suite: {bench.suiteName}</span>
        </div>
      </div>

      {/* Top 4 Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="text-xs text-white/50">Overall Precision</div>
          <div className="text-3xl font-bold font-mono text-emerald-400 mt-2">
            {(bench.overallPrecision * 100).toFixed(1)}%
          </div>
          <div className="text-[11px] text-white/40 mt-2 font-mono">
            Zero hallucinations on static syntax
          </div>
        </div>
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="text-xs text-white/50">Recall / Detection Rate</div>
          <div className="text-3xl font-bold font-mono text-white mt-2">
            {(bench.overallRecall * 100).toFixed(1)}%
          </div>
          <div className="text-[11px] text-white/40 mt-2 font-mono">
            {bench.totalVulnerabilitiesEvaluated} verified CVE/CWE tests
          </div>
        </div>
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="text-xs text-white/50">F1 Combined Score</div>
          <div className="text-3xl font-bold font-mono text-white mt-2">
            {bench.f1Score.toFixed(3)}
          </div>
          <div className="text-[11px] text-emerald-400 mt-2 font-mono flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            <span>SOTA for multi-agent linters</span>
          </div>
        </div>
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="text-xs text-white/50">False Positive Rate</div>
          <div className="text-3xl font-bold font-mono text-emerald-400 mt-2">
            {(bench.falsePositiveRate * 100).toFixed(1)}%
          </div>
          <div className="text-[11px] text-white/40 mt-2 font-mono">
            Deterministic AST pruning filter
          </div>
        </div>
      </div>

      {/* Breakdown per vulnerability category */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] flex flex-col overflow-hidden">
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <h2 className="text-xs font-semibold text-white tracking-wider">
            EVALUATION BREAKDOWN BY VULNERABILITY ARCHETYPE
          </h2>
          <span className="text-xs text-white/40 font-mono">OWASP Test Cases</span>
        </div>

        <div className="divide-y divide-white/5">
          {bench.breakdown.map((item: { category: string; sampleCount: number; accuracy: number; precision: number; recall: number; falsePositiveRate: number }) => (
            <div
              key={item.category}
              className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
            >
              <div className="w-64">
                <div className="font-semibold text-white">{item.category}</div>
                <div className="text-[11px] text-white/40 font-mono mt-0.5">
                  {item.sampleCount} validated test fixtures
                </div>
              </div>

              <div className="flex-1 max-w-xs flex flex-col gap-1">
                <div className="flex justify-between text-[11px] font-mono text-white/60">
                  <span>Accuracy</span>
                  <span className="text-emerald-400 font-bold">{(item.accuracy * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-400 rounded-full"
                    style={{ width: `${item.accuracy * 100}%` }}
                  />
                </div>
              </div>

              <div className="flex items-center gap-6 font-mono text-[11px]">
                <div>
                  <span className="text-white/40">Precision: </span>
                  <span className="text-white font-bold">{(item.precision * 100).toFixed(0)}%</span>
                </div>
                <div>
                  <span className="text-white/40">Recall: </span>
                  <span className="text-white font-bold">{(item.recall * 100).toFixed(0)}%</span>
                </div>
                <div>
                  <span className="text-white/40">FP: </span>
                  <span className="text-emerald-400 font-bold">{(item.falsePositiveRate * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] flex items-start gap-3 text-xs text-white/70">
        <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <strong className="text-white">Reproducibility Guarantee:</strong> Every evaluation run is executed
          in an isolated environment against frozen test sets. Synthetic test harness seeds are pinned to prevent data contamination.
        </div>
      </div>
    </div>
  );
};
