'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ReviewWorkspace } from '@/components/vigil/ReviewWorkspace';
import { MOCK_REVIEWS, MOCK_FINDINGS } from '@/data/vigilData';
import { Review, Finding, Feedback } from '@/lib/types';
import { ChevronDown, Plus, FileCode } from 'lucide-react';

export default function ReviewsPage() {
  const router = useRouter();
  const [reviews, setReviews] = useState<Review[]>(MOCK_REVIEWS);
  const [findings, setFindings] = useState<Finding[]>(MOCK_FINDINGS);
  const [selectedReviewId, setSelectedReviewId] = useState<string>(
    reviews[0]?.id || 'rev-a1b2'
  );
  const [isSelectorOpen, setIsSelectorOpen] = useState(false);

  const currentReview =
    reviews.find((r) => r.id === selectedReviewId) || reviews[0];
  const currentFindings = findings.filter(
    (f) => f.reviewId === currentReview?.id
  );

  const handleDeleteReview = (reviewId: string) => {
    setReviews((prev) => prev.filter((r) => r.id !== reviewId));
    setFindings((prev) => prev.filter((f) => f.reviewId !== reviewId));
    const remaining = reviews.filter((r) => r.id !== reviewId);
    if (remaining.length > 0) {
      setSelectedReviewId(remaining[0].id);
    } else {
      router.push('/dashboard/reviews/new');
    }
  };

  const handleSaveFeedback = (findingId: string, feedback: Feedback) => {
    setFindings((prev) =>
      prev.map((f) => (f.id === findingId ? { ...f, userFeedback: feedback } : f))
    );
  };

  const handleExportReview = (format: 'json' | 'html' | 'pdf') => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify(
          {
            review: currentReview,
            findings: currentFindings,
            exportedAt: new Date().toISOString(),
            format,
            compliance: 'SARIF-2.1.0-Strict',
          },
          null,
          2
        )
      );
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute(
      'download',
      `vigil-audit-${currentReview.id}.${format === 'pdf' ? 'pdf' : format}`
    );
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Review Selector Strip */}
      <div className="h-10 bg-[#0d0d11] border-b border-white/10 px-6 flex items-center justify-between shrink-0 select-none text-xs">
        <div className="flex items-center gap-3">
          <span className="text-white/40 font-mono uppercase text-[10px]">
            Active Review:
          </span>
          <div className="relative">
            <button
              onClick={() => setIsSelectorOpen((v) => !v)}
              className="flex items-center gap-2 text-white font-medium hover:text-white/80 transition-colors py-1 px-2 rounded-lg hover:bg-white/5 cursor-pointer font-mono"
            >
              <FileCode className="w-3.5 h-3.5 text-white/60" />
              <span>
                {currentReview.title} ({currentReview.id})
              </span>
              <ChevronDown className="w-3 h-3 text-white/50" />
            </button>

            {isSelectorOpen && (
              <div className="absolute top-full left-0 mt-1 w-72 rounded-xl border border-white/15 bg-[#09090b] shadow-2xl p-1.5 z-50 animate-in fade-in zoom-in-95">
                <div className="text-[10px] font-mono text-white/40 px-2 py-1 uppercase">
                  Select Review Run
                </div>
                {reviews.map((rev) => (
                  <button
                    key={rev.id}
                    onClick={() => {
                      setSelectedReviewId(rev.id);
                      setIsSelectorOpen(false);
                    }}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left transition-colors cursor-pointer text-xs ${
                      rev.id === currentReview.id
                        ? 'bg-white/10 text-white font-medium'
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    <span className="truncate">{rev.title}</span>
                    <span className="text-[10px] font-mono text-white/40">
                      {rev.totalFindings} findings
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <button
          onClick={() => router.push('/dashboard/reviews/new')}
          className="flex items-center gap-1.5 text-xs text-white/70 hover:text-white transition-colors cursor-pointer py-1 px-2.5 rounded-lg border border-white/10 hover:border-white/20 bg-white/[0.02]"
        >
          <Plus className="w-3 h-3" />
          <span>New Submission</span>
        </button>
      </div>

      {/* Main Review Workspace */}
      <div className="flex-1 overflow-hidden">
        <ReviewWorkspace
          review={currentReview}
          findings={currentFindings}
          onDeleteReview={handleDeleteReview}
          onSaveFeedback={handleSaveFeedback}
          onExport={handleExportReview}
        />
      </div>
    </div>
  );
}
