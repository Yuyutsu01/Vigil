'use client';

import React from 'react';
import { CheckCircle2, Loader2, Clock } from 'lucide-react';
import { ReviewStatus } from '@/lib/types';

interface RunStatusStepperProps {
  status: ReviewStatus;
}

const STEPS: { key: ReviewStatus; label: string }[] = [
  { key: 'queued', label: 'Queued' },
  { key: 'parsing', label: 'Parsing AST' },
  { key: 'baseline_rules', label: 'Baseline Rules' },
  { key: 'llm_security', label: 'LLM Security' },
  { key: 'llm_quality', label: 'Quality Review' },
  { key: 'triage', label: 'Triage & Dedupe' },
  { key: 'complete', label: 'Complete' },
];

export const RunStatusStepper: React.FC<RunStatusStepperProps> = ({ status }) => {
  const currentIndex = STEPS.findIndex((s) => s.key === status);
  const activeIndex = currentIndex === -1 ? 6 : currentIndex;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="w-full bg-black border-b border-white/10 px-4 py-2.5 flex items-center justify-between overflow-x-auto text-xs"
    >
      <span className="sr-only">Pipeline status: {STEPS[activeIndex]?.label || status}</span>
      <div className="flex items-center gap-1.5 text-white/50 font-mono text-[11px] mr-4 shrink-0">
        <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
        <span>PIPELINE</span>
      </div>
      <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-[580px]">
        {STEPS.map((step, idx) => {
          const isDone = idx < activeIndex || status === 'complete';
          const isCurrent = idx === activeIndex && status !== 'complete';

          return (
            <React.Fragment key={step.key}>
              <div
                className={`flex items-center gap-1.5 shrink-0 px-2.5 py-1 rounded-full transition-colors ${
                  isCurrent
                    ? 'bg-white/10 text-white font-medium border border-white/20'
                    : isDone
                    ? 'text-white/60 font-normal'
                    : 'text-white/30'
                }`}
              >
                {isDone ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-white/60 shrink-0" />
                ) : isCurrent ? (
                  <Loader2 className="w-3.5 h-3.5 text-white animate-spin shrink-0" />
                ) : (
                  <Clock className="w-3.5 h-3.5 text-white/20 shrink-0" />
                )}
                <span className="text-[11.5px] font-mono tracking-tight">{step.label}</span>
              </div>
              {idx < STEPS.length - 1 && (
                <div
                  className={`h-[1px] flex-1 min-w-[12px] transition-colors ${
                    idx < activeIndex ? 'bg-emerald-500/50' : 'bg-white/10'
                  }`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
