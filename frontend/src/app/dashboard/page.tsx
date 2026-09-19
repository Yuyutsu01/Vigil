'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { DashboardView } from '@/components/vigil/DashboardView';
import { MOCK_REVIEWS, INITIAL_STATS } from '@/data/vigilData';
import { Review, ReviewStats } from '@/lib/types';

export default function DashboardOverviewPage() {
  const router = useRouter();
  const [reviews] = useState<Review[]>(MOCK_REVIEWS);
  const [stats] = useState<ReviewStats>(INITIAL_STATS);

  const handleSelectReview = (reviewId: string) => {
    router.push(`/dashboard/reviews/${reviewId}`);
  };

  const handleNewReview = () => {
    router.push('/dashboard/reviews/new');
  };

  return (
    <DashboardView
      stats={stats}
      reviews={reviews}
      onSelectReview={handleSelectReview}
      onNewReview={handleNewReview}
    />
  );
}
