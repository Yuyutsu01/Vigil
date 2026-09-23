'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ReviewWorkspace } from '@/components/vigil/ReviewWorkspace';
import { api } from '@/lib/api';
import { Review, Feedback } from '@/lib/types';
import { ChevronDown, Plus, FileCode, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { focusRing } from '@/lib/styles';

export default function ReviewsPage() {
  const router = useRouter();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [currentReview, setCurrentReview] = useState<Review | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSelectorOpen, setIsSelectorOpen] = useState(false);

  // Fetch list of reviews
  const fetchReviewsList = useCallback(() => {
    setIsLoadingList(true);
    setError(null);
    api.listReviews({ limit: 20 })
      .then((res) => {
        setReviews(res.items);
        if (res.items.length > 0) {
          setSelectedReviewId((prev) => (prev && res.items.some((r) => r.id === prev) ? prev : res.items[0].id));
        } else {
          setSelectedReviewId(null);
          setCurrentReview(null);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch reviews list:', err);
        setError(err?.message || 'Failed to load code reviews.');
      })
      .finally(() => {
        setIsLoadingList(false);
      });
  }, []);

  useEffect(() => {
    fetchReviewsList();
  }, [fetchReviewsList]);

  // Fetch single review detail whenever selectedReviewId changes
  useEffect(() => {
    if (!selectedReviewId) {
      setCurrentReview(null);
      return;
    }

    let cancelled = false;
    setIsLoadingDetail(true);
    setError(null);

    api.getReview(selectedReviewId)
      .then((data) => {
        if (cancelled) return;
        setCurrentReview(data);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error(`Failed to fetch review ${selectedReviewId}:`, err);
        setError(err?.message || `Failed to load review ${selectedReviewId}.`);
      })
      .finally(() => {
        if (cancelled) return;
        setIsLoadingDetail(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedReviewId]);

  const handleDeleteReview = async (reviewId: string) => {
    try {
      await api.deleteReview(reviewId);
      setReviews((prev) => prev.filter((r) => r.id !== reviewId));
      const remaining = reviews.filter((r) => r.id !== reviewId);
      if (remaining.length > 0) {
        setSelectedReviewId(remaining[0].id);
      } else {
        setSelectedReviewId(null);
        setCurrentReview(null);
        router.push('/dashboard/reviews/new');
      }
    } catch (err: any) {
      console.error('Failed to delete review:', err);
      alert(err?.message || 'Failed to delete review.');
    }
  };

  const handleSaveFeedback = async (findingId: string, feedback: Feedback) => {
    if (!currentReview) return;
    try {
      await api.submitFindingFeedback(findingId, {
        useful: feedback.helpful,
        disposition: (feedback.type as any) || 'accepted',
        comment: feedback.comment,
        reason_category: feedback.reason,
      });
      // Optimistically update finding feedback in currentReview
      setCurrentReview((prev) => {
        if (!prev || !prev.findings) return prev;
        return {
          ...prev,
          findings: prev.findings.map((f) =>
            f.id === findingId ? { ...f, userFeedback: feedback } : f
          ),
        };
      });
    } catch (err) {
      console.error('Failed to save finding feedback:', err);
    }
  };

  const handleExportReview = async (format: 'json' | 'html' | 'pdf') => {
    if (!currentReview) return;
    try {
      const blob = await api.downloadReviewReport(currentReview.id, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `vigil-report-${currentReview.id}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('Export failed:', err);
      alert(err?.message || 'Failed to download compliance report.');
    }
  };

  // Loading list state
  if (isLoadingList) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-white/60">
        <Loader2 className="w-6 h-6 animate-spin text-white/40" />
        <span className="text-xs font-mono">Loading review runs...</span>
      </div>
    );
  }

  // Error state
  if (error && !currentReview && reviews.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-center p-6">
        <div className="p-3 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400">
          <AlertCircle className="w-6 h-6" />
        </div>
        <div className="max-w-md">
          <h2 className="text-sm font-semibold text-white">Failed to Load Reviews</h2>
          <p className="text-xs text-white/50 mt-1 font-mono">{error}</p>
        </div>
        <button
          onClick={fetchReviewsList}
          className={`px-4 py-2 bg-white/10 hover:bg-white/15 text-white rounded-lg text-xs font-mono flex items-center gap-2 transition-colors cursor-pointer ${focusRing}`}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  // Empty state (0 reviews)
  if (reviews.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-center p-6">
        <div className="p-4 rounded-full bg-white/[0.03] border border-white/10 text-white/40">
          <FileCode className="w-8 h-8" />
        </div>
        <div className="max-w-md">
          <h2 className="text-base font-semibold text-white">No reviews submitted yet</h2>
          <p className="text-xs text-white/50 mt-1">
            Submit your first Python, JavaScript, or TypeScript snippet for multi-agent AST security analysis.
          </p>
        </div>
        <button
          onClick={() => router.push('/dashboard/reviews/new')}
          className={`px-4 py-2 bg-white hover:bg-white/90 text-black font-semibold rounded-full text-xs flex items-center gap-2 transition-colors cursor-pointer ${focusRing}`}
        >
          <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
          <span>New Security Review</span>
        </button>
      </div>
    );
  }

  const activeListItem = reviews.find((r) => r.id === selectedReviewId) || reviews[0];

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
                {activeListItem.title} ({activeListItem.id.slice(0, 8)})
              </span>
              <ChevronDown className="w-3 h-3 text-white/50" />
            </button>

            {isSelectorOpen && (
              <div className="absolute top-full left-0 mt-1 w-80 rounded-xl border border-white/15 bg-[#09090b] shadow-2xl p-1.5 z-50 animate-in fade-in zoom-in-95">
                <div className="text-[10px] font-mono text-white/40 px-2 py-1 uppercase">
                  Select Review Run ({reviews.length})
                </div>
                <div className="max-h-64 overflow-y-auto flex flex-col gap-0.5 mt-1">
                  {reviews.map((rev) => (
                    <button
                      key={rev.id}
                      onClick={() => {
                        setSelectedReviewId(rev.id);
                        setIsSelectorOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left transition-colors cursor-pointer text-xs ${
                        rev.id === selectedReviewId
                          ? 'bg-white/10 text-white font-medium'
                          : 'text-white/60 hover:text-white hover:bg-white/5'
                      }`}
                    >
                      <div className="flex flex-col min-w-0 pr-2">
                        <span className="truncate">{rev.title}</span>
                        <span className="text-[10px] font-mono text-white/40 truncate">
                          {rev.id.slice(0, 8)} • {rev.status}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono text-white/40 shrink-0">
                        {rev.totalFindings} findings
                      </span>
                    </button>
                  ))}
                </div>
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

      {/* Main Review Workspace or Detail Loading State */}
      <div className="flex-1 overflow-hidden">
        {isLoadingDetail && !currentReview ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-white/60">
            <Loader2 className="w-6 h-6 animate-spin text-white/40" />
            <span className="text-xs font-mono">Loading review details...</span>
          </div>
        ) : currentReview ? (
          <ReviewWorkspace
            review={currentReview}
            findings={currentReview.findings || []}
            onDeleteReview={handleDeleteReview}
            onSaveFeedback={handleSaveFeedback}
            onExport={handleExportReview}
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-white/40 text-xs font-mono">
            <span>Review details unavailable.</span>
            {error && <span className="text-rose-400">{error}</span>}
          </div>
        )}
      </div>
    </div>
  );
}
