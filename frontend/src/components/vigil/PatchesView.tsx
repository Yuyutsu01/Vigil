'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { GitCommit, ShieldCheck, ArrowRight } from 'lucide-react';
import { focusRing } from '@/lib/styles';

interface PatchesViewProps {
  onSelectReview?: (reviewId: string) => void;
}

export const PatchesView: React.FC<PatchesViewProps> = () => {
  const router = useRouter();

  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <GitCommit className="w-5 h-5 text-white/80" />
            <span>Autonomous Patch Proposals</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            Machine-generated remediation diffs verified against AST dataflow constraints.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-xs font-mono text-emerald-300">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Automated Regression Safe</span>
        </div>
      </div>

      {/* Empty State Panel */}
      <div className="rounded-2xl border border-white/15 bg-white/[0.02] p-12 flex flex-col items-center justify-center text-center gap-4 my-auto">
        <div className="p-4 rounded-full bg-white/[0.03] border border-white/10 text-white/40">
          <GitCommit className="w-8 h-8" />
        </div>
        <div className="max-w-md">
          <h2 className="text-base font-semibold text-white">No Active Patch Proposals</h2>
          <p className="text-xs text-white/50 mt-1.5 leading-relaxed">
            Autonomous patches are generated per-finding. Open a review from the workspace, select a security finding, and generate a remediation proposal.
          </p>
        </div>
        <button
          onClick={() => router.push('/dashboard/reviews')}
          className={`px-5 py-2.5 bg-white hover:bg-white/90 text-black font-semibold rounded-full text-xs flex items-center gap-2 transition-colors cursor-pointer mt-2 ${focusRing}`}
        >
          <span>Go to Reviews Workspace</span>
          <ArrowRight className="w-3.5 h-3.5 stroke-[2.5]" />
        </button>
      </div>
    </div>
  );
};
