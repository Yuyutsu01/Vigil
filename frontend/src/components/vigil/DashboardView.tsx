'use client';

import React, { useState } from 'react';
import {
  Shield,
  FileCode,
  AlertOctagon,
  Clock,
  ArrowUpRight,
  TrendingUp,
  Search,
  Plus,
  Coins,
} from 'lucide-react';
import { Review, ReviewStats } from '@/lib/types';
import { SeverityBadge } from './SeverityBadge';
import { focusRing } from '@/lib/styles';

interface DashboardViewProps {
  stats: ReviewStats;
  reviews: Review[];
  onSelectReview: (reviewId: string) => void;
  onNewReview: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  stats,
  reviews,
  onSelectReview,
  onNewReview,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredReviews = reviews.filter((r) => {
    const q = searchTerm.toLowerCase();
    return (
      r.title.toLowerCase().includes(q) ||
      r.fileName.toLowerCase().includes(q) ||
      r.language.toLowerCase().includes(q) ||
      r.policyProfile.toLowerCase().includes(q)
    );
  });

  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-white select-none">
      {/* Top Banner with Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <span>Security Review Operations</span>
          </h1>
          <p className="text-xs text-white/50 mt-1">
            Deterministic AST triage, LLM reasoning trace, and enterprise audit telemetry.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            onClick={onNewReview}
            className={`px-4 py-2 bg-white hover:bg-white/90 text-black rounded-full text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer shadow-sm ${focusRing}`}
          >
            <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
            <span>New Security Review</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-white/50">
            <span>Total Reviews</span>
            <FileCode className="w-4 h-4 text-white/60" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {stats.totalReviews}
          </div>
          <div className="text-[11px] text-emerald-400 mt-2 flex items-center gap-1 font-mono">
            <TrendingUp className="w-3 h-3" />
            <span>+14% week over week</span>
          </div>
        </div>

        {/* Card 2 */}
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-white/50">
            <span>Flagged Vulnerabilities</span>
            <AlertOctagon className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {stats.totalFindings}
          </div>
          <div className="text-[11px] text-white/40 mt-2 font-mono flex items-center gap-2">
            <span className="text-red-400 font-bold">{stats.criticalFindings} Critical</span>
            <span>•</span>
            <span className="text-orange-400 font-bold">{stats.highFindings} High</span>
          </div>
        </div>

        {/* Card 3 */}
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-white/50">
            <span>Verified Accuracy (FP Rate)</span>
            <Shield className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {(stats.falsePositiveRate * 100).toFixed(1)}%
          </div>
          <div className="text-[11px] text-emerald-400 mt-2 font-mono">
            AST + Semgrep cross-validated
          </div>
        </div>

        {/* Card 4 */}
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-white/50">
            <span>Token Budget Spent</span>
            <Coins className="w-4 h-4 text-white/60" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            ${stats.totalCostSpent.toFixed(2)}
          </div>
          <div className="text-[11px] text-white/40 mt-2 font-mono">
            Avg {stats.avgReviewTime} / audit run
          </div>
        </div>
      </div>

      {/* Recent Reviews Table */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] flex flex-col overflow-hidden">
        <div className="p-4 border-b border-white/10 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-white tracking-wider">ALL REVIEWS</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/80 font-mono">
              {filteredReviews.length}
            </span>
          </div>

          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-white/40 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search reviews..."
              aria-label="Search reviews"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={`w-full bg-black border border-white/15 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder:text-white/30 focus:outline-none focus:border-white/40 ${focusRing}`}
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-white">
            <thead className="bg-black/50 border-b border-white/10 text-[11px] font-mono text-white/40 uppercase">
              <tr>
                <th className="py-3 px-4">Review ID</th>
                <th className="py-3 px-4">File / Component</th>
                <th className="py-3 px-4">Language</th>
                <th className="py-3 px-4">Findings Breakdown</th>
                <th className="py-3 px-4">Policy Profile</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 font-mono">
              {filteredReviews.map((rev) => (
                <tr
                  key={rev.id}
                  onClick={() => onSelectReview(rev.id)}
                  className="hover:bg-white/[0.03] transition-colors cursor-pointer group"
                >
                  <td className="py-3 px-4 font-bold text-white/90">{rev.id}</td>
                  <td className="py-3 px-4 font-sans">
                    <div className="font-medium text-white flex items-center gap-1.5">
                      <FileCode className="w-3.5 h-3.5 text-white/50" />
                      <span>{rev.fileName}</span>
                    </div>
                    <div className="text-[11px] text-white/40 font-mono mt-0.5">{rev.title}</div>
                  </td>
                  <td className="py-3 px-4 text-white/70">
                    <span className="px-2 py-0.5 rounded-full bg-white/10 text-white/80 text-[10.5px]">
                      {rev.language}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {rev.severityCounts.critical > 0 && (
                        <SeverityBadge severity="critical" size="sm" />
                      )}
                      {rev.severityCounts.high > 0 && (
                        <SeverityBadge severity="high" size="sm" />
                      )}
                      {rev.severityCounts.medium > 0 && (
                        <SeverityBadge severity="medium" size="sm" />
                      )}
                      {rev.totalFindings === 0 && (
                        <span className="text-emerald-400 text-xs">Clean (0)</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-white/60 font-sans">{rev.policyProfile}</td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/30">
                      <Clock className="w-3 h-3" />
                      <span>Completed</span>
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      aria-label={`Open review ${rev.id}`}
                      className={`p-1.5 rounded-full bg-white/5 hover:bg-white/20 text-white/60 group-hover:text-white transition-colors inline-flex items-center ${focusRing}`}
                    >
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
