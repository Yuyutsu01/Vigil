'use client';

import React, { useState } from 'react';
import { GitCommit, Copy, Check, ExternalLink, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { PATCH_PROPOSALS } from '@/data/vigilData';
import { SeverityBadge } from './SeverityBadge';

interface PatchesViewProps {
  onSelectReview: (reviewId: string) => void;
}

export const PatchesView: React.FC<PatchesViewProps> = ({ onSelectReview }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string, patch: string) => {
    navigator.clipboard.writeText(patch);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none">
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
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/20 bg-white/5 text-xs font-mono text-white/80">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Automated Regression Safe</span>
        </div>
      </div>

      <div className="flex flex-col gap-5">
        {PATCH_PROPOSALS.map((patch) => (
          <div
            key={patch.id}
            className="rounded-2xl border border-white/15 bg-white/[0.02] p-5 flex flex-col gap-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-white/50">{patch.id}</span>
                  <SeverityBadge severity={patch.severity} size="sm" />
                  <span className="font-mono text-xs text-white/80 bg-white/10 px-2 py-0.5 rounded-full">
                    {patch.cwe}
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-white mt-1.5">{patch.title}</h3>
                <div className="text-xs text-white/50 font-mono mt-0.5">
                  Target: <span className="text-white/80">{patch.targetFile}</span> (Lines {patch.linesAffected})
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleCopy(patch.id, patch.diffSnippet)}
                  className="px-3 py-1.5 rounded-full border border-white/15 bg-white/5 hover:bg-white/15 text-xs text-white flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  {copiedId === patch.id ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-white/60" />
                      <span>Copy Diff</span>
                    </>
                  )}
                </button>
                <button
                  onClick={() => onSelectReview(patch.relatedReviewId)}
                  className="px-3 py-1.5 rounded-full bg-white hover:bg-white/90 text-black text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <span>Inspect Review</span>
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>
            </div>

            <p className="text-xs text-white/70 leading-relaxed font-normal">
              {patch.explanation}
            </p>

            <div className="rounded-xl border border-white/10 bg-black overflow-hidden font-mono text-xs select-text">
              <div className="px-3.5 py-1.5 bg-white/[0.04] border-b border-white/10 text-[11px] text-white/50 flex justify-between">
                <span>Unified Diff Patch</span>
                <span className="text-emerald-400 font-sans flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Syntax Verified
                </span>
              </div>
              <pre className="p-4 text-xs text-white/90 overflow-x-auto whitespace-pre leading-relaxed">
                {patch.diffSnippet}
              </pre>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
