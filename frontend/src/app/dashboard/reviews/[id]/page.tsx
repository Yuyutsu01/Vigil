'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ReviewWorkspace } from '@/components/vigil/ReviewWorkspace';
import { MOCK_REVIEWS, MOCK_FINDINGS } from '@/data/vigilData';
import { Review, Finding, Feedback } from '@/lib/types';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function ReviewDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reviewId = (params?.id as string) || 'rev-a1b2';

  const [reviews, setReviews] = useState<Review[]>(MOCK_REVIEWS);
  const [findings, setFindings] = useState<Finding[]>(MOCK_FINDINGS);

  const currentReview =
    reviews.find((r) => r.id === reviewId) || reviews[0];
  const currentFindings = findings.filter(
    (f) => f.reviewId === currentReview?.id
  );

  const handleDeleteReview = (id: string) => {
    setReviews((prev) => prev.filter((r) => r.id !== id));
    setFindings((prev) => prev.filter((f) => f.reviewId !== id));
    router.push('/dashboard/reviews');
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

  if (!currentReview) {
    return (
      <div className="p-8 text-center text-white/50 text-sm font-mono">
        <p>Review run {reviewId} not found.</p>
        <Link
          href="/dashboard/reviews"
          className="mt-4 inline-flex items-center gap-2 text-white hover:underline text-xs"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Return to All Reviews
        </Link>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ReviewWorkspace
        review={currentReview}
        findings={currentFindings}
        onDeleteReview={handleDeleteReview}
        onSaveFeedback={handleSaveFeedback}
        onExport={handleExportReview}
      />
    </div>
  );
}
