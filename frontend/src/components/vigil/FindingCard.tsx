'use client';

import React from 'react';
import { FileCode, CheckCircle2, XCircle } from 'lucide-react';
import { Finding } from '@/lib/types';
import { SeverityBadge } from './SeverityBadge';
import { SourceBadge } from './SourceBadge';

import { focusRing } from '@/lib/styles';

interface FindingCardProps {
  finding: Finding;
  isSelected: boolean;
  onSelect: () => void;
}

export const FindingCard: React.FC<FindingCardProps> = ({ finding, isSelected, onSelect }) => {
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`${finding.severity} severity finding: ${finding.title}`}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect();
        }
      }}
      className={`p-3.5 rounded-xl border transition-all cursor-pointer flex flex-col gap-2.5 relative group ${focusRing} ${
        isSelected
          ? 'bg-white/10 border-white shadow-md ring-1 ring-white/30'
          : 'bg-white/[0.03] border-white/10 hover:bg-white/[0.06] hover:border-white/20'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <SeverityBadge severity={finding.severity} size="sm" />
          <SourceBadge source={finding.source} toolName={finding.toolName} size="sm" />
          {finding.cwe && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-white/10 text-white/80 border border-white/15">
              {finding.cwe}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-white/50">
          <span>{Math.round(finding.confidence * 100)}% conf</span>
        </div>
      </div>

      <h4 className="text-[13px] font-medium text-white group-hover:text-white line-clamp-2 leading-snug">
        {finding.title}
      </h4>

      <div className="flex items-center justify-between text-[11.5px] text-white/50 pt-1 border-t border-white/10 font-mono">
        <div className="flex items-center gap-1.5 truncate">
          <FileCode className="w-3 h-3 text-white/40 shrink-0" />
          <span className="text-white/80 truncate">
            {finding.file}:{finding.line}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {finding.userFeedback?.helpful === false ? (
            <span className="text-[10.5px] text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded-full flex items-center gap-1 border border-rose-500/20">
              <XCircle className="w-3 h-3" />
              <span>Flagged FP</span>
            </span>
          ) : finding.userFeedback?.helpful === true ? (
            <span className="text-[10.5px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-full flex items-center gap-1 border border-emerald-500/20">
              <CheckCircle2 className="w-3 h-3" />
              <span>Confirmed</span>
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
};
