'use client';

import React, { useState } from 'react';
import {
  FileText,
  Terminal,
  GitPullRequest,
  Sparkles,
  ExternalLink,
  Copy,
  Check,
  Shield,
  Layers,
  Info,
} from 'lucide-react';
import { Finding, Feedback } from '@/lib/types';
import { SeverityBadge } from './SeverityBadge';
import { SourceBadge } from './SourceBadge';
import { FeedbackButtons } from './FeedbackButtons';
import { focusRing } from '@/lib/styles';

interface FindingDetailPanelProps {
  finding: Finding | null;
  onSaveFeedback: (feedback: Feedback) => void;
}

export const FindingDetailPanel: React.FC<FindingDetailPanelProps> = ({
  finding,
  onSaveFeedback,
}) => {
  const [activeTab, setActiveTab] = useState<
    'explanation' | 'evidence' | 'trace' | 'suggested_fix'
  >('explanation');
  const [copiedPatch, setCopiedPatch] = useState(false);

  if (!finding) {
    return (
      <div className="flex-1 h-full bg-black p-8 flex flex-col items-center justify-center text-center text-white/40 gap-3 select-none">
        <Info className="w-10 h-10 text-white/30 stroke-[1.5]" />
        <div className="text-sm font-medium text-white">Select a Finding</div>
        <p className="text-xs text-white/50 max-w-xs leading-relaxed">
          Click any security finding card from the center panel to inspect its AST evidence,
          explainable reasoning trace, and suggested patch.
        </p>
      </div>
    );
  }

  const handleCopyDiff = () => {
    if (finding.diffPatch) {
      const diffText = `--- a/${finding.file}\n+++ b/${finding.file}\n- ${finding.diffPatch.original.join('\n- ')}\n+ ${finding.diffPatch.replacement.join('\n+ ')}`;
      navigator.clipboard.writeText(diffText);
      setCopiedPatch(true);
      setTimeout(() => setCopiedPatch(false), 2000);
    }
  };

  return (
    <div className="flex-1 h-full bg-black flex flex-col overflow-hidden text-white select-text border-l border-white/10">
      {/* Detail Header */}
      <div className="p-4 border-b border-white/10 bg-black shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <SeverityBadge severity={finding.severity} />
            <SourceBadge source={finding.source} toolName={finding.toolName} />
            {finding.cwe && (
              <a
                href={`https://cwe.mitre.org/data/definitions/${finding.cwe.replace('CWE-', '')}.html`}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-mono text-white/80 hover:text-white flex items-center gap-1 bg-white/10 px-2 py-0.5 rounded-full border border-white/15"
                title="View MITRE CWE Knowledge Base Definition"
              >
                <span>{finding.cwe}</span>
                <ExternalLink className="w-2.5 h-2.5 text-white/50" />
              </a>
            )}
          </div>
          <div className="text-xs font-mono text-white/50">
            Confidence: <span className="text-emerald-400 font-bold">{Math.round(finding.confidence * 100)}%</span>
          </div>
        </div>

        <div>
          <h2 className="text-base font-semibold text-white tracking-tight leading-snug">
            {finding.title}
          </h2>
          <div className="text-xs font-mono text-white/50 mt-1 flex items-center gap-2">
            <span>{finding.file}</span>
            <span className="text-white/30">•</span>
            <span>Lines {finding.line}–{finding.endLine || finding.line}</span>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 border-b border-white/10 -mb-4 pt-1 overflow-x-auto text-xs font-medium" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'explanation'}
            onClick={() => setActiveTab('explanation')}
            className={`pb-2.5 px-3 border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 shrink-0 ${focusRing} ${
              activeTab === 'explanation'
                ? 'border-white text-white font-semibold'
                : 'border-transparent text-white/50 hover:text-white'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Explanation</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'evidence'}
            onClick={() => setActiveTab('evidence')}
            className={`pb-2.5 px-3 border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 shrink-0 ${focusRing} ${
              activeTab === 'evidence'
                ? 'border-white text-white font-semibold'
                : 'border-transparent text-white/50 hover:text-white'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Evidence</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'trace'}
            onClick={() => setActiveTab('trace')}
            className={`pb-2.5 px-3 border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 shrink-0 ${focusRing} ${
              activeTab === 'trace'
                ? 'border-white text-white font-semibold'
                : 'border-transparent text-white/50 hover:text-white'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Trace & Audit</span>
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'suggested_fix'}
            onClick={() => setActiveTab('suggested_fix')}
            className={`pb-2.5 px-3 border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 shrink-0 ${focusRing} ${
              activeTab === 'suggested_fix'
                ? 'border-white text-white font-semibold'
                : 'border-transparent text-white/50 hover:text-white'
            }`}
          >
            <GitPullRequest className="w-3.5 h-3.5" />
            <span>Suggested Fix</span>
          </button>
        </div>
      </div>

      {/* Detail Content Scroll Area */}
      <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-5">
        {/* Tab 1: Explanation */}
        {activeTab === 'explanation' && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-mono uppercase tracking-wider text-white/50 font-bold">
                Security Impact & Root Cause
              </h3>
              <p className="text-[13px] text-white/80 leading-relaxed font-normal">
                {finding.description}
              </p>
            </div>
            {finding.category && (
              <div className="p-3 rounded-xl border border-white/10 bg-white/[0.03] text-xs flex items-center justify-between">
                <span className="text-white/50 font-mono">Classification Category:</span>
                <span className="text-white font-medium px-2 py-0.5 rounded-full bg-white/10">
                  {finding.category}
                </span>
              </div>
            )}
            <div className="flex flex-col gap-2 pt-2 border-t border-white/10">
              <h3 className="text-xs font-mono uppercase tracking-wider text-white/50 font-bold">
                Remediation Guidance
              </h3>
              <div className="p-3.5 rounded-xl border border-white/15 bg-white/[0.03] text-xs text-white/90 leading-relaxed font-normal">
                {finding.suggestedFix}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Evidence */}
        {activeTab === 'evidence' && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-mono uppercase tracking-wider text-white/50 font-bold">
                Flagged AST Code Segment
              </h3>
              <div className="p-3.5 rounded-xl bg-black border border-white/15 font-mono text-xs text-rose-300 overflow-x-auto whitespace-pre">
                {finding.codeSnippet}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-xs font-mono uppercase tracking-wider text-white/50 font-bold">
                Diagnostic Evidence & Rule Output
              </h3>
              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 font-mono text-xs text-white/80 leading-relaxed">
                {finding.evidence || 'Deterministic pattern matched by static engine rules.'}
              </div>
            </div>
            {finding.ruleId && (
              <div className="flex items-center justify-between p-3 rounded-xl border border-white/10 bg-white/[0.03] text-xs font-mono">
                <span className="text-white/40">Origin Rule Identifier:</span>
                <span className="text-white/80 select-all">{finding.ruleId}</span>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Trace & Audit */}
        {activeTab === 'trace' && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] flex flex-col gap-3">
              <div className="flex items-center gap-2 text-xs font-medium text-white">
                <Layers className="w-4 h-4 text-white/70" />
                <span>Detection Provenance Trace</span>
              </div>
              <div className="flex flex-col gap-2 text-xs text-white/60">
                <div className="flex justify-between py-1 border-b border-white/10">
                  <span>Engine / Tool:</span>
                  <span className="text-white font-mono">{finding.toolName || finding.source}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-white/10">
                  <span>Confidence Score:</span>
                  <span className="text-emerald-400 font-mono">{(finding.confidence * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between py-1 border-b border-white/10">
                  <span>AST Node Location:</span>
                  <span className="text-white font-mono">Line {finding.line}:{finding.column || 1}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span>Immutable Fingerprint:</span>
                  <span className="text-white/50 font-mono text-[11px] truncate max-w-[200px]">
                    {finding.fingerprint}
                  </span>
                </div>
              </div>
            </div>
            <div className="p-3.5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-xs text-emerald-300 leading-relaxed">
              <div className="font-semibold text-emerald-400 mb-1 flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                Zero-Execution Policy Check
              </div>
              Static analysis confirmed via AST parsing and semantic reasoning. Untrusted code was not executed or compiled during detection.
            </div>
          </div>
        )}

        {/* Tab 4: Suggested Fix (Diff) */}
        {activeTab === 'suggested_fix' && (
          <div className="flex flex-col gap-4 animate-in fade-in">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-wider text-white/50 font-bold">
                Automated Remediation Patch
              </span>
              <button
                onClick={handleCopyDiff}
                aria-label={copiedPatch ? 'Diff Copied' : 'Copy Diff'}
                className={`flex items-center gap-1.5 text-xs text-white hover:text-white font-mono p-1 rounded hover:bg-white/10 transition-colors cursor-pointer ${focusRing}`}
              >
                {copiedPatch ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-400">Diff Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-white/60" />
                    <span className="text-white/70">Copy Diff</span>
                  </>
                )}
              </button>
            </div>
            {finding.diffPatch ? (
              <div className="rounded-xl border border-white/10 bg-black overflow-hidden font-mono text-xs">
                <div className="px-3.5 py-1.5 bg-white/[0.04] border-b border-white/10 text-[11px] text-white/50">
                  --- a/{finding.file}
                  <br />
                  +++ b/{finding.file}
                </div>
                <div className="p-3 bg-red-950/20 border-b border-red-900/30 flex flex-col gap-0.5 text-red-300">
                  {finding.diffPatch.original.map((line, i) => (
                    <div key={i} className="flex gap-2">
                      <span className="text-red-500 select-none font-bold">-</span>
                      <span className="whitespace-pre overflow-x-auto">{line}</span>
                    </div>
                  ))}
                </div>
                <div className="p-3 bg-emerald-950/20 flex flex-col gap-0.5 text-emerald-300">
                  {finding.diffPatch.replacement.map((line, i) => (
                    <div key={i} className="flex gap-2">
                      <span className="text-emerald-500 select-none font-bold">+</span>
                      <span className="whitespace-pre overflow-x-auto">{line}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03] text-xs text-white/60 font-mono">
                {finding.suggestedFix}
              </div>
            )}
          </div>
        )}

        {/* Continuous Feedback Module */}
        <div className="pt-2 border-t border-white/10 mt-auto">
          <FeedbackButtons
            findingId={finding.id}
            initialFeedback={finding.userFeedback}
            onSaveFeedback={onSaveFeedback}
          />
        </div>
      </div>
    </div>
  );
};
