'use client';

import React from 'react';
import { Target, ShieldCheck, Lock } from 'lucide-react';

export const EvaluationView: React.FC = () => {
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
          <Lock className="w-3.5 h-3.5 text-white/60" />
          <span>Role Required: System Operator / Admin</span>
        </div>
      </div>

      {/* Operator Gated Empty State Panel */}
      <div className="rounded-2xl border border-white/15 bg-white/[0.02] p-12 flex flex-col items-center justify-center text-center gap-4 my-auto">
        <div className="p-4 rounded-full bg-white/[0.03] border border-white/10 text-white/40">
          <Target className="w-8 h-8" />
        </div>
        <div className="max-w-md">
          <h2 className="text-base font-semibold text-white">Operator Benchmark Evaluation Suite</h2>
          <p className="text-xs text-white/50 mt-1.5 leading-relaxed">
            Standardized precision and recall benchmark suites are operator-gated and executed during pipeline qualification runs. Results will appear here once an operator evaluation run is published.
          </p>
        </div>
        <div className="mt-2 flex items-center gap-2 px-3 py-1 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-300 text-xs font-mono">
          <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
          <span>Internal Pipeline Telemetry</span>
        </div>
      </div>
    </div>
  );
};
