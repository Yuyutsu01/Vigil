'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Shield,
  Download,
  Trash2,
  Lock,
  ChevronDown,
  CheckCircle2,
  FileCode,
} from 'lucide-react';
import { Review, Finding, Feedback } from '@/lib/types';
import { CodeViewer } from './CodeViewer';
import { FindingsList } from './FindingsList';
import { FindingDetailPanel } from './FindingDetailPanel';
import { BudgetMeter } from './BudgetMeter';
import { RunStatusStepper } from './RunStatusStepper';
import { DeleteConfirmModal } from './DeleteConfirmModal';
import { focusRing } from '@/lib/styles';

interface ReviewWorkspaceProps {
  review: Review;
  findings: Finding[];
  onDeleteReview: (reviewId: string) => void;
  onSaveFeedback?: (findingId: string, feedback: Feedback) => void;
  onFeedback?: (findingId: string, feedback: Feedback) => void;
  onExport?: (format: 'json' | 'html' | 'pdf') => void;
}

export const ReviewWorkspace: React.FC<ReviewWorkspaceProps> = ({
  review,
  findings,
  onDeleteReview,
  onSaveFeedback,
  onFeedback,
  onExport,
}) => {
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(
    findings[0]?.id || null
  );
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false);
  const [legalHold, setLegalHold] = useState(review.legalHold);

  const selectedFinding = findings.find((f) => f.id === selectedFindingId) || null;

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }
      if (e.key === 'j') {
        const currentIndex = findings.findIndex((f) => f.id === selectedFindingId);
        if (currentIndex < findings.length - 1) {
          setSelectedFindingId(findings[currentIndex + 1].id);
        }
      } else if (e.key === 'k') {
        const currentIndex = findings.findIndex((f) => f.id === selectedFindingId);
        if (currentIndex > 0) {
          setSelectedFindingId(findings[currentIndex - 1].id);
        }
      }
    },
    [findings, selectedFindingId]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleFeedback = (feedback: Feedback) => {
    if (selectedFindingId) {
      if (onSaveFeedback) onSaveFeedback(selectedFindingId, feedback);
      if (onFeedback) onFeedback(selectedFindingId, feedback);
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-black text-white select-none overflow-hidden">
      {/* Top Action Bar */}
      <div className="h-14 px-6 border-b border-white/10 bg-black flex items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-white tracking-wider">
              #{review.id}
            </span>
            <span className="text-white/40">/</span>
            <div className="flex items-center gap-1.5 font-medium text-xs text-white truncate max-w-xs sm:max-w-md">
              <FileCode className="w-3.5 h-3.5 text-white/70 shrink-0" />
              <span className="truncate">{review.fileName}</span>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/80 font-mono border border-white/15">
              {review.language}
            </span>
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span>Complete</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-white/60 bg-white/[0.04] px-2.5 py-0.5 rounded-full border border-white/10">
              <Shield className="w-3 h-3 text-white/70" />
              <span>{review.policyProfile}</span>
            </div>
            <button
              onClick={() => setLegalHold(!legalHold)}
              className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono transition-colors cursor-pointer ${focusRing} ${
                legalHold
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'bg-white/[0.03] text-white/40 border border-white/10 hover:text-white/80'
              }`}
              title="Toggle legal hold compliance lock"
            >
              <Lock className="w-3 h-3" />
              <span>{legalHold ? 'Legal Hold Active' : 'No Hold'}</span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden lg:block">
            <BudgetMeter budget={review.budget} compact />
          </div>

          <div className="relative">
            <button
              onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/15 bg-white/[0.04] hover:bg-white/10 text-xs font-medium text-white transition-colors cursor-pointer ${focusRing}`}
            >
              <Download className="w-3.5 h-3.5 text-white/60" />
              <span>Export</span>
              <ChevronDown className="w-3 h-3 text-white/60" />
            </button>
            {isExportMenuOpen && (
              <div className="absolute right-0 mt-1.5 w-48 rounded-xl border border-white/15 bg-black/95 shadow-2xl py-1 z-50 text-xs text-white backdrop-blur-md">
                <button
                  onClick={() => {
                    onExport?.('json');
                    setIsExportMenuOpen(false);
                  }}
                  className={`w-full text-left px-3.5 py-2 hover:bg-white/10 flex items-center justify-between cursor-pointer ${focusRing}`}
                >
                  <span>SARIF / JSON Format</span>
                  <span className="text-[10px] text-white/40 font-mono">.json</span>
                </button>
                <button
                  onClick={() => {
                    onExport?.('html');
                    setIsExportMenuOpen(false);
                  }}
                  className={`w-full text-left px-3.5 py-2 hover:bg-white/10 flex items-center justify-between cursor-pointer ${focusRing}`}
                >
                  <span>Interactive HTML Audit</span>
                  <span className="text-[10px] text-white/40 font-mono">.html</span>
                </button>
                <button
                  onClick={() => {
                    onExport?.('pdf');
                    setIsExportMenuOpen(false);
                  }}
                  className={`w-full text-left px-3.5 py-2 hover:bg-white/10 flex items-center justify-between cursor-pointer ${focusRing}`}
                >
                  <span>Executive PDF Summary</span>
                  <span className="text-[10px] text-white/40 font-mono">.pdf</span>
                </button>
              </div>
            )}
          </div>

          <button
            onClick={() => setIsDeleteModalOpen(true)}
            aria-label="Delete this review"
            className={`p-1.5 rounded-full border border-white/10 bg-white/[0.03] hover:bg-rose-500/20 hover:border-rose-500/40 text-white/50 hover:text-rose-400 transition-colors cursor-pointer ${focusRing}`}
            title="Delete this review"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <RunStatusStepper status={review.status} />

      <div className="flex-1 flex overflow-hidden">
        <div className="w-full md:w-5/12 lg:w-4/12 h-full">
          <CodeViewer
            code={review.code}
            language={review.language}
            fileName={review.fileName}
            findings={findings}
            selectedFindingId={selectedFindingId}
            onSelectFinding={(id) => setSelectedFindingId(id)}
          />
        </div>

        <div className="hidden md:flex md:w-3/12 lg:w-3/12 h-full">
          <FindingsList
            findings={findings}
            selectedFindingId={selectedFindingId}
            onSelectFinding={(id) => setSelectedFindingId(id)}
          />
        </div>

        <div className="hidden md:flex md:w-4/12 lg:w-5/12 h-full">
          <FindingDetailPanel
            finding={selectedFinding}
            onSaveFeedback={handleFeedback}
          />
        </div>
      </div>

      <DeleteConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={() => onDeleteReview(review.id)}
        reviewTitle={review.title}
        legalHold={legalHold}
      />
    </div>
  );
};
