'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Shield,
  Download,
  Trash2,
  Lock,
  ChevronDown,
  FileCode,
  GripVertical,
} from 'lucide-react';
import { Review, Finding, Feedback } from '@/lib/types';
import { CodeViewer } from './CodeViewer';
import { FindingsList } from './FindingsList';
import { FindingDetailPanel } from './FindingDetailPanel';
import { BudgetMeter } from './BudgetMeter';
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

/* ── Drag handle divider ─────────────────────────────── */
function Divider({ onDrag }: { onDrag: (dx: number) => void }) {
  const dragging = useRef(false);
  const lastX = useRef(0);

  const onMouseDown = (e: React.MouseEvent) => {
    dragging.current = true;
    lastX.current = e.clientX;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      onDrag(e.clientX - lastX.current);
      lastX.current = e.clientX;
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [onDrag]);

  return (
    <div
      onMouseDown={onMouseDown}
      className="w-1.5 h-full flex-shrink-0 flex items-center justify-center cursor-col-resize group select-none"
      style={{ background: 'rgba(255,255,255,0.06)' }}
      aria-hidden
    >
      <GripVertical className="w-3 h-3 text-white/20 group-hover:text-white/50 transition-colors" />
    </div>
  );
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

  // Resizable column widths (px). Initialized lazily from container.
  const containerRef = useRef<HTMLDivElement>(null);
  const [col1W, setCol1W] = useState<number | null>(null);
  const [col2W, setCol2W] = useState<number | null>(null);

  // Set initial widths once container mounts
  useEffect(() => {
    if (!containerRef.current) return;
    const total = containerRef.current.clientWidth;
    setCol1W(Math.round(total * 0.33));
    setCol2W(Math.round(total * 0.25));
  }, []);

  const MIN_COL = 160;

  const handleDrag1 = useCallback((dx: number) => {
    if (!containerRef.current) return;
    const total = containerRef.current.clientWidth;
    setCol1W(prev => {
      const next = (prev ?? Math.round(total * 0.33)) + dx;
      return Math.max(MIN_COL, Math.min(next, total - MIN_COL * 2));
    });
  }, []);

  const handleDrag2 = useCallback((dx: number) => {
    if (!containerRef.current) return;
    const total = containerRef.current.clientWidth;
    setCol2W(prev => {
      const next = (prev ?? Math.round(total * 0.25)) + dx;
      return Math.max(MIN_COL, Math.min(next, total - MIN_COL * 2));
    });
  }, []);

  const REPO_REVIEW_PLACEHOLDER = '[REPOSITORY_REVIEW_MEMORY_ONLY]';
  const isRepoReview =
    review.code === REPO_REVIEW_PLACEHOLDER ||
    Boolean(review.code?.includes('REPOSITORY_REVIEW_MEMORY_ONLY'));

  const displayPath = isRepoReview
    ? (findings[0]?.source_file_path || 'Repository review')
    : review.fileName || 'main.py';

  const selectedFinding = findings.find((f) => f.id === selectedFindingId) || null;

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) return;
      if (e.key === 'j') {
        const idx = findings.findIndex((f) => f.id === selectedFindingId);
        if (idx < findings.length - 1) setSelectedFindingId(findings[idx + 1].id);
      } else if (e.key === 'k') {
        const idx = findings.findIndex((f) => f.id === selectedFindingId);
        if (idx > 0) setSelectedFindingId(findings[idx - 1].id);
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

  const distinctFindingFiles = new Set(
    findings.map((f) => f.source_file_path || f.file).filter(Boolean)
  );
  const scannedFilesCount = Math.max(review.fileCount || 1, distinctFindingFiles.size || 1);

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
              <span className="truncate">{displayPath}</span>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/80 font-mono border border-white/15">
              {review.language}
            </span>
            <div className="flex items-center gap-1 text-[11px] text-white/60 bg-white/[0.04] px-2.5 py-0.5 rounded-full border border-white/10">
              <Shield className="w-3 h-3 text-white/70" />
              <span>{review.policyProfile}</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-cyan-300 bg-cyan-500/10 px-2.5 py-0.5 rounded-full border border-cyan-500/20 font-mono">
              <span>Scanned {scannedFilesCount} files with {findings.length} findings</span>
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
                <button onClick={() => { onExport?.('json'); setIsExportMenuOpen(false); }} className={`w-full text-left px-3.5 py-2 hover:bg-white/10 flex items-center justify-between cursor-pointer ${focusRing}`}>
                  <span>SARIF / JSON Format</span><span className="text-[10px] text-white/40 font-mono">.json</span>
                </button>
                <button onClick={() => { onExport?.('html'); setIsExportMenuOpen(false); }} className={`w-full text-left px-3.5 py-2 hover:bg-white/10 flex items-center justify-between cursor-pointer ${focusRing}`}>
                  <span>Interactive HTML Audit</span><span className="text-[10px] text-white/40 font-mono">.html</span>
                </button>
                <button onClick={() => { onExport?.('pdf'); setIsExportMenuOpen(false); }} className={`w-full text-left px-3.5 py-2 hover:bg-white/10 flex items-center justify-between cursor-pointer ${focusRing}`}>
                  <span>Executive PDF Summary</span><span className="text-[10px] text-white/40 font-mono">.pdf</span>
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

      {/* Resizable 3-column workspace */}
      <div ref={containerRef} className="flex-1 flex overflow-hidden">
        {/* Column 1: Code Viewer */}
        <div
          className="h-full overflow-hidden flex-shrink-0"
          style={{ width: col1W !== null ? col1W : '33%' }}
        >
          <CodeViewer
            code={review.code}
            language={review.language}
            fileName={displayPath}
            findings={findings}
            selectedFindingId={selectedFindingId}
            onSelectFinding={(id) => setSelectedFindingId(id)}
            review={review}
          />
        </div>

        <Divider onDrag={handleDrag1} />

        {/* Column 2: Findings List */}
        <div
          className="hidden md:flex h-full overflow-hidden flex-shrink-0"
          style={{ width: col2W !== null ? col2W : '25%' }}
        >
          <FindingsList
            findings={findings}
            selectedFindingId={selectedFindingId}
            onSelectFinding={(id) => setSelectedFindingId(id)}
          />
        </div>

        <Divider onDrag={handleDrag2} />

        {/* Column 3: Finding Detail — takes remaining space */}
        <div className="hidden md:flex flex-1 h-full overflow-hidden min-w-0">
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