'use client';

import React from 'react';
import { Coins, Cpu, RotateCw } from 'lucide-react';
import { BudgetStats } from '@/lib/types';

interface BudgetMeterProps {
  budget: BudgetStats;
  compact?: boolean;
}

export const BudgetMeter: React.FC<BudgetMeterProps> = ({ budget, compact = false }) => {
  const tokenPct = Math.min(100, Math.round((budget.tokensUsed / budget.tokenLimit) * 100));
  const iterPct = Math.min(100, Math.round((budget.iterations / budget.iterationLimit) * 100));

  if (compact) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex items-center gap-3 px-3 py-1.5 rounded-full border border-white/10 bg-black text-xs font-mono"
      >
        <span className="sr-only">
          Budget: ${budget.costUsed.toFixed(2)} of ${budget.costLimit.toFixed(2)}, Iteration {budget.iterations} of {budget.iterationLimit}
        </span>
        <div className="flex items-center gap-1.5 text-white/80">
          <RotateCw className="w-3 h-3 text-white/60" />
          <span>Iter {budget.iterations}/{budget.iterationLimit}</span>
        </div>
        <span className="text-white/20">|</span>
        <div className="flex items-center gap-1.5 text-white/80">
          <Coins className="w-3 h-3 text-emerald-400" />
          <span>${budget.costUsed.toFixed(2)}</span>
        </div>
        <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden ml-1">
          <div
            className="h-full rounded-full transition-all bg-white"
            style={{ width: `${iterPct}%` }}
          />
        </div>
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col gap-3"
    >
      <span className="sr-only">
        Budget spend: ${budget.costUsed.toFixed(2)} of ${budget.costLimit.toFixed(2)}, {tokenPct}% tokens, {budget.iterations} iterations
      </span>
      <div className="flex items-center justify-between text-xs font-medium text-white">
        <span className="flex items-center gap-1.5">
          <Cpu className="w-3.5 h-3.5 text-white/80" />
          Execution Budget Control
        </span>
        <span className="font-mono text-emerald-400 text-[11px]">Enforced Limit</span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {/* Tokens */}
        <div className="p-2.5 rounded-lg bg-black border border-white/10">
          <div className="text-[11px] text-white/50">Tokens</div>
          <div className="text-sm font-semibold font-mono text-white mt-0.5">
            {(budget.tokensUsed / 1000).toFixed(1)}k{' '}
            <span className="text-xs text-white/40 font-normal">
              / {(budget.tokenLimit / 1000).toFixed(0)}k
            </span>
          </div>
          <div className="w-full h-1 bg-white/10 rounded-full mt-2 overflow-hidden">
            <div className="h-full bg-white rounded-full" style={{ width: `${tokenPct}%` }} />
          </div>
        </div>
        {/* Cost */}
        <div className="p-2.5 rounded-lg bg-black border border-white/10">
          <div className="text-[11px] text-white/50">Cost Limit</div>
          <div className="text-sm font-semibold font-mono text-white mt-0.5">
            ${budget.costUsed.toFixed(2)}{' '}
            <span className="text-xs text-white/40 font-normal">/ ${budget.costLimit.toFixed(2)}</span>
          </div>
          <div className="w-full h-1 bg-white/10 rounded-full mt-2 overflow-hidden">
            <div
              className="h-full bg-emerald-400 rounded-full"
              style={{
                width: `${Math.min(100, (budget.costUsed / budget.costLimit) * 100)}%`,
              }}
            />
          </div>
        </div>
        {/* Iterations */}
        <div className="p-2.5 rounded-lg bg-black border border-white/10">
          <div className="text-[11px] text-white/50">Agent Iterations</div>
          <div className="text-sm font-semibold font-mono text-white mt-0.5">
            {budget.iterations}{' '}
            <span className="text-xs text-white/40 font-normal">/ {budget.iterationLimit} max</span>
          </div>
          <div className="w-full h-1 bg-white/10 rounded-full mt-2 overflow-hidden">
            <div className="h-full bg-white rounded-full" style={{ width: `${iterPct}%` }} />
          </div>
        </div>
      </div>
    </div>
  );
};
