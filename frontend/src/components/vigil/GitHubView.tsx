'use client';

import React from 'react';
import { GitPullRequest, CheckCircle2, ShieldAlert, ArrowUpRight, Github } from 'lucide-react';
import { PULL_REQUEST_REVIEWS } from '@/data/vigilData';
import { SeverityBadge } from './SeverityBadge';

import { focusRing } from '@/lib/styles';

interface GitHubViewProps {
  onSelectReview: (reviewId: string) => void;
}

export const GitHubView: React.FC<GitHubViewProps> = ({ onSelectReview }) => {
  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Github className="w-5 h-5 text-white/80" />
            <span>GitHub Actions & PR Integration</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            Automated CI/CD security gating. Block vulnerable merges before code reaches main.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-xs font-mono text-emerald-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Webhook Active: org/vigil-security</span>
        </div>
      </div>

      <div className="rounded-xl border border-white/10 bg-white/[0.02] flex flex-col overflow-hidden">
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <h2 className="text-xs font-semibold text-white tracking-wider">
            RECENT PULL REQUEST CHECKS
          </h2>
          <span className="text-xs text-white/40 font-mono">Continuous CI Verification</span>
        </div>

        <div className="divide-y divide-white/5">
          {PULL_REQUEST_REVIEWS.map((pr) => (
            <div
              key={pr.id}
              role="button"
              tabIndex={0}
              aria-label={`Inspect review for pull request #${pr.prNumber}: ${pr.title}`}
              onClick={() => onSelectReview(pr.reviewId)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectReview(pr.reviewId);
                }
              }}
              className={`p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-white/[0.03] transition-colors cursor-pointer ${focusRing}`}
            >
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-xl bg-white/5 border border-white/10 shrink-0">
                  <GitPullRequest className="w-4 h-4 text-white/70" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-white">
                      #{pr.prNumber}
                    </span>
                    <span className="text-xs font-medium text-white">{pr.title}</span>
                  </div>
                  <div className="text-[11px] text-white/40 font-mono mt-1 flex items-center gap-2">
                    <span>{pr.repository}</span>
                    <span>•</span>
                    <span>branch: {pr.branch}</span>
                    <span>•</span>
                    <span>commit {pr.commitSha}</span>
                    <span>•</span>
                    <span>by @{pr.author}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4 justify-between md:justify-end">
                <div className="flex items-center gap-2">
                  {pr.severityCounts.critical > 0 && (
                    <SeverityBadge severity="critical" size="sm" />
                  )}
                  {pr.severityCounts.high > 0 && (
                    <SeverityBadge severity="high" size="sm" />
                  )}
                  {pr.severityCounts.medium > 0 && (
                    <SeverityBadge severity="medium" size="sm" />
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-mono font-medium flex items-center gap-1.5 border ${
                      pr.ciStatus === 'passed'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                    }`}
                  >
                    {pr.ciStatus === 'passed' ? (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    ) : (
                      <ShieldAlert className="w-3.5 h-3.5" />
                    )}
                    <span>{pr.ciStatus === 'passed' ? 'Checks Passed' : 'Merge Blocked'}</span>
                  </span>

                  <button
                    type="button"
                    aria-label={`View pull request #${pr.prNumber} on GitHub`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectReview(pr.reviewId);
                    }}
                    className={`p-1.5 rounded-full bg-white/5 hover:bg-white/10 text-white/50 hover:text-white ${focusRing}`}
                  >
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
