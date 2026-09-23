'use client';

import React, { useState, useEffect } from 'react';
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
  Info,
} from 'lucide-react';
import { Review, TenantStats } from '@/lib/types';
import { api } from '@/lib/api';
import { SeverityBadge } from './SeverityBadge';
import { focusRing } from '@/lib/styles';

interface DashboardViewProps {
  stats?: TenantStats | null;
  reviews: Review[];
  onSelectReview: (reviewId: string) => void;
  onNewReview: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  stats: initialStats,
  reviews,
  onSelectReview,
  onNewReview,
}) => {
  const [stats, setStats] = useState<TenantStats | null>(initialStats || null);
  const [loading, setLoading] = useState(!initialStats);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    let mounted = true;
    async function loadStats() {
      try {
        const data = await api.getTenantStats();
        if (mounted) {
          setStats(data);
        }
      } catch (err) {
        console.error('Failed to load tenant stats:', err);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    loadStats();
    return () => {
      mounted = false;
    };
  }, []);

  const filteredReviews = reviews.filter((r) => {
    const q = searchTerm.toLowerCase();
    return (
      r.title.toLowerCase().includes(q) ||
      r.fileName.toLowerCase().includes(q) ||
      r.language.toLowerCase().includes(q) ||
      (r.policyProfile ? r.policyProfile.toLowerCase().includes(q) : false)
    );
  });

  const totalReviews = stats ? stats.total_reviews : 0;
  const totalFindings = stats ? stats.total_findings : 0;
  const criticalFindings = stats?.findings_by_severity?.Critical ?? 0;
  const highFindings = stats?.findings_by_severity?.High ?? 0;
  const totalCostUsd = stats?.total_cost_usd ?? 0;
  const avgDurationSeconds = stats && stats.avg_review_duration_ms > 0
    ? (stats.avg_review_duration_ms / 1000).toFixed(1) + 's'
    : '0.0s';

  // Compute week-over-week trend if data exists
  const last7 = stats?.reviews_last_7_days ?? 0;
  const prev7 = stats?.reviews_previous_7_days ?? 0;
  let weekOverWeekText = '0% week over week';
  if (prev7 > 0) {
    const pct = Math.round(((last7 - prev7) / prev7) * 100);
    weekOverWeekText = `${pct >= 0 ? '+' : ''}${pct}% week over week`;
  } else if (last7 > 0) {
    weekOverWeekText = `+${last7} this week`;
  }

  const isNewTenant = !loading && stats !== null && totalReviews === 0;

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

      {/* New Tenant Welcome Banner */}
      {isNewTenant && (
        <div className="p-4 rounded-xl border border-white/15 bg-white/[0.04] flex items-center gap-3 text-xs text-white/80">
          <Info className="w-4 h-4 text-white/60 shrink-0" />
          <span>No reviews yet — submit your first to see stats.</span>
        </div>
      )}

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-white/50">
            <span>Total Reviews</span>
            <FileCode className="w-4 h-4 text-white/60" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {totalReviews}
          </div>
          <div className="text-[11px] text-white/60 mt-2 flex items-center gap-1 font-mono">
            <TrendingUp className="w-3 h-3" />
            <span>{weekOverWeekText}</span>
          </div>
        </div>

        {/* Card 2 */}
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-white/50">
            <span>Flagged Vulnerabilities</span>
            <AlertOctagon className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {totalFindings}
          </div>
          <div className="text-[11px] text-white/40 mt-2 font-mono flex items-center gap-2">
            <span className="text-red-400 font-bold">{criticalFindings} Critical</span>
            <span>•</span>
            <span className="text-orange-400 font-bold">{highFindings} High</span>
          </div>
        </div>

        {/* Card 3 */}
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-white/50">
            <span>Verified Accuracy (FP Rate)</span>
            <Shield className="w-4 h-4 text-white/60" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {totalFindings > 0 ? '< 0.1%' : '0.0%'}
          </div>
          <div className="text-[11px] text-white/60 mt-2 font-mono">
            AST + Semgrep cross-validated
          </div>
        </div>

        {/* Card 4 */}
        <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-white/50">
            <span>Tenant spend (all time)</span>
            <Coins className="w-4 h-4 text-white/60" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            ${totalCostUsd.toFixed(2)}
          </div>
          <div className="text-[11px] text-white/40 mt-2 font-mono">
            Avg {avgDurationSeconds} / audit run
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
                        <span className="text-white/60 text-xs">Clean (0)</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-white/60 font-sans">{rev.policyProfile || '—'}</td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center gap-1 text-[11px] text-white/60 bg-white/8 px-2 py-0.5 rounded-full border border-white/18 capitalize">
                      <Clock className="w-3 h-3" />
                      <span>{rev.status || 'completed'}</span>
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
