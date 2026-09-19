'use client';

import React, { useState, useMemo } from 'react';
import { Search, ArrowUpDown } from 'lucide-react';
import { Finding, Severity, FindingSource } from '@/lib/types';
import { FindingCard } from './FindingCard';
import { focusRing } from '@/lib/styles';

interface FindingsListProps {
  findings: Finding[];
  selectedFindingId: string | null;
  onSelectFinding: (id: string) => void;
}

export const FindingsList: React.FC<FindingsListProps> = ({
  findings,
  selectedFindingId,
  onSelectFinding,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<Severity | 'all'>('all');
  const [sourceFilter] = useState<FindingSource | 'all'>('all');
  const [sortBy, setSortBy] = useState<'severity' | 'confidence' | 'line'>('severity');

  const filteredFindings = useMemo(() => {
    return findings
      .filter((f) => {
        if (severityFilter !== 'all' && f.severity !== severityFilter) return false;
        if (sourceFilter !== 'all' && f.source !== sourceFilter) return false;
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          return (
            f.title.toLowerCase().includes(q) ||
            f.description.toLowerCase().includes(q) ||
            f.cwe?.toLowerCase().includes(q) ||
            f.ruleId?.toLowerCase().includes(q) ||
            f.file.toLowerCase().includes(q)
          );
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'severity') {
          const weights: Record<Severity, number> = {
            critical: 4,
            high: 3,
            medium: 2,
            low: 1,
            info: 0,
          };
          return weights[b.severity] - weights[a.severity];
        }
        if (sortBy === 'confidence') {
          return b.confidence - a.confidence;
        }
        return a.line - b.line;
      });
  }, [findings, severityFilter, sourceFilter, searchQuery, sortBy]);

  const counts = useMemo(() => {
    return {
      all: findings.length,
      critical: findings.filter((f) => f.severity === 'critical').length,
      high: findings.filter((f) => f.severity === 'high').length,
      medium: findings.filter((f) => f.severity === 'medium').length,
      low: findings.filter((f) => f.severity === 'low').length,
    };
  }, [findings]);

  return (
    <div className="flex flex-col h-full bg-black border-r border-white/10 text-white overflow-hidden select-none">
      {/* Search and Sort Header */}
      <div className="p-3.5 border-b border-white/10 flex flex-col gap-2.5 bg-black">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-white tracking-tight">FINDINGS</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white font-mono border border-white/15">
              {filteredFindings.length} / {findings.length}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-white/50">
            <ArrowUpDown className="w-3 h-3 text-white/40" />
            <select
              aria-label="Sort findings"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className={`bg-black border border-white/15 rounded-full px-2 py-0.5 text-[11px] text-white/80 focus:outline-none focus:border-white/40 ${focusRing}`}
            >
              <option value="severity">Sort: Severity</option>
              <option value="confidence">Sort: Confidence</option>
              <option value="line">Sort: Line</option>
            </select>
          </div>
        </div>

        {/* Search input with accessible label */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-white/40 absolute left-2.5 top-2.5" />
          <input
            type="text"
            aria-label="Filter findings by title, CWE, rule, or file"
            placeholder="Filter by title, CWE, rule, file..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={`w-full bg-white/[0.03] border border-white/15 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder:text-white/30 focus:outline-none focus:border-white/40 ${focusRing}`}
          />
        </div>

        {/* Severity Filter Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 text-[11px] font-mono">
          <button
            onClick={() => setSeverityFilter('all')}
            className={`px-2 py-0.5 rounded-full transition-colors cursor-pointer shrink-0 ${
              severityFilter === 'all'
                ? 'bg-white text-black font-bold'
                : 'bg-white/5 text-white/50 hover:text-white border border-white/10'
            }`}
          >
            All ({counts.all})
          </button>
          <button
            onClick={() => setSeverityFilter('critical')}
            className={`px-2 py-0.5 rounded-full transition-colors cursor-pointer shrink-0 ${
              severityFilter === 'critical'
                ? 'bg-red-500 text-white font-bold'
                : 'bg-red-500/10 text-red-400 border border-red-500/20'
            }`}
          >
            Crit ({counts.critical})
          </button>
          <button
            onClick={() => setSeverityFilter('high')}
            className={`px-2 py-0.5 rounded-full transition-colors cursor-pointer shrink-0 ${
              severityFilter === 'high'
                ? 'bg-orange-500 text-white font-bold'
                : 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
            }`}
          >
            High ({counts.high})
          </button>
          <button
            onClick={() => setSeverityFilter('medium')}
            className={`px-2 py-0.5 rounded-full transition-colors cursor-pointer shrink-0 ${
              severityFilter === 'medium'
                ? 'bg-amber-500 text-black font-bold'
                : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
            }`}
          >
            Med ({counts.medium})
          </button>
        </div>
      </div>

      {/* Findings Scroll List */}
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2">
        {filteredFindings.length === 0 ? (
          <div className="p-8 text-center text-white/40 text-xs font-mono">
            No matching findings for active filters.
          </div>
        ) : (
          filteredFindings.map((finding) => (
            <FindingCard
              key={finding.id}
              finding={finding}
              isSelected={finding.id === selectedFindingId}
              onSelect={() => onSelectFinding(finding.id)}
            />
          ))
        )}
      </div>

      {/* Footer shortcut helper */}
      <div className="h-6 px-3 border-t border-white/10 bg-black flex items-center justify-between text-[10px] text-white/40 font-mono">
        <span>Keyboard: &apos;j&apos; next • &apos;k&apos; prev</span>
        <span>Deterministic Rule + LLM</span>
      </div>
    </div>
  );
};
