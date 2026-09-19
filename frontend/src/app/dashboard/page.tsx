'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { DashboardView } from '@/components/vigil/DashboardView';
import { MOCK_REVIEWS } from '@/data/vigilData';
import { Review } from '@/lib/types';

export default function DashboardOverviewPage() {
  const router = useRouter();
  const [reviews] = useState<Review[]>(MOCK_REVIEWS);

  const handleSelectReview = (reviewId: string) => {
    router.push(`/dashboard/reviews/${reviewId}`);
  };

  const handleNewReview = () => {
    router.push('/dashboard/reviews/new');
  };

  return (
    <DashboardView
      reviews={reviews}
      onSelectReview={handleSelectReview}
      onNewReview={handleNewReview}
    />
  );
}
