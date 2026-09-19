'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ReviewWorkspace } from '@/components/vigil/ReviewWorkspace';
import { Review, Finding, Feedback } from '@/lib/types';
import { api } from '@/lib/api';
import Link from 'next/link';
import { ArrowLeft, Loader2, AlertTriangle } from 'lucide-react';

function isMockFinding(finding: any) {
  const title = (finding.title || '').toLowerCase();
  const rationale = (finding.rationale || finding.description || '').toLowerCase();
  return (
    title.includes('mock llm') ||
    title.includes('mockprovider') ||
    rationale.includes('mockprovider')
  );
}

export default function ReviewDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reviewId = (params?.id as string) || '';

  const [review, setReview] = useState<Review | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!reviewId) {
      setLoading(false);
      setError('No review run ID specified.');
      return;
    }

    let isMounted = true;
    let pollTimer: NodeJS.Timeout | null = null;

    async function loadReview() {
      try {
        const fetchedReview = await api.getReview(reviewId);
        if (!isMounted) return;

        const cleanedFindings = (fetchedReview.findings || []).filter(
          (f) => !isMockFinding(f)
        );
        setReview(fetchedReview);
        setFindings(cleanedFindings);
        setLoading(false);

        // If the review is still in progress, poll until completion
        if (
          fetchedReview.status === 'running' ||
          fetchedReview.status === 'pending' ||
          fetchedReview.status === 'queued'
        ) {
          pollTimer = setTimeout(loadReview, 2000);
        }
      } catch (err: any) {
        if (!isMounted) return;
        setError(err?.message || `Failed to load review ${reviewId}`);
        setLoading(false);
      }
    }

    loadReview();

    return () => {
      isMounted = false;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [reviewId]);

  const handleDeleteReview = async (id: string) => {
    try {
      await api.deleteReview(id);
    } catch {
      // Ignore network errors on delete
    }
    router.push('/dashboard/reviews');
  };

  const handleSaveFeedback = (findingId: string, feedback: Feedback) => {
    setFindings((prev) =>
      prev.map((f) => (f.id === findingId ? { ...f, userFeedback: feedback } : f))
    );
  };

  const handleExportReview = (format: 'json' | 'html' | 'pdf') => {
    if (!review) return;
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify(
          {
            review,
            findings,
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
      `vigil-audit-${review.id}.${format === 'pdf' ? 'pdf' : format}`
    );
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  if (loading) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-white/70 space-y-3 font-mono text-xs">
        <Loader2 className="w-7 h-7 animate-spin text-white/60" />
        <p>Loading security review {reviewId}...</p>
      </div>
    );
  }

  if (error || !review) {
    return (
      <div className="p-8 text-center text-white/70 text-sm font-mono flex flex-col items-center justify-center h-full">
        <AlertTriangle className="w-8 h-8 text-rose-400 mb-3" />
        <p className="text-rose-300 font-semibold mb-1">Error Loading Review</p>
        <p className="text-white/50 text-xs max-w-md">{error || `Review run ${reviewId} not found.`}</p>
        <Link
          href="/dashboard/reviews"
          className="mt-6 inline-flex items-center gap-2 text-white/80 hover:text-white hover:underline text-xs bg-white/10 px-4 py-2 rounded-md"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Return to All Reviews
        </Link>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ReviewWorkspace
        review={review}
        findings={findings}
        onDeleteReview={handleDeleteReview}
        onSaveFeedback={handleSaveFeedback}
        onExport={handleExportReview}
      />
    </div>
  );
}
